from django.conf import settings
from djoser.email import ActivationEmail


class CustomActivationEmail(ActivationEmail):
    def get_context_data(self):
        context = super().get_context_data()
        context["domain"] = settings.FRONT_DOMAIN
        context["site_name"] = "mouseTube"
        return context
