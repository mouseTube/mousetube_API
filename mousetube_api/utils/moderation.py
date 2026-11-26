"""Moderation of what users add to the catalogs, and of the sessions that use them.

Every catalog entry (software, hardware, laboratory, reference, contact, study, strain,
animal profile) goes through the same states:

    draft  ->  waiting validation  ->  validated        (only an administrator validates)

A recording session has its own states:

    draft -> shared -> published
              ^ "waiting validation" when it uses entries nobody validated yet

A session can only be public when everything it uses is validated. Asking to share a
session that uses new entries puts it in "waiting validation": the administrator then
validates the session and all its new entries in one go (see `validate_session`), or
validates the entries one by one, and the session is shared as soon as nothing is left to
validate (see `promote_ready_sessions`).
"""

import logging
from itertools import chain

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.urls import reverse

logger = logging.getLogger(__name__)

DRAFT = "draft"
WAITING = "waiting validation"
VALIDATED = "validated"

SESSION_PUBLIC = ("shared", "published")  # what visitors may see


def sees_everything(user, owner_id):
    """An administrator and the author see all of a session, validated or not."""
    return bool(
        user and user.is_authenticated and (user.is_staff or user.id == owner_id)
    )


# What the others read of a public session: only the entries an administrator validated.
# These work on the data as the API shows it (dicts with a "status"), see the serializers.
def _validated(item):
    return bool(item) and item.get("status") == VALIDATED


def validated_only(items):
    """Keep the validated entries of a list of serialized objects (those whose `status` is `validated`)."""
    return [item for item in items or [] if _validated(item)]


def public_equipment(item):
    """Hardware or software: only its validated references and contacts."""
    item["references"] = validated_only(item.get("references"))
    if "contacts" in item:
        item["contacts"] = validated_only(item["contacts"])
    return item


def public_profile(profile):
    """An animal profile without a strain that nobody validated."""
    if profile.get("strain") and not _validated(profile["strain"]):
        profile["strain"] = None
    return profile


HARDWARE_KEYS = (
    "equipment_acquisition_hardware_soundcards",
    "equipment_acquisition_hardware_speakers",
    "equipment_acquisition_hardware_amplifiers",
    "equipment_acquisition_hardware_microphones",
)


def public_session_data(data):
    """The data of a session for the others: what nobody validated is left out."""
    for key in ("protocol", "laboratory"):
        if data.get(key) and not _validated(data[key]):
            data[key] = None
    data["animal_profiles"] = [
        public_profile(p) for p in validated_only(data.get("animal_profiles"))
    ]
    for key in HARDWARE_KEYS:
        data[key] = [public_equipment(h) for h in validated_only(data.get(key))]
    versions = [
        v
        for v in data.get("equipment_acquisition_software") or []
        if _validated(v.get("software"))
    ]
    for version in versions:
        public_equipment(version["software"])
    data["equipment_acquisition_software"] = versions
    data["references"] = validated_only(data.get("references"))
    # the state of the record and the approval of the author name what waits for validation
    for private in ("zenodo_message", "auto_publish_state", "auto_publish_message"):
        data.pop(private, None)
    return data


def _unique(entries):
    seen, kept = set(), []
    for kind, obj in entries:
        key = (obj._meta.label, obj.pk)
        if key not in seen:
            seen.add(key)
            kept.append((kind, obj))
    return kept


def session_pending_entries(session):
    """What the session uses and nobody validated yet, as (kind, object) pairs.

    Looks at the protocol, laboratory, animal profiles and their strains, the
    equipment (the studies are private to their owner and are not reviewed) (with the references and contacts of the software and hardware) and the
    references of the session itself.
    """
    profiles = list(session.animal_profiles.select_related("strain"))
    hardware = list(
        chain(
            session.equipment_acquisition_hardware_soundcards.all(),
            session.equipment_acquisition_hardware_speakers.all(),
            session.equipment_acquisition_hardware_amplifiers.all(),
            session.equipment_acquisition_hardware_microphones.all(),
        )
    )
    software = [v.software for v in session.equipment_acquisition_software.all()]

    candidates = [("protocol", session.protocol), ("laboratory", session.laboratory)]
    candidates += [("animal profile", p) for p in profiles]
    candidates += [("strain", p.strain) for p in profiles]
    candidates += [("hardware", h) for h in hardware]
    candidates += [("software", s) for s in software]
    references = chain(
        session.references.all(),
        *(item.references.all() for item in (*hardware, *software)),
    )
    candidates += [("reference", r) for r in references]
    candidates += [("contact", c) for s in software for c in s.contacts.all()]

    return _unique(
        (kind, obj)
        for kind, obj in candidates
        if obj is not None and obj.status != VALIDATED
    )


def validate_entries(entries):
    """Mark the given (kind, object) pairs as validated; returns how many changed."""
    changed = 0
    for _kind, obj in entries:
        if obj.status != VALIDATED:
            type(obj).objects.filter(pk=obj.pk).update(status=VALIDATED)
            changed += 1
    return changed


@transaction.atomic
def validate_session(session):
    """Validate everything the session uses, then share it. Returns (entries, session)."""
    entries = session_pending_entries(session)
    validate_entries(entries)
    if session.status != "published":
        type(session).objects.filter(pk=session.pk).update(status="shared")
    session.refresh_from_db()
    from mousetube_api.utils.publication import schedule_auto_publish

    schedule_auto_publish(session)  # published as the author approved, if they did
    return entries, session


