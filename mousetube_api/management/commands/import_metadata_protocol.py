from django.core.management.base import BaseCommand
from mousetube_api.models import RecordingSession, Metadata, MetadataField
from django.contrib.contenttypes.models import ContentType

class Command(BaseCommand):
    help = "Crée ou met à jour les MetadataField (ex: temperature, microphone) pour chaque RecordingSession"

    def handle(self, *args, **options):
        ct = ContentType.objects.get_for_model(RecordingSession)
        sessions = RecordingSession.objects.all()
        count = 0

        mf_names = [
            "temperature",
            "microphone",
            "acquisition_hardware",
            "acquisition_software",
            "sampling_rate",
            "bit_depth",
            "laboratory",
        ]
        mf_dict = {name: MetadataField.objects.get(name=name) for name in mf_names}

        for session in sessions:
            # temperature
            if session.temperature:
                Metadata.objects.update_or_create(
                    content_type=ct,
                    object_id=session.id,
                    metadata_field=mf_dict["temperature"],
                    defaults={"value": {"value": session.temperature, "unit": "°C"}},
                )
                count += 1
            # microphone
            if session.microphone:
                Metadata.objects.update_or_create(
                    content_type=ct,
                    object_id=session.id,
                    metadata_field=mf_dict["microphone"],
                    defaults={"value": {"model": session.microphone}},
                )
                count += 1
            # acquisition_hardware
            if session.acquisition_hardware:
                Metadata.objects.update_or_create(
                    content_type=ct,
                    object_id=session.id,
                    metadata_field=mf_dict["acquisition_hardware"],
                    defaults={"value": {"model": session.acquisition_hardware}},
                )
                count += 1
            # acquisition_software
            if session.acquisition_software:
                Metadata.objects.update_or_create(
                    content_type=ct,
                    object_id=session.id,
                    metadata_field=mf_dict["acquisition_software"],
                    defaults={"value": {"name": session.acquisition_software}},
                )
                count += 1
            # sampling_rate
            if session.sampling_rate:
                Metadata.objects.update_or_create(
                    content_type=ct,
                    object_id=session.id,
                    metadata_field=mf_dict["sampling_rate"],
                    defaults={"value": {"value": session.sampling_rate, "unit": "Hz"}},
                )
                count += 1
            # bit_depth
            if session.bit_depth:
                Metadata.objects.update_or_create(
                    content_type=ct,
                    object_id=session.id,
                    metadata_field=mf_dict["bit_depth"],
                    defaults={"value": {"value": session.bit_depth, "unit": "bits"}},
                )
                count += 1
            # laboratory
            if session.laboratory:
                Metadata.objects.update_or_create(
                    content_type=ct,
                    object_id=session.id,
                    metadata_field=mf_dict["laboratory"],
                    defaults={"value": {"name": session.laboratory}},
                )
                count += 1

        self.stdout.write(self.style.SUCCESS(f"{count} metadata créées/mises à jour pour RecordingSession."))