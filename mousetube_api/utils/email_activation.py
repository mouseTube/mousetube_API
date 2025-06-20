from djoser.email import ActivationEmail
import environ

env = environ.Env()
environ.Env.read_env()

class CustomActivationEmail(ActivationEmail):
    def get_context_data(self):
        context = super().get_context_data()
        context["domain"] = env("FRONT_DOMAIN", default="localhost:3000")
        context["site_name"] = "mouseTube"
        return context
