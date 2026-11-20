from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Count

from mousetube_api.models import Dataset, File, RecordingSession


class Command(BaseCommand):
    help = (
        "A recording imported twice (once in a dataset, once with its original session) "
        "appears twice and the dataset copy belongs to the administrator who imported it. "
        "Keeps the dataset copy (the more complete one), gives it the owner of the original "
        "copy, takes over the animals and the download counter of the original and removes "
        "it. Shows what it would do unless --apply is given."
    )

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="write the changes")

    def handle(self, *args, apply=False, **options):
        in_dataset = set(
            Dataset.objects.values_list("recording_session_list__id", flat=True)
        )
        names = (
            File.objects.values("name")
            .annotate(n=Count("id"))
            .filter(n=2)
            .values_list("name", flat=True)
        )
        merged = 0
        for name in names:
            copies = list(
                File.objects.filter(name=name).select_related(
                    "recording_session__created_by", "created_by"
                )
            )
            dataset_copy = [f for f in copies if f.recording_session_id in in_dataset]
            original = [f for f in copies if f.recording_session_id not in in_dataset]
            if len(dataset_copy) != 1 or len(original) != 1:
                continue
            keep, drop = dataset_copy[0], original[0]
            owner = drop.created_by or drop.recording_session.created_by
            self.stdout.write(
                f"{name}: keeps file {keep.pk} (session {keep.recording_session_id}, "
                f"owner {keep.created_by}), removes file {drop.pk} "
                f"(session {drop.recording_session_id}); owner becomes {owner}"
            )
            if apply:
                with transaction.atomic():
                    keep.subjects.add(*drop.subjects.all())
                    # queryset updates: no validation of an old row on the way
                    File.objects.filter(pk=keep.pk).update(
                        downloads=max(keep.downloads or 0, drop.downloads or 0),
                        created_by=owner,
                    )
                    RecordingSession.objects.filter(
                        pk=keep.recording_session_id
                    ).update(created_by=owner)
                    drop.delete()
            merged += 1
        verb = "merged" if apply else "would be merged (run again with --apply)"
        self.stdout.write(self.style.SUCCESS(f"{merged} {verb}"))
