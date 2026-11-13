from django.core.management.base import BaseCommand

from mousetube_api.models import AnimalProfile, Laboratory, Species
from mousetube_api.utils import ontologies
from mousetube_api.utils.ontologies import (
    OntologyError,
    get_or_create_term,
    match_label,
    match_organization,
)

# (model, free text field, term field, vocabulary): a term is linked only when its label is
# exactly the text written there
LABEL_MATCHES = [
    (Species, "name", "ontology_term", "species"),
    (AnimalProfile, "age", "age_term", "age"),
    (AnimalProfile, "treatment", "treatment_term", "treatment"),
]


class Command(BaseCommand):
    help = (
        "Link the data already in the database to ontology terms when the match is "
        "certain: exact label for species, age and treatment; the match the ROR registry "
        "is sure about for laboratories. Shows what it would do unless --apply is given."
    )

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="write the links")

    def handle(self, *args, apply=False, **options):
        ontologies.TIMEOUT = (
            30  # nobody waits for a command: be patient with a slow service
        )
        linked = 0
        for model, text_field, term_field, vocabulary in LABEL_MATCHES:
            rows = (
                model.objects.filter(**{f"{term_field}__isnull": True})
                .exclude(**{f"{text_field}__isnull": True})
                .exclude(**{text_field: ""})
            )
            for text in rows.values_list(text_field, flat=True).distinct():
                try:
                    found = match_label(vocabulary, text)
                except OntologyError as exc:
                    self.stderr.write(f"{vocabulary} '{text}': {exc}")
                    continue
                if found:
                    linked += self._link(
                        model, text_field, text, term_field, vocabulary, found, apply
                    )
                else:
                    self.stdout.write(f"  no exact term for {vocabulary} '{text}'")

        for lab in Laboratory.objects.filter(organization__isnull=True):
            text = ", ".join(x for x in (lab.institution, lab.name) if x)
            try:
                found = match_organization(text)
            except OntologyError as exc:
                self.stderr.write(f"laboratory {lab.pk}: {exc}")
                continue
            if not found:
                self.stdout.write(
                    f"  no sure organization for laboratory {lab.pk}: {text[:70]}"
                )
                continue
            self.stdout.write(
                f"laboratory {lab.pk}: {text[:60]} -> {found['label']} ({found['curie']})"
            )
            if apply:
                try:
                    lab.organization = get_or_create_term(
                        "organization", found["curie"]
                    )
                    lab.save(update_fields=["organization"])
                except OntologyError as exc:
                    self.stderr.write(str(exc))
                    continue
            linked += 1

        verb = "linked" if apply else "would be linked (run again with --apply)"
        self.stdout.write(self.style.SUCCESS(f"{linked} {verb}"))

    def _link(self, model, text_field, text, term_field, vocabulary, found, apply):
        rows = model.objects.filter(**{text_field: text, f"{term_field}__isnull": True})
        self.stdout.write(
            f"{vocabulary} '{text}' -> {found['label']} ({found['curie']}): {rows.count()}"
        )
        if apply:
            term = get_or_create_term(vocabulary, found["curie"])
            rows.update(**{term_field: term})
        return rows.count() if not apply else 1
