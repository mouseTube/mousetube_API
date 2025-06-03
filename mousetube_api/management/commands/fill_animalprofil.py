from django.core.management.base import BaseCommand
from django.db import transaction
from mousetube_api.models import Subject, AnimalProfil

class Command(BaseCommand):
    help = "Create AnimalProfil instances based on existing Subjects"

    def handle(self, *args, **options):
        self.stdout.write("⏳ Creating AnimalProfil entries from Subject data...")
        created_count = 0
        # Collect existing AnimalProfil keys to avoid duplicates
        self.stdout.write("🔍 Checking existing AnimalProfil entries...")
        existing_keys = set(
            AnimalProfil.objects.values_list("strain_id", "sex", "genotype", "treatment")
        )

        @transaction.atomic
        def process():
            nonlocal created_count
            for subject in Subject.objects.all():
                key = (subject.strain_id, subject.sex, subject.genotype, subject.treatment)

                if key not in existing_keys:
                    name = self.generate_profil_name(subject)
                    profil = AnimalProfil.objects.create(
                        name=name,
                        strain=subject.strain,
                        sex=subject.sex,
                        genotype=subject.genotype,
                        treatment=subject.treatment,
                    )
                    existing_keys.add(key)
                    created_count += 1
                    self.stdout.write(self.style.SUCCESS(f"✔ Created: {profil.name}"))

            self.stdout.write("🔄 Linking Subjects to their corresponding AnimalProfil...")
            for subject in Subject.objects.all():
                profil = AnimalProfil.objects.filter(
                    strain=subject.strain,
                    sex=subject.sex,
                    genotype=subject.genotype,
                    treatment=subject.treatment
                ).first()
                if profil and subject.animal_profil != profil:
                    subject.animal_profil = profil
                    subject.save(update_fields=["animal_profil"])
                    self.stdout.write(f"🔗 Linked Subject '{subject.name}' to AnimalProfil '{profil.name}'")

        process()
        self.stdout.write(self.style.SUCCESS(f"\n✅ Done. {created_count} new AnimalProfil entries created."))

    def generate_profil_name(self, subject):
        parts = [
            subject.strain.name if subject.strain else "unknown_strain",
            subject.sex if subject.sex else "unknown_sex",
            subject.genotype if subject.genotype else "no_genotype",
            subject.treatment if subject.treatment else "no_treatment",
        ]
        return "_".join(parts)
