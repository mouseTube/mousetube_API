from djoser.email import ActivationEmail


class CustomActivationEmail(ActivationEmail):
    def get_context_data(self):
        context = super().get_context_data()
        context["domain"] = "localhost:3000"
        context["site_name"] = "mouseTube"
        return context
