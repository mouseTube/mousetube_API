"""Conversions of existing rows that a change of structure needs.

The migrations are generated when the container starts and are not versioned, so they can
only change the structure. What has to happen to the rows already in the database lives
here, and `manage.py normalize_data` runs it after `migrate`. Every step only touches rows
that still need it: running it again changes nothing.
"""

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import F

from mousetube_api.models import (
    AnimalProfile,
    Contact,
    PageView,
    Species,
    Strain,
    UserProfile,
)
from mousetube_api.utils.ontologies import (
    AGE_TERMS,
    GENERIC_AGE_TERMS,
    MOUSE,
    SEX_TERMS,
    SPECIES_TERMS,
    known_term,
)
from mousetube_api.utils.page_views import normalize_page_path


def normalize_statuses():
    """Contact, Strain and AnimalProfile once spelled it "waiting_validation": the other
    catalogs use a space. One spelling for all."""
    changed = 0
    for model in (Contact, Strain, AnimalProfile):
        changed += model.objects.filter(status="waiting_validation").update(
            status="waiting validation"
        )
    return changed


def create_missing_profiles():
    """An account created before the profile existed has none, and the account page then
    shows nothing: give it an empty one."""
    created = 0
    for user in get_user_model().objects.filter(user_profile__isnull=True):
        UserProfile.objects.create(user=user)
        created += 1
    return created


def link_known_terms():
    """Species, the sex and the age class (of mice) of animal profiles get their ontology
    term (no network call)."""
    linked = 0
    for name, (curie, label) in SPECIES_TERMS.items():
        linked += Species.objects.filter(
            name__iexact=name, ontology_term__isnull=True
        ).update(ontology_term=known_term(curie, label))
    for sex, (curie, label) in SEX_TERMS.items():
        linked += AnimalProfile.objects.filter(sex=sex, sex_term__isnull=True).update(
            sex_term=known_term(curie, label)
        )
    for age, (curie, label) in AGE_TERMS.items():
        linked += AnimalProfile.objects.filter(
            age=age,
            age_term__isnull=True,
            strain__species__name__iexact=MOUSE,
        ).update(age_term=known_term(curie, label))
    # the other species (rat...): the generic stage of the same name
    for age, (curie, label) in GENERIC_AGE_TERMS.items():
        linked += (
            AnimalProfile.objects.filter(age=age, age_term__isnull=True)
            .exclude(strain__species__name__iexact=MOUSE)
            .update(age_term=known_term(curie, label))
        )
    return linked


@transaction.atomic
def merge_page_view_paths():
    """Rows kept before the secret was dropped from the path: fold them into one page a day."""
    merged = 0
    for view in PageView.objects.order_by("pk"):
        clean = normalize_page_path(view.path)
        if clean == view.path:
            continue
        target = PageView.objects.filter(path=clean, date=view.date).first()
        if target:
            PageView.objects.filter(pk=target.pk).update(count=F("count") + view.count)
            view.delete()
        else:
            # renamed in place: `date` is set by the model on creation, so no new row
            PageView.objects.filter(pk=view.pk).update(path=clean)
        merged += 1
    return merged


def run_all():
    return {
        "statuses renamed": normalize_statuses(),
        "profiles created": create_missing_profiles(),
        "terms linked": link_known_terms(),
        "page views merged": merge_page_view_paths(),
    }
