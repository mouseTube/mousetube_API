from django.core.management.base import BaseCommand
from django.contrib.contenttypes.models import ContentType
from mousetube_api.models import Strain, Metadata, MetadataField


class Command(BaseCommand):
    help = "Create metadata for strains"

    def handle(self, *args, **kwargs):
        fields_to_include = ["name", "background", "bibliography"]

        content_type = ContentType.objects.get_for_model(Strain)
        created_count = 0
        skipped_count = 0

        strains = Strain.objects.all()
        self.stdout.write(f" {strains.count()} Strains loaded...")

        for strain in strains:
            for field_name in fields_to_include:
                value = getattr(strain, field_name, None)
                if value is None:
                    continue

                try:
                    metadata_field = MetadataField.objects.get(
                        name=field_name, source="strain"
                    )
                except MetadataField.DoesNotExist:
                    self.stdout.write(
                        self.style.WARNING(
                            f"Field MetadataField '{field_name}' not found. Skip."
                        )
                    )
                    continue

                existing = Metadata.objects.filter(
                    metadata_field=metadata_field,
                    content_type=content_type,
                    object_id=strain.id,
                ).first()

                if existing:
                    skipped_count += 1
                    continue

                Metadata.objects.create(
                    metadata_field=metadata_field,
                    value=value,
                    content_type=content_type,
                    object_id=strain.id,
                )
                created_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Metadata created : {created_count}, already exist : {skipped_count}"
            )
        )
