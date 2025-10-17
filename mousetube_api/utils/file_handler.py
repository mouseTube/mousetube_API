import os
import urllib.parse

from django.conf import settings


def link_to_local_path(file_instance):
    """
    Convert File.link (URLField) to an actual local filesystem path.
    Handles:
      - http(s) URLs pointing to /media or /temp
      - /media/ paths
      - /temp/ paths
      - absolute local paths
    Decodes URL-encoded characters and normalizes the path.
    """
    link = file_instance.link
    if not link:
        raise ValueError("File link is empty")

    link = link.strip()

    if link.startswith(("http://", "https://")):
        parts = urllib.parse.urlsplit(link)
        link = parts.path

    if link.startswith("/media/"):
        path = os.path.join(settings.MEDIA_ROOT, link[len("/media/") :])
    elif link.startswith("/temp/"):
        path = os.path.join(settings.TEMP_ROOT, link[len("/temp/") :])
    else:
        path = link

    path = urllib.parse.unquote(path)
    path = os.path.normpath(path)

    return path
