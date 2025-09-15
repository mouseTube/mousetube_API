def remove_auth_paths(endpoints):
    """
    endpoints: list of tuples (path, path_regex, method, callback)
    """
    filtered = [
        (path, path_regex, method, callback)
        for path, path_regex, method, callback in endpoints
        if not path.startswith("/auth/") and not path.startswith("/accounts/")
    ]
    return filtered