def approve_entries(objs):
    """Validate catalog entries and tell their creators. Returns (changed, shared sessions):
    validating the last missing entry of a session shares it."""
    entries = [(None, obj) for obj in objs if obj.status != VALIDATED]
    changed = validate_entries(entries)
    for _kind, obj in entries:
        notify_creator(
            obj,
            f"[mouseTube] Your {obj._meta.verbose_name} '{obj}' was validated",
            "An administrator validated it: it is now visible to everybody.",
        )
    from mousetube_api.utils.publication import retry_blocked

    retry_blocked()  # published sessions that waited for this validation follow their edits
    return changed, promote_ready_sessions()


def approve_sessions(sessions):
    """Validate sessions and everything they use, then share them. Returns
    (number of sessions, number of entries validated)."""
    shared = entries = 0
    for session in sessions:
        if session.status == "published":
            continue
        done, session = validate_session(session)
        entries += len(done)
        shared += 1
        notify_creator(
            session,
            f"[mouseTube] Your recording session '{session.name}' is shared",
            "An administrator validated your session and what it uses. "
            "It is now visible to everybody.",
        )
    from mousetube_api.utils.publication import retry_blocked

    retry_blocked()
    return shared, entries


def send_back(objs, reason=""):
    """Put entries or sessions back to draft and tell their creators why.
    Returns the objects that were sent back."""
    sent = [o for o in objs if o.status not in (DRAFT, "published")]
    for obj in sent:
        type(obj).objects.filter(pk=obj.pk).update(status=DRAFT)
        what = (
            "recording session"
            if obj._meta.model_name == "recordingsession"
            else obj._meta.verbose_name
        )
        notify_creator(
            obj,
            f"[mouseTube] Your {what} '{obj}' needs changes",
            "An administrator sent it back to draft."
            + (f"\n\nReason: {reason}" if reason else "")
            + "\n\nChange it, then submit it again for review.",
        )
    return sent


def promote_ready_sessions():
    """Share the sessions that wait for a review and now use only validated entries."""
    from mousetube_api.models import RecordingSession

    promoted = []
    for session in RecordingSession.objects.filter(status=WAITING):
        if not session_pending_entries(session):
            RecordingSession.objects.filter(pk=session.pk).update(status="shared")
            session.status = "shared"
            promoted.append(session)
            from mousetube_api.utils.publication import schedule_auto_publish

            schedule_auto_publish(session)
            notify_creator(
                session,
                f"[mouseTube] Your recording session '{session.name}' is shared",
                "An administrator validated what your recording session uses. "
                "It is now visible to everybody.",
            )
    return promoted


# ----------------------------------------------------------------- notifications
def _admin_url(obj):
    meta = obj._meta
    path = reverse(f"admin:{meta.app_label}_{meta.model_name}_change", args=[obj.pk])
    return settings.ADMIN_BASE_URL + path


def notify_admin_review(obj):
    """Tell the administrator that something waits for a decision (never blocks the user)."""
    try:
        meta = obj._meta
        listing = reverse(f"admin:{meta.app_label}_{meta.model_name}_changelist")
        send_mail(
            f"[mouseTube] To review: {meta.verbose_name} '{obj}'",
            f"{obj.created_by or 'A user'} submitted a {meta.verbose_name} for validation.\n\n"
            f"Open it: {_admin_url(obj)}\n"
            f"All the {meta.verbose_name_plural} waiting for a decision: "
            f"{settings.ADMIN_BASE_URL}{listing}?status__exact=waiting+validation\n",
            settings.DEFAULT_FROM_EMAIL,
            [settings.DEFAULT_ADMIN_EMAIL],
            fail_silently=False,
        )
    except Exception:
        logger.exception("Could not notify the administrator about %r", obj)


def notify_creator(obj, subject, text, kind="validation"):
    """E-mail the creator of `obj`, when we have an address for him and he did not turn this
    kind off (`kind`: "validation" or "publication", the choices of his account page)."""
    user = getattr(obj, "created_by", None)
    if not (user and user.email):
        return
    profile = getattr(user, "user_profile", None)
    if profile and not getattr(profile, f"notify_{kind}", True):
        return
    try:
        send_mail(
            subject,
            text,
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=False,
        )
    except Exception:
        logger.exception("Could not e-mail %s about %r", user.email, obj)


def pending_counts():
    """Entries waiting for a decision, per type, for the administrator's dashboard."""
    from mousetube_api.models import (
        AnimalProfile,
        Contact,
        Hardware,
        Laboratory,
        RecordingSession,
        Reference,
        Software,
        Strain,
    )

    rows = []
    for model in (
        RecordingSession,
        Software,
        Hardware,
        Laboratory,
        Reference,
        Contact,
        Strain,
        AnimalProfile,
    ):
        count = model.objects.filter(status=WAITING).count()
        meta = model._meta
        rows.append(
            {
                "label": meta.verbose_name_plural.title(),
                "count": count,
                "url": reverse(f"admin:{meta.app_label}_{meta.model_name}_changelist")
                + "?status__exact=waiting+validation",
            }
        )
    return rows
