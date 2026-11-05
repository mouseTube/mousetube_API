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


LOCMEM = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}


@override_settings(CACHES=LOCMEM)  # do not touch the real Redis counters
class ThrottleTests(TestCase):
    def test_login_is_rate_limited(self):
        client = APIClient()
        codes = [
            client.post(
                "/auth/jwt/create/", {"username": "x", "password": "y"}, format="json"
            ).status_code
            for _ in range(12)
        ]
        self.assertEqual(codes[:10], [401] * 10)
        self.assertEqual(codes[10], 429)


class OrcidAndPrivacyTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user("u", password="x")  # nosec B106
        self.other = User.objects.create_user(
            "o",
            email="o@example.org",
            password="x",  # nosec B106
        )
        self.client = APIClient()

    def test_link_orcid_needs_a_valid_proof(self):
        from mousetube_api.utils.orcid_proof import make_orcid_proof

        self.client.force_authenticate(self.user)
        r = self.client.post("/api/link-orcid/", {"orcid": "0000-0002-1825-0097"})
        self.assertEqual(r.status_code, 400)  # raw iD, no proof
        r = self.client.post("/api/link-orcid/", {"orcid_proof": "forged"})
        self.assertEqual(r.status_code, 400)
        proof = make_orcid_proof("0000-0002-1825-0097")
        r = self.client.post("/api/link-orcid/", {"orcid_proof": proof})
        self.assertEqual(r.status_code, 200)
        self.user.user_profile.refresh_from_db()
        self.assertEqual(self.user.user_profile.orcid, "0000-0002-1825-0097")

    def test_orcid_cannot_be_patched_directly(self):
        self.client.force_authenticate(self.user)
        pid = self.user.user_profile.id
        self.client.patch(f"/api/user_profile/{pid}/", {"orcid": "x"}, format="json")
        self.user.user_profile.refresh_from_db()
        self.assertFalse(self.user.user_profile.orcid)

    def test_profile_list_is_limited_to_own_profile(self):
        self.client.force_authenticate(self.user)
        ids = [p["user"]["id"] for p in self.client.get("/api/user_profile/").json()]
        self.assertEqual(ids, [self.user.id])

    def test_anonymous_does_not_see_contact_email(self):
        from mousetube_api.models import Contact

        Contact.objects.create(
            first_name="a",
            last_name="b",
            email="secret@example.org",
            status="validated",
            created_by=self.other,
        )
        body = APIClient().get("/api/contact/").content.decode()
        self.assertNotIn("secret@example.org", body)
        self.client.force_authenticate(self.user)
        self.assertIn(
            "secret@example.org", self.client.get("/api/contact/").content.decode()
        )

    def test_publish_twice_is_refused(self):
        s = RecordingSession.objects.create(
            name="p", is_multiple=True, created_by=self.user
        )
        # the publish task writes "published" with update() (not in the model choices)
        RecordingSession.objects.filter(pk=s.pk).update(status="published")
        self.client.force_authenticate(self.user)
        r = self.client.post(
            "/api/file/publish_session/",
            {"recording_session_id": s.id, "repository_id": 1},
            format="json",
        )
        self.assertEqual(r.status_code, 409)

    def test_track_page_drops_query_string(self):
        from mousetube_api.models import PageView

        r = APIClient().post("/api/track-page/", {"path": "/hardware?x=1#top"})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(PageView.objects.filter(path="/hardware").exists())
        r = APIClient().post("/api/track-page/", {"path": "no-slash"})
        self.assertEqual(r.status_code, 400)


@override_settings(CACHES=LOCMEM)
class InstitutionalEmailTests(TestCase):
    def test_personal_domains_are_detected(self):
        from mousetube_api.utils.email_domains import is_personal_email

        for email in (
            "a@gmail.com",
            "a@GMAIL.com",
            "a@mail.yahoo.com",  # subdomain of a provider
            "a@free.fr",
            "a@mailinator.com",
        ):
            with self.subTest(email=email):
                self.assertTrue(is_personal_email(email))
        for email in ("a@igbmc.fr", "a@unistra.fr", "a@univ-lyon1.fr", "a@ox.ac.uk"):
            with self.subTest(email=email):
                self.assertFalse(is_personal_email(email))

    def _register(self, email):
        return APIClient().post(
            "/auth/users/",
            {"username": "n", "email": email, "password": "Zx9!tr0ngPassw0rd#"},
            format="json",
        )

    def test_registration_with_personal_email_is_refused(self):
        r = self._register("someone@gmail.com")
        self.assertEqual(r.status_code, 400)
        self.assertIn("email", r.json())

    @override_settings(REQUIRE_INSTITUTIONAL_EMAIL=False)
    def test_check_can_be_turned_off_for_local_dev(self):
        self.assertEqual(self._register("someone@gmail.com").status_code, 201)

    def test_registration_with_institutional_email_works(self):
        self.assertEqual(self._register("someone@igbmc.fr").status_code, 201)

    def test_domains_endpoint_is_public(self):
        body = APIClient().get("/api/personal-email-domains/").json()
        self.assertTrue(body["enforced"])
        self.assertIn("gmail.com", body["domains"])
