from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from mousetube_api.models import UserProfile

User = get_user_model()


@receiver(post_save, sender=get_user_model())
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        exists = UserProfile.objects.filter(user=instance).exists()
        if not exists:
            UserProfile.objects.create(user=instance)
