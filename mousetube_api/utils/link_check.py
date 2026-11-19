"""Check that the download links of the files still answer.

Used by the `check_dead_links` command and by the background task an administrator starts from
the profile page. One request per link and a pause between two of them: the servers (Zenodo
first) must not be overwhelmed. A link is only followed when it points to a public address: the
links are written by users, the server must not be made to look at its own network.
"""

import ipaddress
import os
import socket
import time
from urllib.parse import unquote, urljoin, urlparse

import requests
from django.core.cache import cache
from django.utils import timezone

from mousetube_api.models import File

DELAY = 1  # seconds between two links
MAX_REDIRECTS = 5
STATE_KEY = "link-check:state"
LOCK_KEY = "link-check:lock"
LOCK_SECONDS = 6 * 3600  # a task that died leaves the lock for this long at most


def is_public_host(host):
    """True when every address of `host` is a public one (not local, private or reserved)."""
    if not host:
        return False
    try:
        addresses = {info[4][0] for info in socket.getaddrinfo(host, None)}
    except OSError:
        return False
    for address in addresses:
        ip = ipaddress.ip_address(address.split("%")[0])
        if not ip.is_global or ip.is_multicast:
            return False
    return bool(addresses)


def _request(method, url, **kwargs):
    """One request, following the redirects by hand to look at where each one leads."""
    for _ in range(MAX_REDIRECTS + 1):
        if not url.startswith(("http://", "https://")) or not is_public_host(
            urlparse(url).hostname
        ):
            return None
        response = requests.request(method, url, allow_redirects=False, **kwargs)
        if response.status_code in (301, 302, 303, 307, 308) and response.headers.get(
            "location"
        ):
            url = urljoin(url, response.headers["location"])
            response.close()
            continue
        return response
    return None  # too many redirects


def check_link(url):
    """(state, code, response): state is ok, broken, skipped (not looked at) or unknown (busy)."""
    if not url.startswith(("http://", "https://")):
        return "skipped", None, None
    if not is_public_host(urlparse(url).hostname):
        return "skipped", None, None  # localhost, private network, unknown host
    try:
        response = _request("HEAD", url, timeout=5)
        if response is not None and response.status_code >= 400:
            response = _request("GET", url, timeout=10, stream=True)
    except requests.RequestException:
        return "broken", None, None
    if response is None:
        return "skipped", None, None  # it led to a non public address, or in circles
    if response.status_code == 429:
        return (
            "unknown",
            429,
            None,
        )  # the server asks to slow down: nothing is concluded
    state = "ok" if response.status_code < 400 else "broken"
    headers = response.headers
    response.close()
    return state, response.status_code, headers


def extract_filename(headers, url):
    """The file name given by the server (Content-Disposition), else the end of the address."""
    for part in (headers or {}).get("content-disposition", "").split(";"):
        if "filename=" in part:
            return part.strip().split("filename=")[-1].strip('"')
    return os.path.basename(unquote(urlparse(url).path)) or None


def run(progress=None, fill_name=False, pause=time.sleep):
    """Check every link; the validity of each file follows the answer. Returns the counts."""
    files = list(
        File.objects.exclude(link__isnull=True).exclude(link="").order_by("id")
    )
    counts = {
        "total": len(files),
        "done": 0,
        "ok": 0,
        "broken": 0,
        "skipped": 0,
        "unknown": 0,
    }
    for file in files:
        state, _, headers = check_link(file.link)
        if state == "ok":
            if not file.is_valid_link:
                File.objects.filter(pk=file.pk).update(is_valid_link=True)
            if fill_name and not file.name:
                name = extract_filename(headers, file.link)
                if name:
                    File.objects.filter(pk=file.pk).update(name=name)
        elif state == "broken" and file.is_valid_link:
            File.objects.filter(pk=file.pk).update(is_valid_link=False)
        counts[state] += 1
        counts["done"] += 1
        if progress:
            progress(counts)
        if state != "skipped":
            pause(DELAY)
    return counts


# -- what the interface follows: kept in the cache, so that the web and the worker both see it


def read_state():
    return cache.get(STATE_KEY)


def write_state(**changes):
    state = {**(cache.get(STATE_KEY) or {}), **changes}
    cache.set(STATE_KEY, state, 7 * 24 * 3600)
    return state


def start_state(task_id=""):
    return write_state(
        state="running",
        task_id=task_id,
        started_at=timezone.now().isoformat(),
        finished_at=None,
        error="",
        total=0,
        done=0,
        ok=0,
        broken=0,
        skipped=0,
        unknown=0,
    )
