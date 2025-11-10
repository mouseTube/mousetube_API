# mousetube_api/apps.py

from django.apps import AppConfig
from django.conf import settings
from django.db.models.signals import post_migrate


def create_orcid_social_app(sender, **kwargs):
    """
    Crée ou met à jour automatiquement le Site et le SocialApp ORCID
    après les migrations.
    """
    from allauth.socialaccount.models import SocialApp
    from django.contrib.sites.models import Site

    # --- Get ORCID credentials ---
    creds = (
        getattr(settings, "SOCIALACCOUNT_PROVIDERS", {}).get("orcid", {}).get("APP", {})
    )
    client_id = creds.get("client_id")
    secret = creds.get("secret")

    if not client_id or not secret:
        print(
            "[WARN] SocialApp ORCID not created : client_id and secret missing in settings"
        )
        return

    # --- Update or create SITE ---
    site, created = Site.objects.update_or_create(
        id=settings.SITE_ID,
        defaults={
            "domain": "https://mousetube.fr",
            "name": "mousetube.fr",
        },
    )
    if created:
        print(f"[INFO] Site created : {site.domain}")
    else:
        print(f"[INFO] Site updated : {site.domain}")

    # --- Update or create SocialApp ORCID ---
    app, created = SocialApp.objects.get_or_create(
        provider="orcid",
        defaults={
            "name": "ORCID",
            "client_id": client_id,
            "secret": secret,
        },
    )
    # Link SocialApp to SITE
    if site not in app.sites.all():
        app.sites.add(site)

    # Update credential if needed
    updated = False
    if app.client_id != client_id:
        app.client_id = client_id
        updated = True
    if app.secret != secret:
        app.secret = secret
        updated = True
    if updated:
        app.save()
        print("[INFO] SocialApp ORCID mis à jour avec les nouvelles credentials")

    if created:
        print(f"[INFO] SocialApp ORCID créé et lié au site {site.domain}")


class MousetubeApiConfig(AppConfig):
    name = "mousetube_api"

    def ready(self):
        # --- Import signals ---
        import mousetube_api.utils.signals  # noqa: F401

        # --- Connect function to post_migrate ---
        post_migrate.connect(create_orcid_social_app, sender=self)
