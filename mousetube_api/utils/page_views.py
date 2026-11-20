"""Addresses as the page-view statistics keep them."""

# pages whose address carries a one-time secret (account activation, password reset): the
# statistics must not store it, and count them as one page
SECRET_PAGES = ("/activate", "/password")


def normalize_page_path(path):
    for prefix in SECRET_PAGES:
        if path == prefix or path.startswith(prefix + "/"):
            return prefix
    return path
