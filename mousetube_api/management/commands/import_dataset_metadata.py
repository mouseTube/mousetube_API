import json

import requests
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from mousetube_api.utils.dataset_metadata import import_datasets


class Command(BaseCommand):
    help = (
        "Create datasets, with their sessions and files, from a metadata JSON: the API of "
        "mouseTube 0.5 (https://mousetube.fr/api/dataset/) or this API's /api/dataset/metadata/."
    )

    def add_arguments(self, parser):
        source = parser.add_mutually_exclusive_group(required=True)
        source.add_argument("--url", help="URL returning the JSON (http or https).")
        source.add_argument("--file", help="Path of a JSON file.")
        parser.add_argument(
            "--created-by", help="Username set as creator of what is created."
        )
        parser.add_argument(
            "--dry-run", action="store_true", help="Do everything, then roll back."
        )

    def handle(self, *args, **options):
        if options["url"]:
            if not options["url"].startswith(("http://", "https://")):
                raise CommandError("--url must start with http:// or https://")
            try:
                response = requests.get(options["url"], timeout=60)
                response.raise_for_status()
                payload = response.json()
            except (requests.RequestException, ValueError) as exc:
                raise CommandError(f"Could not read {options['url']}: {exc}") from exc
        else:
            try:
                with open(options["file"], encoding="utf-8") as fh:
                    payload = json.load(fh)
            except (OSError, ValueError) as exc:
                raise CommandError(f"Could not read {options['file']}: {exc}") from exc

        users = get_user_model().objects
        if options["created_by"]:
            created_by = users.filter(username=options["created_by"]).first()
            if created_by is None:
                raise CommandError(f"User '{options['created_by']}' does not exist.")
        else:
            # sessions must have a creator: default to the first superuser
            created_by = (
                users.filter(is_superuser=True, is_active=True).order_by("pk").first()
            )
            if created_by is None:
                raise CommandError("No superuser found: pass --created-by USERNAME.")
        self.stdout.write(f"Creator of the imported records: {created_by.username}")

        try:
            stats = import_datasets(payload, created_by, options["dry_run"])
        except (KeyError, TypeError) as exc:
            raise CommandError(f"Unexpected JSON structure: {exc!r}") from exc

        for model, counts in stats.items():
            self.stdout.write(
                f"{model:16} created {counts['created']:4}   reused {counts['existing']:4}"
            )
        label = "DRY RUN (rolled back)" if options["dry_run"] else "Done"
        self.stdout.write(self.style.SUCCESS(label))
