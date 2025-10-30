import json
import os
import re
from urllib.parse import unquote

import requests
from django.conf import settings

from mousetube_api.models import File, Repository
from mousetube_api.utils.file_handler import link_to_local_path

ZENODO_API = getattr(settings, "ZENODO_API", "https://sandbox.zenodo.org/api/")
ZENODO_TOKEN = getattr(settings, "ZENODO_TOKEN", None)

if not ZENODO_TOKEN:
    raise ValueError("Zenodo token not configured in settings.")

METADATA_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string", "title": "Title"},
        "description": {"type": "string", "title": "Description", "format": "textarea"},
        "upload_type": {
            "type": "string",
            "title": "Upload type",
            "enum": ["dataset"],
            "default": "dataset",
            "readOnly": True,
        },
        "creators": {
            "type": "array",
            "title": "Creators",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "title": "Full name"},
                    "affiliation": {"type": "string", "title": "Affiliation"},
                    "orcid": {"type": "string", "title": "ORCID"},
                },
                "required": ["name"],
            },
        },
        "contributors": {
            "type": "array",
            "title": "Contributors",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "title": "Full name"},
                    "type": {
                        "type": "string",
                        "title": "Contributor type",
                        "enum": [
                            "ContactPerson",
                            "DataCollector",
                            "DataCurator",
                            "DataManager",
                            "Distributor",
                            "Editor",
                            "HostingInstitution",
                            "Producer",
                            "ProjectLeader",
                            "ProjectManager",
                            "ProjectMember",
                            "RegistrationAgency",
                            "RegistrationAuthority",
                            "RelatedPerson",
                            "Researcher",
                            "ResearchGroup",
                            "RightsHolder",
                            "Supervisor",
                            "Sponsor",
                            "WorkPackageLeader",
                            "Other",
                        ],
                    },
                    "affiliation": {"type": "string", "title": "Affiliation"},
                    "orcid": {"type": "string", "title": "ORCID"},
                    "gnd": {"type": "string", "title": "GND identifier"},
                },
                "required": ["name", "type"],
            },
        },
        "references": {
            "type": "array",
            "title": "References",
            "items": {"type": "string", "title": "Reference"},
        },
        "communities": {
            "type": "array",
            "title": "Communities",
            "items": {
                "type": "object",
                "properties": {
                    "identifier": {"type": "string", "title": "Community ID"}
                },
                "required": ["identifier"],
            },
            "default": [{"identifier": "mousetube"}],
            "readOnly": True,
        },
    },
    "required": ["title", "description", "upload_type", "creators"],
}


def _build_session_description(recording_session, files):
    """
    Build a description string for a recording session including all files.
    Includes session metadata, protocol, animal profiles, and file metadata.
    """
    lines = [
        f"Recording session: {recording_session.name}",
        f"Date: {recording_session.date}",
        f"Duration: {recording_session.duration} seconds",
    ]
    if recording_session.description:
        lines.append(f"Session description: {recording_session.description}")

    if getattr(recording_session, "protocol", None):
        lines.append(f"Protocol: {recording_session.protocol.name}")
        if recording_session.protocol.description:
            lines.append(
                f"Protocol description: {recording_session.protocol.description}"
            )

    # Animal profiles
    animal_profiles = getattr(recording_session, "animal_profiles", None)
    if animal_profiles:
        for ap in animal_profiles.all():
            lines.append(
                f"Animal: {ap.name}, Strain: {ap.strain}, Species: {ap.strain.species}, Sex: {ap.sex}, Genotype: {ap.genotype}, Treatment: {ap.treatment} "
            )

    # File-specific metadata
    for f in files:
        local_path = f.link  # link is the URLField
        lines.append(f"\nFile: {f.name or os.path.basename(local_path)}")
        lines.append(f"Format: {f.format}")
        lines.append(f"Duration: {f.duration} s")
        lines.append(f"Sampling rate: {f.sampling_rate} Hz")
        lines.append(f"Bit depth: {f.bit_depth}")

    return "\n".join(lines)


