from django.conf import settings
from django.db import migrations


def create_missing_profiles(apps, schema_editor):
    """Accounts created before the profile existed (or without its signal) have none, and
    the account page then shows nothing. Give each of them an empty one."""
    app_label, model_name = settings.AUTH_USER_MODEL.split(".")
    User = apps.get_model(app_label, model_name)
    UserProfile = apps.get_model("mousetube_api", "UserProfile")
    for user in User.objects.filter(user_profile__isnull=True):
        UserProfile.objects.create(user=user)


class Migration(migrations.Migration):
    dependencies = [("mousetube_api", "0003_align_statuses")]

    operations = [
        migrations.RunPython(create_missing_profiles, migrations.RunPython.noop),
    ]
