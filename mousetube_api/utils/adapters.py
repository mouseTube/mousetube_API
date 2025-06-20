from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.socialaccount.models import SocialApp
from django.contrib.sites.shortcuts import get_current_site
from django.core.exceptions import MultipleObjectsReturned
from django.http import HttpResponseRedirect
from allauth.core.exceptions import ImmediateHttpResponse
from rest_framework_simplejwt.tokens import RefreshToken
import environ
from django.conf import settings


env = environ.Env()
environ.Env.read_env() 

class MySocialAccountAdapter(DefaultSocialAccountAdapter):
    def is_open_for_signup(self, request, sociallogin):
        return True

    def pre_social_login(self, request, sociallogin):
        domain = env("FRONT_DOMAIN", default="localhost:3000")
        protocol = "https" if not settings.DEBUG else "http"
        if sociallogin.account.provider != "orcid":
            return

        given_names = (
            (
                sociallogin.account.extra_data.get("person", {})
                .get("name", {})
                .get("given-names", {})
                or {}
            )
            .get("value", "")
            .strip()
        )
        family_name = (
            (
                sociallogin.account.extra_data.get("person", {})
                .get("name", {})
                .get("family-name", {})
                or {}
            )
            .get("value", "")
            .strip()
        )
        orcid_id = sociallogin.account.uid
        from django.contrib.auth import get_user_model

        User = get_user_model()

        matching_users = User.objects.filter(
            first_name__iexact=given_names, last_name__iexact=family_name
        )
        for user in matching_users:
            profile = getattr(user, "user_profile", None)
            if profile and not profile.orcid:
                raise ImmediateHttpResponse(
                    HttpResponseRedirect(
                        f"{protocol}://{domain}/account/link-orcid?orcid={orcid_id}&first_name={given_names}&last_name={family_name}&user_id={user.id}"
                    )
                )

        from mousetube_api.models import UserProfile

        try:
            profile = UserProfile.objects.get(orcid=orcid_id)
            user = profile.user
            refresh = RefreshToken.for_user(user)
            token = str(refresh.access_token)
            raise ImmediateHttpResponse(
                HttpResponseRedirect(
                    f"{protocol}://{domain}/auth/callback?token={token}"
                )
            )
        except UserProfile.DoesNotExist:
            raise ImmediateHttpResponse(
                HttpResponseRedirect(
                    f"{protocol}://{domain}/account/register?orcid={orcid_id}&first_name={given_names}&last_name={family_name}"
                )
            )

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
        return visible_apps.first()
