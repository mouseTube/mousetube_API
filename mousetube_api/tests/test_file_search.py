"""The search of files puts the files whose own name matches first."""

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from mousetube_api.models import RecordingSession
from mousetube_api.tests.test_security import LOCMEM, FreshCache


@override_settings(CACHES=LOCMEM)
class FileSearchOrder(FreshCache, TestCase):
    def test_the_files_named_like_the_search_come_first(self):
        from mousetube_api.models import File

        owner = get_user_model().objects.create_user("o", "o@igbmc.fr", "pw-pw-pw-1")
        # "zebra" is in the name of the session of the first file, and in the name of the second
        session = RecordingSession.objects.create(
            name="zebra session", is_multiple=True, created_by=owner
        )
        RecordingSession.objects.filter(pk=session.pk).update(status="shared")
        for name in ("a_other.wav", "my_zebra.wav", "zebra_rec.wav"):
            File.objects.create(
                name=name, recording_session=session, status="done", created_by=owner
            )
        names = [
            f["name"]
            for f in APIClient()
            .get("/api/file/", {"search": "zebra"})
            .json()["results"]
        ]
        self.assertEqual(names, ["zebra_rec.wav", "my_zebra.wav", "a_other.wav"])
