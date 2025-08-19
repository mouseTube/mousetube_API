from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from mousetube_api.models import UserProfile
from mousetube_api.models import Software, SoftwareVersion

User = get_user_model()


@receiver(post_save, sender=get_user_model())
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        exists = UserProfile.objects.filter(user=instance).exists()
        if not exists:
            UserProfile.objects.create(user=instance)


@receiver(post_save, sender=Software)
def create_default_version(sender, instance, created, **kwargs):
    if created and not instance.versions.exists():
        SoftwareVersion.objects.create(
            software=instance, version="", created_by=instance.created_by
        )


@receiver(post_delete, sender=SoftwareVersion)
def delete_software_if_no_versions(sender, instance, **kwargs):
    software = instance.software
    if not software.versions.exists():
        software.delete()
