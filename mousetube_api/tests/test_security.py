import tempfile
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
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


class FreshCache:
    """LocMem is shared by the whole test process: reset the rate-limit counters."""

    def setUp(self):
        from django.core.cache import cache

        cache.clear()
        super().setUp()


@override_settings(CACHES=LOCMEM)  # do not touch the real Redis counters
class ThrottleTests(FreshCache, TestCase):
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
class InstitutionalEmailTests(FreshCache, TestCase):
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


@override_settings(CACHES=LOCMEM)
class AccountRequestWorkflowTests(FreshCache, TestCase):
    """e-mail confirmation by the user, then activation by an admin."""

    def setUp(self):
        super().setUp()
        from django.core import mail

        self.mail = mail
        self.client = APIClient()
        r = self.client.post(
            "/auth/users/",
            {
                "username": "newbie",
                "email": "newbie@igbmc.fr",
                "password": "Zx9!tr0ngPassw0rd#",
            },
            format="json",
        )
        self.assertEqual(r.status_code, 201)
        self.user = get_user_model().objects.get(username="newbie")

    def _link(self):
        from django.contrib.auth.tokens import default_token_generator
        from djoser import utils

        return {
            "uid": utils.encode_uid(self.user.pk),
            "token": default_token_generator.make_token(self.user),
        }

    def test_registration_mails_the_user_not_the_admin(self):
        self.assertFalse(self.user.is_active)
        self.assertEqual([m.to for m in self.mail.outbox], [["newbie@igbmc.fr"]])

    def test_confirmation_notifies_admin_once_and_does_not_activate(self):
        self.mail.outbox.clear()
        for _ in range(2):  # a second click must not mail the admin again
            r = self.client.post("/auth/users/activation/", self._link(), format="json")
            self.assertEqual(r.status_code, 204)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)
        self.assertEqual(len(self.mail.outbox), 1)
        self.assertEqual(self.mail.outbox[0].to, ["mousetube@igbmc.fr"])
        self.assertIn(
            f"/admin/auth/user/{self.user.pk}/change/", self.mail.outbox[0].body
        )

    def test_bad_token_is_refused(self):
        link = self._link() | {"token": "forged"}
        r = self.client.post("/auth/users/activation/", link, format="json")
        self.assertEqual(r.status_code, 400)

    def test_admin_action_activates_only_confirmed_accounts(self):
        from django.contrib.admin.sites import site
        from django.contrib.messages.storage.fallback import FallbackStorage
        from django.test import RequestFactory

        other = get_user_model().objects.create_user(
            "unconfirmed", email="u@igbmc.fr", is_active=False
        )
        self.client.post("/auth/users/activation/", self._link(), format="json")
        self.mail.outbox.clear()

        request = RequestFactory().post("/admin/")
        request.user = get_user_model().objects.create_superuser(
            "root", "r@igbmc.fr", "x"
        )
        request.session = {}
        request._messages = FallbackStorage(request)
        admin_obj = site._registry[get_user_model()]
        admin_obj.activate_accounts(
            request, get_user_model().objects.filter(pk__in=[self.user.pk, other.pk])
        )

        self.user.refresh_from_db()
        other.refresh_from_db()
        self.assertTrue(self.user.is_active)
        self.assertFalse(other.is_active)
        self.assertEqual([m.to for m in self.mail.outbox], [["newbie@igbmc.fr"]])


class OauthPagesTests(SimpleTestCase):
    """The allauth screens use our templates (no allauth menu, link back to the website)."""

    def _render(self, name, **ctx):
        from django.template.loader import render_to_string
        from django.test import RequestFactory

        return render_to_string(name, ctx, request=RequestFactory().get("/"))

    def test_continue_page_explains_and_posts(self):
        html = self._render(
            "socialaccount/login.html",
            process="connect",
            provider=SimpleNamespace(name="ORCID"),
        )
        self.assertIn("Continue to ORCID", html)
        self.assertIn("csrfmiddlewaretoken", html)
        self.assertNotIn("Menu:", html)

    def test_error_and_cancel_pages_link_back_to_login(self):
        for name in (
            "socialaccount/authentication_error.html",
            "socialaccount/login_cancelled.html",
        ):
            with self.subTest(name=name):
                self.assertIn("/account/login", self._render(name))


@override_settings(CACHES=LOCMEM)
class AdminAccountReviewTests(TestCase):
    """The admin list of account requests, and the reject action."""

    def setUp(self):
        from allauth.account.models import EmailAddress
        from django.core import mail

        self.mail = mail
        User = get_user_model()
        self.root = User.objects.create_superuser("root", "root@igbmc.fr", "x")
        self.pending = User.objects.create_user(
            "pending", email="p@igbmc.fr", is_active=False
        )
        EmailAddress.objects.create(
            user=self.pending, email="p@igbmc.fr", verified=True, primary=True
        )
        self.unconfirmed = User.objects.create_user(
            "unconf", email="u@igbmc.fr", password="pw", is_active=False
        )
        self.active = User.objects.create_user("active", email="a@igbmc.fr")
        self.old = User.objects.create_user(
            "old", email="o@igbmc.fr", password="pw", is_active=False
        )
        # an author imported from mouseTube 0.5: inactive, no password, nobody waits for it
        self.imported = User.objects.create_user("mt05-7", is_active=False)
        User.objects.filter(pk=self.old.pk).update(last_login="2024-01-01T00:00:00Z")
        self.client.force_login(self.root)
        self.url = "/admin/auth/user/"

    def _usernames(self, query):
        html = self.client.get(self.url + query).content.decode()
        return [
            u
            for u in ("pending", "unconf", "active", "old", "mt05-7")
            if f">{u}</a>" in html
        ]

    def test_filter_lists_only_requests_waiting_for_a_decision(self):
        self.assertEqual(self._usernames("?account_request=review"), ["pending"])
        self.assertEqual(
            self._usernames("?account_request=unconfirmed"), ["unconf", "old"]
        )

    def _reject(self, users, **extra):
        return self.client.post(
            self.url,
            {
                "action": "reject_accounts",
                "_selected_action": [u.pk for u in users],
                **extra,
            },
        )

    def test_reject_asks_for_a_reason_first(self):
        r = self._reject([self.pending])
        self.assertContains(r, "Reason")
        self.assertTrue(get_user_model().objects.filter(pk=self.pending.pk).exists())

    def test_reject_deletes_the_request_and_mails_the_reason(self):
        r = self._reject(
            [self.pending, self.active, self.old],
            apply="1",
            reason="Use your institutional address",
        )
        self.assertEqual(r.status_code, 302)
        users = get_user_model().objects
        self.assertFalse(users.filter(pk=self.pending.pk).exists())
        # an active account and an account that already logged in are never deleted
        self.assertTrue(users.filter(pk=self.active.pk).exists())
        self.assertTrue(users.filter(pk=self.old.pk).exists())
        self.assertEqual([m.to for m in self.mail.outbox], [["p@igbmc.fr"]])
        self.assertIn("Use your institutional address", self.mail.outbox[0].body)


@override_settings(CACHES=LOCMEM)
class PendingLoginStatusTests(FreshCache, TestCase):
    """The owner of a pending account sees where the request stands; nobody else learns more."""

    def setUp(self):
        super().setUp()
        from allauth.account.models import EmailAddress

        User = get_user_model()
        self.review = User.objects.create_user(
            "review", email="r@igbmc.fr", password="Zx9!tr0ng", is_active=False
        )
        EmailAddress.objects.create(
            user=self.review, email="r@igbmc.fr", verified=True, primary=True
        )
        self.unconfirmed = User.objects.create_user(
            "unconf", email="u@igbmc.fr", password="Zx9!tr0ng", is_active=False
        )
        User.objects.create_user("live", email="l@igbmc.fr", password="Zx9!tr0ng")

    def _login(self, username, password="Zx9!tr0ng"):
        r = APIClient().post(
            "/auth/jwt/create/",
            {"username": username, "password": password},
            format="json",
        )
        return r.status_code, r.json()

    def test_states_are_shown_with_the_right_password(self):
        code, body = self._login("review")
        self.assertEqual((code, body["account_status"]), (401, "awaiting_review"))
        code, body = self._login("unconf")
        self.assertEqual(body["account_status"], "awaiting_email_confirmation")

    def test_nothing_more_is_revealed_without_the_password(self):
        generic = "No active account found with the given credentials"
        for username, password in (
            ("review", "wrong"),
            ("unconf", "wrong"),
            ("live", "wrong"),
            ("nobody", "whatever"),
        ):
            with self.subTest(username=username):
                code, body = self._login(username, password)
                self.assertEqual(code, 401)
                self.assertEqual(body["detail"], generic)
                self.assertNotIn("account_status", body)

    def test_active_account_still_logs_in(self):
        code, body = self._login("live")
        self.assertEqual(code, 200)
        self.assertIn("access", body)


