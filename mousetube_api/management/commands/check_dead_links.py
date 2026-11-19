import logging

from django.core.management.base import BaseCommand

from mousetube_api.utils import link_check

logger = logging.getLogger("check_dead_links")


class Command(BaseCommand):
    help = (
        "Check for dead links in mousetube files (an administrator can also start it from the "
        "profile page)"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--fill_name",
            action="store_true",
            help="Retrieve the name of the file from the downloaded file",
        )

    def handle(self, *args, **options):
        logger.info("Starting dead link check...")
        counts = link_check.run(fill_name=options["fill_name"])
        logger.info(
            "Total: %(total)s, ok: %(ok)s, broken: %(broken)s, skipped: %(skipped)s, "
            "busy: %(unknown)s",
            counts,
        )
        logger.info("Dead link check finished.")
