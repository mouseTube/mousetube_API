"""The account page of the signed-in user: unlink ORCID, statistics, notifications, export."""

import json

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from mousetube_api.models import Favorite, File, Laboratory, UserProfile
from mousetube_api.tests.test_security import LOCMEM
from mousetube_api.utils.moderation import notify_creator
from mousetube_api.utils.publication import _tell_author

PASSWORD = "correct-horse-battery-1"


@override_settings(CACHES=LOCMEM)  # do not touch the real Redis counters
class Profile(TestCase):
    def setUp(self):
        cache.clear()
        User = get_user_model()
        self.user = User.objects.create_user("me", "me@igbmc.fr", PASSWORD)
        self.other = User.objects.create_user("other", "other@igbmc.fr", PASSWORD)
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def profile(self, user=None):
        return UserProfile.objects.get(user=user or self.user)

    # --- ORCID

    def unlink(self, password=PASSWORD):
        return self.client.post(
            "/api/unlink-orcid/", {"current_password": password}, format="json"
        )

    def test_the_orcid_is_removed_and_can_be_linked_again_by_another_account(self):
        UserProfile.objects.filter(user=self.user).update(orcid="0000-0002-1825-0097")
        self.assertEqual(self.unlink().status_code, 200)
        self.assertIsNone(self.profile().orcid)
        # free again: another account may link it
        UserProfile.objects.filter(user=self.other).update(orcid="0000-0002-1825-0097")
        self.assertEqual(self.profile(self.other).orcid, "0000-0002-1825-0097")

    def test_the_password_is_asked_to_remove_the_orcid(self):
        UserProfile.objects.filter(user=self.user).update(orcid="0000-0002-1825-0097")
        self.assertEqual(self.unlink("wrong").status_code, 400)
        self.assertEqual(self.profile().orcid, "0000-0002-1825-0097")

    def test_a_visitor_cannot_remove_an_orcid(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.unlink().status_code, 401)

    def test_removing_the_orcid_touches_only_the_account_that_asks(self):
        UserProfile.objects.filter(user=self.other).update(orcid="0000-0001-2345-6789")
        self.unlink()
        self.assertEqual(self.profile(self.other).orcid, "0000-0001-2345-6789")

    # --- statistics

    def test_the_statistics_count_the_files_the_user_added_only(self):
        File.objects.create(name="a.wav", created_by=self.user, downloads=3)
        File.objects.create(name="b.wav", created_by=self.user, downloads=4)
        File.objects.create(name="c.wav", created_by=self.other, downloads=100)
        data = self.client.get("/api/my-stats/").data
        self.assertEqual((data["files"], data["downloads"]), (2, 7))
        self.assertEqual(data["date_joined"], self.user.date_joined)

    def test_a_user_without_file_has_zero_downloads(self):
        self.assertEqual(self.client.get("/api/my-stats/").data["downloads"], 0)

    def test_a_sign_in_updates_the_last_login(self):
        self.assertIsNone(self.user.last_login)
        self.client.force_authenticate(None)
        answer = self.client.post(
            "/auth/jwt/create/", {"username": "me", "password": PASSWORD}, format="json"
        )
        self.assertEqual(answer.status_code, 200)
        self.user.refresh_from_db()
        self.assertIsNotNone(self.user.last_login)

    def test_a_visitor_has_no_statistics(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get("/api/my-stats/").status_code, 401)

    # --- notifications

    def lab(self):
        # a user read again: the one of setUp keeps the profile it created, as it was then
        user = get_user_model().objects.get(pk=self.user.pk)
        return Laboratory.objects.create(name="Lab", created_by=user)

    def test_both_notifications_are_on_by_default(self):
        profile = self.profile()
        self.assertTrue(profile.notify_validation and profile.notify_publication)
        notify_creator(self.lab(), "validated", "text")
        _tell_author(self.lab(), "published", "text")
        self.assertEqual(len(self.to_me()), 2)

    def to_me(self):
        """What reached the user (creating a laboratory also mails the administrator)."""
        return [m for m in mail.outbox if m.to == ["me@igbmc.fr"]]

    def test_a_kind_turned_off_is_not_sent_the_other_is(self):
        UserProfile.objects.filter(user=self.user).update(notify_validation=False)
        notify_creator(self.lab(), "validated", "text")
        self.assertEqual(self.to_me(), [])
        _tell_author(self.lab(), "published", "text")
        self.assertEqual(len(self.to_me()), 1)
        UserProfile.objects.filter(user=self.user).update(notify_publication=False)
        _tell_author(self.lab(), "published", "text")
        self.assertEqual(len(self.to_me()), 1)

    def test_the_user_changes_his_choices_and_nobody_else_can(self):
        profile = self.profile()
        url = f"/api/user_profile/{profile.pk}/"
        self.assertEqual(
            self.client.patch(
                url, {"notify_validation": False}, format="json"
            ).status_code,
            200,
        )
        self.assertFalse(self.profile().notify_validation)
        self.client.force_authenticate(self.other)
        answer = self.client.patch(url, {"notify_publication": False}, format="json")
        self.assertEqual(answer.status_code, 403)
        self.assertTrue(self.profile().notify_publication)

    # --- export

    def test_the_export_holds_the_account_and_the_contributions_of_the_user_only(self):
        self.lab()
        Laboratory.objects.create(name="Not mine", created_by=self.other)
        File.objects.create(name="a.wav", created_by=self.user)
        File.objects.create(name="b.wav", created_by=self.other)
        answer = self.client.get("/api/my-data/")
        self.assertEqual(answer.status_code, 200)
        self.assertIn("attachment", answer["Content-Disposition"])
        data = json.loads(answer.content)
        self.assertEqual(data["account"]["email"], "me@igbmc.fr")
        found = data["contributions"]
        self.assertEqual(
            [r["name"] for r in found["mousetube_api.Laboratory"]], ["Lab"]
        )
        self.assertEqual([r["name"] for r in found["mousetube_api.File"]], ["a.wav"])
        self.assertEqual(data["profile"][0]["notify_validation"], True)

    def test_the_export_never_holds_a_secret(self):
        text = self.client.get("/api/my-data/").content.decode()
        self.assertNotIn(self.user.password, text)
        self.assertNotIn("sessions_revoked_at", text)
        self.assertNotIn("other@igbmc.fr", text)

    def test_the_export_holds_the_favorites_of_the_user(self):
        lab = self.lab()
        Favorite.objects.create(user=self.user, content_object=lab)
        Favorite.objects.create(user=self.other, content_object=lab)
        found = json.loads(self.client.get("/api/my-data/").content)["contributions"]
        self.assertEqual(len(found["mousetube_api.Favorite"]), 1)

    def test_the_export_is_limited_to_once_a_minute_and_for_signed_in_users(self):
        self.assertEqual(self.client.get("/api/my-data/").status_code, 200)
        self.assertEqual(self.client.get("/api/my-data/").status_code, 429)
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get("/api/my-data/").status_code, 401)
