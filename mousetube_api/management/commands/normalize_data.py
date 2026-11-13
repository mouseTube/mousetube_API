from django.core.management.base import BaseCommand

from mousetube_api.utils.data_upgrades import run_all


class Command(BaseCommand):
    help = (
        "Convert the rows that a change of structure leaves behind (status spelling, "
        "missing profiles, ontology terms of known species and sexes). Safe to run again."
    )

    def handle(self, *args, **options):
        for step, count in run_all().items():
            self.stdout.write(f"{step}: {count}")
        self.stdout.write(self.style.SUCCESS("Done"))