def build_metadata_payload(recording_session, files):
    """
    Build the JSON payload for Zenodo metadata based on a recording session and its files.
    """
    description = _build_session_description(recording_session, files)
    first_file = files[0]

    user = getattr(first_file, "created_by", None)
    if user:
        profile = getattr(user, "user_profile", None)
        family_name = getattr(user, "last_name", "Unknown") or "Unknown"
        given_name = getattr(user, "first_name", "Unknown") or "Unknown"
        affiliation = (
            getattr(profile, "laboratory", None) and profile.laboratory.name or None
        )
        orcid = getattr(profile, "orcid", None)
        creators = [
            {
                "name": f"{family_name}, {given_name}",
                "affiliation": affiliation,
                "orcid": orcid,
            }
        ]
    else:
        creators = [{"name": "Unknown, Unknown"}]

    metadata_payload = {
        "title": recording_session.name or "Untitled session",
        "upload_type": "dataset",
        "description": description,
        "creators": creators,
        "communities": [{"identifier": "mousetube"}],
    }

    return metadata_payload


def prepare_deposition_for_session(recording_session, new_file=None):
    """
    Prepare a Zenodo deposition for all files in a recording session.
    Uploads only valid files and cleans up temp files.
    Excludes files with status 'pending', 'processing', or 'error'.

    Args:
        recording_session: RecordingSession instance.
        new_file: optional File instance that triggered the deposition update.

    Returns:
        deposition_id: Zenodo deposition ID.
    """
    # 🔹 Get valid files
    files = (
        File.objects.filter(recording_session=recording_session)
        .exclude(status__in=["pending", "processing", "error"])
        .exclude(doi__isnull=False)
    )

    if new_file and new_file not in files:
        # includ files
        files = list(files) + [new_file]

    if not files:
        raise ValueError("No valid files found for this recording session.")

    # 🔹 parameters
    params = {"access_token": ZENODO_TOKEN}
    headers = {"Content-Type": "application/json"}

    existing_file = next((f for f in files if f.repository and f.external_id), None)
    if existing_file:
        deposition_id = existing_file.external_id
        repo = existing_file.repository
        print(
            f"ℹ️ Using existing {repo.name} repository with deposition ID {deposition_id}"
        )
    else:
        # Create new zenodo repo
        r = requests.post(
            ZENODO_API + "/deposit/depositions",
            params=params,
            json={},
            headers=headers,
            timeout=60,
        )
        r.raise_for_status()
        deposition_id = r.json()["id"]

        repo, _ = Repository.objects.get_or_create(name="Zenodo")

    # 🔹 Upload files
    for file_instance in files:
        if file_instance.external_id == deposition_id:
            continue  # already uploaded

        local_path = link_to_local_path(file_instance)
        if not os.path.exists(local_path) or os.path.getsize(local_path) == 0:
            print(
                f"⚠️ Skipping file {file_instance.id}, not found or empty: {local_path}"
            )
            file_instance.status = "error"
            file_instance.save(update_fields=["status"])
            continue

        filename = re.sub(r"[^a-zA-Z0-9._-]", "_", os.path.basename(local_path))
        upload_url = f"{ZENODO_API + '/deposit/depositions'}/{deposition_id}/files"

        try:
            with open(local_path, "rb") as file_obj:
                files_payload = {"file": (filename, file_obj)}
                r = requests.post(
                    upload_url, params=params, files=files_payload, timeout=60
                )
                r.raise_for_status()
        except requests.exceptions.HTTPError as e:
            print(f"❌ Failed to upload file {file_instance.id}: {e}")
            file_instance.status = "error"
            file_instance.save(update_fields=["status"])
            continue

        # Update file after upload
        file_instance.repository = repo
        file_instance.external_id = deposition_id
        file_instance.save(update_fields=["repository", "external_id"])

    # 🔹 delete temporary files
    for file_instance in files:
        local_path = link_to_local_path(file_instance)
        if "/temp/" in local_path and os.path.exists(local_path):
            os.remove(local_path)

    # 🔹 update zenodo metadata
    metadata_payload = build_metadata_payload(recording_session, files)

    r = requests.put(
        f"{ZENODO_API + '/deposit/depositions'}/{deposition_id}",
        params=params,
        data=json.dumps({"metadata": metadata_payload}),
        headers=headers,
        timeout=60,
    )
    r.raise_for_status()

    return deposition_id


