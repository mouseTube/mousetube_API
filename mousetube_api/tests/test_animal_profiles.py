"""An animal profile is told by its fields, not by a name (see utils/animal_profiles.py)."""

from io import StringIO

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from mousetube_api.models import (
    AnimalProfile,
    Favorite,
    RecordingSession,
    Species,
    Strain,
    Subject,
)
from mousetube_api.tests.test_security import LOCMEM, FreshCache
from mousetube_api.utils import animal_profiles
from mousetube_api.utils.moderation import validate_entries


@override_settings(CACHES=LOCMEM)
class AnimalProfileKey(FreshCache, TestCase):
    def setUp(self):
        super().setUp()
        User = get_user_model()
        self.alice = User.objects.create_user("alice", "a@igbmc.fr", "pw-pw-pw-1")
        self.bob = User.objects.create_user("bob", "b@igbmc.fr", "pw-pw-pw-1")
        species = Species.objects.create(name="Mus musculus")
        self.strain = Strain.objects.create(
            name="B6", background="b", species=species, status="validated"
        )

    def as_user(self, user):
        client = APIClient()
        client.force_authenticate(user)
        return client

    def post(self, user, **extra):
        return self.as_user(user).post(
            "/api/animalprofile/",
            {
                "strain_id": self.strain.id,
                "sex": "male",
                "genotype": "Fmr1 KO",
                **extra,
            },
            format="json",
        )

    def make(self, status="validated", user=None, **extra):
        fields = {"sex": "male", "genotype": "Fmr1 KO", **extra}
        return AnimalProfile.objects.create(
            strain=self.strain, status=status, created_by=user, **fields
        )

    # --- the fingerprint and the name

    def test_the_slightest_difference_makes_another_profile(self):
        base = self.make()
        for change in (
            {"genotype": "Fmr1 KO "},  # a space at the end is not a difference...
            {"genotype": "Fmr1  KO"},  # ...nor a doubled one
        ):
            self.assertEqual(self.make(**change).fingerprint, base.fingerprint, change)
        for change in (
            {"genotype": "fmr1 KO"},  # the case is kept
            {"sex": "female"},
            {"age": "pup"},
            {"treatment": "saline"},
            {"diet": "chow"},
            {"description": "weaned at P21"},
        ):
            self.assertNotEqual(
                self.make(**change).fingerprint, base.fingerprint, change
            )

    def test_a_precise_stage_tells_a_profile_but_the_class_term_does_not(self):
        from mousetube_api.models import OntologyTerm
        from mousetube_api.utils.ontologies import AGE_TERMS, known_term

        base = self.make()
        curie, label = AGE_TERMS["adult"]
        with_class_term = self.make()  # what the API gives to every adult mouse
        AnimalProfile.objects.filter(pk=with_class_term.pk).update(
            age_term=known_term(curie, label)
        )
        with_class_term.refresh_from_db()
        self.assertEqual(
            animal_profiles.fingerprint(animal_profiles.values_of(with_class_term)),
            base.fingerprint,
        )
        precise = OntologyTerm.objects.create(
            curie="MmusDv:0000112", label="P35", ontology="mmusdv", iri="http://x/p35"
        )
        stage = self.make(age_term=precise)
        self.assertNotEqual(stage.fingerprint, base.fingerprint)

    def test_the_name_is_made_from_the_fields_and_ends_with_the_fingerprint(self):
        profile = self.make(treatment="saline")
        self.assertEqual(
            profile.name,
            f"B6 · M · adult · Fmr1 KO · saline #{profile.fingerprint[:6]}",
        )

    def test_a_long_text_does_not_break_the_name(self):
        profile = self.make(genotype="x" * 255)
        self.assertLessEqual(len(profile.name), 255)
        self.assertTrue(profile.name.endswith(profile.fingerprint[:6]))

    def test_the_name_cannot_be_chosen(self):
        answer = self.post(self.alice, name="My name")
        self.assertEqual(answer.status_code, 201)
        self.assertNotEqual(answer.data["name"], "My name")
        self.assertIn("Fmr1 KO", answer.data["name"])

    # --- creating

    def test_the_same_fields_as_a_validated_profile_give_that_profile(self):
        existing = self.make()
        answer = self.post(self.alice)
        self.assertEqual(answer.status_code, 200)  # not 201: nothing was made
        self.assertEqual(answer.data["id"], existing.id)
        self.assertEqual(AnimalProfile.objects.count(), 1)

    def test_a_difference_in_a_free_text_makes_a_profile_of_its_own(self):
        self.make()
        answer = self.post(self.alice, treatment="saline")
        self.assertNotEqual(answer.data["id"], AnimalProfile.objects.first().id)
        self.assertEqual(AnimalProfile.objects.count(), 2)

    def test_a_draft_of_somebody_else_is_neither_reused_nor_shown(self):
        theirs = self.make(status="draft", user=self.bob)
        answer = self.post(self.alice)
        self.assertEqual(answer.status_code, 201)
        self.assertNotEqual(answer.data["id"], theirs.id)
        self.assertEqual(answer.data["status"], "draft")
        self.assertEqual(AnimalProfile.objects.count(), 2)

    # --- the table of choice

    def test_the_table_can_be_sorted_on_a_column(self):
        self.make(genotype="b")
        self.make(genotype="c")
        self.make(genotype="a")

        def genotypes(ordering):
            answer = self.as_user(self.alice).get(
                "/api/animalprofile/", {"ordering": ordering}
            )
            return [p["genotype"] for p in answer.json()["results"]]

        self.assertEqual(genotypes("genotype"), ["a", "b", "c"])
        self.assertEqual(genotypes("-genotype"), ["c", "b", "a"])
        self.assertEqual(len(genotypes("password")), 3)  # not a column: ignored

    # --- changing

    def test_a_change_to_the_fields_of_a_validated_profile_is_refused(self):
        self.make(genotype="WT")
        mine = self.make(status="draft", user=self.alice)
        answer = self.as_user(self.alice).patch(
            f"/api/animalprofile/{mine.id}/", {"genotype": "WT"}, format="json"
        )
        self.assertEqual(answer.status_code, 400)
        mine.refresh_from_db()
        self.assertEqual(mine.genotype, "Fmr1 KO")

    def test_submitting_a_profile_is_not_blocked_by_a_look_alike(self):
        self.make()
        mine = self.make(
            status="draft", user=self.alice
        )  # same fields, older than the rule
        answer = self.as_user(self.alice).patch(
            f"/api/animalprofile/{mine.id}/",
            {"status": "waiting validation"},
            format="json",
        )
        self.assertEqual(answer.status_code, 200)

    def test_a_change_gives_a_new_name(self):
        mine = self.make(status="draft", user=self.alice)
        before = mine.name
        self.as_user(self.alice).patch(
            f"/api/animalprofile/{mine.id}/", {"diet": "chow"}, format="json"
        )
        mine.refresh_from_db()
        self.assertNotEqual(mine.name, before)
        self.assertIn("chow", mine.name)

    # --- validating

    def test_validating_a_copy_merges_it_into_the_validated_profile(self):
        kept = self.make()
        copy = self.make(status="waiting validation", user=self.alice)
        subject = Subject.objects.create(name="s1", animal_profile=copy)
        session = RecordingSession.objects.create(
            name="sess", is_multiple=True, created_by=self.alice
        )
        session.animal_profiles.add(copy)
        kind = ContentType.objects.get_for_model(AnimalProfile)
        Favorite.objects.create(user=self.alice, content_type=kind, object_id=copy.pk)
        Favorite.objects.create(user=self.bob, content_type=kind, object_id=copy.pk)
        Favorite.objects.create(user=self.bob, content_type=kind, object_id=kept.pk)

        self.assertEqual(validate_entries([("animal profile", copy)]), 1)

        self.assertEqual(list(AnimalProfile.objects.all()), [kept])
        subject.refresh_from_db()
        self.assertEqual(subject.animal_profile, kept)
        self.assertEqual(list(session.animal_profiles.all()), [kept])
        # Alice keeps her favorite, on the kept one; Bob already had it: no double
        self.assertEqual(
            sorted(
                Favorite.objects.filter(
                    content_type=kind, object_id=kept.pk
                ).values_list("user__username", flat=True)
            ),
            ["alice", "bob"],
        )
        self.assertEqual(Favorite.objects.count(), 2)

    def test_validating_a_profile_nobody_has_yet_just_validates_it(self):
        mine = self.make(status="waiting validation", user=self.alice)
        validate_entries([("animal profile", mine)])
        mine.refresh_from_db()
        self.assertEqual(mine.status, "validated")

    # --- the existing profiles

    def old(self, name, status="validated", **extra):
        """A profile as it was before: typed name, no fingerprint."""
        profile = self.make(status=status, **extra)
        AnimalProfile.objects.filter(pk=profile.pk).update(name=name, fingerprint="")
        return profile

    def rekey(self, *args):
        out = StringIO()
        call_command("rekey_animal_profiles", *args, stdout=out)
        return out.getvalue()

    def test_the_command_shows_and_writes_nothing_without_apply(self):
        a, b = self.old("one"), self.old("two")
        report = self.rekey()
        self.assertIn("1 validated duplicates to merge", report)
        self.assertEqual(
            sorted(AnimalProfile.objects.values_list("name", flat=True)), ["one", "two"]
        )
        a.refresh_from_db(), b.refresh_from_db()
        self.assertEqual((a.fingerprint, b.fingerprint), ("", ""))

    def test_the_command_names_the_profiles_and_merges_the_validated_copies(self):
        first = self.old("one")
        copy = self.old("two")
        subject = Subject.objects.create(name="s1", animal_profile=copy)
        waiting = self.old("three", status="waiting validation")  # not merged here
        other = self.old("four", genotype="WT")
        self.rekey("--apply")
        self.assertEqual(
            set(AnimalProfile.objects.values_list("pk", flat=True)),
            {first.pk, waiting.pk, other.pk},
        )
        subject.refresh_from_db()
        self.assertEqual(subject.animal_profile, first)
        for profile in AnimalProfile.objects.all():
            self.assertTrue(profile.fingerprint)
            self.assertTrue(profile.name.endswith(profile.fingerprint[:6]))
        # run again: nothing left to do
        self.assertIn("0 to rename, 0 validated duplicates", self.rekey())

    def test_the_command_tells_what_differs_only_by_the_case(self):
        self.old("one", genotype="Wt")
        self.old("two", genotype="wt")
        self.assertIn("only the case differs", self.rekey())

    def test_the_fingerprints_follow_the_terms_linked_in_bulk(self):
        mine = self.make()
        before = mine.fingerprint
        from mousetube_api.models import OntologyTerm

        term = OntologyTerm.objects.create(
            curie="CHEBI:1", label="x", ontology="chebi", iri="http://x/1"
        )
        AnimalProfile.objects.filter(pk=mine.pk).update(treatment_term=term)
        self.assertEqual(animal_profiles.refresh_fingerprints(), 1)
        mine.refresh_from_db()
        self.assertNotEqual(mine.fingerprint, before)
