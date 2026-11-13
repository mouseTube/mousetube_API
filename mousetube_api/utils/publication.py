"""A published session keeps living: the record in the repository follows its edits, and files
added later make a new version.

- editing a published session updates the description of its record (no new version: a version
  is for new files) in the background, unless it now uses entries nobody validated yet: the update
  then waits for their validation, so the public never reads about something unvalidated
- adding files to a published session makes a draft of a new version that holds all the files;
  publishing it gives the version its own DOI, the DOI of the whole stays the same
"""

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
