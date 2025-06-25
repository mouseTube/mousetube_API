from django.apps import AppConfig


class MousetubeApiConfig(AppConfig):
    name = "mousetube_api"

    def ready(self):
        import mousetube_api.utils.signals
