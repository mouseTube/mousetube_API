import logging
import os

import soundfile as sf
from celery import shared_task
from django.conf import settings

from mousetube_api.models import File, RecordingSession, Repository
from mousetube_api.utils.file_handler import link_to_local_path
from mousetube_api.utils.zenodo import (
    prepare_zenodo_deposition_for_session,
    publish_zenodo_deposition,
)

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
def process_file(self, file_id):
    """
    Process a single file:
    1️⃣ Extract metadata
    2️⃣ Prepare the repository deposition (Zenodo or future repo)
    """
    file_instance = File.objects.get(id=file_id)
    try:
        # ---- 1. Start processing ----
        file_instance.status = "processing"
        file_instance.save(update_fields=["status"])

        # ---- 2. Get local path and extract metadata ----
        local_path = link_to_local_path(file_instance)
        extract_metadata(file_instance, local_path)

        # ---- 3. Prepare repository deposition for the recording session ----
        rs = file_instance.recording_session
        if not rs:
            raise ValueError("File has no recording session assigned.")
        deposition_id = prepare_zenodo_deposition_for_session(rs, file_instance)

        # ---- 4. Mark file as done ----
        file_instance.status = "done"
        file_instance.save(update_fields=["status"])

        return f"✅ File {file_instance.id} processed successfully, deposition {deposition_id} used."

    except Exception as e:
        file_instance.status = "error"
        file_instance.save(update_fields=["status"])
        logger.exception(f"Error processing file {file_instance.id}: {e}")
        raise


@shared_task(bind=True)
def publish_session_deposition(self, recording_session_id):
    self.update_state(state="STARTED", meta={"progress": 5})
    print(recording_session_id)

    rs = RecordingSession.objects.get(id=recording_session_id)
    files = File.objects.filter(recording_session=rs)
    print(files)

    if not files.exists():
        raise ValueError("No files found for this recording session.")

    # Step 1 — Start publication
    self.update_state(state="STARTED", meta={"progress": 20})

    # Step 2 — Publishing
    first_file = files.first()
    print(first_file)
    doi = publish_zenodo_deposition(first_file)
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

    self.update_state(state="STARTED", meta={"progress": 90})

    # Étape finale
    return {"message": f"✅ Session {rs.id} published with DOI {doi}.", "progress": 100}
