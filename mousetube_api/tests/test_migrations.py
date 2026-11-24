"""The migrations are versioned: a change of the models comes with its migration."""

from io import StringIO

from django.core.management import call_command
from django.test import TestCase


class MigrationsTests(TestCase):
    def test_no_model_change_is_missing_its_migration(self):
        out = StringIO()
        try:
            call_command("makemigrations", "--check", "--dry-run", stdout=out)
        except SystemExit:
            self.fail(f"run `makemigrations` and commit the file:\n{out.getvalue()}")


class WorkerResilienceTests(TestCase):
    def test_file_processing_is_given_back_when_the_worker_dies(self):
        from mousetube_api.tasks import process_file

        self.assertTrue(process_file.acks_late)
        self.assertTrue(process_file.reject_on_worker_lost)
