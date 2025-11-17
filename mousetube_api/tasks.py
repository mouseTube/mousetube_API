import logging
import os

import soundfile as sf
from celery import shared_task
from django.core.exceptions import ValidationError

from mousetube_api.models import File, RecordingSession, Reference, Repository, Software
from mousetube_api.utils.file_handler import link_to_local_path
from mousetube_api.utils.repository import (
    delete_repository_file,
    prepare_repository_deposition_for_session,
    publish_repository_deposition,
)

logger = logging.getLogger(__name__)


AUDIO_EXTENSIONS = {
    ".wav",
    ".flac",
    ".aiff",
    ".aif",
    ".ogg",
    ".mp3",
}


def extract_metadata(file_instance, local_path):
    """Extract duration, sample rate, bit depth, format from the audio file.
    Only fills empty attributes on the File instance.
    Raises ValidationError if file is not a supported audio.
    """
    _, ext = os.path.splitext(local_path)
    if ext.lower() not in AUDIO_EXTENSIONS:
        raise ValidationError(f"Unsupported audio format: {ext}")

    updated_fields = []

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
                file_instance.bit_depth = bit_depth_map.get(f.subtype)
                updated_fields.append("bit_depth")
    except RuntimeError as e:
        raise ValidationError(f"Cannot read audio file: {e}")

    if not file_instance.format:
        _, ext = os.path.splitext(local_path)
        file_instance.format = ext.lower().lstrip(".").upper()
        updated_fields.append("format")

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
    # ✅ if no repo_id, try to get from file
    if not repository_id and file_instance.repository_id:
        repository_id = file_instance.repository_id

    # ✅ if still no repo_id, default to 1
    if not repository_id:
        repository_id = 1
    repository = Repository.objects.get(id=repository_id)

    try:
        file_instance.status = "processing"
        file_instance.save(update_fields=["status"])

        local_path = link_to_local_path(file_instance)
        extract_metadata(file_instance, local_path)

        rs = file_instance.recording_session
        if not rs:
            raise ValueError("File has no recording session assigned.")

        deposition_id = prepare_repository_deposition_for_session(
            repository, rs, file_instance
        )

        file_instance.status = "done"
        file_instance.save(update_fields=["status"])

        return f"✅ File {file_instance.id} processed successfully on {repository.name}, deposition {deposition_id}."

    except Exception as e:
        file_instance.status = "error"
        file_instance.save(update_fields=["status"])
        logger.exception(f"Error processing file {file_instance.id}: {e}")
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

    except Exception as e:
        logger.exception(f"❌ Error deleting file {file_id}: {e}")
        raise


@shared_task(bind=True)
def publish_session_deposition(self, recording_session_id, repository_id, payload=None):
    """
    Publish a deposition for a recording session.
    """
    repository = Repository.objects.get(id=repository_id)
    rs = RecordingSession.objects.get(id=recording_session_id)
    files = File.objects.filter(recording_session=rs)

    if not files.exists():
        raise ValueError("No files found for this recording session.")

    self.update_state(state="STARTED", meta={"progress": 20})

    doi = publish_repository_deposition(repository, rs, payload)
    self.update_state(state="STARTED", meta={"progress": 60})

    RecordingSession.objects.filter(id=rs.id).update(status="published")
    if rs.protocol:
        rs.protocol.__class__.objects.filter(id=rs.protocol.id).update(
            status="validated"
        )
    if rs.laboratory:
        rs.laboratory.__class__.objects.filter(id=rs.laboratory.id).update(
            status="validated"
        )

    rs.studies.update(status="validated")
    rs.animal_profiles.update(status="validated")

    strain_ids = rs.animal_profiles.exclude(strain__isnull=True).values_list(
        "strain_id", flat=True
    )
    if strain_ids:
        from .models import Strain

        Strain.objects.filter(id__in=strain_ids).update(status="validated")

    if rs.equipment_acquisition_software.exists():
        Software.objects.filter(
            versions__in=rs.equipment_acquisition_software.all()
        ).update(status="validated")

    if rs.equipment_acquisition_hardware_soundcards.exists():
        rs.equipment_acquisition_hardware_soundcards.update(status="validated")

    if rs.equipment_acquisition_hardware_speakers.exists():
        rs.equipment_acquisition_hardware_speakers.update(status="validated")

    if rs.equipment_acquisition_hardware_amplifiers.exists():
        rs.equipment_acquisition_hardware_amplifiers.update(status="validated")

    if rs.equipment_acquisition_hardware_microphones.exists():
        rs.equipment_acquisition_hardware_microphones.update(status="validated")

    # --- ✅ References linked via recording session references field ---
    rs.references.all().update(status="validated")

    # --- ✅ References linked to acquisition software ---
    if rs.equipment_acquisition_software.exists():
        Reference.objects.filter(
            software__in=rs.equipment_acquisition_software.all()
        ).update(status="validated")

    # --- ✅ References linked to acquisition hardware ---
    hardware_relations = [
        rs.equipment_acquisition_hardware_soundcards,
        rs.equipment_acquisition_hardware_speakers,
        rs.equipment_acquisition_hardware_amplifiers,
        rs.equipment_acquisition_hardware_microphones,
    ]
    for hw in hardware_relations:
        if hw.exists():
            Reference.objects.filter(hardware__in=hw.all()).update(status="validated")

    # update file is_valid_link attribut if status is "done"
    files.filter(status="done").update(is_valid_link=True)

    self.update_state(state="STARTED", meta={"progress": 90})

    return {"message": f"✅ Session {rs.id} published with DOI {doi}.", "progress": 100}
