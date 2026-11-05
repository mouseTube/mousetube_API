from rest_framework.throttling import SimpleRateThrottle

# (scope, path prefix) of POST endpoints that can be brute-forced or used to spam the admin
_THROTTLED = (
    ("auth", "/auth/jwt/create"),
    ("auth", "/auth/jwt/refresh"),
    ("auth", "/auth/users/reset_password"),
    ("auth", "/auth/users/resend_activation"),
    ("auth", "/auth/users/activation"),
    ("register", "/auth/users/"),
)


class AuthEndpointsThrottle(SimpleRateThrottle):
    """Per-IP limit on login/registration only; every other endpoint is untouched."""

    scope = (
        "auth"  # default so __init__ can read a rate; get_cache_key picks the real one
    )

    def get_cache_key(self, request, view):
        if request.method != "POST":
            return None
        for scope, prefix in _THROTTLED:
            # exact match for "/auth/users/" so /auth/users/me/ etc. are not counted
            if request.path.startswith(prefix) and (
                prefix != "/auth/users/" or request.path.rstrip("/") == "/auth/users"
            ):
                self.scope = scope
                self.rate = self.get_rate()
                self.num_requests, self.duration = self.parse_rate(self.rate)
                return self.cache_format % {
                    "scope": scope,
                    "ident": self.get_ident(request),
                }
        return None
