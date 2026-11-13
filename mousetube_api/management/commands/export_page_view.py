import os

from django.core.management.base import BaseCommand
from django.template.loader import render_to_string
from django.utils import timezone

from mousetube_api.models import PageView

LOGS_DIR = "logs/"


class Command(BaseCommand):
    help = "Export page views to a static HTML report"

    def handle(self, *args, **kwargs):
        year = timezone.now().year
        filename = f"stats_{year}.html"
        output_path = os.path.join(LOGS_DIR, filename)

        # Get all visites for the current year
        views = PageView.objects.filter(date__year=year).order_by("date")

        # Organize data by date and path for easy filtering
        data = [
            {"path": view.path, "date": view.date.isoformat(), "count": view.count}
            for view in views
        ]

        context = {
            "rows": data,
            "year": year,
            "generated": timezone.now().strftime("%d %b %Y, %H:%M"),
        }
        html = render_to_string("stats/report.html", context)
        for name in (filename, "latest.html"):
            with open(os.path.join(LOGS_DIR, name), "w") as f:
                f.write(html)

        self.stdout.write(self.style.SUCCESS(f"Exported stats to {output_path}"))
