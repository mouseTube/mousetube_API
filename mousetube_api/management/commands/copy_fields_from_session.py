from django.core.management.base import BaseCommand
from mousetube_api.models import File, RecordingSession, Protocol

class Command(BaseCommand):
    help = "Copy fields from RecordingSession to File and Protocol if not already set."

    def handle(self, *args, **options):
        updated_files = 0
        updated_protocols = set()

        # Iterate over all files with their related recording session
        for file in File.objects.select_related('recording_session').all():
            rs = file.recording_session
            if rs:
                file_modified = False

                # Copy date if not already set
                if rs.date and not file.date:
                    file.date = rs.date
                    file_modified = True

                # Copy sampling rate if not already set
                if rs.sampling_rate and not file.sampling_rate:
                    file.sampling_rate = rs.sampling_rate
                    file_modified = True

                # Copy bit depth if not already set and valid
                if rs.bit_depth and not file.bit_depth:
                    try:
                        file.bit_depth = int(rs.bit_depth)
                        file_modified = True
                    except ValueError:
                        self.stdout.write(self.style.WARNING(
                            f"Invalid bit_depth for File ID {file.id}"
                        ))

                # Save file if any field was updated
                if file_modified:
                    file.save()
                    updated_files += 1

                # Update protocol if available
                protocol = rs.protocol
                protocol_modified = False

                # Copy temperature if not already set and valid
                if rs.temperature and not protocol.context_temperature_value:
                    try:
                        protocol.context_temperature_value = rs.temperature
                        protocol.context_temperature_unit = "°C"
                        protocol_modified = True
                    except ValueError:
                        self.stdout.write(self.style.WARNING(
                            f"Invalid temperature for RecordingSession ID {rs.id}"
                        ))

                # Copy light cycle if not already set and value is valid
                if rs.light_cycle and not protocol.context_light_cycle:
                    if rs.light_cycle.lower() in ["day", "night"]:
                        protocol.context_light_cycle = rs.light_cycle.lower()
                        protocol_modified = True

                # Save protocol if modified
                if protocol_modified:
                    protocol.save()
                    updated_protocols.add(protocol.id)

        # Print summary
        self.stdout.write(self.style.SUCCESS(
            f"{updated_files} file(s) updated, {len(updated_protocols)} protocol(s) updated."
        ))
