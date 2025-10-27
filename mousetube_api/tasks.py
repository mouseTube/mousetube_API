import logging
import os

import soundfile as sf
from celery import shared_task

from mousetube_api.models import File, RecordingSession, Repository, Software
from mousetube_api.utils.file_handler import link_to_local_path
from mousetube_api.utils.repository import publish_repository_deposition

logger = logging.getLogger(__name__)


def extract_metadata(file_instance, local_path):
    """Extract duration, sample rate, bit depth, format from the audio file.
    Only fills empty attributes on the File instance.
    """
    updated_fields = []

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
    from mousetube_api.utils.repository import prepare_repository_deposition_for_session

    file_instance = File.objects.get(id=file_id)
    # ✅ Si aucun repository_id n'est fourni, fallback sur celui du fichier
    if not repository_id and file_instance.repository_id:
        repository_id = file_instance.repository_id

    # ✅ Si toujours rien, utiliser repo par défaut
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


@shared_task(bind=True)
def publish_session_deposition(self, recording_session_id, repository_id):
    repository = Repository.objects.get(id=repository_id)
    rs = RecordingSession.objects.get(id=recording_session_id)
    files = File.objects.filter(recording_session=rs)

    if not files.exists():
        raise ValueError("No files found for this recording session.")

    self.update_state(state="STARTED", meta={"progress": 20})

    first_file = files.first()
    doi = publish_repository_deposition(repository, first_file)
    self.update_state(state="STARTED", meta={"progress": 60})

    # Step 3 — Update status
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

    # update file is_valid_link attribut if status is "done"
    files.filter(status="done").update(is_valid_link=True)

    self.update_state(state="STARTED", meta={"progress": 90})

    return {"message": f"✅ Session {rs.id} published with DOI {doi}.", "progress": 100}
