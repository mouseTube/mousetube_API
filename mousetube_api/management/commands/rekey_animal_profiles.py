from collections import defaultdict

from django.core.management.base import BaseCommand
from django.db import transaction

from mousetube_api.models import AnimalProfile
from mousetube_api.utils import animal_profiles

VALIDATED = "validated"


class Command(BaseCommand):
    help = (
        "Gives every animal profile its fingerprint and the name made from its fields (the "
        "names typed by hand are replaced), and merges the validated profiles that say exactly "
        "the same thing: the subjects, sessions and favorites of the others move to the oldest "
        "one. Profiles that are not validated are never merged here (an administrator decides "
        "when validating them). Shows what it would do unless --apply is given."
    )

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="write the changes")

    def handle(self, *args, apply=False, **options):
        profiles = list(
            AnimalProfile.objects.select_related(
                "strain__species", "age_term", "treatment_term", "diet_term"
            ).order_by("pk")
        )
        groups, folded = defaultdict(list), defaultdict(set)
        renames = 0
        for profile in profiles:
            values = animal_profiles.values_of(profile)
            print_ = animal_profiles.fingerprint(values)
            groups[print_].append(profile)
            folded[animal_profiles.fingerprint(values, fold_case=True)].add(print_)
            profile._new = (print_, animal_profiles.display_name(profile, print_))
            if (profile.fingerprint, profile.name) != profile._new:
                renames += 1

        same = {p: g for p, g in groups.items() if len(g) > 1}
        merges = []
        for group in same.values():
            validated = [p for p in group if p.status == VALIDATED]
            for duplicate in validated[1:]:
                merges.append((validated[0], duplicate))
            kept = ", ".join(f"#{p.pk} ({p.status})" for p in group)
            self.stdout.write(f"the same fields: {kept}: {group[0]._new[1]}")
        for prints in folded.values():
            if len(prints) > 1:
                names = " | ".join(groups[p][0]._new[1] for p in sorted(prints))
                self.stdout.write(f"only the case differs (kept apart): {names}")

        self.stdout.write(
            f"{len(profiles)} profiles, {renames} to rename, "
            f"{len(merges)} validated duplicates to merge"
        )
        if not apply:
            self.stdout.write(
                self.style.SUCCESS("Nothing written (run again with --apply)")
            )
            return
        with transaction.atomic():
            for profile in profiles:
                AnimalProfile.objects.filter(pk=profile.pk).update(
                    fingerprint=profile._new[0], name=profile._new[1]
                )
            for keep, duplicate in merges:
                animal_profiles.merge_into(keep, duplicate)
        self.stdout.write(self.style.SUCCESS("Done"))
