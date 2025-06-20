from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.socialaccount.models import SocialApp
from django.contrib.sites.shortcuts import get_current_site
from django.core.exceptions import MultipleObjectsReturned
from django.http import HttpResponseRedirect
from allauth.core.exceptions import ImmediateHttpResponse
from rest_framework_simplejwt.tokens import RefreshToken
from mousetube_api.models import UserProfile
from django.conf import settings
from django.contrib.auth import get_user_model

User = get_user_model()


class MySocialAccountAdapter(DefaultSocialAccountAdapter):
    def is_open_for_signup(self, request, sociallogin):
        return True

    def pre_social_login(self, request, sociallogin):
        process = request.session.pop("orcid_process", None)

        if sociallogin.account.provider != "orcid":
            return

        domain = settings.FRONT_DOMAIN
        protocol = "https" if not settings.DEBUG else "http"

        given_names = (
            sociallogin.account.extra_data.get("person", {})
            .get("name", {})
            .get("given-names", {})
            .get("value", "")
            .strip()
        )
        family_name = (
            sociallogin.account.extra_data.get("person", {})
            .get("name", {})
            .get("family-name", {})
            .get("value", "")
            .strip()
        )
        orcid_id = sociallogin.account.uid

        try:
            profile = UserProfile.objects.get(orcid=orcid_id)
            user = profile.user
            token = str(RefreshToken.for_user(user).access_token)

            redirect_url = f"{protocol}://{domain}/auth/callback?token={token}"
            raise ImmediateHttpResponse(HttpResponseRedirect(redirect_url))

        except UserProfile.DoesNotExist:
            if process == "connect":
                redirect_url = (
                    f"{protocol}://{domain}/account/link-orcid"
                    f"?orcid={orcid_id}&first_name={given_names}&last_name={family_name}"
                )
                raise ImmediateHttpResponse(HttpResponseRedirect(redirect_url))
            else:
                redirect_url = (
                    f"{protocol}://{domain}/account/register"
                    f"?orcid={orcid_id}&first_name={given_names}&last_name={family_name}"
                )
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
