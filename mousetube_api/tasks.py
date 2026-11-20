import logging
import os

import soundfile as sf
from celery import shared_task
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db.models import Q

from mousetube_api.models import File, RecordingSession, Repository
from mousetube_api.utils.file_handler import (
    UploadError,
    explain,
    link_to_local_path,
    remove_temp,
    set_progress,
)
from mousetube_api.utils.repository import (
    default_repository,
    delete_repository_file,
    prepare_repository_deposition_for_session,
    publish_repository_deposition,
)

logger = logging.getLogger(__name__)

SUPPORTED_FORMATS = {choice[0].upper() for choice in File.FORMAT_CHOICES}

AUDIO_FORMATS = {"WAV", "MP3", "FLAC", "OGG", "AIFF"}


def extract_metadata(file_instance, local_path):
    """
    Extract duration, sample rate, bit depth from audio files.
    For non-audio files, only sets the format field.
    """

    _, ext = os.path.splitext(local_path)
    file_format = ext.lower().lstrip(".").upper()

    updated_fields = []

    # --- Validate format based on model ---
    if file_format not in SUPPORTED_FORMATS:
        raise ValidationError(f"Unsupported format: {file_format}")

    # --- Assign format if missing ---
    if not file_instance.format:
        file_instance.format = file_format
        updated_fields.append("format")

    # --- If not audio → stop here ---
    if file_format not in AUDIO_FORMATS:
        if updated_fields:
            file_instance.save(update_fields=updated_fields)
        return

    # --- Audio metadata extraction ---
    try:
        with sf.SoundFile(local_path) as f:
            if not file_instance.sampling_rate:
                file_instance.sampling_rate = f.samplerate
                updated_fields.append("sampling_rate")

            if not file_instance.duration:
                file_instance.duration = int(len(f) / f.samplerate)
                updated_fields.append("duration")

            if not file_instance.bit_depth:
                bit_depth_map = {
                    "PCM_16": 16,
                    "PCM_24": 24,
                    "PCM_32": 32,
                    "FLOAT": 32,
                    "DOUBLE": 64,
                }
                bitdepth = bit_depth_map.get(f.subtype)

                if bitdepth is not None:  # ❗ only save if real value
                    file_instance.bit_depth = bitdepth
                    updated_fields.append("bit_depth")

    except RuntimeError as e:
        logger.warning("Unreadable audio %s: %s", local_path, e)
        raise ValidationError(
            "This file could not be read as audio: it may be corrupted or not the "
            "format its extension says."
        )

    # --- Save only updated fields ---
    if updated_fields:
        file_instance.save(update_fields=updated_fields)


@shared_task(bind=True, max_retries=1)
def process_file(self, file_id, repository_id):
    """
    Process a single file:
    1️⃣ Extract metadata
    2️⃣ Prepare the repository deposition (Zenodo or other)
    """

    file_instance = File.objects.get(id=file_id)

    if not repository_id and file_instance.repository_id:
        repository_id = file_instance.repository_id

    repository = (
        Repository.objects.get(id=repository_id)
        if repository_id
        else default_repository()
    )
    if repository is None:
        raise ValueError("No repository is configured.")

    try:
        file_instance.status = "processing"
        file_instance.error_message = ""
        file_instance.save(update_fields=["status", "error_message"])
        set_progress(file_instance.id, 0)

        local_path = link_to_local_path(file_instance)
        extract_metadata(file_instance, local_path)

        # --- Reference to the session ---
        rs = file_instance.recording_session
        if not rs:
            raise ValueError("File has no recording session assigned.")

        # --- Deposition repository ---
        deposition_id = prepare_repository_deposition_for_session(
            repository, rs, file_instance
        )

        file_instance.status = "done"
        file_instance.save(update_fields=["status"])

        return f"✅ File {file_instance.id} processed successfully on {repository.name}, deposition {deposition_id}."

    except Exception as exc:
        file_instance.status = "error"
        file_instance.error_message = explain(exc)[:500]
        file_instance.save(update_fields=["status", "error_message"])
        logger.exception(f"Error processing file {file_instance.id}")
        try:
            remove_temp(link_to_local_path(file_instance))  # no orphan upload
        except ValueError:
            pass
        raise


@shared_task(bind=True, max_retries=1)
def delete_file_from_repository(self, file_id, repository_id=None):
    """
    Delete a file from its repository and locally.
    1️⃣ Mark file as 'deleting'
    2️⃣ Delete from remote repository
    3️⃣ Delete local record
    4️⃣ Return success message
    """

    try:
        file_instance = File.objects.get(id=file_id)
        repository = file_instance.repository

        # fallback if needed
        if not repository and repository_id:
            repository = Repository.objects.get(id=repository_id)
        elif not repository:
            raise ValueError("File has no repository assigned.")

        file_instance.status = "processing"
        file_instance.save(update_fields=["status"])

        # 🔹 Remote deletion
        delete_repository_file(repository, file_instance)

        # 🔹 Local deletion
        file_instance.delete()

        return f"✅ File {file_id} deleted successfully from {repository.name}"

    except File.DoesNotExist:
        logger.warning(f"⚠️ File {file_id} not found for deletion.")
        return f"File {file_id} not found."

    except Exception:
        logger.exception(f"❌ Error deleting file {file_id}")
        raise


