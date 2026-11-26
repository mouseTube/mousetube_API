"""Rows that follow others: the profile of a new account, the first version of a software."""

from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from mousetube_api.models import Software, SoftwareVersion, UserProfile, UsvDetection
from mousetube_api.utils.sessions import revoke_sessions

User = get_user_model()


@receiver(post_save, sender=get_user_model())
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        exists = UserProfile.objects.filter(user=instance).exists()
        if not exists:
            UserProfile.objects.create(user=instance)


@receiver(pre_save, sender=get_user_model())
def revoke_sessions_on_new_password(sender, instance, update_fields=None, **kwargs):
    """Whoever changes the password (the user, the e-mail of a forgotten one, an administrator), the
    sign-ins made with the old one end. The user signs in again with the new one."""
    if not instance.pk or (update_fields and "password" not in update_fields):
        return
    old = (
        get_user_model()
        .objects.filter(pk=instance.pk)
        .values_list("password", flat=True)
        .first()
    )
    if old is not None and old != instance.password:
        revoke_sessions(instance)


@receiver(post_save, sender=Software)
def create_default_version(sender, instance, created, **kwargs):
    if created and not instance.versions.exists():
        SoftwareVersion.objects.create(
            software=instance, version="", created_by=instance.created_by
        )


@receiver(post_delete, sender=SoftwareVersion)
def delete_software_if_no_versions(sender, instance, **kwargs):
    try:
        software = instance.software
    except ObjectDoesNotExist:
        return

    if not software.versions.exists():
        software.delete()


@receiver(post_delete, sender=UsvDetection)
def delete_stored_table(sender, instance, **kwargs):
    """The table kept to be sent to the repository goes with its row (no orphan on the disk)."""
    if instance.original:
        instance.original.delete(save=False)
