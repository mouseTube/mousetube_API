from django.conf import settings


def site_urls(request):
    """Lets the allauth pages link back to the website (logo, login page)."""
    return {"FRONT_URL": settings.FRONT_URL}
