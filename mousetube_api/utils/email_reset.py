from djoser.email import PasswordResetEmail

class CustomPasswordResetEmail(PasswordResetEmail):
    def get_context_data(self):
        context = super().get_context_data()
        context["domain"] = "localhost:3000"  # ou ton domaine réel en prod
        context["site_name"] = "mouseTube"
        return context