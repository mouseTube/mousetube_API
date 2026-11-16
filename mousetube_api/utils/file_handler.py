import os
import shutil
import tempfile
import time
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


TEMP_MAX_AGE = 24 * 3600  # seconds a half-finished upload may stay on the server


def remove_temp(path):
    """Delete `path` when it is an upload still in MEDIA_ROOT/temp; never anything else."""
    try:
        if is_temp_path(path) and os.path.isfile(path):
            os.remove(path)
    except (OSError, ValueError):
        pass


def purge_temp_files(max_age=TEMP_MAX_AGE):
    """Delete the uploads older than `max_age` that nothing took over (abandoned or failed)."""
    temp_root = os.path.join(settings.MEDIA_ROOT, "temp")
    if not os.path.isdir(temp_root):
        return 0
    limit = time.time() - max_age
    removed = 0
    for entry in os.scandir(temp_root):
        try:
            if entry.is_file(follow_symlinks=False) and entry.stat().st_mtime < limit:
                os.remove(entry.path)
                removed += 1
        except OSError:
            continue
    return removed


UPLOADS_IN_FLIGHT = "uploads-in-flight"


def _same_disk(a, b):
    try:
        return os.stat(a).st_dev == os.stat(b).st_dev
    except OSError:
        return False


def upload_room(in_flight=0):
    """Largest upload the server can take right now, in bytes (0 when it is full).

    The ceiling is MAX_UPLOAD_SIZE, lowered to what the disk holds: an upload exists twice for a
    moment (Django's temporary copy, then media/temp) when both are on the same disk, the uploads
    being received (`in_flight` bytes) are counted, and UPLOAD_FREE_SPACE_RESERVE stays free.
    """
    from django.conf import settings

    media = settings.MEDIA_ROOT
    os.makedirs(media, exist_ok=True)
    scratch = tempfile.gettempdir()
    reserve = settings.UPLOAD_FREE_SPACE_RESERVE
    free = shutil.disk_usage(media).free
    if _same_disk(media, scratch):
        room = (free - reserve) // 2 - in_flight
    else:
        room = min(free, shutil.disk_usage(scratch).free) - reserve - in_flight
    return max(0, min(settings.MAX_UPLOAD_SIZE, room))


def reserve_upload(size):
    """Count an upload that starts; returns what the others already being received weigh."""
    from django.core.cache import cache

    cache.add(
        UPLOADS_IN_FLIGHT, 0, timeout=3600
    )  # a crashed worker cannot leave it stuck
    return int(cache.incr(UPLOADS_IN_FLIGHT, size)) - size


def release_upload(size):
    from django.core.cache import cache

    try:
        if int(cache.decr(UPLOADS_IN_FLIGHT, size)) < 0:
            cache.set(UPLOADS_IN_FLIGHT, 0, timeout=3600)
    except ValueError:  # the counter expired meanwhile
        pass


class UploadError(Exception):
    """A failure whose message is fit to be shown to the user as it is."""


def explain(exc):
    """What went wrong, for the user: no URL, token or traceback ever goes in there."""
    import requests
    from django.core.exceptions import ValidationError

    if isinstance(exc, UploadError):
        return str(exc)
    if isinstance(exc, ValidationError):
        return " ".join(exc.messages)
    if isinstance(exc, requests.HTTPError) and exc.response is not None:
        code = exc.response.status_code
        if code in (401, 403):
            return (
                "The repository refused our credentials. "
                "An administrator has to renew the access."
            )
        if code == 413:
            return "The repository refuses a file this large."
        if code == 429:
            return "The repository is busy. Try again in a few minutes."
        if code >= 500:
            return "The repository has a problem right now. Try again later."
        return "The repository rejected the file."
    if isinstance(exc, (requests.ConnectionError, requests.Timeout)):
        return "The repository did not answer. Try again later."
    return "The file could not be processed. An administrator can find the details in the logs."


def set_progress(file_id, percent):
    """Remember how far the transfer to the repository is (read by the status endpoint)."""
    from django.core.cache import cache

    cache.set(f"file-progress:{file_id}", percent, 3600)


def get_progress(file_id):
    from django.core.cache import cache

    return cache.get(f"file-progress:{file_id}") or 0


class ProgressReader:
    """A file that reports how much of it was read; `requests` streams it with a length."""

    def __init__(self, path, file_id):
        self._file = open(path, "rb")  # noqa: SIM115 - closed by __exit__
        self._size = os.path.getsize(path)
        self._read = 0
        self._file_id = file_id
        self._reported = -1

    def __len__(self):
        return self._size

    def read(self, size=-1):
        chunk = self._file.read(size)
        self._read += len(chunk)
        percent = self._read * 100 // self._size if self._size else 100
        if percent != self._reported:
            self._reported = percent
            set_progress(self._file_id, percent)
        return chunk

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self._file.close()
