import requests
import json
from django.conf import settings


ZENODO_API = "https://sandbox.zenodo.org/api/deposit/depositions"


def publish_to_zenodo(file_instance, local_path=None):
    """
    Publish a file to Zenodo with dynamic token and authors.
    1. Create a new deposition
    2. Upload the file
    3. Add metadata (title, description, creators)
    4. Publish and store DOI
    """

    token = getattr(settings, "ZENODO_TOKEN", None)
    if not token:
        raise ValueError("Zenodo token is missing. Please configure ZENODO_TOKEN in settings.")

    headers = {"Content-Type": "application/json"}
    params = {"access_token": token}

    # 1. Create deposition
    r = requests.post(ZENODO_API, params=params, json={}, headers=headers)
    r.raise_for_status()
    deposition_id = r.json()["id"]

    # 2. Upload file (from local_path or FileField)
    file_path = local_path or file_instance.file.path
    with open(file_path, "rb") as f:
        files = {"file": f}
        upload_url = f"{ZENODO_API}/{deposition_id}/files"
        r = requests.post(upload_url, params=params, files=files)
        r.raise_for_status()

    # 3. Add metadata
    # Dynamically collect authors
    creators = []
    if hasattr(file_instance, "authors") and file_instance.authors.exists():
        # If ManyToMany relation
        for author in file_instance.authors.all():
            creators.append({
                "name": f"{author.last_name}, {author.first_name}",
                "affiliation": getattr(author, "affiliation", "") or ""
            })
    elif hasattr(file_instance, "created_by") and file_instance.created_by:
        # Fallback: use uploader
        creators.append({
            "name": f"{file_instance.created_by.last_name}, {file_instance.created_by.first_name}",
            "affiliation": getattr(file_instance.created_by, "affiliation", "") or ""
        })
    else:
        # Last fallback: anonymous
        creators.append({"name": "Unknown", "affiliation": ""})

    metadata = {
        "metadata": {
            "title": file_instance.name,
            "upload_type": "dataset",
            "description": file_instance.notes or "",
            "creators": creators,
        }
    }

    r = requests.put(
        f"{ZENODO_API}/{deposition_id}",
        params=params,
        data=json.dumps(metadata),
        headers=headers
    )
    r.raise_for_status()

    # 4. Publish and get DOI
    r = requests.post(f"{ZENODO_API}/{deposition_id}/actions/publish", params=params)
    r.raise_for_status()
    doi = r.json().get("doi")

    # Save DOI in database
    if doi:
        file_instance.doi = doi
        file_instance.save()

    return doi
