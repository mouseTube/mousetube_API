"""What nobody validated is never public, even when the session that uses it is.

A shared or published session stays public when its author edits it; the entries that nobody
validated yet (equipment, animals, laboratory...) are simply not shown to the others. The test
fills a shared session with entries of every kind, none validated, each with a sentinel in its
name, and reads every public endpoint as a visitor and as another user.
"""

import json

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from mousetube_api.models import (
    AnimalProfile,
    Contact,
    Dataset,
    File,
    Hardware,
    Laboratory,
    Protocol,
    RecordingSession,
    Reference,
    Software,
    SoftwareVersion,
    Species,
    Strain,
    Subject,
)

SENTINELS = (
    "LEAKLAB",
    "LEAKPROFILE",
    "LEAKSTRAIN",
    "LEAKMIC",
    "LEAKSOFT",
    "LEAKREF",
    "LEAKCONTACT",
    "LEAKDOC",
    "LEAKPROTOCOL",
    "LEAKSUBJECTPROFILE",
)


class UnvalidatedIsNotPublicTests(TestCase):
    maxDiff = None

    def setUp(self):
        cache.clear()
        User = get_user_model()
        self.owner = User.objects.create_user("own", "own@igbmc.fr", "x")
        self.other = User.objects.create_user("oth", "oth@igbmc.fr", "x")
        draft = {"status": "draft", "created_by": self.owner}
        species = Species.objects.create(name="Mus musculus")
        strain = Strain.objects.create(
            name="LEAKSTRAIN", background="LEAKSTRAIN", species=species, **draft
        )
        self.profile = AnimalProfile.objects.create(
            name="LEAKPROFILE", strain=strain, sex="male", genotype="wt", **draft
        )
        self.mic = Hardware.objects.create(name="LEAKMIC", type="microphone", **draft)
        self.mic.references.add(Reference.objects.create(name="LEAKDOC", **draft))
        self.soft = Software.objects.create(name="LEAKSOFT", type="recording", **draft)
        self.soft.contacts.add(
            Contact.objects.create(
                last_name="LEAKCONTACT", first_name="x", email="c@x.org", **draft
            )
        )
        version = SoftwareVersion.objects.create(
            software=self.soft, version="1", created_by=self.owner
        )
        protocol = Protocol.objects.create(
            name="LEAKPROTOCOL",
            animals_sex="male(s)",
            animals_age="pup",
            animals_housing="grouped",
            context_number_of_animals="2",
            context_duration="short term (<1h)",
            context_cage="unfamiliar test cage",
            context_bedding="bedding",
            context_light_cycle="day",
            **draft,
        )
        lab = Laboratory.objects.create(name="LEAKLAB", **draft)
        self.session = RecordingSession.objects.create(
            name="Public session",
            is_multiple=True,
            status="shared",
            protocol=protocol,
            laboratory=lab,
            created_by=self.owner,
        )
        self.session.animal_profiles.add(self.profile)
        self.session.equipment_acquisition_hardware_microphones.add(self.mic)
        self.session.equipment_acquisition_software.add(version)
        self.session.references.add(Reference.objects.create(name="LEAKREF", **draft))
        subject = Subject.objects.create(
            name="LEAKSUBJECT", animal_profile=self.profile, created_by=self.owner
        )
        self.file = File.objects.create(
            name="rec.wav",
            recording_session=self.session,
            status="done",
            created_by=self.owner,
        )
        self.file.subjects.add(subject)
        self.dataset = Dataset.objects.create(name="Public set", created_by=self.owner)
        self.dataset.recording_session_list.add(self.session)

    def _urls(self):
        f, d, s = self.file.pk, self.dataset.pk, self.session.pk
        return [
            "/api/file/",
            f"/api/file/{f}/",
            "/api/file/?search=LEAK",
            "/api/file/?search=LEAKMIC",
            "/api/file/?search=LEAKPROFILE",
            "/api/file/?search=LEAKSTRAIN",
            "/api/file/?search=LEAKLAB",
            "/api/file/?search=LEAKPROTOCOL",
            "/api/file/?search=LEAKSOFT",
            "/api/file/filters/",
            f"/api/file/{f}/usv-detections/",
            "/api/dataset/",
            f"/api/dataset/{d}/",
            f"/api/dataset/{d}/metadata/",
            "/api/dataset/metadata/",
            "/api/protocol/",
            "/api/animalprofile/",
            "/api/strain/",
            "/api/subject/",
            "/api/laboratory/",
            "/api/hardware/",
            "/api/hardware/?used=1",
            "/api/software/",
            "/api/software/?used=1",
            "/api/software-version/",
            "/api/contact/",
            "/api/reference/",
            "/api/species/",
            "/api/study/",
            f"/api/recording-session/{s}/",
        ]

    def _leaks(self, client):
        found = []
        for url in self._urls():
            response = client.get(url)
            body = (
                json.dumps(response.json())
                if response.status_code == 200
                and response["Content-Type"].startswith("application/json")
                else ""
            )
            found += [(url, w) for w in SENTINELS if w in body]
        return found

    def test_a_visitor_sees_none_of_it(self):
        leaks = {}
        for url, word in self._leaks(APIClient()):
            leaks.setdefault(url, []).append(word)
        self.assertEqual(leaks, {})

    def test_another_user_sees_none_of_it(self):
        client = APIClient()
        client.force_authenticate(self.other)
        self.assertEqual(self._leaks(client), [])

    def test_the_files_keep_relative_urls_for_the_logo_of_the_repository(self):
        """The website puts its own base in front of them: an absolute URL breaks the logo."""
        from mousetube_api.models import Repository

        logo = Repository.objects.create(name="Zenodo", logo="logo/zenodo.png")
        File.objects.filter(pk=self.file.pk).update(repository=logo)
        data = APIClient().get("/api/file/").json()
        self.assertTrue(data["results"][0]["repository"]["logo"].startswith("/media/"))

    def test_the_author_still_sees_it(self):
        client = APIClient()
        client.force_authenticate(self.owner)
        self.assertIn(
            "LEAKMIC", client.get(f"/api/file/{self.file.pk}/").content.decode()
        )

    def test_it_appears_once_validated_and_not_before(self):
        from mousetube_api.utils.moderation import (
            approve_entries,
            session_pending_entries,
        )

        client = APIClient()
        page = lambda: client.get(f"/api/file/{self.file.pk}/").content.decode()
        self.assertNotIn("LEAKMIC", page())
        self.assertNotIn("LEAKREF", page())
        approve_entries([obj for _kind, obj in session_pending_entries(self.session)])
        self.session.refresh_from_db()
        self.assertEqual(session_pending_entries(self.session), [])
        for word in ("LEAKMIC", "LEAKREF", "LEAKLAB", "LEAKPROFILE", "LEAKSOFT"):
            self.assertIn(word, page())
        self.assertIn(
            "LEAKSOFT", client.get("/api/file/?search=LEAKSOFT").content.decode()
        )

    def test_a_validated_equipment_does_not_show_its_unvalidated_reference(self):
        Hardware.objects.filter(pk=self.mic.pk).update(status="validated")
        body = APIClient().get(f"/api/file/{self.file.pk}/").content.decode()
        self.assertIn("LEAKMIC", body)
        self.assertNotIn("LEAKDOC", body)

    def test_nothing_is_published_in_a_repository_while_something_waits(self):
        from mousetube_api.models import Repository

        repository = Repository.objects.create(name="Zenodo")
        client = APIClient()
        client.force_authenticate(self.owner)
        response = client.post(
            "/api/file/publish_session/",
            {"recording_session_id": self.session.pk, "repository_id": repository.pk},
            format="json",
        )
        self.assertEqual(response.status_code, 409)

    def test_the_state_of_the_record_does_not_name_what_waits(self):
        RecordingSession.objects.filter(pk=self.session.pk).update(
            zenodo_message="The record will be updated once validated: hardware LEAKMIC"
        )
        body = APIClient().get(f"/api/file/{self.file.pk}/").content.decode()
        self.assertNotIn("LEAKMIC", body)


