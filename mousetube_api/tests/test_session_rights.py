"""What each kind of user may do with a session in each of its states, in one table."""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.test import TestCase
from rest_framework.test import APIClient

from mousetube_api.models import Protocol, RecordingSession
from mousetube_api.utils.session_rights import session_rights

# (status, who) -> (can_edit, can_withdraw, can_share, can_delete)
TABLE = {
    ("draft", "author"): (True, False, True, True),
    ("waiting validation", "author"): (False, True, False, False),
    ("shared", "author"): (True, False, False, False),
    ("published", "author"): (True, False, False, False),
    ("draft", "other"): (False, False, False, False),
    ("waiting validation", "other"): (False, False, False, False),
    ("shared", "other"): (False, False, False, False),
    ("published", "other"): (False, False, False, False),
    ("draft", "visitor"): (False, False, False, False),
    ("shared", "visitor"): (False, False, False, False),
    ("draft", "admin"): (True, False, True, True),
    ("waiting validation", "admin"): (True, True, False, True),
    ("shared", "admin"): (True, False, False, True),
    ("published", "admin"): (True, False, False, True),
}


class SessionRightsTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.users = {
            "author": User.objects.create_user("author", "a@igbmc.fr", "x"),
            "other": User.objects.create_user("other", "o@igbmc.fr", "x"),
            "admin": User.objects.create_user("adm", "m@igbmc.fr", "x", is_staff=True),
            "visitor": AnonymousUser(),
        }
        self.protocol = Protocol.objects.create(
            animals_sex="male(s)",
            animals_age="pup",
            animals_housing="grouped",
            context_number_of_animals="2",
            context_duration="short term (<1h)",
            context_cage="unfamiliar test cage",
            context_bedding="bedding",
            context_light_cycle="day",
            created_by=self.users["author"],
        )

    def _session(self, status):
        self.count = getattr(self, "count", 0) + 1
        session = RecordingSession.objects.create(
            name=f"s-{status}-{self.count}",
            is_multiple=True,
            protocol=self.protocol,
            created_by=self.users["author"],
        )
        RecordingSession.objects.filter(pk=session.pk).update(status=status)
        session.refresh_from_db()
        return session

    def test_the_table(self):
        for (status, who), expected in TABLE.items():
            rights = session_rights(self._session(status), self.users[who])
            got = (
                rights["can_edit"],
                rights["can_withdraw"],
                rights["can_share"],
                rights["can_delete"],
            )
            self.assertEqual(got, expected, f"{who} on a {status} session")

    def test_only_the_author_of_a_session_under_review_is_told_why_it_is_locked(self):
        session = self._session("waiting validation")
        self.assertIn(
            "review", session_rights(session, self.users["author"])["locked_reason"]
        )
        for who in ("other", "admin", "visitor"):
            self.assertEqual(
                session_rights(session, self.users[who])["locked_reason"], ""
            )

    def test_the_api_follows_the_table(self):
        """The routes give the answer of the table, not their own."""
        for (status, who), (can_edit, _w, _s, can_delete) in TABLE.items():
            if who != "author":  # the routes list the sessions of their author
                continue
            client = APIClient()
            client.force_authenticate(self.users[who])
            session = self._session(status)
            url = f"/api/recording-session/{session.pk}/"
            patch = client.patch(url, {"description": "x"}, format="json")
            self.assertEqual(
                patch.status_code == 200, can_edit, f"edit by {who} of a {status}"
            )
            delete = client.delete(url)
            self.assertEqual(
                delete.status_code == 204, can_delete, f"delete by {who} of a {status}"
            )

    def test_the_session_tells_its_author_what_he_may_do(self):
        client = APIClient()
        client.force_authenticate(self.users["author"])
        session = self._session("waiting validation")
        data = client.get(f"/api/recording-session/{session.pk}/").json()
        self.assertFalse(data["rights"]["can_edit"])
        self.assertTrue(data["rights"]["can_withdraw"])
