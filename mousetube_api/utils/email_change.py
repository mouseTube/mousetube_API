"""The change of the e-mail address of a signed-in user.

The address is what recovers a forgotten password, so changing it is as sensitive as the password:

- the request asks the current password (a stolen session is not enough) and the new address follows
  the rules of the registration (institutional);
- a link is sent to the NEW address only: it proves the user owns it. The link holds a signed token
  bound to the user, the old and the new address and the current password, so it dies when it is
  used (the address changes), when the password changes, or after a day;
- the link works only for the signed-in user it was made for. Otherwise someone who mistyped the
  address would give the account to the owner of the typo, who could then reset the password;
- the answer is the same whether the address is free or not (no way to probe which addresses have an
  account), and the number of mails is limited by user and by address;
- the old address is told at the request and at the change, with the new one partly hidden.
"""

import logging
from smtplib import SMTPException
from urllib.parse import urlencode

from allauth.account.models import EmailAddress
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import signing
from django.core.cache import cache
from django.core.mail import send_mail
from django.db import transaction
from django.utils.crypto import salted_hmac

from mousetube_api.utils.email_domains import is_personal_email

logger = logging.getLogger(__name__)

SALT = "mousetube.email-change"
MAX_AGE = 24 * 3600
PER_USER = (5, 3600)  # requests, seconds
PER_ADDRESS_PAUSE = 600  # seconds between two mails to the same address


class EmailChangeError(Exception):
    """The request or the token is refused; `.args[0]` is shown to the user."""


class MailNotSent(Exception):
    """The mail to the new address could not be sent: nothing is pending."""


def _fingerprint(user):
    """Changes with the password, so a new password cancels the links already sent."""
    return salted_hmac(SALT, user.password).hexdigest()[:20]


def _make_token(user, new_email):
    return signing.dumps(
        {"u": user.pk, "o": user.email, "n": new_email, "p": _fingerprint(user)},
        salt=SALT,
    )


def _taken(email, user):
    """True when another account already uses the address (case does not matter)."""
    User = get_user_model()
    return (
        User.objects.filter(email__iexact=email).exclude(pk=user.pk).exists()
        or EmailAddress.objects.filter(email__iexact=email).exclude(user=user).exists()
    )


def check_new_email(user, value):
    """Return the address to use or raise EmailChangeError (the rules of the registration)."""
    new_email = get_user_model().objects.normalize_email(value.strip())
    if settings.REQUIRE_INSTITUTIONAL_EMAIL and is_personal_email(new_email):
        raise EmailChangeError(
            "Please use your institutional email address (university, research institute, "
            "hospital...). Personal addresses such as Gmail, Outlook, Yahoo or iCloud are "
            "not accepted."
        )
    if new_email.lower() == (user.email or "").lower():
        raise EmailChangeError("This is already your e-mail address.")
    return new_email


def _mask(email):
    local, _, domain = email.partition("@")
    return f"{local[:1]}***@{domain}"


def _within_limits(user, new_email):
    """False when the user asked too often or the address got a mail a moment ago."""
    limit, window = PER_USER
    key = f"email-change:user:{user.pk}"
    cache.add(key, 0, window)
    try:
        if cache.incr(key) > limit:
            return False
    except ValueError:  # the key expired between add and incr
        cache.set(key, 1, window)
    return cache.add(f"email-change:to:{new_email.lower()}", 1, PER_ADDRESS_PAUSE)


def request_change(user, new_email):
    """Send the link to the new address. Nothing is sent when the address is taken or too solicited,
    and the caller answers the same: the answer must not tell."""
    if not _within_limits(user, new_email) or _taken(new_email, user):
        return
    link = f"{settings.FRONT_URL}/account/confirm-email?" + urlencode(
        {"token": _make_token(user, new_email)}
    )
    try:
        send_mail(
            "[mouseTube] Confirm your new e-mail address",
            f"Hello {user.first_name or user.username},\n\n"
            f"The mouseTube account '{user.username}' asked to use this address as its e-mail "
            "address.\n\n"
            "To confirm it, sign in to mouseTube with that account, then open this link "
            f"(valid 24 hours):\n{link}\n\n"
            "If you did not ask for this, ignore this message: nothing changes.\n\n"
            "The mouseTube team",
            settings.DEFAULT_FROM_EMAIL,
            [new_email],
            fail_silently=False,
        )
    except (OSError, SMTPException) as error:
        logger.exception("E-mail change: mail to the new address failed")
        cache.delete(
            f"email-change:to:{new_email.lower()}"
        )  # the user may try again now
        raise MailNotSent from error
    _tell_old_address(
        user,
        "[mouseTube] A change of your e-mail address was requested",
        f"A change of the e-mail address of your mouseTube account '{user.username}' to "
        f"{_mask(new_email)} was requested. Nothing changes until the link sent to that address "
        "is opened by you, signed in.\n\n"
        "If this was not you, change your password now (Preferences in your account, or "
        "'Log out of all devices') and write to "
        f"{settings.DEFAULT_ADMIN_EMAIL}.",
    )


def _tell_old_address(user, subject, body):
    """Best effort: a failing notice must not block the user."""
    try:
        send_mail(
            subject,
            f"Hello {user.first_name or user.username},\n\n{body}\n\nThe mouseTube team",
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=False,
        )
    except (OSError, SMTPException):
        logger.exception("E-mail change: notice to user %s failed", user.pk)


def confirm_change(user, token):
    """Apply the change the token asks for, if it is still valid and is the user's."""
    try:
        data = signing.loads(token, salt=SALT, max_age=MAX_AGE)
        wanted = (data["u"], data["o"], data["n"], data["p"])
    except (signing.BadSignature, KeyError, TypeError):
        raise EmailChangeError("This link is invalid or expired.") from None
    uid, old_email, new_email, fingerprint = wanted
    if uid != user.pk:
        raise EmailChangeError("This link was made for another account.")

    User = get_user_model()
    with transaction.atomic():
        user = User.objects.select_for_update().get(pk=user.pk)
        # the address moved, or the password changed, since the link was made
        if user.email != old_email or _fingerprint(user) != fingerprint:
            raise EmailChangeError("This link is invalid or expired.")
        if _taken(new_email, user):
            raise EmailChangeError("This address is already used by another account.")
        user.email = new_email
        user.save(update_fields=["email"])
        EmailAddress.objects.filter(user=user).delete()
        EmailAddress.objects.create(
            user=user, email=new_email, primary=True, verified=True
        )
    try:  # the notice goes to the address the account had
        send_mail(
            "[mouseTube] Your e-mail address was changed",
            f"Hello {user.first_name or user.username},\n\n"
            f"The e-mail address of your mouseTube account '{user.username}' is now "
            f"{_mask(new_email)}.\n\nIf this was not you, write to "
            f"{settings.DEFAULT_ADMIN_EMAIL} right away.\n\nThe mouseTube team",
            settings.DEFAULT_FROM_EMAIL,
            [old_email],
            fail_silently=False,
        )
    except (OSError, SMTPException):
        logger.exception("E-mail change: final notice to user %s failed", user.pk)
    return new_email