@override_settings(CACHES=LOCMEM)
class OrcidProofExpiryTests(FreshCache, TestCase):
    def test_expired_proof_is_refused_at_registration(self):
        import time
        from unittest import mock

        from mousetube_api.utils.orcid_proof import MAX_AGE, make_orcid_proof

        proof = make_orcid_proof("0000-0002-1825-0097")
        body = {
            "username": "late",
            "email": "late@igbmc.fr",
            "password": "Zx9!tr0ngPassw0rd#",
            "orcid_proof": proof,
        }
        with mock.patch(
            "django.core.signing.time.time", return_value=time.time() + MAX_AGE + 5
        ):
            r = APIClient().post("/auth/users/", body, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("orcid_proof", r.json())
        # still valid inside the window
        self.assertEqual(
            APIClient().post("/auth/users/", body, format="json").status_code, 201
        )


class OrcidLoginRedirectTests(TestCase):
    """ORCID login of an account that is not active yet must not hand out a token."""

    def _redirect(self, user):
        from allauth.core.exceptions import ImmediateHttpResponse
        from django.test import RequestFactory

        from mousetube_api.utils.adapters import MySocialAccountAdapter

        request = RequestFactory().get("/")
        request.session = {}
        sociallogin = SimpleNamespace(
            account=SimpleNamespace(
                provider="orcid",
                uid=user.user_profile.orcid,
                extra_data={},
            )
        )
        with self.assertRaises(ImmediateHttpResponse) as caught:
            MySocialAccountAdapter().pre_social_login(request, sociallogin)
        return caught.exception.response.url

    def _user(self, **kwargs):
        user = get_user_model().objects.create_user(
            "orcid_user", email="o@igbmc.fr", **kwargs
        )
        user.user_profile.orcid = "0000-0002-1825-0097"
        user.user_profile.save()
        return user

    def test_pending_account_is_sent_back_to_login_with_its_status(self):
        url = self._redirect(self._user(is_active=False))
        self.assertIn("/account/login?account_status=awaiting_email_confirmation", url)
        self.assertNotIn("token", url)

    def test_active_account_gets_a_token_in_the_fragment(self):
        url = self._redirect(self._user())
        self.assertIn("/auth/callback#token=", url)


# ----------------------------------------------------------------------------
# Datasets: import of the 0.5 metadata, public metadata route, admin-only form
# ----------------------------------------------------------------------------
@override_settings(CACHES=LOCMEM)
class DatasetMetadataTests(FreshCache, TestCase):
    sample = None

    @classmethod
    def setUpTestData(cls):
        import json
        from pathlib import Path

        cls.payload = json.loads(
            (Path(__file__).parent / "data" / "dataset_0_5_sample.json").read_text()
        )
        cls.admin = get_user_model().objects.create_superuser("adm", "a@igbmc.fr", "x")
        cls.user = get_user_model().objects.create_user("usr", "u@igbmc.fr", "x")

    def _import(self, payload=None):
        from mousetube_api.utils.dataset_metadata import import_datasets

        return import_datasets(payload or self.payload, self.admin)

    def test_import_creates_both_datasets_with_their_own_names(self):
        from mousetube_api.models import Dataset, File

        stats = self._import()
        self.assertEqual(stats["Dataset"]["created"], 2)
        # the production quirk: metadata of "Rat dataset" is named "Mouse dataset"
        self.assertEqual(
            sorted(Dataset.objects.values_list("name", flat=True)),
            ["Mouse dataset", "Rat dataset"],
        )
        self.assertEqual(RecordingSession.objects.count(), 4)
        self.assertEqual(File.objects.count(), 4)
        f = File.objects.first()
        self.assertTrue(f.doi.startswith("10.5281/zenodo"))
        self.assertEqual(f.repository.name, "Zenodo")

    def test_search_finds_a_dataset_by_its_files_and_does_not_repeat_it(self):
        from mousetube_api.models import File

        self._import()
        name = File.objects.first().name
        dataset = (
            File.objects.first().recording_session.dataset_recording_sessions.get()
        )
        found = self.client.get("/api/dataset/", {"search": name}).json()["results"]
        self.assertEqual([d["id"] for d in found], [dataset.id])
        self.assertEqual(
            self.client.get("/api/dataset/", {"search": "zzzz"}).json()["count"], 0
        )

    def test_file_and_software_search_do_not_crash_and_match_words(self):
        from mousetube_api.models import File, Software

        self._import()
        f = File.objects.first()
        # a pasted file name finds the file, words are looked up one by one
        for query in (f.name, f.name.split(".")[0], f"{f.name[:6]} {f.doi[:4]}"):
            response = self.client.get("/api/file/", {"search": query})
            self.assertEqual(response.status_code, 200, query)
            self.assertIn(f.id, [r["id"] for r in response.json()["results"]], query)
        self.assertEqual(
            self.client.get("/api/file/", {"search": f"{f.name} zzzz"}).json()["count"],
            0,
        )
        Software.objects.create(name="Zorbtool Analyser", status="validated")
        for query, count in (
            ("Zorbtool Analyser", 1),
            ("analyser zorbtool", 1),
            ("zzzz", 0),
        ):
            response = self.client.get("/api/software/", {"search": query})
            self.assertEqual(response.status_code, 200, query)
            self.assertEqual(response.json()["count"], count, query)

    def test_no_list_or_detail_route_crashes_for_a_visitor_or_a_user(self):
        """Fields left over from 0.5 used to give 500 errors (search, anonymous detail)."""
        from rest_framework.test import APIClient

        from mousetube_api.models import Software, SoftwareVersion
        from mousetube_api.urls import router

        self._import()
        software = Software.objects.first()
        software.status = "validated"
        software.save()
        SoftwareVersion.objects.get_or_create(software=software, version="1.0")
        routes = {prefix for prefix, *_ in router.registry} | {
            "repository",
            "reference",
            "hardware",
            "file",
            "country",
        }
        clients = {"visitor": APIClient()}
        clients["user"] = APIClient()
        clients["user"].force_authenticate(self.admin)
        for who, client in clients.items():
            for route in sorted(routes):
                for query in ("", "?search=x", "?search=two words", "?filter=x"):
                    response = client.get(f"/api/{route}/{query}")
                    self.assertLess(response.status_code, 500, (who, route, query))
                    data = response.json() if response.status_code == 200 else {}
                    results = data.get("results") if isinstance(data, dict) else data
                    if (
                        query == ""
                        and isinstance(results, list)
                        and results
                        and isinstance(results[0], dict)
                    ):
                        pk = results[0].get("id")
                        if pk:
                            detail = client.get(f"/api/{route}/{pk}/")
                            self.assertLess(
                                detail.status_code, 500, (who, route, "detail")
                            )

    def test_author_email_and_role_are_not_public(self):
        from rest_framework.test import APIClient

        from mousetube_api.models import File

        self._import()
        f = File.objects.first()
        author = f.recording_session.created_by
        author.email = "someone@igbmc.fr"
        author.save()
        other = get_user_model().objects.create_user("other", "o@igbmc.fr", "x")

        def created_by(client):
            result = client.get("/api/file/", {"search": f.name}).json()["results"][0]
            return result["recording_session"]["created_by"]

        visitor = APIClient()
        seen = created_by(visitor)
        self.assertEqual(seen["username"], author.username)  # the name stays public
        self.assertNotIn("email", seen)
        self.assertNotIn("is_staff", seen)
        client = APIClient()
        client.force_authenticate(other)
        self.assertNotIn(
            "email", created_by(client)
        )  # another user does not see it either
        # the website reads the e-mail and the role of the signed-in user from here
        client.force_authenticate(author)
        me = client.get("/auth/users/me/").json()
        self.assertEqual(me["email"], "someone@igbmc.fr")
        self.assertIn("is_staff", me)
        # the account page reads it from the profile list
        mine = client.get("/api/user_profile/", {"user_id": author.id}).json()
        self.assertEqual(mine[0]["user"]["email"], "someone@igbmc.fr")

        # hidden by default, the author can choose to show it, nobody else can choose for him
        profile = author.user_profile
        self.assertFalse(profile.email_public)
        self.assertEqual(mine[0]["email_public"], False)
        other_client = APIClient()
        other_client.force_authenticate(other)
        self.assertEqual(
            other_client.patch(
                f"/api/user_profile/{profile.id}/", {"email_public": True}
            ).status_code,
            403,
        )
        self.assertEqual(
            client.patch(
                f"/api/user_profile/{profile.id}/", {"email_public": True}
            ).status_code,
            200,
        )
        self.assertEqual(created_by(visitor)["email"], "someone@igbmc.fr")
        self.assertNotIn("is_staff", created_by(visitor))  # the role stays private
        client.patch(f"/api/user_profile/{profile.id}/", {"email_public": False})
        self.assertNotIn("email", created_by(visitor))

    def test_import_twice_creates_nothing_new(self):
        from mousetube_api.models import File

        self._import()
        again = self._import()
        self.assertEqual(again["Dataset"]["created"], 0)
        self.assertEqual(again["RecordingSession"]["created"], 0)
        self.assertEqual(again["File"]["created"], 0)
        self.assertEqual(File.objects.count(), 4)

    def test_dry_run_changes_nothing(self):
        from mousetube_api.models import Dataset
        from mousetube_api.utils.dataset_metadata import import_datasets

        import_datasets(self.payload, self.admin, dry_run=True)
        self.assertEqual(Dataset.objects.count(), 0)

    def test_metadata_route_is_public_and_has_no_emails(self):
        from mousetube_api.models import Dataset

        self._import()
        ds = Dataset.objects.get(name="Mouse dataset")
        r = APIClient().get(f"/api/dataset/{ds.id}/metadata/")
        self.assertEqual(r.status_code, 200)
        body = r.json()["dataset"]
        self.assertEqual(body["name"], "Mouse dataset")
        self.assertEqual(len(body["recording_session_list"]), 2)
        session = body["recording_session_list"][0]
        self.assertTrue(session["file_list"][0]["doi"].startswith("10.5281/zenodo"))
        self.assertNotIn("@", r.content.decode())  # no contact e-mail
        all_ = APIClient().get("/api/dataset/metadata/").json()["datasets"]
        self.assertEqual([d["name"] for d in all_], ["Mouse dataset", "Rat dataset"])

    def test_export_then_import_gives_the_same_dataset(self):
        from mousetube_api.models import Dataset, File

        self._import()
        ds = Dataset.objects.get(name="Mouse dataset")
        exported = APIClient().get(f"/api/dataset/{ds.id}/metadata/").json()
        first = exported["dataset"]["recording_session_list"][0]
        Dataset.objects.all().delete()
        RecordingSession.objects.all().delete()
        File.objects.all().delete()
        self._import(exported)
        again = Dataset.objects.get(name="Mouse dataset")
        self.assertEqual(
            APIClient()
            .get(f"/api/dataset/{again.id}/metadata/")
            .json()["dataset"]["recording_session_list"][0]["file_list"][0]["doi"],
            first["file_list"][0]["doi"],
        )

    def test_only_admins_create_datasets_and_list_session_choices(self):
        self._import()
        ids = list(RecordingSession.objects.values_list("id", flat=True)[:2])
        body = {"name": "Mine", "description": "d", "recording_session_ids": ids}
        anon, usr, adm = APIClient(), APIClient(), APIClient()
        usr.force_authenticate(self.user)
        adm.force_authenticate(self.admin)
        self.assertEqual(
            anon.post("/api/dataset/", body, format="json").status_code, 401
        )
        self.assertEqual(
            usr.post("/api/dataset/", body, format="json").status_code, 403
        )
        r = adm.post("/api/dataset/", body, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(len(r.json()["recording_sessions"]), 2)
        self.assertEqual(usr.get("/api/dataset/session-choices/").status_code, 403)
        choices = adm.get("/api/dataset/session-choices/?search=").json()
        self.assertEqual(len(choices), 4)
        self.assertIn("files_count", choices[0])

    def test_django_admin_dataset_form_renders_for_a_superuser(self):
        self.client.force_login(self.admin)
        self.assertEqual(
            self.client.get("/admin/mousetube_api/dataset/add/").status_code, 200
        )
        self.assertEqual(
            self.client.get("/admin/mousetube_api/dataset/").status_code, 200
        )


PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00"
    b"\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xf8\xff\xff?\x00\x05\xfe\x02\xfe\xa7"
    b"5\x81\x84\x00\x00\x00\x00IEND\xaeB`\x82"
)


class _Response:
    def __init__(self, status=200, content_type="image/png", content=PNG):
        self.status_code, self.content = status, content
        self.headers = {"content-type": content_type}


@override_settings(CACHES=LOCMEM)
class DatasetImagesAndChipsTests(FreshCache, TestCase):
    @classmethod
    def setUpTestData(cls):
        import json
        from pathlib import Path

        cls.payload = json.loads(
            (Path(__file__).parent / "data" / "dataset_0_5_sample.json").read_text()
        )
        cls.admin = get_user_model().objects.create_superuser("adm", "a@igbmc.fr", "x")

    def setUp(self):
        super().setUp()
        import shutil
        import tempfile

        self.media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.media, True)

    def _import(self, **kwargs):
        from mousetube_api.utils.dataset_metadata import import_datasets

        with override_settings(MEDIA_ROOT=self.media):
            return import_datasets(self.payload, self.admin, **kwargs)

    def test_no_download_unless_asked(self):
        from unittest import mock

        from mousetube_api.models import File

        with mock.patch("mousetube_api.utils.dataset_metadata.requests.get") as get:
            self._import()
        get.assert_not_called()
        self.assertFalse(File.objects.exclude(spectrogram="").exclude(spectrogram=None))

    def test_images_are_copied_from_the_old_site_once(self):
        from unittest import mock

        from mousetube_api.models import File

        with mock.patch(
            "mousetube_api.utils.dataset_metadata.requests.get",
            return_value=_Response(),
        ) as get:
            stats = self._import(images_from="https://old.example")
            self.assertEqual(stats["Image"]["created"], 2 * File.objects.count())
            self.assertTrue(
                get.call_args_list[0].args[0].startswith("https://old.example/media/")
            )
            calls = get.call_count
            again = self._import(images_from="https://old.example")
        self.assertEqual(again["Image"]["created"], 0)
        self.assertEqual(get.call_count, calls)  # nothing downloaded twice
        f = File.objects.first()
        self.assertTrue(f.spectrogram.name.endswith(".png"))
        self.assertTrue(f.plot.name.endswith(".png"))

    def test_a_bad_image_is_counted_as_failed_not_fatal(self):
        from unittest import mock

        with mock.patch(
            "mousetube_api.utils.dataset_metadata.requests.get",
            return_value=_Response(status=404),
        ):
            stats = self._import(images_from="https://old.example")
        self.assertGreater(stats["Image (failed)"]["created"], 0)
        self.assertEqual(stats["Dataset"]["created"], 2)

    def test_dataset_api_gives_chips_and_downloads_for_each_file(self):
        self._import()
        body = APIClient().get("/api/dataset/").json()
        mouse = next(d for d in body["results"] if d["name"] == "Mouse dataset")
        first = mouse["files"][0]
        self.assertIn("downloads", first)
        self.assertIn("pup", first["session"]["chips"])
        self.assertNotIn("unspecified", first["session"]["chips"])
        self.assertTrue(first["session"]["animal_profiles"])