def deposit_session(recording_session_id, repository_id, payload=None, progress=None):
    """Publish the deposit of a session in its repository; returns (message, doi).

    Shared by the task of the Publish button and by the publication after validation."""
    progress = progress or (lambda percent: None)
    repository = Repository.objects.get(id=repository_id)
    rs = RecordingSession.objects.get(id=recording_session_id)
    files = File.objects.filter(recording_session=rs)

    if not files.exists():
        raise UploadError("This session has no file to deposit.")

    # a file that already has its DOI was deposited elsewhere (an import, a record of
    # someone else): there is nothing to send for it, and nothing to publish
    to_deposit = files.filter(Q(doi__isnull=True) | Q(doi=""))
    if not to_deposit.exists():
        RecordingSession.objects.filter(id=rs.id).update(status="published")
        return (
            f"✅ Session {rs.id}: every file already has its DOI.",
            None,
        )

    progress(20)

    try:
        doi = publish_repository_deposition(repository, rs, payload)
    except UploadError:
        raise
    except Exception as exc:
        logger.exception("Deposit of session %s failed", rs.id)
        raise UploadError(explain(exc)) from exc
    progress(60)

    # the deposit does not validate anything: the session was shared, so what it uses was
    # validated by an administrator before
    RecordingSession.objects.filter(id=rs.id).update(status="published")

    # update file is_valid_link attribut if status is "done"
    files.filter(status="done").update(is_valid_link=True)

    progress(90)
    return f"✅ Session {rs.id} published with DOI {doi}.", doi


@shared_task(bind=True)
def publish_session_deposition(self, recording_session_id, repository_id, payload=None):
    """
    Publish a deposition for a recording session.
    """
    message, _doi = deposit_session(
        recording_session_id,
        repository_id,
        payload,
        progress=lambda p: self.update_state(state="STARTED", meta={"progress": p}),
    )
    return {"message": message, "progress": 100}


@shared_task
def auto_publish_session(recording_session_id):
    """Publish a session that was validated, as its author approved the preview."""
    from mousetube_api.utils import publication

    session = RecordingSession.objects.get(id=recording_session_id)
    if (
        session.auto_publish_state != "publishing"
        or session.auto_publish_repository_id is None
    ):
        return "nothing to publish"
    try:
        message, doi = deposit_session(
            session.id, session.auto_publish_repository_id, session.auto_publish_payload
        )
    except Exception as exc:
        logger.exception("Automatic publication of session %s failed", session.id)
        publication.finish_auto_publish(session.id, error=explain(exc))
        return "failed"
    publication.finish_auto_publish(session.id, doi=doi or "")
    return message


def _transient(exc):
    """True when Zenodo may simply be busy or unreachable: trying again later can work."""
    import requests

    cause = exc.__cause__ if isinstance(exc, UploadError) else exc
    if isinstance(cause, (requests.ConnectionError, requests.Timeout)):
        return True
    response = getattr(cause, "response", None)
    return response is not None and (
        response.status_code >= 500 or response.status_code == 429
    )


@shared_task(bind=True, max_retries=4)
def update_published_record(self, recording_session_id):
    """The published record follows the edits of its session (description, keywords...).

    One update at a time per record: two edits in a row would otherwise unlock and publish
    the same record at once. The session is read once the lock is held, so the last update
    tells the last edit. A busy or unreachable repository is retried with a growing delay.
    """
    import time

    from django.core.cache import cache

    from mousetube_api.utils.zenodo import update_published_metadata

    lock = f"update-published-record:{recording_session_id}"
    for _ in range(12):  # wait up to a minute for the update that is running
        if cache.add(lock, "1", timeout=600):
            break
        time.sleep(5)
    else:
        raise self.retry(countdown=30)

    try:
        session = RecordingSession.objects.get(id=recording_session_id)
        update_published_metadata(session)
        RecordingSession.objects.filter(id=session.id).update(
            zenodo_state="synced", zenodo_message=""
        )
    except Exception as exc:
        logger.exception(
            "Update of the record of session %s failed", recording_session_id
        )
        if _transient(exc) and self.request.retries < self.max_retries:
            # still "pending" for the user: it is tried again
            raise self.retry(exc=exc, countdown=min(60 * 2**self.request.retries, 900))
        RecordingSession.objects.filter(id=recording_session_id).update(
            zenodo_state="failed", zenodo_message=explain(exc)[:500]
        )
        raise
    finally:
        cache.delete(lock)


@shared_task(bind=True)
def check_dead_links(self, fill_name=False):
    """Check the download links of the files; the interface follows it in the cache."""
    from django.core.cache import cache
    from django.utils import timezone

    from mousetube_api.utils import link_check

    link_check.start_state(self.request.id or "")
    try:
        counts = link_check.run(
            progress=lambda c: link_check.write_state(**c), fill_name=fill_name
        )
        link_check.write_state(
            **counts, state="done", finished_at=timezone.now().isoformat()
        )
    except Exception as exc:
        logger.exception("Check of the links failed")
        link_check.write_state(
            state="failed",
            error=explain(exc)[:300],
            finished_at=timezone.now().isoformat(),
        )
        raise
    finally:
        cache.delete(link_check.LOCK_KEY)


@shared_task
def export_page_views():
    """Regenerate the static page-view report (was run inside a web request)."""
    call_command("export_page_view", verbosity=0)
