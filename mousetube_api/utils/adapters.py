"""Sign-in with ORCID (allauth): what happens when the ORCID iD is known or not."""

from urllib.parse import urlencode

from allauth.core.exceptions import ImmediateHttpResponse
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.socialaccount.models import SocialApp
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.sites.shortcuts import get_current_site
from django.core.exceptions import MultipleObjectsReturned
from django.http import HttpResponseRedirect
from rest_framework_simplejwt.tokens import RefreshToken

from mousetube_api.models import UserProfile
from mousetube_api.utils.email_domains import is_personal_email
from mousetube_api.utils.orcid_proof import make_orcid_proof
from mousetube_api.utils.registration import email_is_verified

User = get_user_model()


def _orcid_name(extra_data, part):
    """A part of the name in the ORCID record ("given-names" or "family-name"), or "".

    ORCID sends null, not an empty value, for a name that is private on the record or that the
    person does not have (many records have no family name): that must not break the login."""
    name = (extra_data.get("person") or {}).get("name") or {}
    return ((name.get(part) or {}).get("value") or "").strip()


def _orcid_email(extra_data):
    """The institutional address of the record, or "" (ORCID only gives the ones that are public).

    It only pre-fills the form: the address is confirmed by the link sent to it, like any other.
    A personal address (gmail...) is not offered: the registration refuses it."""
    emails = ((extra_data.get("person") or {}).get("emails") or {}).get("email") or []
    for entry in emails:
        address = ((entry or {}).get("email") or "").strip()
        if address and not is_personal_email(address):
            return address
    return ""


class MySocialAccountAdapter(DefaultSocialAccountAdapter):
    """Sign-in with ORCID: a known ORCID iD logs in, an unknown one goes to the registration form."""

    def is_open_for_signup(self, request, sociallogin):
        """ORCID may always start a registration (an administrator still reviews it)."""
        return True

    def pre_social_login(self, request, sociallogin):
        """
        Handle login with ORCID.

        Args:
            request (HttpRequest): The current HTTP request.
            sociallogin (SocialLogin): The social login information from Allauth.

        Raises:
            ImmediateHttpResponse: Redirects the user depending on whether the ORCID is known.
        """
        process = request.session.pop("orcid_process", None)

        if sociallogin.account.provider != "orcid":
            return

        domain = settings.FRONT_DOMAIN
        protocol = "https" if not settings.DEBUG else "http"

        given_names = _orcid_name(sociallogin.account.extra_data, "given-names")
        family_name = _orcid_name(sociallogin.account.extra_data, "family-name")
        email = _orcid_email(sociallogin.account.extra_data)
        orcid_id = sociallogin.account.uid

        try:
            profile = UserProfile.objects.get(orcid=orcid_id)
            user = profile.user
            if not user.is_active:
                # ORCID proved who they are, so showing the state of the request is safe.
                state = (
                    "awaiting_review"
                    if email_is_verified(user)
                    else "awaiting_email_confirmation"
                )
                query = urlencode({"account_status": state})
                redirect_url = f"{protocol}://{domain}/account/login?{query}"
                raise ImmediateHttpResponse(HttpResponseRedirect(redirect_url))
            token = str(RefreshToken.for_user(user).access_token)

            # Fragment (#), not query (?): it is never sent to servers, logs or Referer.
            redirect_url = (
                f"{protocol}://{domain}/auth/callback#{urlencode({'token': token})}"
            )
            raise ImmediateHttpResponse(HttpResponseRedirect(redirect_url))

        except UserProfile.DoesNotExist:
            page = "link-orcid" if process == "connect" else "register"
            query = urlencode(
                {
                    "orcid": orcid_id,
                    "orcid_proof": make_orcid_proof(orcid_id),
                    "first_name": given_names,
                    "last_name": family_name,
                    **({"email": email} if email else {}),
                }
            )
            redirect_url = f"{protocol}://{domain}/account/{page}?{query}"
            raise ImmediateHttpResponse(HttpResponseRedirect(redirect_url))

    def get_app(self, request, provider, client_id=None):
        site = get_current_site(request)

        visible_apps = (
            SocialApp.objects.filter(provider=provider, sites=site)
            .exclude(name__isnull=True)
            .exclude(name__exact="")
        )

        if not visible_apps.exists():
            visible_apps = (
                SocialApp.objects.filter(provider=provider)
                .exclude(name__isnull=True)
                .exclude(name__exact="")
            )

        if not visible_apps.exists():
            return None

        if visible_apps.count() > 1:
            raise MultipleObjectsReturned(
                f"Multiple SocialApp instances found for provider '{provider}'"
            )

        app = visible_apps.first()
        return app