def delete_file(file_instance):
    """
    Delete a file from a Zenodo deposition.
    Requires deposition_id to be stored in file_instance.
    """
    if not file_instance.external_id:
        raise ValueError(f"File {file_instance.id} has no external_id (deposition ID).")

    deposition_id = file_instance.external_id
    filename = os.path.basename(unquote(file_instance.link or file_instance.name or ""))
    if not filename:
        raise ValueError(f"File {file_instance.id} has no name to delete on Zenodo.")

    params = {"access_token": ZENODO_TOKEN}
    headers = {"Content-Type": "application/json"}

    # 🔹 List files
    list_url = f"{ZENODO_API}/deposit/depositions/{deposition_id}/files"
    r = requests.get(list_url, params=params, headers=headers, timeout=30)
    r.raise_for_status()

    files = r.json()
    target = next((f for f in files if f["filename"] == filename), None)
    if not target:
        print(f"⚠️ File '{filename}' not found in deposition {deposition_id}")
        return False

    # 🔹 Delete file
    delete_url = (
        f"{ZENODO_API}/deposit/depositions/{deposition_id}/files/{target['id']}"
    )
    r = requests.delete(delete_url, params=params, timeout=30)
    if r.status_code not in (200, 204):
        raise ValueError(f"Zenodo deletion failed: {r.status_code} {r.text}")

    print(f"🗑️ Deleted {filename} from Zenodo deposition {deposition_id}")
    return True


def publish_deposition(recording_session, payload=None):
    """
    Publish an existing Zenodo deposition (make it public).
    Updates only files without a manually set DOI/link.
    """
    files = File.objects.filter(recording_session=recording_session)
    first_file_with_id = files.filter(external_id__isnull=False).first()
    if not first_file_with_id:
        raise ValueError("No Zenodo deposition_id found for this file/session.")
    deposition_id = first_file_with_id.external_id

    params = {"access_token": ZENODO_TOKEN}

    # Update metadata if provided
    if payload:
        headers = {"Content-Type": "application/json"}
        r = requests.put(
            f"{ZENODO_API}/deposit/depositions/{deposition_id}",
            params=params,
            data=json.dumps({"metadata": payload}),
            headers=headers,
            timeout=60,
        )
        r.raise_for_status()

    # Publish deposition
    try:
        r = requests.post(
            f"{ZENODO_API}/deposit/depositions/{deposition_id}/actions/publish",
            params=params,
            timeout=60,
        )
        r.raise_for_status()
    except requests.HTTPError as e:
        content = getattr(e.response, "text", str(e))
        raise ValueError(f"Zenodo publish failed: {content}")

    zenodo_doi = r.json().get("doi")
    if not zenodo_doi:
        raise ValueError("Zenodo did not return a DOI after publishing.")

    base_url = ZENODO_API.split("/api")[0]

    # Update files from session
    for f in files:
        # Update only files without DOI and matching deposition_id
        if not f.doi and f.external_id == deposition_id:
            f.doi = zenodo_doi
            f.link = f"{base_url}/records/{deposition_id}/files/{f.name}?download=1"
            f.external_url = f"{base_url}/records/{deposition_id}"
            f.save(update_fields=["doi", "link", "external_url"])
        elif f.doi and f.link:
            if not f.link.startswith(base_url):
                # Remove repository link if DOI/link point elsewhere
                f.repository = None
                f.save(update_fields=["repository"])
    return zenodo_doi
