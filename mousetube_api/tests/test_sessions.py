"""Log out of all devices, and a new password ends the sign-ins made with the old one.

Everything goes through the real routes: a sign-in gives an access and a refresh token, and a
revoked sign-in is refused on both. Two sign-ins of the same user are independent until one of them
asks for the revocation.
"""

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from mousetube_api.models import UserProfile
from mousetube_api.serializers import UserProfileSerializer
from mousetube_api.tests.test_security import LOCMEM
from mousetube_api.utils.sessions import IAT_MS

PASSWORD = "correct-horse-battery-1"
NEW = "a-longer-new-passphrase-2"


@override_settings(CACHES=LOCMEM)  # do not touch the real Redis counters
class Sessions(TestCase):
    def setUp(self):
        cache.clear()
        User = get_user_model()
        self.user = User.objects.create_user("me", "me@igbmc.fr", PASSWORD)
        self.other = User.objects.create_user("oth", "oth@igbmc.fr", PASSWORD)

    def sign_in(self, username="me", password=PASSWORD):
        answer = APIClient().post(
            "/auth/jwt/create/",
            {"username": username, "password": password},
            format="json",
        )
        self.assertEqual(answer.status_code, 200, answer.data)
        return answer.data

    def who(self, tokens):
        """The answer of a call that needs a sign-in, with the access token of `tokens`."""
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        return client.get("/auth/users/me/")

    def renew(self, tokens):
        return APIClient().post(
            "/auth/jwt/refresh/", {"refresh": tokens["refresh"]}, format="json"
        )

    def log_out_everywhere(self, tokens):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        return client.post("/auth/logout_all/")

    def test_a_sign_in_works_and_carries_its_moment(self):
        tokens = self.sign_in()
        self.assertEqual(self.who(tokens).status_code, 200)
        self.assertEqual(self.renew(tokens).status_code, 200)
        self.assertIn(IAT_MS, RefreshToken(tokens["refresh"]))

    def test_a_visitor_cannot_log_out_everywhere(self):
        self.assertEqual(APIClient().post("/auth/logout_all/").status_code, 401)

    def test_log_out_everywhere_ends_every_sign_in_of_the_user(self):
        phone, laptop = self.sign_in(), self.sign_in()
        self.assertEqual(self.log_out_everywhere(phone).status_code, 204)
        for tokens in (phone, laptop):  # this one included
            self.assertEqual(self.who(tokens).status_code, 401)
            self.assertEqual(self.renew(tokens).status_code, 401)

    def test_other_users_are_not_touched(self):
        mine, theirs = self.sign_in(), self.sign_in("oth")
        self.log_out_everywhere(mine)
        self.assertEqual(self.who(theirs).status_code, 200)
        self.assertEqual(self.renew(theirs).status_code, 200)

    def test_signing_in_again_right_after_works(self):
        """The same second: the page signs in again to stay connected after a new password."""
        old = self.sign_in()
        self.log_out_everywhere(old)
        new = self.sign_in()
        self.assertEqual(self.who(new).status_code, 200)
        self.assertEqual(self.renew(new).status_code, 200)
        self.assertEqual(self.who(old).status_code, 401)

    def test_signing_in_does_not_end_the_other_sign_ins(self):
        """A sign-in updates the last login of the user: that must not count as a change."""
        first = self.sign_in()
        self.sign_in()
        self.assertEqual(self.who(first).status_code, 200)

    def test_a_token_made_before_this_existed_is_read_with_its_iat(self):
        old = RefreshToken.for_user(self.user)  # no iat_ms
        tokens = {"access": str(old.access_token), "refresh": str(old)}
        self.assertEqual(self.who(tokens).status_code, 200)
        self.log_out_everywhere(self.sign_in())
        self.assertEqual(self.who(tokens).status_code, 401)
        self.assertEqual(self.renew(tokens).status_code, 401)

    def test_a_new_password_ends_the_other_sign_ins(self):
        other_device = self.sign_in()
        client = APIClient()
        client.force_authenticate(self.user)
        answer = client.post(
            "/auth/users/set_password/",
            {"current_password": PASSWORD, "new_password": NEW, "re_new_password": NEW},
            format="json",
        )
        self.assertEqual(answer.status_code, 204)
        self.assertEqual(self.who(other_device).status_code, 401)
        self.assertEqual(self.renew(other_device).status_code, 401)
        self.assertEqual(self.who(self.sign_in(password=NEW)).status_code, 200)

    def test_a_password_changed_by_other_means_ends_the_sign_ins_too(self):
        """The e-mail of a forgotten password, an administrator: they all save the user."""
        tokens = self.sign_in()
        self.user.set_password(NEW)
        self.user.save()
        self.assertEqual(self.who(tokens).status_code, 401)

    def test_saving_a_user_without_a_new_password_changes_nothing(self):
        tokens = self.sign_in()
        self.user.first_name = "Someone"
        self.user.save()
        self.user.save(update_fields=["last_login"])
        self.assertEqual(self.who(tokens).status_code, 200)

    def test_the_profile_does_not_show_nor_take_the_moment(self):
        self.log_out_everywhere(self.sign_in())
        profile = UserProfile.objects.get(user=self.user)
        self.assertIsNotNone(profile.sessions_revoked_at)
        self.assertNotIn("sessions_revoked_at", UserProfileSerializer(profile).data)
        serializer = UserProfileSerializer(
            profile, data={"sessions_revoked_at": None}, partial=True
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()
        profile.refresh_from_db()
        self.assertIsNotNone(profile.sessions_revoked_at)  # the user cannot clear it
