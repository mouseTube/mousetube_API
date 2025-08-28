def remove_auth_paths(endpoints):
    """
    endpoints: liste de tuples (path, path_regex, method, callback)
    On retourne la liste filtrée pour enlever /auth/ et /accounts/
    """
    filtered = [
        (path, path_regex, method, callback)
        for path, path_regex, method, callback in endpoints
        if not path.startswith("/auth/") and not path.startswith("/accounts/")
    ]
    return filtered