@override_settings(CACHES=LOCMEM)
class CreationPipelineTests(FreshCache, TestCase):
    """Creating a vocalization: session, protocol, animal profile, file."""

    def setUp(self):
        super().setUp()
        from mousetube_api.models import AnimalProfile, Species, Strain

        User = get_user_model()
        self.alice = User.objects.create_user("alice", "a@igbmc.fr", "x")
        self.bob = User.objects.create_user("bob", "b@igbmc.fr", "x")
        self.repository = Repository.objects.create(name="Zenodo")
        species = Species.objects.create(name="Mus musculus")
        strain = Strain.objects.create(
            name="C57BL/6J", background="C57BL", species=species, status="validated"
        )
        self.draft_profile = AnimalProfile.objects.create(
            name="draft profile",
            strain=strain,
            sex="male",
            genotype="+/+",
            status="draft",
            created_by=self.alice,
        )
        self.alice_client = self._client(self.alice)
        self.bob_client = self._client(self.bob)

    def _client(self, user):
        client = APIClient()
        client.force_authenticate(user)
        return client

    def _session(self, client=None, **extra):
        data = {"name": "S", "date": "2026-01-02T10:00:00Z", **extra}
        return (client or self.alice_client).post(
            "/api/recording-session/", data, format="json"
        )

    def test_private_drafts_of_others_cannot_be_used_or_read(self):
        from mousetube_api.models import Hardware

        mic = Hardware.objects.create(
            name="mic", type="microphone", status="draft", created_by=self.alice
        )
        response = self._session(
            self.bob_client,
            animal_profile_ids=[self.draft_profile.id],
        )
        self.assertEqual(response.status_code, 400)
        response = self._session(
            self.bob_client, equipment_acquisition_hardware_microphone_ids=[mic.id]
        )
        self.assertEqual(response.status_code, 400)
        # the owner can, and nobody else can read the draft profile
        self.assertEqual(
            self._session(animal_profile_ids=[self.draft_profile.id]).status_code, 201
        )
        url = f"/api/animalprofile/{self.draft_profile.id}/"
        self.assertEqual(self.bob_client.get(url).status_code, 404)
        self.assertEqual(APIClient().get(url).status_code, 404)

    def test_invalid_values_give_400_not_500(self):
        for extra in (
            {"equipment_channels": "quadraphonic"},
            {"equipment_sound_isolation": "xx"},
            {"context_temperature_value": "warm", "context_temperature_unit": "K"},
        ):
            response = self._session(**extra)
            self.assertEqual(response.status_code, 400, extra)
        self.assertEqual(RecordingSession.objects.count(), 0)  # nothing half created

    def test_files_only_in_ones_own_session_and_only_the_creator_changes_them(self):
        session_id = self._session().json()["id"]
        payload = {
            "recording_session_id": session_id,
            "name": "a.wav",
            "link": "https://zenodo.org/a.wav",
            "doi": "10.5281/zenodo.1",
        }
        # no repository sent: the default one (found by name) is used
        created = self.alice_client.post("/api/file/", payload, format="json")
        self.assertEqual(created.status_code, 201, created.content)
        self.assertEqual(created.json()["repository"]["name"], "Zenodo")
        file_id = created.json()["id"]

        intruder = self.bob_client.post(
            "/api/file/", {**payload, "name": "b.wav"}, format="json"
        )
        self.assertEqual(intruder.status_code, 403)
        self.assertEqual(
            self.bob_client.delete(f"/api/file/{file_id}/").status_code, 403
        )
        self.assertEqual(
            self.bob_client.put(
                f"/api/file/{file_id}/", payload, format="json"
            ).status_code,
            403,
        )
        self.assertEqual(
            self.alice_client.delete(f"/api/file/{file_id}/").status_code, 204
        )

    def test_files_of_a_draft_session_are_private_until_it_is_shared(self):
        session_id = self._session().json()["id"]
        self.alice_client.post(
            "/api/file/",
            {
                "recording_session_id": session_id,
                "name": "draft.wav",
                "link": "https://zenodo.org/d.wav",
                "doi": "10.5281/zenodo.2",
            },
            format="json",
        )

        def count(client):
            return client.get("/api/file/").json()["count"]

        self.assertEqual(count(APIClient()), 0)
        self.assertEqual(count(self.bob_client), 0)
        self.assertEqual(count(self.alice_client), 1)  # its owner sees it
        RecordingSession.objects.filter(pk=session_id).update(status="shared")
        self.assertEqual(count(APIClient()), 1)

    def test_catalog_records_are_only_changed_by_their_creator(self):
        from mousetube_api.models import Hardware, Species, Strain

        mic = self.alice_client.post(
            "/api/hardware/", {"name": "mic", "type": "microphone"}, format="json"
        )
        self.assertEqual(mic.status_code, 201, mic.content)
        # a draft is private: nobody else even sees it
        url = f"/api/hardware/{mic.json()['id']}/"
        self.assertEqual(self.bob_client.get(url).status_code, 404)
        self.assertEqual(APIClient().get(url).status_code, 404)
        # a published one is public but only its creator changes it
        Hardware.objects.update(status="validated")
        self.assertEqual(APIClient().get(url).status_code, 200)
        self.assertEqual(
            self.bob_client.patch(url, {"description": "x"}, format="json").status_code,
            403,
        )
        self.assertEqual(self.bob_client.delete(url).status_code, 403)
        # validated by an administrator: not even its creator changes it any more
        self.assertEqual(
            self.alice_client.patch(
                url, {"description": "ok"}, format="json"
            ).status_code,
            403,
        )
        admin_client = self._client(
            get_user_model().objects.create_superuser("root", "r@igbmc.fr", "x")
        )
        self.assertEqual(
            admin_client.patch(url, {"description": "ok"}, format="json").status_code,
            200,
        )
        # draft strains are private too
        strain = self.alice_client.post(
            "/api/strain/",
            {
                "name": "mine",
                "background": "b",
                "species_id": Species.objects.get().id,
            },
            format="json",
        )
        self.assertEqual(strain.status_code, 201, strain.content)
        self.assertEqual(
            APIClient().get(f"/api/strain/{strain.json()['id']}/").status_code, 404
        )
        self.assertEqual(Strain.objects.filter(name="mine").count(), 1)

    def test_the_client_cannot_choose_the_creator_and_studies_have_ordered_dates(self):
        from mousetube_api.models import Laboratory

        lab = self.alice_client.post(
            "/api/laboratory/",
            {"name": "L", "country": "FR", "created_by": self.bob.id},
            format="json",
        )
        self.assertEqual(lab.status_code, 201, lab.content)
        self.assertEqual(Laboratory.objects.get().created_by, self.alice)
        self.alice_client.patch(
            f"/api/laboratory/{lab.json()['id']}/",
            {"created_by": self.bob.id},
            format="json",
        )
        self.assertEqual(Laboratory.objects.get().created_by, self.alice)

        backwards = self.alice_client.post(
            "/api/study/",
            {"name": "S", "start_date": "2026-05-01", "end_date": "2026-01-01"},
            format="json",
        )
        self.assertEqual(backwards.status_code, 400)


