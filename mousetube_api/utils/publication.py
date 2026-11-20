"""A published session keeps living: the record in the repository follows its edits, and files
added later make a new version.

- editing a published session updates the description of its record (no new version: a version
  is for new files) in the background, unless it now uses entries nobody validated yet: the update
  then waits for their validation, so the public never reads about something unvalidated
- adding files to a published session makes a draft of a new version that holds all the files;
  publishing it gives the version its own DOI, the DOI of the whole stays the same
- a session that waits for an administrator can be published by itself once it is shared: its
  author approves the preview of the publication while it waits, and it goes out as approved when
  the session is validated, unless what would be published is no longer what was approved (the
  author is told and publishes it by hand, with a new preview)
"""

import hashlib
import json

from django.db import transaction

from mousetube_api.utils.moderation import session_pending_entries

PUBLISHED = "published"


def latest_version(session):
    return session.publication_versions.order_by("-number").first()


def has_record(session):
    """True when a record of this session was published by mouseTube (and can follow it)."""
    return session.status == PUBLISHED and session.publication_versions.exists()


def _set_state(session, state, message=""):
    type(session).objects.filter(pk=session.pk).update(
        zenodo_state=state, zenodo_message=message[:500]
    )
    session.zenodo_state, session.zenodo_message = state, message[:500]


def schedule_sync(session):
    """Make the record follow the session: now, or once its new entries are validated."""
    if not has_record(session):
        return
    pending = session_pending_entries(session)
    if pending:
        names = ", ".join(sorted({f"{kind} {obj}" for kind, obj in pending}))
        _set_state(
            session,
            "blocked",
            f"The record will be updated once an administrator validates: {names}.",
        )
        return
    _set_state(session, "pending")
    from mousetube_api.tasks import update_published_record

    transaction.on_commit(lambda: update_published_record.delay(session.id))


def retry_blocked():
    """After a validation: the sessions that waited for it follow their edits now."""
    from mousetube_api.models import RecordingSession

    for session in RecordingSession.objects.filter(zenodo_state="blocked"):
        schedule_sync(session)


# ---------------------------------------------------------------- publication after validation
MAX_APPROVED_PAYLOAD = 200_000  # characters of JSON: a description, not a file


def _files_for_preview(session):
    from mousetube_api.models import File

    return File.objects.filter(recording_session=session).exclude(
        status__in=["pending", "processing", "error"]
    )


def preview_digest(repository, session):
    """A fingerprint of the metadata that would be proposed for the session right now."""
    from mousetube_api.utils.repository import build_repository_metadata_payload

    payload = build_repository_metadata_payload(
        repository, session, _files_for_preview(session)
    )
    text = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(text.encode()).hexdigest()


def approve_auto_publish(session, repository, payload):
    """The author approved the preview: remember what was approved. The session must wait."""
    session.auto_publish_state = "approved"
    session.auto_publish_message = ""
    session.auto_publish_repository = repository
    session.auto_publish_payload = payload
    session.auto_publish_digest = preview_digest(repository, session)
    session.save(
        update_fields=[
            "auto_publish_state",
            "auto_publish_message",
            "auto_publish_repository",
            "auto_publish_payload",
            "auto_publish_digest",
        ]
    )


def reset_auto_publish(session):
    """Forget the approval (withdrawn request, changed mind)."""
    type(session).objects.filter(pk=session.pk).update(
        auto_publish_state="",
        auto_publish_message="",
        auto_publish_repository=None,
        auto_publish_payload=None,
        auto_publish_digest="",
    )
    session.auto_publish_state = ""


def _tell_author(session, subject, text):
    from mousetube_api.utils.moderation import notify_creator

    notify_creator(session, f"[mouseTube] {subject}", text)


def schedule_auto_publish(session):
    """The session was just shared: publish it as its author approved, if they did.

    Nothing goes out if the metadata is no longer what the author looked at (an administrator
    corrected an entry meanwhile): the author is told and publishes by hand."""
    if session.auto_publish_state != "approved" or session.status != "shared":
        return
    repository = session.auto_publish_repository
    try:
        unchanged = (
            repository is not None
            and preview_digest(repository, session) == session.auto_publish_digest
        )
    except (
        NotImplementedError,
        IndexError,
        ValueError,
    ):  # no preview: do not publish blindly
        unchanged = False
    if not unchanged:
        message = (
            "What would be published changed after you approved the preview: check it "
            "again and publish the session from its page."
        )
        type(session).objects.filter(pk=session.pk).update(
            auto_publish_state="stale", auto_publish_message=message
        )
        session.auto_publish_state = "stale"
        _tell_author(
            session,
            f"Your session '{session.name}' is shared, but not published yet",
            "An administrator validated it, but it is not published automatically: "
            f"{message}",
        )
        return
    type(session).objects.filter(pk=session.pk).update(auto_publish_state="publishing")
    session.auto_publish_state = "publishing"
    from mousetube_api.tasks import auto_publish_session

    transaction.on_commit(lambda: auto_publish_session.delay(session.id))


def finish_auto_publish(session_id, doi=None, error=None):
    """Record how the automatic publication ended, and tell the author."""
    from mousetube_api.models import RecordingSession

    session = RecordingSession.objects.get(pk=session_id)
    if error is None:
        RecordingSession.objects.filter(pk=session_id).update(
            auto_publish_state="done",
            auto_publish_message=f"Published with the DOI {doi}.",
            auto_publish_payload=None,
        )
        _tell_author(
            session,
            f"Your session '{session.name}' is published",
            f"It was published as you approved it, with the DOI {doi}.\n"
            f"https://doi.org/{doi}",
        )
        return
    RecordingSession.objects.filter(pk=session_id).update(
        auto_publish_state="failed", auto_publish_message=str(error)[:500]
    )
    _tell_author(
        session,
        f"Your session '{session.name}' is shared, but could not be published",
        f"The automatic publication failed: {error}\n"
        "The session stays shared: you can publish it from its page.",
    )
