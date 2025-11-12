from django.core.management.base import BaseCommand
from django.db import transaction

from mousetube_api.models import Contact, LegacyUser, Software


class Command(BaseCommand):
    help = "Migrate LegacyUser entries to Contact and preserve Software relationships"

    @transaction.atomic
    def handle(self, *args, **options):
        created_contacts = 0
        linked_softwares = 0

        for legacy_user in LegacyUser.objects.all():
            softwares = Software.objects.filter(users=legacy_user)

            if not softwares.exists():
                continue
            contact, created = Contact.objects.get_or_create(
                email=legacy_user.email_user,
                defaults={
                    "first_name": legacy_user.first_name_user or "",
                    "last_name": legacy_user.name_user or "",
                    "unit": legacy_user.unit_user or "",
                    "institution": legacy_user.institution_user or "",
                    "address": legacy_user.address_user or "",
                    "country": legacy_user.country_user or "",
                    "status": "validated",
                },
            )

            if created:
                created_contacts += 1

            for sw in softwares:
                sw.contacts.add(contact)
                linked_softwares += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"✅ Migration done : {created_contacts} contacts created, {linked_softwares} Software–Contact links added."
            )
        )