@override_settings(CACHES=LOCMEM)
class ModerationTests(FreshCache, TestCase):
    """draft -> waiting validation -> validated, and the sessions that use the entries."""

    def setUp(self):
        super().setUp()
        from mousetube_api.models import Species, Strain

        User = get_user_model()
        self.alice = User.objects.create_user("alice", "a@igbmc.fr", "x")
        self.root = User.objects.create_superuser("root", "r@igbmc.fr", "x")
        self.client_a = self._client(self.alice)
        self.client_root = self._client(self.root)
        self.species = Species.objects.create(name="Mus musculus")
        self.strain = Strain.objects.create(
            name="B6", background="b", species=self.species, status="validated"
        )

    def _client(self, user):
        client = APIClient()
        client.force_authenticate(user)
        return client

    def _hardware(self, **extra):
        response = self.client_a.post(
            "/api/hardware/",
            {"name": "mic", "type": "microphone", **extra},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()["id"]

    def _session(self, **extra):
        response = self.client_a.post(
            "/api/recording-session/",
            {"name": "S", "date": "2026-01-02T10:00:00Z", **extra},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()

    # ---- the entries of the catalogs ------------------------------------------------
    def test_every_entry_starts_as_a_draft_and_the_owner_submits_it(self):
        from django.core import mail

        from mousetube_api.models import (
            AnimalProfile,
            Contact,
            Hardware,
            Laboratory,
            Reference,
            Software,
            Strain,
            Study,
        )

        models = {
            "software": Software,
            "hardware": Hardware,
            "contact": Contact,
            "laboratory": Laboratory,
            "reference": Reference,
            "study": Study,
            "strain": Strain,
            "animalprofile": AnimalProfile,
        }
        payloads = {
            "software": {"name": "S", "type": "analysis"},
            "hardware": {"name": "H", "type": "microphone"},
            "contact": {"last_name": "C", "email": "c@igbmc.fr", "country": "FR"},
            "laboratory": {"name": "L", "country": "FR"},
            "reference": {"name": "R"},
            "study": {"name": "St"},
            "strain": {"name": "Sn", "background": "b", "species_id": self.species.id},
            "animalprofile": {
                "name": "AP",
                "strain_id": self.strain.id,
                "sex": "male",
                "genotype": "+/+",
            },
        }
        for kind, payload in payloads.items():
            created = self.client_a.post(f"/api/{kind}/", payload, format="json")
            self.assertEqual(created.status_code, 201, (kind, created.content))
            self.assertEqual(created.json()["status"], "draft", kind)
            self.assertEqual(len(mail.outbox), 0, kind)  # nothing to review yet
            url = f"/api/{kind}/{created.json()['id']}/"
            # one spelling for everybody
            submit = self.client_a.patch(
                url, {"status": "waiting validation"}, format="json"
            )
            self.assertEqual(submit.status_code, 200, (kind, submit.content))
            self.assertEqual(submit.json()["status"], "waiting validation", kind)
            self.assertEqual(len(mail.outbox), 1, kind)
            self.assertIn("To review", mail.outbox[0].subject)
            mail.outbox.clear()
            wrong = self.client_a.patch(
                url, {"status": "waiting_validation"}, format="json"
            )
            self.assertEqual(wrong.status_code, 400, kind)
            self.assertEqual(
                self.client_a.patch(
                    url, {"status": "validated"}, format="json"
                ).status_code,
                400,
                kind,
            )
            # the administrator validates (in the admin); the owner cannot change it any more
            models[kind].objects.filter(pk=created.json()["id"]).update(
                status="validated"
            )
            self.assertEqual(
                self.client_a.patch(
                    url, {"status": "draft"}, format="json"
                ).status_code,
                403,
                kind,
            )
            mail.outbox.clear()

    def test_the_old_spelling_of_the_waiting_status_is_converted(self):
        from mousetube_api.models import Contact, Strain
        from mousetube_api.utils.data_upgrades import normalize_statuses

        contact = Contact.objects.create(
            last_name="C", email="c@igbmc.fr", created_by=self.alice
        )
        Contact.objects.filter(pk=contact.pk).update(status="waiting_validation")
        Strain.objects.filter(pk=self.strain.pk).update(status="waiting_validation")
        self.assertEqual(normalize_statuses(), 2)
        contact.refresh_from_db()
        self.strain.refresh_from_db()
        self.assertEqual(contact.status, "waiting validation")
        self.assertEqual(self.strain.status, "waiting validation")
        self.assertEqual(normalize_statuses(), 0)  # nothing left to do

    # ---- sessions -------------------------------------------------------------------
    def test_a_session_using_validated_entries_is_shared_at_once(self):
        hardware = self._hardware()
        from mousetube_api.models import Hardware

        Hardware.objects.filter(pk=hardware).update(status="validated")
        session = self._session(
            equipment_acquisition_hardware_microphone_ids=[hardware], status="shared"
        )
        self.assertEqual(session["status"], "shared")

    def test_a_session_using_new_entries_waits_for_a_review(self):
        from django.core import mail

        hardware = self._hardware()  # still a draft
        session = self._session(
            equipment_acquisition_hardware_microphone_ids=[hardware], status="shared"
        )
        self.assertEqual(session["status"], "waiting validation")
        self.assertEqual(len(mail.outbox), 1)
        # while it waits it is private and cannot be edited by its owner
        self.assertEqual(APIClient().get("/api/file/").json()["count"], 0)
        url = f"/api/recording-session/{session['id']}/"
        self.assertEqual(
            self.client_a.patch(url, {"description": "x"}, format="json").status_code,
            403,
        )
        self.assertEqual(self.client_a.delete(url).status_code, 403)
        # but he can withdraw his request
        withdrawn = self.client_a.patch(url, {"status": "draft"}, format="json")
        self.assertEqual(withdrawn.status_code, 200, withdrawn.content)
        self.assertEqual(withdrawn.json()["status"], "draft")

    def test_the_owner_is_told_what_a_waiting_session_still_needs(self):
        hardware = self._hardware()
        session = self._session(
            equipment_acquisition_hardware_microphone_ids=[hardware], status="shared"
        )
        self.assertEqual(
            [(e["kind"], e["name"]) for e in session["pending_entries"]],
            [("hardware", "mic")],
        )
        url = f"/api/recording-session/{session['id']}/"
        self.assertEqual(len(self.client_a.get(url).json()["pending_entries"]), 1)
        # nobody else gets that list, and a list of sessions does not compute it
        other = self._client(
            get_user_model().objects.create_user("o", "o@igbmc.fr", "x")
        )
        self.assertEqual(other.get(url).status_code, 404)  # a private session
        listing = self.client_a.get("/api/recording-session/").json()
        rows = listing["results"] if isinstance(listing, dict) else listing
        self.assertEqual(rows[0]["pending_entries"], [])

    def test_an_owner_cannot_publish_a_session_himself(self):
        response = self.client_a.post(
            "/api/recording-session/",
            {"name": "P", "date": "2026-01-02T10:00:00Z", "status": "published"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_the_administrator_validates_a_session_and_what_it_uses_in_one_go(self):
        from mousetube_api.models import Hardware, RecordingSession
        from mousetube_api.utils.moderation import (
            session_pending_entries,
            validate_session,
        )

        hardware = self._hardware()
        session_id = self._session(
            equipment_acquisition_hardware_microphone_ids=[hardware], status="shared"
        )["id"]
        session = RecordingSession.objects.get(pk=session_id)
        pending = session_pending_entries(session)
        self.assertEqual([kind for kind, _ in pending], ["hardware"])
        entries, session = validate_session(session)
        self.assertEqual(len(entries), 1)
        self.assertEqual(session.status, "shared")
        self.assertEqual(Hardware.objects.get(pk=hardware).status, "validated")
        self.assertEqual(session_pending_entries(session), [])

    def test_validating_the_last_entry_shares_the_waiting_session(self):
        from django.core import mail

        from mousetube_api.models import Hardware, RecordingSession
        from mousetube_api.utils.moderation import promote_ready_sessions

        hardware = self._hardware()
        session_id = self._session(
            equipment_acquisition_hardware_microphone_ids=[hardware], status="shared"
        )["id"]
        self.assertEqual(promote_ready_sessions(), [])  # still something to validate
        Hardware.objects.filter(pk=hardware).update(status="validated")
        mail.outbox.clear()
        self.assertEqual([s.pk for s in promote_ready_sessions()], [session_id])
        self.assertEqual(RecordingSession.objects.get(pk=session_id).status, "shared")
        self.assertEqual(len(mail.outbox), 1)  # its owner is told

    def test_a_repository_deposit_needs_a_shared_session(self):
        from unittest import mock

        session = self._session()
        repository = Repository.objects.create(name="Zenodo")
        with mock.patch("mousetube_api.views.publish_session_deposition") as task:
            task.delay.return_value = SimpleNamespace(id="t1")
            refused = self.client_a.post(
                "/api/file/publish_session/",
                {"recording_session_id": session["id"], "repository_id": repository.id},
                format="json",
            )
            self.assertEqual(refused.status_code, 409)
            task.delay.assert_not_called()
            RecordingSession.objects.filter(pk=session["id"]).update(status="shared")
            accepted = self.client_a.post(
                "/api/file/publish_session/",
                {"recording_session_id": session["id"], "repository_id": repository.id},
                format="json",
            )
            self.assertEqual(accepted.status_code, 202)

    # ---- the administrator's screens --------------------------------------------------
    def _admin(self):
        self.client.force_login(self.root)
        return self.client

    def test_the_dashboard_and_the_list_show_what_waits_for_a_decision(self):
        from mousetube_api.models import Hardware

        waiting = self._hardware()
        self.client_a.patch(
            f"/api/hardware/{waiting}/", {"status": "waiting validation"}, format="json"
        )
        Hardware.objects.create(
            name="other draft", type="speaker", created_by=self.alice
        )
        admin_client = self._admin()
        index = admin_client.get("/admin/").content.decode()
        self.assertIn("To review (1)", index)
        self.assertIn("1 waiting", index)
        listing = admin_client.get(
            "/admin/mousetube_api/hardware/?status__exact=waiting+validation"
        ).content.decode()
        self.assertIn("mic", listing)
        self.assertNotIn("other draft", listing)

    def test_the_administrator_validates_in_bulk_and_the_creator_is_told(self):
        from django.core import mail

        from mousetube_api.models import Hardware, RecordingSession

        hardware = self._hardware()
        session_id = self._session(
            equipment_acquisition_hardware_microphone_ids=[hardware], status="shared"
        )["id"]
        mail.outbox.clear()
        response = self._admin().post(
            "/admin/mousetube_api/hardware/",
            {"action": "validate_selected", "_selected_action": [hardware]},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Hardware.objects.get(pk=hardware).status, "validated")
        # the session that only waited for it is shared, and its owner heard about both
        self.assertEqual(RecordingSession.objects.get(pk=session_id).status, "shared")
        recipients = [m.to for m in mail.outbox]
        self.assertEqual(recipients, [["a@igbmc.fr"], ["a@igbmc.fr"]])

    def test_the_administrator_sends_back_with_a_reason(self):
        from django.core import mail

        from mousetube_api.models import Hardware

        hardware = self._hardware(status="waiting validation")
        mail.outbox.clear()
        data = {"action": "send_back_to_draft", "_selected_action": [hardware]}
        confirm_page = self._admin().post("/admin/mousetube_api/hardware/", data)
        self.assertContains(confirm_page, "Reason")  # first the confirmation page
        self.assertEqual(Hardware.objects.get(pk=hardware).status, "waiting validation")
        self.client.post(
            "/admin/mousetube_api/hardware/",
            {**data, "apply": "1", "reason": "Add the reference."},
            follow=True,
        )
        self.assertEqual(Hardware.objects.get(pk=hardware).status, "draft")
        self.assertIn("Add the reference.", mail.outbox[0].body)

    def test_a_session_is_reviewed_with_everything_it_uses(self):
        from mousetube_api.models import Hardware, RecordingSession

        hardware = self._hardware()
        session_id = self._session(
            equipment_acquisition_hardware_microphone_ids=[hardware], status="shared"
        )["id"]
        admin_client = self._admin()
        page = admin_client.get(
            f"/admin/mousetube_api/recordingsession/{session_id}/change/"
        ).content.decode()
        self.assertIn("Entries nobody validated yet", page)
        self.assertIn("hardware:", page)
        admin_client.post(
            "/admin/mousetube_api/recordingsession/",
            {"action": "validate_sessions", "_selected_action": [session_id]},
            follow=True,
        )
        self.assertEqual(RecordingSession.objects.get(pk=session_id).status, "shared")
        self.assertEqual(Hardware.objects.get(pk=hardware).status, "validated")


@override_settings(CACHES=LOCMEM)
class ProfilePageTests(FreshCache, TestCase):
    """The account page reads the profile: an account without one must still get it."""

    def test_an_account_without_a_profile_gets_one_on_first_use(self):
        from mousetube_api.models import UserProfile

        user = get_user_model().objects.create_user("old", "o@igbmc.fr", "x")
        UserProfile.objects.filter(
            user=user
        ).delete()  # created before profiles existed
        client = APIClient()
        client.force_authenticate(user)
        response = client.get("/api/user_profile/", {"user_id": user.id})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)
        self.assertEqual(response.json()[0]["user"]["username"], "old")
        self.assertEqual(UserProfile.objects.filter(user=user).count(), 1)

    def test_every_account_gets_a_profile_and_running_again_changes_nothing(self):
        from mousetube_api.models import UserProfile
        from mousetube_api.utils.data_upgrades import create_missing_profiles

        users = [
            get_user_model().objects.create_user(f"u{i}", f"u{i}@igbmc.fr", "x")
            for i in range(2)
        ]
        UserProfile.objects.all().delete()
        self.assertEqual(create_missing_profiles(), len(users))
        self.assertEqual(UserProfile.objects.count(), len(users))
        self.assertEqual(create_missing_profiles(), 0)


def _fake_vocabularies(url, params=None, **kwargs):
    """Stands for the EBI Ontology Lookup Service and the ROR registry."""
    params = params or {}

    class Reply:
        status_code = 200

        def __init__(self, payload):
            self.payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self.payload

    if "/ols4/api/search" in url:
        return Reply(
            {
                "response": {
                    "docs": [
                        {
                            "obo_id": "PATO:0000384",
                            "label": "male",
                            "ontology_name": "pato",
                            "iri": "http://purl.obolibrary.org/obo/PATO_0000384",
                        }
                    ]
                }
            }
        )
    if "/ols4/api/ontologies/" in url:
        terms = {
            "MmusDv:0000092": ("postnatal stage", "mmusdv"),
            "NBO:0000037": ("vocalization behavior", "nbo"),
            "CHEBI:27732": ("caffeine", "chebi"),
        }
        known = terms.get(params.get("obo_id"))
        if not known:
            return Reply({"_embedded": {"terms": []}})
        label, ontology = known
        return Reply(
            {
                "_embedded": {
                    "terms": [
                        {
                            "obo_id": params["obo_id"],
                            "label": label,
                            "ontology_name": ontology,
                            "iri": "http://purl.obolibrary.org/obo/"
                            + params["obo_id"].replace(":", "_"),
                            "is_obsolete": False,
                        }
                    ]
                }
            }
        )
    if "api.ror.org" in url:
        item = {
            "id": "https://ror.org/0015ws592",
            "names": [
                {"value": "IGBMC", "types": ["acronym"]},
                {
                    "value": "Institut de génétique et de biologie moléculaire et cellulaire",
                    "types": ["label", "ror_display"],
                },
            ],
            "locations": [
                {
                    "geonames_details": {
                        "name": "Illkirch-Graffenstaden",
                        "country_name": "France",
                    }
                }
            ],
        }
        if url.rstrip("/").endswith("organizations"):
            return Reply({"items": [item]})
        return Reply(item)
    raise AssertionError(f"unexpected call: {url}")


@override_settings(CACHES=LOCMEM)
class OntologyTests(FreshCache, TestCase):
    """Fields with a controlled vocabulary: search, check at the source, store."""

    PATCH = "mousetube_api.utils.ontologies.requests.get"

    def setUp(self):
        super().setUp()
        from mousetube_api.models import Species, Strain

        self.user = get_user_model().objects.create_user("onto", "o@igbmc.fr", "x")
        self.client_u = APIClient()
        self.client_u.force_authenticate(self.user)
        species = Species.objects.create(name="Mus musculus")
        self.strain = Strain.objects.create(
            name="B6", background="b", species=species, status="validated"
        )

    def _profile(self, **extra):
        return self.client_u.post(
            "/api/animalprofile/",
            {
                "name": "AP",
                "strain_id": self.strain.id,
                "sex": "male",
                "genotype": "+/+",
                **extra,
            },
            format="json",
        )

    def test_search_needs_a_signed_in_user_and_a_known_field(self):
        self.assertEqual(
            APIClient().get("/api/ontology/search/?field=sex&q=male").status_code, 401
        )
        self.assertEqual(
            self.client_u.get("/api/ontology/search/?field=nonsense&q=x").status_code,
            400,
        )
        self.assertEqual(
            self.client_u.get("/api/ontology/search/?q=x").status_code, 400
        )

    def test_search_gives_terms_and_is_cached(self):
        from unittest import mock

        with mock.patch(self.PATCH, side_effect=_fake_vocabularies) as get:
            first = self.client_u.get("/api/ontology/search/?field=sex&q=male")
            self.assertEqual(first.status_code, 200)
            self.assertEqual(first.json()["results"][0]["curie"], "PATO:0000384")
            self.assertEqual(first.json()["vocabulary"], "PATO")
            self.client_u.get("/api/ontology/search/?field=sex&q=male")
            self.assertEqual(
                get.call_count, 1
            )  # the second answer comes from the cache
            # fewer than two letters: nothing to ask
            self.assertEqual(
                self.client_u.get("/api/ontology/search/?field=sex&q=m").json()[
                    "results"
                ],
                [],
            )
            self.assertEqual(get.call_count, 1)

    def test_organizations_come_from_the_ror_registry(self):
        from unittest import mock

        with mock.patch(self.PATCH, side_effect=_fake_vocabularies):
            found = self.client_u.get(
                "/api/ontology/search/?field=organization&q=IGBMC"
            )
        term = found.json()["results"][0]
        self.assertEqual(term["curie"], "ROR:0015ws592")
        self.assertEqual(term["detail"], "Illkirch-Graffenstaden, France")

    def test_the_vocabulary_service_being_down_is_a_clear_error(self):
        from unittest import mock

        import requests

        with mock.patch(self.PATCH, side_effect=requests.ConnectionError("down")):
            response = self.client_u.get("/api/ontology/search/?field=sex&q=male")
        self.assertEqual(response.status_code, 502)

    def test_the_sex_term_is_filled_without_asking_anybody(self):
        from unittest import mock

        with mock.patch(self.PATCH, side_effect=AssertionError("no network call")):
            created = self._profile()
        self.assertEqual(created.status_code, 201, created.content)
        self.assertEqual(created.json()["sex_term"]["curie"], "PATO:0000384")
        self.assertEqual(created.json()["sex_term"]["label"], "male")

    def test_the_age_class_of_a_mouse_gets_its_developmental_stage(self):
        from unittest import mock

        expected = {
            "pup": "MmusDv:0000177",
            "juvenile": "MmusDv:0000178",
            "adult": "MmusDv:0000110",
        }
        with mock.patch(self.PATCH, side_effect=AssertionError("no network call")):
            for age, curie in expected.items():
                created = self._profile(age=age, name=f"AP {age}")
                self.assertEqual(created.status_code, 201, created.content)
                self.assertEqual(created.json()["age_term"]["curie"], curie)

            # the age changes: so does the stage
            profile = self._profile(age="pup", name="AP changing").json()
            changed = self.client_u.patch(
                f"/api/animalprofile/{profile['id']}/", {"age": "adult"}, format="json"
            )
            self.assertEqual(changed.json()["age_term"]["curie"], "MmusDv:0000110")

    def test_a_precise_stage_chosen_by_the_user_is_kept(self):
        from unittest import mock

        from mousetube_api.models import OntologyTerm

        OntologyTerm.objects.create(
            curie="MmusDv:0000151",
            label="6-week-old stage",
            ontology="mmusdv",
            iri="http://purl.obolibrary.org/obo/MmusDv_0000151",
        )
        with mock.patch(self.PATCH, side_effect=AssertionError("no network call")):
            created = self._profile(age="adult", age_term={"curie": "MmusDv:0000151"})
        self.assertEqual(created.json()["age_term"]["curie"], "MmusDv:0000151")

    def test_another_species_keeps_its_age_class_without_a_mouse_stage(self):
        from mousetube_api.models import Species, Strain

        rat = Strain.objects.create(
            name="Wistar",
            background="w",
            species=Species.objects.create(name="Rattus norvegicus"),
            status="validated",
        )
        created = self.client_u.post(
            "/api/animalprofile/",
            {
                "name": "rat",
                "strain_id": rat.id,
                "sex": "male",
                "age": "adult",
                "genotype": "+/+",
            },
            format="json",
        )
        self.assertEqual(created.status_code, 201, created.content)
        self.assertIsNone(created.json()["age_term"])

    def test_a_term_is_checked_at_its_source_then_stored_once(self):
        from unittest import mock

        from mousetube_api.models import OntologyTerm

        with mock.patch(self.PATCH, side_effect=_fake_vocabularies) as get:
            ok = self._profile(age_term={"curie": "MmusDv:0000092"})
            self.assertEqual(ok.status_code, 201, ok.content)
            self.assertEqual(ok.json()["age_term"]["label"], "postnatal stage")
            calls = get.call_count
            # the same term again: already known, no new call
            self._profile(name="AP2", age_term="MmusDv:0000092")
            self.assertEqual(get.call_count, calls)
        self.assertEqual(OntologyTerm.objects.filter(curie="MmusDv:0000092").count(), 1)

    def test_a_wrong_term_is_refused_with_a_400(self):
        from unittest import mock

        with mock.patch(self.PATCH, side_effect=_fake_vocabularies):
            # a term of another vocabulary
            wrong_vocabulary = self._profile(age_term={"curie": "PATO:0000384"})
            self.assertEqual(wrong_vocabulary.status_code, 400)
            self.assertIn("age_term", wrong_vocabulary.json())
            # not an identifier, or one that does not exist
            self.assertEqual(
                self._profile(age_term={"curie": "nonsense"}).status_code, 400
            )
            self.assertEqual(
                self._profile(age_term={"curie": "MmusDv:9999999"}).status_code, 400
            )
        import requests

        with mock.patch(self.PATCH, side_effect=requests.Timeout("slow")):
            self.assertEqual(
                self._profile(age_term={"curie": "MmusDv:0000092"}).status_code, 400
            )

    def test_a_session_has_behavior_terms_and_a_lab_has_its_organization(self):
        from unittest import mock

        with mock.patch(self.PATCH, side_effect=_fake_vocabularies):
            session = self.client_u.post(
                "/api/recording-session/",
                {
                    "name": "S",
                    "date": "2026-01-02T10:00:00Z",
                    "behavior_terms": [{"curie": "NBO:0000037"}],
                },
                format="json",
            )
            self.assertEqual(session.status_code, 201, session.content)
            self.assertEqual(
                [t["label"] for t in session.json()["behavior_terms"]],
                ["vocalization behavior"],
            )
            lab = self.client_u.post(
                "/api/laboratory/",
                {
                    "name": "L",
                    "country": "FR",
                    "organization": {"curie": "ROR:0015ws592"},
                },
                format="json",
            )
            self.assertEqual(lab.status_code, 201, lab.content)
            self.assertEqual(
                lab.json()["organization"]["iri"], "https://ror.org/0015ws592"
            )
            # a term list must be a list
            bad = self.client_u.post(
                "/api/recording-session/",
                {
                    "name": "S2",
                    "date": "2026-01-02T10:00:00Z",
                    "behavior_terms": {"curie": "NBO:0000037"},
                },
                format="json",
            )
            self.assertEqual(bad.status_code, 400)

    def test_the_terms_of_a_session_reach_zenodo_and_the_dataset_export(self):
        from mousetube_api.models import OntologyTerm, RecordingSession
        from mousetube_api.utils import zenodo
        from mousetube_api.utils.dataset_metadata import _session

        self._profile()  # male: sex_term is set without any network call
        from mousetube_api.models import AnimalProfile

        profile = AnimalProfile.objects.get()
        behavior = OntologyTerm.objects.create(
            curie="NBO:0000001",
            label="grooming",
            ontology="nbo",
            iri="http://purl.obolibrary.org/obo/NBO_0000001",
        )
        session = RecordingSession.objects.create(
            name="s", is_multiple=True, created_by=self.user
        )
        session.animal_profiles.add(profile)
        session.behavior_terms.add(behavior)

        files = [SimpleNamespace(created_by=None)]
        payload = zenodo.build_metadata_payload(session, files)
        subjects = {s["term"]: s["identifier"] for s in payload["subjects"]}
        self.assertEqual(
            subjects["male"], "http://purl.obolibrary.org/obo/PATO_0000384"
        )
        self.assertEqual(subjects["grooming"], behavior.iri)
        self.assertIn(
            '<a href="http://purl.obolibrary.org/obo/PATO_0000384">male</a>',
            payload["description"],
        )

        exported = _session(session)
        self.assertEqual(
            exported["animal_profiles"][0]["sex_term"]["curie"], "PATO:0000384"
        )
        self.assertEqual(exported["behavior_terms"][0]["label"], "grooming")

    def test_units_and_known_terms_are_documented(self):
        from mousetube_api.utils.ontologies import UNITS

        self.assertEqual(UNITS["sampling_rate"]["curie"], "UO:0000106")
        self.assertEqual(UNITS["duration"]["curie"], "UO:0000010")


@override_settings(CACHES=LOCMEM)
class OwnAccountTests(FreshCache, TestCase):
    """What a user can change on his own account."""

    def test_a_user_changes_his_name_but_never_his_role_or_login(self):
        user = get_user_model().objects.create_user("plain", "p@igbmc.fr", "x")
        client = APIClient()
        client.force_authenticate(user)
        for forbidden in (
            {"is_staff": True},
            {"is_superuser": True},
            {"is_active": False},
            {"username": "renamed"},
            {"email": "other@igbmc.fr"},
        ):
            client.patch("/auth/users/me/", forbidden, format="json")
        user.refresh_from_db()
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertTrue(user.is_active)
        self.assertEqual(user.username, "plain")
        self.assertEqual(user.email, "p@igbmc.fr")

        response = client.patch(
            "/auth/users/me/",
            {"first_name": "Ada", "last_name": "Lovelace"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        user.refresh_from_db()
        self.assertEqual((user.first_name, user.last_name), ("Ada", "Lovelace"))

    def test_the_profile_flag_administrator_is_not_set_by_its_owner(self):
        from mousetube_api.models import UserProfile

        user = get_user_model().objects.create_user("plain", "p@igbmc.fr", "x")
        profile = UserProfile.objects.get(user=user)
        client = APIClient()
        client.force_authenticate(user)
        client.patch(
            f"/api/user_profile/{profile.id}/", {"administrator": True}, format="json"
        )
        profile.refresh_from_db()
        self.assertFalse(profile.administrator)


class DataUpgradeCommandTests(TestCase):
    """manage.py normalize_data runs after migrate: it converts what a change of structure
    leaves behind and is safe to run every time."""

    def test_species_and_sex_get_their_terms_without_any_network_call(self):
        from io import StringIO
        from unittest import mock

        from django.core.management import call_command

        from mousetube_api.models import AnimalProfile, Species, Strain

        species = Species.objects.create(name="Mus musculus")
        strain = Strain.objects.create(
            name="B6", background="b", species=species, status="validated"
        )
        profile = AnimalProfile.objects.create(
            name="AP", strain=strain, sex="female", genotype="+/+", age="adult"
        )
        profile_stage = "MmusDv:0000110"
        with mock.patch(
            "mousetube_api.utils.ontologies.requests.get",
            side_effect=AssertionError("no network call"),
        ):
            out = StringIO()
            call_command("normalize_data", stdout=out)
            self.assertIn("terms linked: 3", out.getvalue())  # species, sex, stage
            species.refresh_from_db()
            profile.refresh_from_db()
            self.assertEqual(species.ontology_term.curie, "NCBITaxon:10090")
            self.assertEqual(profile.sex_term.curie, "PATO:0000383")
            self.assertEqual(profile.age_term.curie, profile_stage)
            again = StringIO()
            call_command("normalize_data", stdout=again)
            self.assertIn("terms linked: 0", again.getvalue())


@override_settings(CACHES=LOCMEM, ZENODO_TOKEN="t")
class UploadCleanupTests(FreshCache, TestCase):
    """An upload must never leave a file on the server when something goes wrong."""

    def setUp(self):
        super().setUp()
        import os

        self.media = tempfile.mkdtemp()
        self.temp = os.path.join(self.media, "temp")
        os.makedirs(self.temp)
        override = override_settings(MEDIA_ROOT=self.media)
        override.enable()
        self.addCleanup(override.disable)
        self.user = get_user_model().objects.create_user("up", "up@igbmc.fr", "x")
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.repository = Repository.objects.create(name="Zenodo")

    def _upload(self, name="a.csv", content=b"a,b\n1,2\n"):
        from django.core.files.uploadedfile import SimpleUploadedFile

        return self.client.post(
            "/api/file/upload_async/",
            {"file": SimpleUploadedFile(name, content)},
            format="multipart",
        )

    def _stored(self):
        import os

        return os.listdir(self.temp)

    def _file_in_temp(self, name="b.csv", content=b"a,b\n1,2\n"):
        import os

        from mousetube_api.models import File

        with open(os.path.join(self.temp, name), "wb") as out:
            out.write(content)
        session = RecordingSession.objects.create(
            name="s", is_multiple=True, created_by=self.user
        )
        return File.objects.create(
            name=name,
            link=f"/media/temp/{name}",
            repository=self.repository,
            recording_session=session,
            created_by=self.user,
        )

    def test_a_valid_upload_is_stored_in_temp(self):
        self.assertEqual(self._upload().status_code, 200)
        self.assertEqual(len(self._stored()), 1)

    @override_settings(MAX_UPLOAD_SIZE=5)
    def test_too_large_is_refused_and_nothing_is_stored(self):
        self.assertEqual(self._upload().status_code, 413)
        self.assertEqual(self._stored(), [])

    def test_unsupported_type_is_refused_and_nothing_is_stored(self):
        self.assertEqual(self._upload("virus.exe").status_code, 400)
        self.assertEqual(self._stored(), [])

    def test_old_uploads_are_purged_and_recent_ones_kept(self):
        import os
        import time

        from mousetube_api.utils.file_handler import purge_temp_files

        old = os.path.join(self.temp, "old.wav")
        new = os.path.join(self.temp, "new.wav")
        for path in (old, new):
            open(path, "wb").close()
        past = time.time() - 3 * 24 * 3600
        os.utime(old, (past, past))
        self.assertEqual(purge_temp_files(), 1)
        self.assertEqual(self._stored(), ["new.wav"])

    def test_the_next_upload_purges_the_abandoned_ones(self):
        import os
        import time

        old = os.path.join(self.temp, "abandoned.wav")
        open(old, "wb").close()
        past = time.time() - 3 * 24 * 3600
        os.utime(old, (past, past))
        self._upload()
        self.assertNotIn("abandoned.wav", self._stored())

    def test_a_file_that_cannot_be_read_does_not_stay_on_the_server(self):
        from mousetube_api.tasks import process_file

        f = self._file_in_temp("broken.wav", b"this is not audio")
        with self.assertRaises(ValidationError):
            process_file(f.id, self.repository.id)
        f.refresh_from_db()
        self.assertEqual(f.status, "error")
        self.assertEqual(self._stored(), [])

    def _zenodo(self, put):
        from unittest import mock

        created = mock.Mock(**{"json.return_value": {"id": 7}})
        deposition = mock.Mock(
            **{"json.return_value": {"links": {"bucket": "https://z.test/files/b"}}}
        )
        return (
            mock.patch(
                "mousetube_api.utils.zenodo.requests.post", return_value=created
            ),
            mock.patch(
                "mousetube_api.utils.zenodo.requests.get", return_value=deposition
            ),
            mock.patch("mousetube_api.utils.zenodo.requests.put", side_effect=put),
        )

    def test_a_failed_zenodo_upload_fails_the_task_and_says_why(self):
        import requests

        from mousetube_api.tasks import process_file
        from mousetube_api.utils.file_handler import UploadError

        def put(*args, **kwargs):
            raise requests.ConnectionError("down https://z.test/?access_token=SECRET")

        f = self._file_in_temp()
        post, get, put_patch = self._zenodo(put)
        with post, get, put_patch, self.assertRaises(UploadError):
            process_file(f.id, self.repository.id)
        f.refresh_from_db()
        self.assertEqual(f.status, "error")  # used to end as "done"
        self.assertIn("did not answer", f.error_message)
        self.assertNotIn("SECRET", f.error_message)
        self.assertEqual(self._stored(), [])

    def test_the_file_is_streamed_with_its_progress_and_the_upload_removed(self):
        from unittest import mock

        from mousetube_api.tasks import process_file
        from mousetube_api.utils.file_handler import get_progress

        seen = {}

        def put(url, data=None, **kwargs):
            if hasattr(data, "read"):  # the file, not the metadata
                seen["length"] = len(data)
                seen["url"] = url
                while data.read(4):
                    pass
            return mock.Mock()

        f = self._file_in_temp()
        post, get, put_patch = self._zenodo(put)
        with post, get, put_patch:
            process_file(f.id, self.repository.id)
        f.refresh_from_db()
        self.assertEqual(f.status, "done")
        self.assertEqual(f.external_id, "7")
        self.assertEqual(seen["length"], len(b"a,b\n1,2\n"))
        self.assertEqual(seen["url"], "https://z.test/files/b/b.csv")
        self.assertEqual(get_progress(f.id), 100)
        self.assertEqual(self._stored(), [])

    def test_the_status_endpoint_gives_progress_and_the_readable_error(self):
        from mousetube_api.utils.file_handler import set_progress

        f = self._file_in_temp()
        f.celery_task_id = "none"
        f.status = "processing"
        f.save()
        set_progress(f.id, 42)
        data = self.client.get(f"/api/file/{f.id}/status/").json()
        self.assertEqual(data["progress"], 42)
        f.status, f.error_message = "error", "The repository is busy."
        f.save()
        self.assertEqual(
            self.client.get(f"/api/file/{f.id}/status/").json()["error_message"],
            "The repository is busy.",
        )

    def test_error_messages_never_carry_urls_or_tokens(self):
        import requests

        from mousetube_api.utils.file_handler import explain

        response = SimpleNamespace(status_code=403, text="token=SECRET")
        text = explain(
            requests.HTTPError(
                "403 for https://z/?access_token=SECRET", response=response
            )
        )
        self.assertIn("credentials", text)
        self.assertNotIn("SECRET", text)
        self.assertNotIn(
            "https", explain(RuntimeError("boom https://x?access_token=SECRET"))
        )

    def test_the_publish_error_written_for_the_user_reaches_everybody_else_stays_hidden(
        self,
    ):
        from unittest import mock

        from mousetube_api.utils.file_handler import UploadError

        for error, shown in (
            (UploadError("The repository is busy."), "The repository is busy."),
            (RuntimeError("https://z/?access_token=SECRET"), None),
        ):
            result = mock.Mock(state="FAILURE", result=error, info=None)
            result.failed.return_value = True
            result.successful.return_value = False
            with mock.patch("mousetube_api.views.AsyncResult", return_value=result):
                data = self.client.get(
                    "/api/recording-session/get_task_status?task_id=x"
                )
            self.assertEqual(data.json()["error"], shown)


class LinkOntologyTermsCommandTests(TestCase):
    """Existing data is linked to vocabularies only when the match is certain."""

    def setUp(self):
        from mousetube_api.models import Laboratory, Species

        self.pasteur = Laboratory.objects.create(
            name="Genetics", institution="Institut Pasteur"
        )
        self.unknown = Laboratory.objects.create(name="London lab")
        self.species = Species.objects.create(name="Peromyscus maniculatus")

    def _run(self, *args):
        from io import StringIO
        from unittest import mock

        from django.core.management import call_command

        from mousetube_api.utils.ontologies import known_term

        cmd = "mousetube_api.management.commands.link_ontology_terms"
        organizations = {
            "Institut Pasteur, Genetics": {
                "curie": "ROR:0495fxg12",
                "label": "Institut Pasteur",
            }
        }
        with (
            mock.patch(
                f"{cmd}.match_organization", side_effect=lambda t: organizations.get(t)
            ),
            mock.patch(
                f"{cmd}.match_label",
                side_effect=lambda v, t: (
                    {"curie": "NCBITaxon:10042", "label": t} if v == "species" else None
                ),
            ),
            mock.patch(
                f"{cmd}.get_or_create_term",
                side_effect=lambda v, c: known_term(c, "x"),
            ),
        ):
            out = StringIO()
            call_command("link_ontology_terms", *args, stdout=out)
        return out.getvalue()

    def test_nothing_is_written_without_apply(self):
        output = self._run()
        self.pasteur.refresh_from_db()
        self.assertIsNone(self.pasteur.organization)
        self.assertIn("would be linked", output)

    def test_apply_links_what_is_certain_and_leaves_the_rest(self):
        self._run("--apply")
        for obj in (self.pasteur, self.unknown, self.species):
            obj.refresh_from_db()
        self.assertEqual(self.pasteur.organization.curie, "ROR:0495fxg12")
        self.assertIsNone(self.unknown.organization)
        self.assertEqual(self.species.ontology_term.curie, "NCBITaxon:10042")


@override_settings(CACHES=LOCMEM)
class FileFiltersAndDownloadsTests(FreshCache, TestCase):
    """The facets of the list of files, and the download counter."""

    def setUp(self):
        super().setUp()
        from mousetube_api.models import (
            AnimalProfile,
            File,
            Species,
            Strain,
        )

        self.owner = get_user_model().objects.create_user("o", "o@igbmc.fr", "x")
        self.repository = Repository.objects.create(name="Zenodo")

        def make(species, sex, age, fmt, status):
            sp, _ = Species.objects.get_or_create(name=species)
            strain, _ = Strain.objects.get_or_create(
                name=f"strain {species}",
                defaults={"background": "b", "species": sp, "status": "validated"},
            )
            profile = AnimalProfile.objects.create(
                name=f"p {species}{sex}{age}",
                strain=strain,
                sex=sex,
                age=age,
                genotype="+/+",
                status="validated",
            )
            session = RecordingSession.objects.create(
                name=f"s {species}{sex}{age}",
                is_multiple=True,
                status=status,
                created_by=self.owner,
            )
            session.animal_profiles.add(profile)
            return File.objects.create(
                name=f"{species}-{sex}-{age}.{fmt.lower()}",
                format=fmt,
                recording_session=session,
                repository=self.repository,
                created_by=self.owner,
            )

        self.mouse = make("Mus musculus", "male", "pup", "WAV", "shared")
        self.rat = make("Rattus norvegicus", "female", "adult", "MP3", "shared")
        self.secret = make("Mus musculus", "male", "adult", "WAV", "draft")
        self.client = APIClient()

    def _names(self, query):
        data = self.client.get(f"/api/file/?{query}").json()
        return {f["name"] for f in data["results"]}

    def test_species_sex_age_format_and_repository_narrow_the_list(self):
        both = {self.mouse.name, self.rat.name}
        self.assertEqual(self._names(""), both)
        self.assertEqual(self._names("species=Mus musculus"), {self.mouse.name})
        self.assertEqual(self._names("species=Rattus norvegicus"), {self.rat.name})
        self.assertEqual(self._names("sex=female"), {self.rat.name})
        self.assertEqual(self._names("age=pup"), {self.mouse.name})
        self.assertEqual(self._names("file_format=mp3"), {self.rat.name})
        self.assertEqual(self._names("repository=Zenodo"), both)
        self.assertEqual(self._names("repository=Figshare"), set())

    def test_values_of_one_facet_are_alternatives_and_facets_add_up(self):
        both = {self.mouse.name, self.rat.name}
        self.assertEqual(self._names("species=Mus musculus,Rattus norvegicus"), both)
        self.assertEqual(self._names("species=Mus musculus&sex=female"), set())

    def test_filters_never_reveal_a_draft(self):
        self.assertNotIn(self.secret.name, self._names("species=Mus musculus"))
        options = self.client.get("/api/file/filters/").json()
        self.assertEqual(options["species"], ["Mus musculus", "Rattus norvegicus"])
        self.assertEqual(options["format"], ["MP3", "WAV"])
        self.assertEqual(options["sex"], ["female", "male"])
        self.assertEqual(options["age"], ["adult", "pup"])
        self.assertEqual(options["repository"], ["Zenodo"])

    def test_a_visitor_download_is_counted_once_per_hour(self):
        url = f"/api/file/{self.mouse.pk}/download/"
        first = self.client.post(url).json()
        self.assertEqual((first["downloads"], first["counted"]), (1, True))
        again = self.client.post(url).json()
        self.assertEqual((again["downloads"], again["counted"]), (1, False))
        self.assertEqual(
            self.client.get(f"/api/file/{self.mouse.pk}/").json()["downloads"], 1
        )

    def test_a_draft_cannot_be_downloaded_by_a_visitor(self):
        self.assertEqual(
            self.client.post(f"/api/file/{self.secret.pk}/download/").status_code, 404
        )


@override_settings(CACHES=LOCMEM)
class CatalogFiltersTests(FreshCache, TestCase):
    """Software and hardware lists: type, used, documented, favorites, mine."""

    def setUp(self):
        super().setUp()
        from mousetube_api.models import (
            Favorite,
            Hardware,
            Reference,
            Software,
            SoftwareVersion,
        )

        User = get_user_model()
        self.me = User.objects.create_user("me", "me@igbmc.fr", "x")
        self.other = User.objects.create_user("other", "ot@igbmc.fr", "x")
        ref = Reference.objects.create(name="manual", status="validated")

        def hw(name, kind, **extra):
            return Hardware.objects.create(
                name=name, type=kind, status="validated", created_by=self.other, **extra
            )

        self.mic = hw("Mic", "microphone")
        self.card = hw("Card", "soundcard")
        self.mic.references.add(ref)
        session = RecordingSession.objects.create(
            name="s", is_multiple=True, status="shared", created_by=self.other
        )
        session.equipment_acquisition_hardware_microphones.add(self.mic)

        self.soft_used = Software.objects.create(
            name="Used", type="acquisition", status="validated", created_by=self.other
        )
        self.soft_doc = Software.objects.create(
            name="Documented", type="analysis", status="validated", created_by=self.me
        )
        self.soft_doc.references.add(ref)
        version = SoftwareVersion.objects.create(software=self.soft_used, version="1")
        session.equipment_acquisition_software.add(version)

        from django.contrib.contenttypes.models import ContentType

        Favorite.objects.create(
            user=self.me,
            content_type=ContentType.objects.get_for_model(Software),
            object_id=self.soft_used.pk,
        )
        self.client = APIClient()

    def _names(self, url, client=None):
        data = (client or self.client).get(url).json()
        return {item["name"] for item in data["results"]}

    def test_hardware_by_type_use_and_documentation(self):
        self.assertEqual(self._names("/api/hardware/"), {"Mic", "Card"})
        self.assertEqual(self._names("/api/hardware/?type=microphone"), {"Mic"})
        self.assertEqual(
            self._names("/api/hardware/?type=microphone,soundcard"), {"Mic", "Card"}
        )
        self.assertEqual(self._names("/api/hardware/?used=1"), {"Mic"})
        self.assertEqual(self._names("/api/hardware/?documented=1"), {"Mic"})
        self.assertEqual(
            self._names("/api/hardware/?documented=1&type=soundcard"), set()
        )

    def test_software_by_type_use_and_documentation(self):
        self.assertEqual(self._names("/api/software/?type=analysis"), {"Documented"})
        self.assertEqual(self._names("/api/software/?used=1"), {"Used"})
        self.assertEqual(self._names("/api/software/?documented=1"), {"Documented"})

    def test_use_only_counts_shared_sessions(self):
        from mousetube_api.models import RecordingSession

        RecordingSession.objects.update(status="draft")
        self.assertEqual(self._names("/api/hardware/?used=1"), set())

    def test_favorites_and_mine_need_an_account(self):
        self.assertEqual(
            self._names("/api/software/?favorites=1"), {"Used", "Documented"}
        )  # a visitor has none: the filter is ignored
        mine = APIClient()
        mine.force_authenticate(self.me)
        self.assertEqual(self._names("/api/software/?favorites=1", mine), {"Used"})
        self.assertEqual(self._names("/api/software/?mine=1", mine), {"Documented"})


@override_settings(CACHES=LOCMEM)
class MySessionsListTests(FreshCache, TestCase):
    """The list behind the "My vocalizations" tab: own sessions, with their files."""

    def setUp(self):
        super().setUp()
        from mousetube_api.models import File

        User = get_user_model()
        self.me = User.objects.create_user("me", "me@igbmc.fr", "x")
        self.other = User.objects.create_user("ot", "ot@igbmc.fr", "x")
        self.repository = Repository.objects.create(name="Zenodo")

        def session(name, owner, status):
            return RecordingSession.objects.create(
                name=name, is_multiple=True, status=status, created_by=owner
            )

        self.draft = session("draft one", self.me, "draft")
        self.published = session("published one", self.me, "shared")
        RecordingSession.objects.filter(pk=self.published.pk).update(status="published")
        session("not mine", self.other, "shared")
        File.objects.create(
            name="a.wav",
            recording_session=self.published,
            repository=self.repository,
            doi="10.5281/zenodo.1",
            created_by=self.me,
        )
        File.objects.create(
            name="b.wav", recording_session=self.published, created_by=self.me
        )
        self.client = APIClient()
        self.client.force_authenticate(self.me)

    def test_only_my_sessions_with_the_number_of_files_and_the_doi(self):
        data = self.client.get("/api/recording-session/?ordering=-modified_at").json()
        by_name = {s["name"]: s for s in data["results"]}
        self.assertEqual(set(by_name), {"draft one", "published one"})
        self.assertEqual(by_name["draft one"]["files_count"], 0)
        self.assertIsNone(by_name["draft one"]["doi"])
        self.assertEqual(by_name["published one"]["files_count"], 2)
        self.assertEqual(by_name["published one"]["doi"], "10.5281/zenodo.1")

    def test_the_list_can_be_sorted_from_a_to_z_and_back(self):
        names = lambda q: [
            s["name"]
            for s in self.client.get(f"/api/recording-session/?{q}").json()["results"]
        ]
        self.assertEqual(names("ordering=name"), ["draft one", "published one"])
        self.assertEqual(names("ordering=-name"), ["published one", "draft one"])

    def test_the_list_can_be_narrowed_by_status(self):
        data = self.client.get("/api/recording-session/?status=draft").json()
        self.assertEqual([s["name"] for s in data["results"]], ["draft one"])


@override_settings(CACHES=LOCMEM, ZENODO_TOKEN="t")
class PublishSessionTests(FreshCache, TestCase):
    """Publishing only concerns the files mouseTube sent and nobody published yet."""

    def setUp(self):
        super().setUp()
        from mousetube_api.models import File

        self.user = get_user_model().objects.create_user("pub", "pub@igbmc.fr", "x")
        self.repository = Repository.objects.create(name="Zenodo")
        self.session = RecordingSession.objects.create(
            name="imported", is_multiple=True, status="shared", created_by=self.user
        )
        File.objects.create(
            name="a.wav",
            recording_session=self.session,
            repository=self.repository,
            doi="10.5281/zenodo.1",
            external_id=20627872,
            created_by=self.user,
        )

    def _publish(self):
        from unittest import mock

        from mousetube_api.tasks import publish_session_deposition

        with (
            mock.patch.object(publish_session_deposition, "update_state"),
            mock.patch(
                "mousetube_api.utils.zenodo.requests.post",
                side_effect=AssertionError("nothing may be sent to the repository"),
            ),
        ):
            return publish_session_deposition(self.session.id, self.repository.id)

    def test_files_that_already_have_a_doi_are_not_sent_again(self):
        result = self._publish()
        self.assertEqual(result["progress"], 100)
        self.session.refresh_from_db()
        self.assertEqual(self.session.status, "published")

    def test_the_list_says_what_is_left_to_deposit(self):
        from mousetube_api.models import File

        client = APIClient()
        client.force_authenticate(self.user)

        def left():
            data = client.get("/api/recording-session/").json()
            return data["results"][0]["files_to_deposit"]

        self.assertEqual(left(), 0)
        File.objects.create(
            name="new.wav", recording_session=self.session, created_by=self.user
        )
        self.assertEqual(left(), 1)


class MergeImportedDuplicatesTests(TestCase):
    """A recording imported in a dataset and with its session is kept once."""

    def setUp(self):
        from mousetube_api.models import Dataset, File, Subject

        User = get_user_model()
        self.admin = User.objects.create_user("admin", "ad@igbmc.fr", "x")
        self.author = User.objects.create_user("mt05-4", "au@igbmc.fr", "x")

        def session(name, owner):
            return RecordingSession.objects.create(
                name=name, is_multiple=True, status="shared", created_by=owner
            )

        dataset_session = session("one file", self.admin)
        original_session = session("whole experiment", self.author)
        self.keep = File.objects.create(
            name="a.wav",
            recording_session=dataset_session,
            created_by=self.admin,
            downloads=5,
            duration=10,
        )
        self.drop = File.objects.create(
            name="a.wav",
            recording_session=original_session,
            created_by=self.author,
            downloads=9,
        )
        self.other = File.objects.create(
            name="b.wav", recording_session=original_session, created_by=self.author
        )
        self.subject = Subject.objects.create(name="animal 1")
        self.drop.subjects.add(self.subject)
        dataset = Dataset.objects.create(name="Mouse dataset", created_by=self.admin)
        dataset.recording_session_list.add(dataset_session)
        self.dataset_session = dataset_session

    def _run(self, *args):
        from io import StringIO

        from django.core.management import call_command

        out = StringIO()
        call_command("merge_imported_duplicates", *args, stdout=out)
        return out.getvalue()

    def test_nothing_changes_without_apply(self):
        from mousetube_api.models import File

        self.assertIn("would be merged", self._run())
        self.assertEqual(File.objects.filter(name="a.wav").count(), 2)

    def test_the_dataset_copy_is_kept_with_the_owner_and_the_animals_of_the_original(
        self,
    ):
        from mousetube_api.models import File

        self._run("--apply")
        copies = File.objects.filter(name="a.wav")
        self.assertEqual(copies.count(), 1)
        kept = copies.get()
        self.assertEqual(kept.pk, self.keep.pk)
        self.assertEqual(kept.duration, 10)  # what the dataset copy knew
        self.assertEqual(kept.downloads, 9)
        self.assertEqual(kept.created_by, self.author)
        self.assertEqual(list(kept.subjects.all()), [self.subject])
        self.dataset_session.refresh_from_db()
        self.assertEqual(self.dataset_session.created_by, self.author)
        # the rest of the original session is untouched
        self.assertTrue(File.objects.filter(name="b.wav").exists())
        self.assertIn("0 would be merged", self._run().replace("0 would", "0 would"))


class PageViewStatisticsTests(TestCase):
    """The statistics report must not become a way in, nor store one-time secrets."""

    def _track(self, path):
        return APIClient().post("/api/track-page/", {"path": path}, format="json")

    def test_a_secret_in_the_address_is_not_stored(self):
        from mousetube_api.models import PageView

        self.assertEqual(
            self._track("/activate/MTA/dhmj4d-secrettoken").status_code, 200
        )
        self.assertEqual(self._track("/password/reset/xx/yy").status_code, 200)
        self.assertEqual(
            set(PageView.objects.values_list("path", flat=True)),
            {"/activate", "/password"},
        )

    def test_old_rows_are_folded_into_one_page_a_day(self):
        from mousetube_api.models import PageView
        from mousetube_api.utils.data_upgrades import merge_page_view_paths

        PageView.objects.create(path="/activate/a/b", count=2)
        PageView.objects.create(path="/activate/c/d", count=3)
        PageView.objects.create(path="/software", count=1)
        # another day: the date is set by the model on creation, so put it back by hand
        old_day = PageView.objects.create(path="/activate/e/f", count=4)
        PageView.objects.filter(pk=old_day.pk).update(date="2026-03-01")
        self.assertEqual(merge_page_view_paths(), 3)
        self.assertEqual(PageView.objects.filter(path="/activate").count(), 2)
        self.assertEqual(
            sum(
                PageView.objects.filter(path="/activate").values_list(
                    "count", flat=True
                )
            ),
            9,
        )
        self.assertEqual(
            PageView.objects.get(path="/activate", date="2026-03-01").count, 4
        )
        self.assertEqual(PageView.objects.count(), 3)
        self.assertEqual(merge_page_view_paths(), 0)

    def test_a_hostile_address_cannot_inject_markup_in_the_report(self):
        import os
        import tempfile
        from unittest import mock

        from django.core.management import call_command

        self._track('/"><script>alert(1)</script>')
        with tempfile.TemporaryDirectory() as logs:
            with mock.patch(
                "mousetube_api.management.commands.export_page_view.LOGS_DIR", logs
            ):
                call_command("export_page_view", verbosity=0)
            with open(os.path.join(logs, "latest.html")) as report:
                html = report.read()
        self.assertNotIn("<script>alert(1)", html)
        self.assertIn("\\u003Cscript\\u003Ealert(1)", html)  # data, never markup


@override_settings(CACHES=LOCMEM)
class ReviewApiTests(FreshCache, TestCase):
    """The review page of the administrators: who may use it, and what it decides."""

    def setUp(self):
        super().setUp()
        from allauth.account.models import EmailAddress

        from mousetube_api.models import Hardware, Software, SoftwareVersion

        User = get_user_model()
        self.admin = User.objects.create_user(
            "boss", "boss@igbmc.fr", "x", is_staff=True
        )
        self.member = User.objects.create_user("member", "m@igbmc.fr", "x")
        self.author = User.objects.create_user(
            "author", "au@igbmc.fr", "x", first_name="Ada", last_name="Lovelace"
        )
        self.software = Software.objects.create(
            name="Waiting soft",
            type="acquisition",
            status="waiting validation",
            created_by=self.author,
        )
        self.validated = Software.objects.create(
            name="Fine soft", status="validated", created_by=self.author
        )
        self.hardware = Hardware.objects.create(
            name="Waiting mic",
            type="microphone",
            status="waiting validation",
            created_by=self.author,
        )
        self.session = RecordingSession.objects.create(
            name="Needs review",
            is_multiple=True,
            status="waiting validation",
            created_by=self.author,
        )
        version = SoftwareVersion.objects.create(software=self.software, version="1")
        self.session.equipment_acquisition_software.add(version)

        self.applicant = User.objects.create_user(
            "newbie", "newbie@igbmc.fr", "x", is_active=False
        )
        EmailAddress.objects.create(
            user=self.applicant, email=self.applicant.email, verified=True, primary=True
        )
        self.client = APIClient()
        self.client.force_authenticate(self.admin)

    def _decide(self, kind, action, ids, **extra):
        return self.client.post(
            f"/api/review/{kind}/decision/",
            {"action": action, "ids": ids, **extra},
            format="json",
        )

    def test_only_staff_can_use_it(self):
        for who, expected in ((None, 401), (self.member, 403), (self.admin, 200)):
            client = APIClient()
            if who:
                client.force_authenticate(who)
            self.assertEqual(client.get("/api/review/").status_code, expected, who)
            self.assertEqual(
                client.post(
                    "/api/review/software/decision/",
                    {"action": "validate", "ids": [self.software.pk]},
                    format="json",
                ).status_code,
                expected if expected != 200 else 200,
            )
        self.software.refresh_from_db()
        self.assertEqual(self.software.status, "validated")  # only the admin's call

    def test_the_summary_counts_what_waits(self):
        data = self.client.get("/api/review/").json()
        per_kind = {k["kind"]: k["count"] for k in data["kinds"]}
        self.assertEqual(per_kind["software"], 1)
        self.assertEqual(per_kind["hardware"], 1)
        self.assertEqual(per_kind["sessions"], 1)
        self.assertEqual(per_kind["accounts"], 1)
        self.assertEqual(per_kind["strains"], 0)
        self.assertEqual(data["total"], 4)

    def test_the_list_describes_each_item(self):
        item = self.client.get("/api/review/software/").json()["results"][0]
        self.assertEqual(item["title"], "Waiting soft")
        self.assertEqual(item["created_by"]["name"], "Ada Lovelace")
        self.assertIn("Type", [f["label"] for f in item["facts"]])
        session = self.client.get("/api/review/sessions/").json()["results"][0]
        self.assertEqual([p["kind"] for p in session["pending"]], ["software"])
        account = self.client.get("/api/review/accounts/").json()["results"][0]
        self.assertTrue(account["can_validate"])
        self.assertEqual(self.client.get("/api/review/nothing/").status_code, 404)

    def test_validating_an_entry_validates_it_and_tells_its_creator(self):
        from django.core import mail

        done = self._decide("hardware", "validate", [self.hardware.pk]).json()
        self.assertEqual(done["done"], 1)
        self.hardware.refresh_from_db()
        self.assertEqual(self.hardware.status, "validated")
        self.assertIn("validated", mail.outbox[-1].subject)
        self.assertEqual(mail.outbox[-1].to, ["au@igbmc.fr"])

    def test_sending_back_gives_the_reason(self):
        from django.core import mail

        self._decide(
            "hardware", "send_back", [self.hardware.pk], reason="Add the maker"
        )
        self.hardware.refresh_from_db()
        self.assertEqual(self.hardware.status, "draft")
        self.assertIn("Add the maker", mail.outbox[-1].body)

    def test_a_session_is_validated_with_everything_it_uses(self):
        data = self._decide("sessions", "validate", [self.session.pk]).json()
        self.assertEqual(data["done"], 1)
        self.session.refresh_from_db()
        self.software.refresh_from_db()
        self.assertEqual(self.session.status, "shared")
        self.assertEqual(self.software.status, "validated")

    def test_only_what_waits_is_touched(self):
        data = self._decide("software", "send_back", [self.validated.pk]).json()
        self.assertEqual(data["done"], 0)
        self.validated.refresh_from_db()
        self.assertEqual(self.validated.status, "validated")

    def test_accounts_are_activated_or_rejected_with_the_safeguards_of_the_admin(self):
        from django.core import mail

        done = self._decide("accounts", "validate", [self.applicant.pk]).json()
        self.assertEqual(done["done"], 1)
        self.applicant.refresh_from_db()
        self.assertTrue(self.applicant.is_active)
        self.assertEqual(mail.outbox[-1].to, ["newbie@igbmc.fr"])

        from allauth.account.models import EmailAddress

        User = get_user_model()
        other = User.objects.create_user(
            "other", "other@igbmc.fr", "x", is_active=False
        )
        EmailAddress.objects.create(user=other, email=other.email, verified=True)
        used = User.objects.create_user("used", "used@igbmc.fr", "x", is_active=False)
        EmailAddress.objects.create(user=used, email=used.email, verified=True)
        User.objects.filter(pk=used.pk).update(last_login="2026-01-01T00:00:00Z")
        result = self._decide("accounts", "send_back", [other.pk, used.pk]).json()
        self.assertEqual(result["done"], 1)  # the request is rejected and deleted
        self.assertEqual([s["id"] for s in result["skipped"]], [used.pk])
        self.assertFalse(User.objects.filter(pk=other.pk).exists())
        self.assertTrue(User.objects.filter(pk=used.pk).exists())

    def test_a_malformed_decision_is_refused(self):
        self.assertEqual(self._decide("software", "explode", [1]).status_code, 400)
        self.assertEqual(
            self.client.post(
                "/api/review/software/decision/", {"action": "validate"}, format="json"
            ).status_code,
            400,
        )


class SessionEntriesFollowTheSessionTests(TestCase):
    """A shared session only uses validated entries, whichever way it became shared."""

    def setUp(self):
        from mousetube_api.models import Hardware

        self.admin = get_user_model().objects.create_superuser(
            "root", "r@igbmc.fr", "x"
        )
        self.author = get_user_model().objects.create_user("auth", "a@igbmc.fr", "x")
        self.mic = Hardware.objects.create(
            name="Waiting mic",
            type="microphone",
            status="waiting validation",
            created_by=self.author,
        )
        self.session = RecordingSession.objects.create(
            name="s",
            is_multiple=True,
            status="waiting validation",
            created_by=self.author,
        )
        self.session.equipment_acquisition_hardware_microphones.add(self.mic)

    def _save_in_the_admin(self, status):
        from unittest import mock

        from django.contrib import admin
        from django.test import RequestFactory

        RecordingSession.objects.filter(pk=self.session.pk).update(status=status)
        self.session.refresh_from_db()
        model_admin = admin.site._registry[RecordingSession]
        request = RequestFactory().post("/admin/")
        request.user = self.admin
        form = mock.Mock(instance=self.session)
        with mock.patch.object(model_admin, "message_user") as message:
            model_admin.save_related(request, form, [], True)
        return message

    def test_setting_the_status_to_shared_in_the_admin_validates_what_it_uses(self):
        message = self._save_in_the_admin("shared")
        self.mic.refresh_from_db()
        self.assertEqual(self.mic.status, "validated")
        self.assertIn("validated with it", message.call_args.args[1])

    def test_a_session_that_is_not_public_leaves_its_entries_alone(self):
        message = self._save_in_the_admin("waiting validation")
        self.mic.refresh_from_db()
        self.assertEqual(self.mic.status, "waiting validation")
        message.assert_not_called()
