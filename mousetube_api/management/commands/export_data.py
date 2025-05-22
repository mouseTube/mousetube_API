from django.core.management.base import BaseCommand
from django.core.serializers import serialize
import json
from mousetube_api.models import Strain, Subject, Protocol, Experiment, File, User


class Command(BaseCommand):
    help = "Export data from User, Strain, Subject, Protocol, Experiment, and File models to a JSON fixture file"

    def handle(self, *args, **kwargs):
        users = User.objects.all()
        strains = Strain.objects.all()
        subjects = Subject.objects.select_related("strain").all()
        protocols = Protocol.objects.all()
        experiments = Experiment.objects.select_related("protocol").all()
        files = File.objects.select_related("experiment", "subject").all()

        users_json = serialize("json", users)
        strains_json = serialize("json", strains)
        subjects_json = serialize("json", subjects)
        protocols_json = serialize("json", protocols)
        experiments_json = serialize("json", experiments)
        files_json = serialize("json", files)

        data = {
            "users": json.loads(users_json),
            "strains": json.loads(strains_json),
            "subjects": json.loads(subjects_json),
            "protocols": json.loads(protocols_json),
            "experiments": json.loads(experiments_json),
            "files": json.loads(files_json),
        }

        with open("exported_data.json", "w") as f:
            json.dump(
                data["users"]
                + data["strains"]
                + data["subjects"]
                + data["protocols"]
                + data["experiments"]
                + data["files"],
                f,
                indent=4,
            )

        self.stdout.write(
            self.style.SUCCESS("Data exported successfully to 'exported_data.json'.")
        )
