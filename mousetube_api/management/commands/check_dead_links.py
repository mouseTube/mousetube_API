import logging
import os
import time
from urllib.parse import unquote, urlparse

import requests
from django.core.management.base import BaseCommand

from mousetube_api.models import File

logger = logging.getLogger("check_dead_links")


class Command(BaseCommand):
    help = "Check for dead links in mousetube files"

    def add_arguments(self, parser):
        # Add command line arguments
        parser.add_argument(
            "--fill_name",
            action="store_true",
            help="Retrieve the name of the file from the downloaded file",
        )

    def handle(self, *args, **options):
        logger.info("Starting dead link check...")

        fill_name_mode = options["fill_name"]
        files = File.objects.exclude(link__isnull=True).exclude(link="")

        for file in files:
            url = file.link
            parsed = urlparse(url)

            # Check if the URL is valid
            if not url.startswith(("http://", "https://")):
                logger.error(f"Invalid URL format: {url}")
                continue

            # Skip local links (localhost, 127.0.0.1)
            if parsed.hostname in ["localhost", "127.0.0.1"]:
                logger.info(f"Skipping local link: {url}")
                continue

            try:
                # Send a HEAD request to avoid downloading the entire file
                time.sleep(1)  # Sleep for 1 second to avoid overwhelming the server

                # Check if the URL is reachable
                # Use a timeout to avoid hanging indefinitely
                # Use allow_redirects=True to follow redirects
                # Try HEAD first
                response = requests.head(url, allow_redirects=True, timeout=5)
                if response.status_code >= 400:
                    # If HEAD fails, try GET
                    response = requests.get(
                        url, allow_redirects=True, timeout=10, stream=True
                    )
                link_alive = response.status_code < 400
                if response.status_code == 429:
                    logger.warning(
                        f"Rate limite reached with status code {response.status_code}: {url}"
                    )
                    continue
            except requests.RequestException as e:
                # Log broken links
                logger.error(f"BROKEN: {url} (Exception: {e})")
                link_alive = False

            # If the link is alive
            if link_alive:
                logger.info(f"OK: {url} {response.status_code}")
                if not file.is_valid_link:
                    file.is_valid_link = True
                    file.save()

                # Fill name if requested
                if fill_name_mode and not file.name:
                    filename = self.extract_filename(response, url)
                    if filename:
                        logger.info(f"Setting filename: {filename}")
                        file.name = filename
                        file.save()
            else:
                # If the link is dead
                logger.error(f"BROKEN: {url} {response.status_code}")
                if file.is_valid_link:
                    file.is_valid_link = False
                    file.save()

        files = File.objects.exclude(link__isnull=True).exclude(link="")
        valid_files = files.filter(is_valid_link=True)
        invalid_files = files.filter(is_valid_link=False)
        logger.info(f"Total files: {files.count()}")
        logger.info(f"Valid files: {valid_files.count()}")
        logger.info(f"Invalid files: {invalid_files.count()}")
        logger.info("Dead link check finished.")

    def extract_filename(self, response, url):
        """
        Try to extract filename from Content-Disposition header, fall back to URL path.
        """
        content_disposition = response.headers.get("content-disposition")
        if content_disposition:
            parts = content_disposition.split(";")
            for part in parts:
                if "filename=" in part:
                    filename = part.strip().split("filename=")[-1]
                    filename = filename.strip('"')
                    return filename

        # Fallback to using the last part of the URL path
        path = unquote(urlparse(url).path)
        filename = os.path.basename(path)
        return filename if filename else None
