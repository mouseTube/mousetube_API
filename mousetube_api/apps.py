from django.apps import AppConfig


class MousetubeApiConfig(AppConfig):
    name = "mousetube_api"

    def ready(self):
        pass
        # Ensure that signals are imported when the app is ready
        # This will register the signal handlers defined in utils/signals.py
