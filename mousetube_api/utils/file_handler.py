import os

from django.conf import settings


def link_to_local_path(file_instance):
    """
    Convert File.link (URLField) to an actual local filesystem path.
    Handles:
      - http(s) URLs pointing to /media or /temp
      - /media/ paths
      - /temp/ paths
      - absolute local paths
    """
    link = file_instance.link
    if not link:
        raise ValueError("File link is empty")
    link = link.strip()

    if link.startswith("http://") or link.startswith("https://"):
        path_part = "/" + link.split("/", 3)[-1]  # keep /media/... or /temp/...
        link = path_part

    if link.startswith("/media/"):
        return os.path.join(settings.MEDIA_ROOT, link.replace("/media/", ""))
    elif link.startswith("/temp/"):
        return os.path.join(settings.TEMP_ROOT, link.replace("/temp/", ""))
    return link
