from celery import shared_task
from django.conf import settings
from django.core.files.storage import default_storage
from .models import File
from .utils.zenodo import publish_to_zenodo
import soundfile as sf
import os
import traceback


@shared_task(bind=True)
def process_file(self, file_id):
    """
    Celery task to:
    1. Prepare the file locally
    2. Extract metadata
    3. Publish to Zenodo
    Handles all errors and updates file status.
    """
    file_instance = File.objects.get(id=file_id)

    try:
        # ---- 1. Start processing ----
        file_instance.status = "processing"
        file_instance.save(update_fields=["status"])

        local_path = move_or_prepare_file(file_instance)

        # ---- 2. Extract metadata ----
        extract_metadata(file_instance, local_path)
        file_instance.status = "metadata_extracted"
        file_instance.save(update_fields=["status"])

        # ---- 3. Publish to Zenodo ----
        publish_to_zenodo(file_instance, local_path)
        file_instance.status = "published"
        file_instance.save(update_fields=["status"])

        return f"✅ File {file_instance.id} processed successfully."

    except Exception as e:
        # ---- Error handling ----
        file_instance.status = "error"
        # Enregistrer une trace utile pour le debug (sans champ dédié)
        file_instance.status_detail = str(e)[:500]  # si tu as ce champ
        file_instance.save(update_fields=["status", "status_detail"])
        # Optionnel : log complet côté Celery
        self.retry(exc=e, countdown=10, max_retries=1)  # ou retire si tu ne veux pas de retry
        raise


def move_or_prepare_file(file_instance):
    """Prépare un fichier localement."""
    if hasattr(file_instance, "file") and file_instance.file:
        return file_instance.file.path

    temp_path = os.path.join(settings.MEDIA_ROOT, f"tmp_{file_instance.id}")
    if not default_storage.exists(file_instance.link):
        raise FileNotFoundError(f"Remote file not found: {file_instance.link}")

    with default_storage.open(file_instance.link, "rb") as f_in, open(temp_path, "wb") as f_out:
        f_out.write(f_in.read())

    return temp_path


def extract_metadata(file_instance, local_path):
    """Extract duration, sample rate, bit depth."""
    with sf.SoundFile(local_path) as f:
        file_instance.sampling_rate = f.samplerate
        file_instance.duration = int(len(f) / f.samplerate)
        file_instance.bit_depth = _subtype_to_bitdepth(f.subtype)
    file_instance.save(update_fields=["sampling_rate", "duration", "bit_depth"])


def _subtype_to_bitdepth(subtype):
    mapping = {
        "PCM_16": 16,
        "PCM_24": 24,
        "PCM_32": 32,
        "FLOAT": 32,
        "DOUBLE": 64,
    }
    return mapping.get(subtype)
