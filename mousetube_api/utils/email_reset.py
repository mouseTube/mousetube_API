"""The password reset e-mail (djoser)."""

from django.conf import settings
from djoser.email import PasswordResetEmail


class CustomPasswordResetEmail(PasswordResetEmail):
    """The password reset e-mail, with the address and the name of the website in its links."""

    def get_context_data(self):
        context = super().get_context_data()
        context["domain"] = settings.FRONT_DOMAIN
        context["site_name"] = "mouseTube"
        return context
