"""Account request workflow: e-mail confirmation by the user, then activation by an admin."""

import logging

from allauth.account.models import EmailAddress
from django.conf import settings
from django.core.mail import send_mail
from django.urls import reverse

logger = logging.getLogger(__name__)


def confirm_email_and_notify_admin(user):
    """The user proved they own the address: record it and ask an admin to review.

    Idempotent: a second click on the link does not send a second e-mail to the admin.
    The mail is sent first, so if it fails the user can click the link again.
    """
    address, _ = EmailAddress.objects.get_or_create(
        user=user, email=user.email, defaults={"primary": True}
    )
    if address.verified:
        return False

    profile = getattr(user, "user_profile", None)
    admin_url = settings.ADMIN_BASE_URL + reverse(
        "admin:auth_user_change", args=[user.pk]
    )
    send_mail(
        f"[mouseTube] Account request to review: {user.username}",
        "A new user confirmed their e-mail address and is waiting for activation.\n\n"
        f"Username: {user.username}\n"
        f"Name: {user.first_name} {user.last_name}\n"
        f"Email: {user.email} (confirmed)\n"
        f"ORCID: {getattr(profile, 'orcid', None) or '-'}\n\n"
        "To activate the account, open it, tick 'Active' and save:\n"
        f"{admin_url}\n\n"
        "Several requests: select them in the users list and use the action "
        "'Activate selected accounts'.",
        settings.DEFAULT_FROM_EMAIL,
        [settings.DEFAULT_ADMIN_EMAIL],
        fail_silently=False,
    )
    address.verified = True
    address.save(update_fields=["verified"])
    return True


def email_is_verified(user):
    return EmailAddress.objects.filter(
        user=user, email=user.email, verified=True
    ).exists()


def send_account_activated_email(user):
    try:
        send_mail(
            "[mouseTube] Your account is active",
            f"Hello {user.first_name or user.username},\n\n"
            "An administrator has activated your mouseTube account. "
            f"You can now log in: {settings.FRONT_URL}/account/login\n\n"
            "The mouseTube team",
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
        )
    except Exception:
        logger.exception("Could not send the activation notice to user %s", user.pk)
