from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from mousetube_api.models import Dataset, RecordingSession


class Command(BaseCommand):
    help = "Create a dataset from a list of RecordingSession IDs or names."

    def add_arguments(self, parser):
        parser.add_argument(
            "--name", type=str, required=True, help="Name of the dataset to create."
        )

        parser.add_argument(
            "--description", type=str, help="Description of the dataset to create."
        )

        parser.add_argument("--doi", type=str, help="DOI of the dataset to create.")

        parser.add_argument("--link", type=str, help="Link of the dataset to create.")

        parser.add_argument(
            "--sessions", nargs="*", type=int, help="List of RecordingSession IDs."
        )

        parser.add_argument(
            "--session-names",
            nargs="*",
            type=str,
            help="List of RecordingSession names.",
        )

        parser.add_argument(
            "--file",
            type=str,
            help=(
                "Path to a text file containing RecordingSession identifiers.\n"
                "Format: one ID or name per line.\n"
                "Examples:\n"
                "  12\n"
                "  45\n"
                "  Session ABC\n"
                "Blank lines are ignored. IDs are integers, other lines are treated as names."
            ),
        )

        parser.add_argument(
            "--created-by", type=str, help="Username of the creator. Optional."
        )

    def handle(self, *args, **options):
        name = options["name"]
        description = options.get("description")
        doi = options.get("doi")
        link = options.get("link")
        session_ids = options.get("sessions") or []
        session_names = options.get("session_names") or []
        file_path = options.get("file")
        created_by_username = options.get("created_by")

        # Load creator user if provided
        created_by = None
        if created_by_username:
            User = get_user_model()
            try:
                created_by = User.objects.get(username=created_by_username)
            except User.DoesNotExist:
                raise CommandError(f"User '{created_by_username}' does not exist.")

        # Read file content if provided
        if file_path:
            try:
                with open(file_path, "r") as f:
                    lines = [line.strip() for line in f.readlines() if line.strip()]
                # Try converting lines to integers (IDs), fallback to names
                for line in lines:
                    try:
                        session_ids.append(int(line))
                    except ValueError:
                        session_names.append(line)
            except FileNotFoundError:
                raise CommandError(f"File not found: {file_path}")

        # Deduplicate inputs
        session_ids = list(set(session_ids))
        session_names = list(set(session_names))

        # Fetch recording sessions
        recording_sessions = []

        # By ID
        for session_id in session_ids:
            try:
                recording_sessions.append(RecordingSession.objects.get(id=session_id))
            except RecordingSession.DoesNotExist:
                raise CommandError(
                    f"RecordingSession with ID {session_id} does not exist."
                )

        # By name
        for session_name in session_names:
            qs = RecordingSession.objects.filter(name=session_name)
            if not qs.exists():
                raise CommandError(
                    f"RecordingSession with name '{session_name}' does not exist."
                )
            if qs.count() > 1:
                raise CommandError(
                    f"Multiple RecordingSessions found with name '{session_name}'. Use IDs instead."
                )
            recording_sessions.append(qs.first())

        # Create or update dataset
        dataset = Dataset.objects.filter(name=name).first()
        # If it exists, update it
        if dataset:
            if description is not None:
                dataset.description = description

            if doi is not None:
                dataset.doi = doi

            if link is not None:
                dataset.link = link

            if created_by is not None:
                dataset.created_by = created_by

            dataset.save()
            created = False
        else:
            # Otherwise, create it
            dataset = Dataset.objects.create(
                name=name,
                description=description,
                doi=doi,
                link=link,
                created_by=created_by,
            )
            created = True

        dataset.recording_session_list.set(recording_sessions)

        action = "created" if created else "updated"

        self.stdout.write(
            self.style.SUCCESS(
                f"Dataset '{dataset.name}' {action} with {len(recording_sessions)} recording sessions."
            )
        )
