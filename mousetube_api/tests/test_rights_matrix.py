"""Who may read, change and delete a catalog entry, by status and by role.

One rule for the seven moderated catalogs (documented in docs/dev/rights.md), checked on every
cell of the table: the status of the entry and who asks (visitor, another user, the author, an
administrator). The studies follow it too, but are private to their author.
"""

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from mousetube_api.models import (
    AnimalProfile,
    Contact,
    Hardware,
    Laboratory,
    Reference,
    Software,
    Species,
    Strain,
    Study,
)

STATUSES = ("draft", "waiting validation", "validated")
ROLES = ("visitor", "other", "author", "admin")


def expected(status, role, private=False):
    """(read, change, delete) answers of the API for an entry of `status` seen by `role`."""
    if role == "visitor":
        return (
            (401, 401, 401)
            if private
            else (200 if status == "validated" else 404, 401, 401)
        )
    if role == "admin":
        return 200, 200, 204
    if private and role == "other":
        return 404, 404, 404
    if status == "validated":
        return (
            200,
            403,
            403,
        )  # public, and locked for its author since an administrator validated it
    if role == "other":
        return 404, 404, 404  # not validated: private to its author
    return (
        200,
        200,
        204 if status == "draft" else 403,
    )  # a request under review is not deleted


class CatalogRightsTests(TestCase):
    def setUp(self):
        cache.clear()
        User = get_user_model()
        self.users = {
            "visitor": None,
            "other": User.objects.create_user("o", "o@igbmc.fr", "x"),
            "author": User.objects.create_user("a", "a@igbmc.fr", "x"),
            "admin": User.objects.create_user("m", "m@igbmc.fr", "x", is_staff=True),
        }
        self.species = Species.objects.create(name="Mus musculus")
        self.count = 0

    def make(self, model, status):
        self.count += 1
        n, author = self.count, self.users["author"]
        extra = {"status": status, "created_by": author}
        if model is Laboratory:
            return Laboratory.objects.create(name=f"lab{n}", **extra)
        if model is Reference:
            return Reference.objects.create(name=f"ref{n}", **extra)
        if model is Contact:
            return Contact.objects.create(
                last_name=f"c{n}", email=f"c{n}@x.org", **extra
            )
        if model is Hardware:
            return Hardware.objects.create(name=f"hw{n}", type="microphone", **extra)
        if model is Software:
            return Software.objects.create(name=f"sw{n}", type="acquisition", **extra)
        if model is Strain:
            return Strain.objects.create(
                name=f"st{n}", background="b", species=self.species, **extra
            )
        if model is AnimalProfile:
            strain = Strain.objects.create(
                name=f"sx{n}", background="b", species=self.species, status="validated"
            )
            return AnimalProfile.objects.create(
                name=f"ap{n}", strain=strain, sex="male", genotype="wt", **extra
            )
        return Study.objects.create(name=f"study{n}", **extra)

    def as_role(self, role):
        client = APIClient()
        if self.users[role]:
            client.force_authenticate(self.users[role])
        return client

    def listed(self, client, base, pk, query=""):
        url = f"/api/{base}/{query}"
        while url:
            response = client.get(url)
            if response.status_code != 200:
                return False
            data = response.json()
            rows = data["results"] if isinstance(data, dict) else data
            if pk in [row["id"] for row in rows]:
                return True
            url = (
                (data.get("next") or "").split("testserver")[-1]
                if isinstance(data, dict)
                else ""
            )
        return False

    def test_every_cell_of_the_table(self):
        catalogs = {
            Laboratory: "laboratory",
            Reference: "reference",
            Contact: "contact",
            Hardware: "hardware",
            Software: "software",
            Strain: "strain",
            AnimalProfile: "animalprofile",
            Study: "study",
        }
        for model, base in catalogs.items():
            private = model is Study
            for status in STATUSES:
                for role in ROLES:
                    read, change, delete = expected(status, role, private)
                    client = self.as_role(role)
                    with self.subTest(model=model.__name__, status=status, role=role):
                        entry = self.make(model, status)
                        self.assertEqual(
                            client.get(f"/api/{base}/{entry.pk}/").status_code, read
                        )
                        entry = self.make(model, status)
                        body = (
                            {"description": "x"}
                            if model in (Hardware, Software, Reference)
                            else {"name": f"new{self.count}"}
                        )
                        patched = client.patch(
                            f"/api/{base}/{entry.pk}/", body, format="json"
                        )
                        self.assertEqual(patched.status_code, change, patched.content)
                        entry = self.make(model, status)
                        self.assertEqual(
                            client.delete(f"/api/{base}/{entry.pk}/").status_code,
                            delete,
                        )

    def test_the_lists_show_validated_entries_and_one_s_own_never_the_others(self):
        for model, base in {
            Laboratory: "laboratory",
            Reference: "reference",
            Contact: "contact",
            Hardware: "hardware",
            Software: "software",
            Strain: "strain",
            AnimalProfile: "animalprofile",
        }.items():
            entries = {status: self.make(model, status) for status in STATUSES}
            for role in ROLES:
                for status, entry in entries.items():
                    sees = role == "admin" or status == "validated" or role == "author"
                    if role == "visitor":
                        sees = status == "validated"
                    with self.subTest(model=model.__name__, status=status, role=role):
                        client = self.as_role(role)
                        self.assertEqual(self.listed(client, base, entry.pk), sees)
                        # asking for a status does not widen what one may see
                        query = f"?status={status.replace(' ', '+')}"
                        self.assertEqual(
                            self.listed(client, base, entry.pk, query), sees
                        )

    def test_a_visitor_cannot_create_and_a_user_can(self):
        body = {"name": "New lab", "country": "FR"}
        self.assertEqual(
            self.as_role("visitor")
            .post("/api/laboratory/", body, format="json")
            .status_code,
            401,
        )
        created = self.as_role("other").post("/api/laboratory/", body, format="json")
        self.assertEqual(created.status_code, 201, created.content)
        self.assertEqual(created.json()["status"], "draft")

    def test_the_author_moves_an_entry_between_draft_and_waiting_but_cannot_validate_it(
        self,
    ):
        entry = self.make(Laboratory, "draft")
        client = self.as_role("author")
        url = f"/api/laboratory/{entry.pk}/"
        self.assertEqual(
            client.patch(
                url, {"status": "waiting validation"}, format="json"
            ).status_code,
            200,
        )
        self.assertEqual(
            client.patch(url, {"status": "draft"}, format="json").status_code, 200
        )
        self.assertEqual(
            client.patch(url, {"status": "validated"}, format="json").status_code, 400
        )
        self.assertEqual(
            self.as_role("admin")
            .patch(url, {"status": "validated"}, format="json")
            .status_code,
            200,
        )