class ProtocolCatalogTests(TestCase):
    """Like the other catalogs: visitors list the validated protocols, an author also his own."""

    def setUp(self):
        User = get_user_model()
        self.author = User.objects.create_user("pa", "pa@igbmc.fr", "x")
        self.other = User.objects.create_user("po", "po@igbmc.fr", "x")
        base = {
            "animals_sex": "male(s)",
            "animals_housing": "grouped",
            "context_number_of_animals": "2",
            "context_duration": "short term (<1h)",
            "context_cage": "unfamiliar test cage",
            "context_bedding": "bedding",
            "context_light_cycle": "day",
        }
        self.public = Protocol.objects.create(
            animals_age="pup", status="validated", created_by=self.author, **base
        )
        self.draft = Protocol.objects.create(
            animals_age="adult", created_by=self.author, **base
        )
        Protocol.objects.filter(pk=self.draft.pk).update(status="draft")
        self.base = base

    def _ids(self, user=None, query=""):
        client = APIClient()
        if user:
            client.force_authenticate(user)
        data = client.get(f"/api/protocol/{query}").json()
        return {p["id"] for p in data["results"]}

    def test_a_visitor_and_another_user_only_list_the_validated_ones(self):
        self.assertEqual(self._ids(), {self.public.pk})
        self.assertEqual(self._ids(self.other), {self.public.pk})

    def test_the_author_lists_his_draft_and_can_filter_by_status(self):
        self.assertEqual(self._ids(self.author), {self.public.pk, self.draft.pk})
        self.assertEqual(self._ids(self.author, "?status=draft"), {self.draft.pk})

    def test_another_user_cannot_open_a_draft_protocol(self):
        client = APIClient()
        client.force_authenticate(self.other)
        self.assertEqual(client.get(f"/api/protocol/{self.draft.pk}/").status_code, 404)

    def test_creating_a_protocol_that_exists_as_a_draft_validates_it(self):
        client = APIClient()
        client.force_authenticate(self.other)
        response = client.post(
            "/api/protocol/", {**self.base, "animals_age": "adult"}, format="json"
        )
        self.assertIn(response.status_code, (200, 201), response.content)
        self.draft.refresh_from_db()
        self.assertEqual(self.draft.status, "validated")
