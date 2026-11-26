"""The change of the e-mail address of a signed-in user.

The address recovers a forgotten password: whoever controls it controls the account. These tests
hold the rules that keep it so (see utils/email_change.py).
"""

from unittest import mock
from urllib.parse import parse_qs, urlparse

from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.core import mail, signing
from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from mousetube_api.tests.test_security import LOCMEM
from mousetube_api.utils import email_change

PASSWORD = "correct-horse-battery-1"
NEW = "new.address@univ-lyon1.fr"


def token_of(message):
    """The token in the link of a mail."""
    link = next(w for w in message.body.split() if "confirm-email?token=" in w)
    return parse_qs(urlparse(link).query)["token"][0]


@override_settings(CACHES=LOCMEM)  # do not touch the real Redis counters
class EmailChange(TestCase):
    def setUp(self):
        cache.clear()
        User = get_user_model()
        self.user = User.objects.create_user(
            "me", "me@igbmc.fr", PASSWORD, first_name="Me"
        )
        EmailAddress.objects.create(
            user=self.user, email="me@igbmc.fr", primary=True, verified=True
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def ask(self, new=NEW, password=PASSWORD, client=None):
        return (client or self.client).post(
            "/auth/users/change_email/",
            {"new_email": new, "current_password": password},
            format="json",
        )

    def confirm(self, token, client=None):
        return (client or self.client).post(
            "/auth/users/confirm_email_change/", {"token": token}, format="json"
        )

    def asked(self, new=NEW):
        """Ask and return the token of the link sent to the new address."""
        self.assertEqual(self.ask(new).status_code, 202)
        return token_of(next(m for m in mail.outbox if m.to == [new]))

    # --- the request

    def test_a_visitor_cannot_ask(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.ask().status_code, 401)
        self.assertEqual(mail.outbox, [])

    def test_the_password_is_asked(self):
        answer = self.ask(password="not-the-password")
        self.assertEqual(answer.status_code, 400)
        self.assertIn("current_password", answer.data)
        self.assertEqual(mail.outbox, [])

    def test_the_link_goes_to_the_new_address_only_and_the_old_one_is_told(self):
        self.assertEqual(self.ask().status_code, 202)
        to_new = [m for m in mail.outbox if m.to == [NEW]]
        to_old = [m for m in mail.outbox if m.to == ["me@igbmc.fr"]]
        self.assertEqual((len(to_new), len(to_old)), (1, 1))
        self.assertIn("/account/confirm-email?token=", to_new[0].body)
        # the old address learns of the request, without the link and without the new address
        self.assertNotIn("token=", to_old[0].body)
        self.assertNotIn(NEW, to_old[0].body)
        self.user.refresh_from_db()
        self.assertEqual(
            self.user.email, "me@igbmc.fr"
        )  # nothing changes before the link

    def test_a_personal_address_is_refused_like_at_the_registration(self):
        answer = self.ask("someone@gmail.com")
        self.assertEqual(answer.status_code, 400)
        self.assertIn("new_email", answer.data)
        self.assertEqual(mail.outbox, [])

    def test_the_same_address_is_refused(self):
        self.assertEqual(self.ask("ME@igbmc.fr").status_code, 400)

    def test_an_address_of_another_account_gets_the_same_answer_and_no_mail(self):
        get_user_model().objects.create_user("other", "taken@univ-lyon1.fr", PASSWORD)
        free = self.ask("free@univ-lyon1.fr")
        taken = self.ask("Taken@Univ-Lyon1.fr")  # case does not matter
        self.assertEqual((free.status_code, taken.status_code), (202, 202))
        self.assertEqual(free.data, taken.data)
        self.assertEqual(
            [m.to for m in mail.outbox if "token=" in m.body], [["free@univ-lyon1.fr"]]
        )

    def test_the_number_of_requests_is_limited(self):
        for i in range(email_change.PER_USER[0]):
            self.assertEqual(self.ask(f"a{i}@univ-lyon1.fr").status_code, 202)
        sent = len(mail.outbox)
        self.assertEqual(
            self.ask("one-more@univ-lyon1.fr").status_code, 202
        )  # same answer
        self.assertEqual(len(mail.outbox), sent)  # but nothing is sent

    def test_an_address_gets_one_mail_at_a_time(self):
        self.ask()
        sent = len(mail.outbox)
        self.ask()
        self.assertEqual(len(mail.outbox), sent)

    def test_a_mail_that_fails_is_told_and_the_user_can_try_again(self):
        with override_settings(
            EMAIL_BACKEND="mousetube_api.tests.test_email_change.Broken"
        ):
            self.assertEqual(self.ask().status_code, 503)
        self.assertEqual(self.ask().status_code, 202)

    # --- the confirmation

    def test_the_link_changes_the_address_and_the_old_one_is_told(self):
        token = self.asked()
        mail.outbox.clear()
        answer = self.confirm(token)
        self.assertEqual((answer.status_code, answer.data["email"]), (200, NEW))
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, NEW)
        # one verified address, the new one: the account is still confirmed
        self.assertEqual(
            list(
                EmailAddress.objects.filter(user=self.user).values_list(
                    "email", "verified"
                )
            ),
            [(NEW, True)],
        )
        self.assertEqual([m.to for m in mail.outbox], [["me@igbmc.fr"]])

    def test_the_link_works_once(self):
        token = self.asked()
        self.assertEqual(self.confirm(token).status_code, 200)
        self.assertEqual(self.confirm(token).status_code, 400)

    def test_another_signed_in_user_cannot_use_the_link(self):
        token = self.asked()
        other = get_user_model().objects.create_user(
            "other", "other@igbmc.fr", PASSWORD
        )
        client = APIClient()
        client.force_authenticate(other)
        self.assertEqual(self.confirm(token, client).status_code, 400)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "me@igbmc.fr")

    def test_someone_not_signed_in_cannot_use_the_link(self):
        # the owner of a mistyped address must not be able to take the account
        token = self.asked()
        self.assertEqual(self.confirm(token, APIClient()).status_code, 401)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "me@igbmc.fr")

    def test_a_new_password_cancels_the_link(self):
        token = self.asked()
        self.user.set_password("another-passphrase-2")
        self.user.save()
        self.assertEqual(self.confirm(token).status_code, 400)

    def test_an_expired_link_is_refused(self):
        token = self.asked()
        with mock.patch.object(email_change, "MAX_AGE", -1):
            self.assertEqual(self.confirm(token).status_code, 400)

    def test_a_forged_or_other_token_is_refused(self):
        forged = signing.dumps(
            {
                "u": self.user.pk,
                "o": "me@igbmc.fr",
                "n": "evil@univ-lyon1.fr",
                "p": "x",
            },
            salt="another-salt",
        )
        for bad in (forged, "garbage", ""):
            self.assertEqual(self.confirm(bad).status_code, 400, bad)
        # the signed payload with a wrong fingerprint
        bad_fingerprint = signing.dumps(
            {"u": self.user.pk, "o": "me@igbmc.fr", "n": NEW, "p": "x"},
            salt=email_change.SALT,
        )
        self.assertEqual(self.confirm(bad_fingerprint).status_code, 400)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "me@igbmc.fr")

    def test_the_address_taken_meanwhile_is_refused(self):
        token = self.asked()
        get_user_model().objects.create_user("other", NEW, PASSWORD)
        self.assertEqual(self.confirm(token).status_code, 400)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "me@igbmc.fr")

    def test_the_second_of_two_links_is_dead_once_the_first_is_used(self):
        first = self.asked("first@univ-lyon1.fr")
        second = self.asked("second@univ-lyon1.fr")
        self.assertEqual(self.confirm(first).status_code, 200)
        self.assertEqual(self.confirm(second).status_code, 400)

    # --- no other way in

    def test_the_profile_route_cannot_change_the_address(self):
        self.client.patch("/auth/users/me/", {"email": NEW}, format="json")
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "me@igbmc.fr")


class Broken:
    """A mail backend that always fails (the relay is down)."""

    def __init__(self, *args, **kwargs):
        pass

    def send_messages(self, messages):
        raise OSError("relay down")

    def open(self):
        pass

    def close(self):
        pass
