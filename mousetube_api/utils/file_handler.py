import os
import urllib.parse

from django.conf import settings


def link_to_local_path(file_instance):
    """
    Convert File.link (URLField) to an actual local filesystem path.
    Handles http(s) URLs pointing to /media or /temp, /media/ and /temp/ paths.
    The result is always confined to MEDIA_ROOT: anything else (absolute paths,
    `..` traversal, symlinks pointing outside) raises ValueError.
    """
    link = file_instance.link
    if not link:
        raise ValueError("File link is empty")

    link = link.strip()

    if link.startswith(("http://", "https://")):
        link = urllib.parse.urlsplit(link).path

    link = urllib.parse.unquote(link)

    if link.startswith("/media/"):
        rel = link[len("/media/") :]
    elif link.startswith("/temp/"):
        rel = "temp/" + link[len("/temp/") :]
    else:
        raise ValueError("File link must point to /media/ or /temp/")

    media_root = os.path.realpath(settings.MEDIA_ROOT)
    path = os.path.realpath(os.path.join(media_root, rel))
    if os.path.commonpath([media_root, path]) != media_root:
        raise ValueError("File link points outside MEDIA_ROOT")

    return path


def is_temp_path(path):
    """True if `path` is inside MEDIA_ROOT/temp (the only place we may delete from)."""
    temp_root = os.path.realpath(os.path.join(settings.MEDIA_ROOT, "temp"))
    return os.path.commonpath([temp_root, os.path.realpath(path)]) == temp_root
