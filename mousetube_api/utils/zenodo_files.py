"""The files of a Zenodo record, and the zip of a dataset that is sent while it is made.

Nothing is written on the server: the zip is made as it goes, one file after the other, so there is
no disk space to count (a publication at the same time does not compete for it) and nothing is left
to clean when a download is cut or something fails.
"""

import re
import time
import zipfile
from urllib.parse import quote, unquote, urlparse

import requests
from django.core.cache import cache

# The only servers the application goes to fetch from: the links are written by users.
HOSTS = ("zenodo.org", "sandbox.zenodo.org")
CHUNK = 1 << 20
RECORD_SECONDS = 3600  # how long the list of the files of a record is kept
LOOKUPS_PER_MINUTE = 60  # Zenodo limits the requests by address: never use it all
_RECORD_PATH = re.compile(r"^/(?:api/)?records?/(\d+)(?:/|$)")


class ZenodoUnavailable(Exception):
    """Zenodo did not answer, or answered something else than a record."""


class ZenodoBusy(Exception):
    """Too many lookups in the last minute: try again a little later."""


def record_of(link):
    """(host, record id) of a link to a Zenodo record or to one of its files, else `None`."""
    try:
        url = urlparse(link or "")
    except ValueError:
        return None
    if url.scheme not in ("http", "https") or url.hostname not in HOSTS:
        return None
    found = _RECORD_PATH.match(url.path)
    return (url.hostname, found.group(1)) if found else None


def file_url(host, record_id, name):
    """The address that downloads one file of a record (the name is encoded: spaces, accents)."""
    return f"https://{host}/records/{record_id}/files/{quote(name, safe='')}?download=1"


def name_in(link, fallback):
    """The name of the file in a link to `/files/<name>`, else `fallback` (a link to the whole
    record, like `files-archive`, does not say which file the row is about)."""
    path = urlparse(link or "").path
    if "/files/" in path:
        return unquote(path.split("/files/", 1)[1]) or fallback
    return fallback


def _room():
    """False once `LOOKUPS_PER_MINUTE` lookups were made in the current minute."""
    key = f"zenodo-lookups:{int(time.time() // 60)}"
    cache.add(key, 0, 120)
    return cache.incr(key) <= LOOKUPS_PER_MINUTE


def record_files(host, record_id):
    """Name, size and download address of each file of a record, kept an hour: one visit does not
    ask Zenodo again, and a loop over the files cannot use up its limit."""
    key = f"zenodo-record:{host}:{record_id}"
    files = cache.get(key)
    if files is not None:
        return files
    if not _room():
        raise ZenodoBusy()
    try:
        answer = requests.get(
            f"https://{host}/api/records/{record_id}",
            timeout=15,
            headers={"User-Agent": "mouseTube"},
        )
        answer.raise_for_status()
        entries = answer.json().get("files") or []
    except (requests.RequestException, ValueError, AttributeError) as error:
        raise ZenodoUnavailable(str(error)) from error
    files = [
        {
            "name": entry["key"],
            "size": entry.get("size"),
            "url": file_url(host, record_id, entry["key"]),
        }
        for entry in entries
        if isinstance(entry, dict) and entry.get("key")
    ]
    cache.set(key, files, RECORD_SECONDS)
    return files


class _Sink:
    """What the zip is written to: it keeps the bytes until they are sent (it cannot seek)."""

    def __init__(self):
        self.parts = []

    def write(self, data):
        self.parts.append(bytes(data))
        return len(data)

    def flush(self):
        pass

    def take(self):
        data = b"".join(self.parts)
        self.parts.clear()
        return data


def iter_zip(entries, max_bytes):
    """The bytes of a zip of `entries` ((name in the zip, address, size or None)), one chunk at a
    time. The files are stored, not compressed (WAV does not shrink). A file that cannot be read is
    left out and written in `_errors.txt`, at the end; after `max_bytes` nothing more is added."""
    sink = _Sink()
    problems = []
    sent = 0
    with zipfile.ZipFile(sink, "w", zipfile.ZIP_STORED, allowZip64=True) as archive:
        for index, (name, url, size) in enumerate(entries):
            if sent >= max_bytes:
                problems.extend(
                    f"{n}: not added, size limit reached" for n, _, _ in entries[index:]
                )
                break
            try:
                with requests.get(url, stream=True, timeout=(10, 60)) as answer:
                    answer.raise_for_status()
                    info = zipfile.ZipInfo(name, time.localtime()[:6])
                    info.compress_type = zipfile.ZIP_STORED
                    received = 0
                    with archive.open(info, "w", force_zip64=True) as out:
                        for chunk in answer.iter_content(CHUNK):
                            out.write(chunk)
                            received += len(chunk)
                            sent += len(chunk)
                            yield sink.take()
                            if sent >= max_bytes:
                                break
                    if (size and received != size) or sent >= max_bytes:
                        problems.append(
                            f"{name}: incomplete ({received} of {size or '?'} bytes)"
                        )
            except requests.RequestException as error:
                problems.append(f"{name}: {error.__class__.__name__}")
            yield sink.take()
        if problems:
            archive.writestr("_errors.txt", "\n".join(problems) + "\n")
    yield sink.take()
