"""Keep the database schema page of the documentation in step with the models."""

from django.core.management.base import BaseCommand, CommandError

from mousetube_api.utils import schema_docs


class Command(BaseCommand):
    help = (
        "Add the tables and fields that are new to docs/assets/schema/schema-<lang>.json, remove the "
        "ones that are gone and fix the types. The descriptions of what is new are marked TODO: write "
        "them (in both languages)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--check",
            action="store_true",
            help="Only say what differs, change nothing (exit with an error if something does).",
        )

    def handle(self, *args, **options):
        if options["check"]:
            problems = schema_docs.check()
            for problem in problems:
                self.stdout.write(problem)
            if problems:
                raise CommandError(
                    f"{len(problems)} difference(s): run `python manage.py sync_schema_docs`."
                )
            self.stdout.write(self.style.SUCCESS("The schema page follows the models."))
            return
        for lang in schema_docs.LANGUAGES:
            data = schema_docs.read(lang)
            changes = schema_docs.sync(data, lang)
            schema_docs.write(lang, data)
            todo = [
                c
                for c in changes
                if c.endswith(("describe the field", "describe the table"))
            ]
            self.stdout.write(
                f"{lang}: {len(changes)} change(s), {len(todo)} description(s) to write"
            )
            for change in changes:
                self.stdout.write(f"  {change}")
