"""Log out of all devices: sign-ins that are no longer valid.

A JWT cannot be taken back once it is issued, so the server remembers, by user, the moment up to which
the sign-ins are revoked (`UserProfile.sessions_revoked_at`): an access or a refresh token made for a
sign-in up to then is refused. Changing the password does the same. A token carries the moment of its
sign-in in milliseconds (`iat_ms`; the standard `iat` is in seconds, too coarse to sign in again right
after a revocation); a token without it (made before this existed) is read with its `iat`.
"""

import time

from django.utils import timezone
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken

from mousetube_api.models import UserProfile

IAT_MS = "iat_ms"


def signed_in_at_ms():
    """The moment of a sign-in, to put in its token."""
    return int(time.time() * 1000)


def revoke_sessions(user):
    """Every sign-in made up to now is no longer valid (the user signs in again)."""
    UserProfile.objects.filter(user=user).update(sessions_revoked_at=timezone.now())


def is_revoked(user_id, token):
    """True when the sign-in the token was made for is revoked."""
    revoked_at = (
        UserProfile.objects.filter(user_id=user_id)
        .values_list("sessions_revoked_at", flat=True)
        .first()
    )
    if revoked_at is None:
        return False
    issued_ms = token.get(IAT_MS)
    if issued_ms is None:
        issued_ms = int(token.get("iat", 0)) * 1000
    return issued_ms <= int(revoked_at.timestamp() * 1000)


class RevocableJWTAuthentication(JWTAuthentication):
    """The JWT authentication, which also refuses the sign-ins that were revoked."""

    def get_user(self, validated_token):
        user = super().get_user(validated_token)
        if is_revoked(user.pk, validated_token):
            raise AuthenticationFailed(
                "Your session has ended. Sign in again.", code="session_revoked"
            )
        return user


class RevocableTokenRefreshSerializer(TokenRefreshSerializer):
    """The renewal of an access token, refused for a sign-in that was revoked."""

    def validate(self, attrs):
        refresh = RefreshToken(attrs["refresh"])
        if is_revoked(refresh.get("user_id"), refresh):
            raise TokenError("Your session has ended. Sign in again.")
        return super().validate(attrs)
