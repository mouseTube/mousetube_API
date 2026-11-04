import tempfile
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings
from rest_framework.test import APIClient

from mousetube_api.models import RecordingSession, Repository
from mousetube_api.utils.file_handler import is_temp_path, link_to_local_path


class LinkToLocalPathTests(SimpleTestCase):
    """link_to_local_path must never leave MEDIA_ROOT."""

    def setUp(self):
        self.media = tempfile.mkdtemp()
        self.override = override_settings(MEDIA_ROOT=self.media)
        self.override.enable()
        self.addCleanup(self.override.disable)

    def resolve(self, link):
        return link_to_local_path(SimpleNamespace(link=link))

    def test_media_and_temp_links_resolve_inside_media_root(self):
        self.assertTrue(self.resolve("/media/a.wav").startswith(self.media))
        self.assertTrue(
            self.resolve("https://x.org/media/temp/a.wav").startswith(self.media)
        )
        self.assertTrue(is_temp_path(self.resolve("/temp/a.wav")))

    def test_escapes_are_rejected(self):
        for link in (
            "/etc/passwd",
            "/media/../../etc/passwd",
            "/media/%2e%2e/%2e%2e/etc/passwd",
            "https://x.org/media/../../etc/passwd",
            "relative/path.wav",
        ):
            with self.subTest(link=link), self.assertRaises(ValueError):
                self.resolve(link)

    def test_only_media_temp_is_deletable(self):
        self.assertFalse(is_temp_path(self.resolve("/media/a.wav")))


class PermissionTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user("owner", password="x")  # nosec B106
        self.other = User.objects.create_user("other", password="x")  # nosec B106
        self.session = RecordingSession.objects.create(
            name="s", is_multiple=True, created_by=self.owner
        )
        self.client = APIClient()

    def test_anonymous_cannot_read_task_status(self):
        self.assertEqual(
            self.client.get(
                "/api/recording-session/get_task_status?task_id=x"
            ).status_code,
            401,
        )

    def test_anonymous_cannot_write_by_default(self):
        self.assertEqual(self.client.post("/api/hardware/", {}).status_code, 401)

    def test_anonymous_can_still_track_pages(self):
        self.assertNotIn(
            self.client.post("/api/track-page/", {"path": "/"}).status_code, (401, 403)
        )

    def test_cannot_publish_someone_elses_session(self):
        self.client.force_authenticate(self.other)
        r = self.client.post(
            "/api/file/publish_session/",
            {"recording_session_id": self.session.id, "repository_id": 1},
            format="json",
        )
        self.assertEqual(r.status_code, 403)

    def test_cannot_read_payload_of_someone_elses_session(self):
        self.client.force_authenticate(self.other)
        repo = Repository.objects.create(name="r")
        r = self.client.get(
            f"/api/repository/{repo.id}/sessions/{self.session.id}/payload/"
        )
        self.assertEqual(r.status_code, 403)

    def test_non_staff_cannot_self_validate(self):
        self.client.force_authenticate(self.other)
        r = self.client.post(
            "/api/hardware/", {"name": "m", "type": "microphone"}, format="json"
        )
        self.assertEqual(r.status_code, 201)
        r = self.client.patch(
            f"/api/hardware/{r.data['id']}/", {"status": "validated"}, format="json"
        )
        self.assertEqual(r.status_code, 400)
