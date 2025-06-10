from django.core.management.base import BaseCommand
from mousetube_api.models import (
    RecordingSession,
    AcquisitionSoftwareUsage,
)


class Command(BaseCommand):
    help = "Migrate acquisition software and versions to AcquisitionSoftwareUsage"

    def handle(self, *args, **options):
        count = 0
        for session in RecordingSession.objects.all():
            softwares = session.equipment_acquisition_software_software.all()
            versions = session.equipment_acquisition_software_version.all()
            # Pour chaque software lié à la session
            for software in softwares:
                # Cherche les versions liées à ce software
                software_versions = versions.filter(software=software)
                if software_versions.exists():
                    for version in software_versions:
                        obj, created = AcquisitionSoftwareUsage.objects.get_or_create(
                            recording_session=session,
                            software=software,
                            version=version,
                        )
                        if created:
                            count += 1
                else:
                    # Si aucune version liée, crée une entrée sans version
                    obj, created = AcquisitionSoftwareUsage.objects.get_or_create(
                        recording_session=session,
                        software=software,
                        version=None,
                    )
                    if created:
                        count += 1
        self.stdout.write(
            self.style.SUCCESS(f"Migrated {count} AcquisitionSoftwareUsage entries.")
        )
