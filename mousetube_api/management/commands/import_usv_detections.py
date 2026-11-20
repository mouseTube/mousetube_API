import os
import re

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from mousetube_api.models import File, UsvDetection
from mousetube_api.utils import usv

RESULT_FILES = {
    "usvseg": "usvseg.csv",
    "deepsqueak": "deepsqueak.xlsx",
    "avisoft": "avisoft.csv",
    "sonotrack": "sonotrack.txt",
    "ratrec": "ratrec.csv",
    "usvtoolbox": "usvtoolbox.csv",
}
# how the settings file names the tools ("USVSeg", "USV Toolbox"...); only the automatic Avisoft run
LABELS = {"usvtoolbox": "usv toolbox", "avisoft": "avisoft (automatic"}


def read_parameters(folder):
    """`parameters_analysis.csv` lists each tool with its version and settings: label;settings."""
    found = {}
    path = os.path.join(folder, "parameters_analysis.csv")
    if not os.path.exists(path):
        return found
    with open(path, encoding="utf-8", errors="replace") as handle:
        for line in handle:
            label, _, settings = line.rstrip("\n").partition(";")
            name = label.strip().lower()
            for tool in RESULT_FILES:
                if name.startswith(LABELS.get(tool, tool)):
                    version = re.search(r"\d+(\.\d+)+", label)
                    found[tool] = (
                        version.group() if version else "",
                        settings.strip().strip('"'),
                    )
    return found


class Command(BaseCommand):
    help = (
        "Link the results of USV detectors to the files they were run on. --dir holds one folder per "
        "recording, named like the file without .wav, with the results of each tool "
        "(usvseg.csv, deepsqueak.xlsx, avisoft.csv, sonotrack.txt, ratrec.csv, usvtoolbox.csv) and "
        "parameters_analysis.csv. Running it again replaces the same results."
    )

    def add_arguments(self, parser):
        parser.add_argument("--dir", required=True, help="Folder of the results.")
        parser.add_argument("--tools", default=",".join(RESULT_FILES))
        parser.add_argument("--created-by", help="Username recorded as the importer.")
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        tools = [t.strip() for t in options["tools"].split(",") if t.strip()]
        unknown = [t for t in tools if t not in RESULT_FILES]
        if unknown:
            raise CommandError(f"Unknown tool(s): {', '.join(unknown)}.")
        if not os.path.isdir(options["dir"]):
            raise CommandError(f"{options['dir']} is not a folder.")
        user = None
        if options["created_by"]:
            user = (
                get_user_model().objects.filter(username=options["created_by"]).first()
            )
            if user is None:
                raise CommandError(f"User '{options['created_by']}' does not exist.")

        done = skipped = 0
        with transaction.atomic():
            for stem in sorted(os.listdir(options["dir"])):
                folder = os.path.join(options["dir"], stem)
                if not os.path.isdir(folder):
                    continue
                files = list(File.objects.filter(name__in=[f"{stem}.wav", stem]))
                if len(files) != 1:
                    self.stdout.write(
                        f"  skipped {stem}: {len(files)} file(s) of that name in the database"
                    )
                    skipped += 1
                    continue
                file = files[0]
                parameters = read_parameters(folder)
                for tool in tools:
                    path = os.path.join(folder, RESULT_FILES[tool])
                    if not os.path.exists(path):
                        continue
                    with open(path, "rb") as handle:
                        calls = usv.parse(tool, handle.read())
                    version, settings = parameters.get(tool, ("", ""))
                    UsvDetection.objects.update_or_create(
                        file=file,
                        tool=tool,
                        defaults={
                            "tool_version": version,
                            "parameters": settings,
                            "reference": usv.TOOLS[tool]["reference"],
                            "calls": calls,
                            "summary": usv.summarize(
                                calls
                            ),  # the span is the one the calls cover
                            "source": f"results published with the recording: {stem}",
                            "created_by": user,
                        },
                    )
                    done += 1
                    self.stdout.write(f"  {stem}: {tool} {len(calls)} calls")
            if options["dry_run"]:
                transaction.set_rollback(True)
        label = "DRY RUN (rolled back)" if options["dry_run"] else "Done"
        self.stdout.write(
            self.style.SUCCESS(f"{label}: {done} results, {skipped} recordings skipped")
        )
