from django.core.management.base import BaseCommand

from mousetube_api.models import File
from mousetube_api.utils.zenodo_files import (
    ZenodoBusy,
    ZenodoUnavailable,
    file_url,
    match_name,
    record_files,
    record_of,
)


class Command(BaseCommand):
    help = (
        "Replace the links to a whole Zenodo record (.../files-archive: the zip of every file of the "
        "record, which Zenodo no longer gives to programs) by the link of the file of the row. The "
        "name is read in the record (Zenodo tells capitals apart: a row can have another case than "
        "the file); a row whose file is not in the record is left as it is. Shows the changes; "
        "--apply writes them. Run check_dead_links afterwards."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Write the new links (without it, nothing is changed)",
        )

    def handle(self, *args, **options):
        changed = skipped = 0
        for file in File.objects.filter(link__endswith="/files-archive").order_by("id"):
            record = record_of(file.link)
            name = self.name_in_record(record, file.name) if record else None
            if not name:
                skipped += 1
                self.stdout.write(f"{file.pk}: left as it is ({self.why}): {file.link}")
                continue
            link = file_url(*record, name)
            self.stdout.write(f"{file.pk}: {file.link} -> {link}")
            if options["apply"]:
                File.objects.filter(pk=file.pk).update(link=link)
            changed += 1
        verb = "changed" if options["apply"] else "to change (run with --apply)"
        self.stdout.write(f"{changed} {verb}, {skipped} left as they are.")

    def name_in_record(self, record, name):
        """The name of the file in the record (the list is kept an hour: one request per record)."""
        self.why = ""
        if not name:
            self.why = "the row has no name"
            return None
        try:
            names = [entry["name"] for entry in record_files(*record)]
        except ZenodoBusy:
            self.why = "too many requests to Zenodo, run it again in a minute"
            return None
        except ZenodoUnavailable:
            self.why = "Zenodo does not answer"
            return None
        found = match_name(names, name)
        if not found:
            self.why = "no such file in the record"
        return found
