"""An animal profile is told by what it says, not by a name somebody chose.

Its fingerprint is a hash of every field (the text as typed, without the stray spaces, and the
terms of the vocabularies): the same fields give the same fingerprint, the slightest difference
gives another one, so nothing is lost by merging and nothing is forbidden. The name is made from
the fields and ends with the start of the fingerprint, so two profiles never look the same.

- creating a profile whose fingerprint belongs to a validated profile gives that profile back
- validating a profile whose fingerprint belongs to a validated profile merges it into that one
  (the subjects, the sessions and the favorites follow)
"""

import hashlib
import json

from django.db import transaction

VALIDATED = "validated"

TEXT_FIELDS = ("sex", "age", "genotype", "treatment", "diet", "description")
# sex_term is not told: it follows the sex, nobody chooses it
TERM_FIELDS = ("age_term", "treatment_term", "diet_term")
FIELDS = ("strain",) + TEXT_FIELDS + TERM_FIELDS

SEX_LETTER = {"male": "M", "female": "F"}
NAME_LENGTH = 230  # the rest of the 255 characters is the end of the name: " #" + 6


def clean(text):
    """The text without the spaces at its ends and the doubled ones; the case is kept (the
    nomenclature of genes may depend on it)."""
    return " ".join(str(text or "").split())


def values_of(profile):
    """The fields that tell a profile, from a saved (or unsaved) profile."""
    values = {field: getattr(profile, field) for field in TEXT_FIELDS}
    for field in ("strain",) + TERM_FIELDS:
        values[field] = getattr(profile, field)
    return values


def _age_term(values):
    """The stage chosen for the age, when it says more than the age class does: the class has
    its own term (given to every profile alike), which tells nothing more."""
    from mousetube_api.utils.ontologies import AGE_TERMS, GENERIC_AGE_TERMS, MOUSE

    term = values.get("age_term")
    if term is None:
        return None
    species = getattr(getattr(values.get("strain"), "species", None), "name", "")
    known = AGE_TERMS if (species or "").strip().lower() == MOUSE else GENERIC_AGE_TERMS
    default = known.get(values.get("age"))
    return None if default and term.curie == default[0] else term.pk


def fingerprint(values, fold_case=False):
    """The fingerprint of a profile: `values` maps the fields to their value, a related object
    or its identifier (what is missing counts as empty). `fold_case` is only for reports."""
    parts = []
    for field in FIELDS:
        value = values.get(field)
        if field in TEXT_FIELDS:
            value = clean(value)
            value = value.casefold() if fold_case else value
        elif field == "age_term":
            value = _age_term(values)
        else:
            value = getattr(value, "pk", value)
        parts.append(value)
    return hashlib.sha256(json.dumps(parts).encode()).hexdigest()


def display_name(profile, print_=None):
    """The name of a profile: what it says, shortened, then the start of its fingerprint."""
    bits = [
        profile.strain.name,
        SEX_LETTER.get(profile.sex, profile.sex),
        profile.age,
        profile.genotype,
        profile.treatment,
        profile.diet,
    ]
    text = " · ".join(b for b in map(clean, bits) if b)
    return f"{text[:NAME_LENGTH]} #{(print_ or fingerprint(values_of(profile)))[:6]}"


def refresh_fingerprints():
    """After terms were linked in bulk (queryset updates do not go through `save`): the profiles
    that already have a fingerprint follow. The others wait for `rekey_animal_profiles`, which
    gives them their generated name."""
    from mousetube_api.models import AnimalProfile

    changed = 0
    for profile in AnimalProfile.objects.exclude(fingerprint="").select_related(
        "strain__species", "age_term", "treatment_term", "diet_term"
    ):
        print_ = fingerprint(values_of(profile))
        name = display_name(profile, print_)
        if (print_, name) != (profile.fingerprint, profile.name):
            AnimalProfile.objects.filter(pk=profile.pk).update(
                fingerprint=print_, name=name
            )
            changed += 1
    return changed


def validated_twin(print_, exclude=None):
    """The validated profile that has this fingerprint, or `None`."""
    from mousetube_api.models import AnimalProfile

    if not print_:  # not computed yet (a profile older than the fingerprints)
        return None
    twins = AnimalProfile.objects.filter(fingerprint=print_, status=VALIDATED)
    if exclude is not None:
        twins = twins.exclude(pk=exclude)
    return twins.order_by("pk").first()


@transaction.atomic
def merge_into(keep, duplicate):
    """Everything that used `duplicate` uses `keep`, then `duplicate` is removed."""
    from django.contrib.contenttypes.models import ContentType

    from mousetube_api.models import AnimalProfile, Favorite, RecordingSession, Subject

    Subject.objects.filter(animal_profile=duplicate).update(animal_profile=keep)
    for session in RecordingSession.objects.filter(animal_profiles=duplicate):
        session.animal_profiles.add(keep)
        session.animal_profiles.remove(duplicate)
    kind = ContentType.objects.get_for_model(AnimalProfile)
    favorites = Favorite.objects.filter(content_type=kind, object_id=duplicate.pk)
    already = Favorite.objects.filter(content_type=kind, object_id=keep.pk).values(
        "user"
    )
    favorites.exclude(user__in=already).update(object_id=keep.pk)
    favorites.delete()  # the ones whose user already has the kept profile as favorite
    duplicate.delete()
