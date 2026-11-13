import json
import os
import re
from urllib.parse import quote, unquote

import requests
from django.conf import settings
from django.db.models import Q

from mousetube_api.models import File, Repository
from mousetube_api.utils.file_handler import (
    ProgressReader,
    UploadError,
    explain,
    is_temp_path,
    link_to_local_path,
)
from mousetube_api.utils.ontologies import session_terms
from mousetube_api.utils.zenodo_description import description, keywords

ZENODO_API = getattr(settings, "ZENODO_API", "https://sandbox.zenodo.org/api/")


def _auth_headers():
    """Bearer header instead of ?access_token=: URLs end up in logs and error messages."""
    token = getattr(settings, "ZENODO_TOKEN", None)
    if not token:
        raise ValueError("Zenodo token not configured in settings.")
    return {"Authorization": f"Bearer {token}"}


METADATA_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string", "title": "Title"},
        "description": {"type": "string", "title": "Description", "format": "textarea"},
        "keywords": {
            "type": "array",
            "title": "Keywords",
            "items": {"type": "string", "title": "Keyword"},
        },
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
        "license": {
            "type": "string",
            "title": "License",
            "enum": [
                "CC0-1.0",  # Creative Commons Zero v1.0 Universal
                "CC-BY-4.0",  # Attribution 4.0 International
                "CC-BY-SA-4.0",  # Attribution-ShareAlike 4.0 International
                "CC-BY-NC-4.0",  # Attribution-NonCommercial 4.0 International
                "CC-BY-ND-4.0",  # Attribution-NoDerivatives 4.0 International
                "CC-BY-NC-SA-4.0",  # Attribution-NonCommercial-ShareAlike 4.0 International
                "CC-BY-NC-ND-4.0",  # Attribution-NonCommercial-NoDerivatives 4.0 International
            ],
            "default": "CC-BY-4.0",
        },
    },
    "required": ["title", "description", "upload_type", "creators"],
}


def build_metadata_payload(recording_session, files):
    """
    Build the JSON payload for Zenodo metadata based on a recording session and its files.
    """
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
        "description": description(recording_session, user),
        "keywords": keywords(recording_session),
        "creators": creators,
        "communities": [{"identifier": "mousetube"}],
        "license": "CC-BY-NC-4.0",
    }

    # the terms also go in the structured subjects, so that Zenodo can index them
    subjects = [
        {"term": t.label, "identifier": t.iri, "scheme": "url"}
        for t in session_terms(recording_session)
        if t.iri
    ]
    if subjects:
        metadata_payload["subjects"] = subjects

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
    files = [
        f
        for f in File.objects.filter(recording_session=recording_session)
        if f.status not in ["pending", "processing", "error"] and not f.doi
    ]

    if new_file and new_file not in files:
        # includ files
        files = list(files) + [new_file]

    if not files:
        raise ValueError("No valid files found for this recording session.")

    # 🔹 parameters
    auth = _auth_headers()
    headers = {**auth, "Content-Type": "application/json"}

    failed = []  # (file name, reason for the user) of the files that did not reach Zenodo
    try:
        # 🔹 Check for existing deposition
        existing_file = next((f for f in files if f.repository and f.external_id), None)
        if existing_file:
            deposition_id = existing_file.external_id
            repo = existing_file.repository
        else:
            # Create new zenodo repo
            r = requests.post(
                ZENODO_API + "/deposit/depositions",
                json={},
                headers=headers,
                timeout=300,
            )
            r.raise_for_status()
            deposition_id = r.json()["id"]

            repo, _ = Repository.objects.get_or_create(name="Zenodo")

        # 🔹 Upload files: streamed to the bucket of the deposition, never loaded in memory
        r = requests.get(
            f"{ZENODO_API}/deposit/depositions/{deposition_id}",
            headers=auth,
            timeout=60,
        )
        r.raise_for_status()
        bucket = r.json()["links"]["bucket"]

        for file_instance in files:
            if file_instance.external_id == deposition_id:
                continue  # already uploaded

            try:
                local_path = link_to_local_path(file_instance)
            except ValueError:
                local_path = ""
            if not os.path.exists(local_path) or os.path.getsize(local_path) == 0:
                file_instance.status = "error"
                file_instance.save(update_fields=["status"])
                failed.append(
                    (
                        file_instance.name,
                        "The file is no longer on the server or is empty. Upload it again.",
                    )
                )
                continue

            filename = re.sub(r"[^a-zA-Z0-9._-]", "_", os.path.basename(local_path))
            try:
                with ProgressReader(local_path, file_instance.id) as reader:
                    r = requests.put(
                        f"{bucket}/{quote(filename)}",
                        data=reader,
                        headers={**auth, "Content-Type": "application/octet-stream"},
                        timeout=(30, 3600),
                    )
                r.raise_for_status()
            except requests.exceptions.RequestException as e:
                file_instance.status = "error"
                file_instance.save(update_fields=["status"])
                failed.append((file_instance.name, explain(e)))
                continue

            # Update file after upload
            file_instance.repository = repo
            file_instance.external_id = deposition_id
            file_instance.save(update_fields=["repository", "external_id"])

    finally:
        # 🔹 delete temporary files
        for file_instance in files:
            try:
                local_path = link_to_local_path(file_instance)
            except ValueError:
                continue
            if is_temp_path(local_path) and os.path.exists(local_path):
                os.remove(local_path)

    if failed:
        # the task must not end as "done" when a file did not arrive
        raise UploadError(" ".join(f"{name}: {why}" for name, why in failed))

    # 🔹 update zenodo metadata
    metadata_payload = build_metadata_payload(recording_session, files)

    r = requests.put(
        f"{ZENODO_API + '/deposit/depositions'}/{deposition_id}",
        data=json.dumps({"metadata": metadata_payload}),
        headers=headers,
        timeout=300,
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

    auth = _auth_headers()
    headers = {**auth, "Content-Type": "application/json"}

    # 🔹 List files
    list_url = f"{ZENODO_API}/deposit/depositions/{deposition_id}/files"
    r = requests.get(list_url, headers=headers, timeout=30)
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
    r = requests.delete(delete_url, headers=auth, timeout=30)
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
    # the files sent by mouseTube and not published yet (the others have their DOI already)
    first_file_with_id = files.filter(
        Q(doi__isnull=True) | Q(doi=""), external_id__isnull=False
    ).first()
    if not first_file_with_id:
        raise UploadError("No file of this session was sent to the repository yet.")
    deposition_id = first_file_with_id.external_id

    auth = _auth_headers()

    # Update metadata if provided
    if payload:
        headers = {**auth, "Content-Type": "application/json"}
        r = requests.put(
            f"{ZENODO_API}/deposit/depositions/{deposition_id}",
            data=json.dumps({"metadata": payload}),
            headers=headers,
            timeout=60,
        )
        r.raise_for_status()

    # Publish deposition
    try:
        r = requests.post(
            f"{ZENODO_API}/deposit/depositions/{deposition_id}/actions/publish",
            headers=auth,
            timeout=60,
        )
        r.raise_for_status()
    except requests.RequestException as e:
        raise UploadError(f"Publishing failed. {explain(e)}") from e

    zenodo_doi = r.json().get("doi")
    if not zenodo_doi:
        raise UploadError("The repository did not return a DOI. Try again later.")

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
