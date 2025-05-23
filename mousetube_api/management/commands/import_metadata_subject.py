from django.core.management.base import BaseCommand
from django.contrib.contenttypes.models import ContentType
from mousetube_api.models import Subject, Metadata, MetadataField

class Command(BaseCommand):
    help = "Create metadata for subjects"

    def handle(self, *args, **kwargs):
        fields_to_include = [
            "name", "origin", "sex", "group", "genotype", "treatment"
        ]

        content_type = ContentType.objects.get_for_model(Subject)
        created_count = 0
        skipped_count = 0

        subjects = Subject.objects.all()
        self.stdout.write(f"Traitement de {subjects.count()} sujets...")

        for subject in subjects:
            for field_name in fields_to_include:
                value = getattr(subject, field_name, None)
                if value is None:
                    continue

                try:
                    metadata_field = MetadataField.objects.get(name=field_name, source="subject")
                except MetadataField.DoesNotExist:
                    self.stdout.write(self.style.WARNING(
                        f"Champ MetadataField '{field_name}' introuvable. Ignoré."
                    ))
                    continue

                # Check if metadata already exists
                # Use the ContentType and object_id to filter
                # the existing metadata for the specific subject
                # and metadata field
                existing = Metadata.objects.filter(
                    metadata_field=metadata_field,
                    content_type=content_type,
                    object_id=subject.id,
                ).first()

                if existing:
                    skipped_count += 1
                    continue

                Metadata.objects.create(
                    metadata_field=metadata_field,
                    value=value,
                    content_type=content_type,
                    object_id=subject.id,
                )
                created_count += 1

        self.stdout.write(self.style.SUCCESS(
            f"Métadonnées créées : {created_count}, déjà existantes : {skipped_count}"
        ))
