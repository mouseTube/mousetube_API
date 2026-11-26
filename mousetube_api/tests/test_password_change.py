"""The change of password of a signed-in user.

It asks the current password and applies the same rules as the registration (the validators of
Django), and, like the login, it is rate limited: a stolen session must not be enough to guess the
current password without limit.
"""

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from mousetube_api.tests.test_security import LOCMEM

OLD = "correct-horse-battery-1"
NEW = "a-longer-new-passphrase-2"
# what the registration refuses: too short, only digits, a common password
WEAK = ("short1", "123456789012", "password123")


@override_settings(CACHES=LOCMEM)  # do not touch the real Redis counters
class PasswordChange(TestCase):
    def setUp(self):
        cache.clear()
        self.user = get_user_model().objects.create_user(
            "me", "me@igbmc.fr", OLD, first_name="Me", last_name="Ok"
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def change(self, current=OLD, new=NEW):
        return self.client.post(
            "/auth/users/set_password/",
            {
                "current_password": current,
                "new_password": new,
                "re_new_password": new,
            },
            format="json",
        )

    def test_a_visitor_cannot_change_a_password(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.change().status_code, 401)

    def test_the_new_password_replaces_the_old_one(self):
        self.assertEqual(self.change().status_code, 204)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(NEW))
        self.assertFalse(self.user.check_password(OLD))

    def test_the_current_password_is_asked(self):
        answer = self.change(current="not-the-password")
        self.assertEqual(answer.status_code, 400)
        self.assertIn("current_password", answer.data)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(OLD))

    def test_it_refuses_what_the_registration_refuses(self):
        for weak in WEAK:
            answer = self.change(new=weak)
            self.assertEqual(answer.status_code, 400, weak)
            self.assertIn("new_password", answer.data, weak)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(OLD))

    def test_the_registration_and_the_change_agree(self):
        """The same passwords are refused at the registration, the same one is accepted."""
        anonymous = APIClient()
        for weak in WEAK:
            answer = anonymous.post(
                "/auth/users/",
                {
                    "username": f"u{len(weak)}",
                    "email": f"u{len(weak)}@igbmc.fr",
                    "password": weak,
                    "re_password": weak,
                },
                format="json",
            )
            self.assertEqual(answer.status_code, 400, weak)
            self.assertIn("password", answer.data, weak)

    def test_it_is_rate_limited_like_the_login(self):
        codes = [self.change(current=f"guess-{n}").status_code for n in range(12)]
        self.assertEqual(codes[:10], [400] * 10)
        self.assertEqual(codes[10], 429)
        # the password was not guessed, so it did not change
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(OLD))
