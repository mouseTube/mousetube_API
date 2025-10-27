from mousetube_api.models import File
from mousetube_api.utils import zenodo


def get_repository_metadata_schema(repository):
    """Return metadata schema definition for a given repository."""
    repo_name = repository.name.lower()

    if repo_name == "zenodo":
        return zenodo.ZENODO_METADATA_SCHEMA

    raise NotImplementedError(f"Repository '{repository.name}' is not yet supported.")


def build_repository_metadata_payload(repository, recording_session, files):
    """Build metadata payload for given repository."""
    repo_name = repository.name.lower()

    if repo_name == "zenodo":
        return zenodo.build_zenodo_metadata_payload(
            recording_session,
            files=File.objects.filter(recording_session=recording_session).exclude(
                status__in=["pending", "processing", "error"]
            ),
        )

    raise NotImplementedError(f"Repository '{repository.name}' is not yet supported.")


def prepare_repository_deposition_for_session(
    repository, recording_session, file_instance
):
    """Prepare repository given a repository."""
    repo_name = repository.name.lower()

    if repo_name == "zenodo":
        return zenodo.prepare_zenodo_deposition_for_session(
            recording_session, file_instance
        )

    raise NotImplementedError(f"Repository '{repository.name}' is not yet supported.")


def publish_repository_deposition(repository, file_instance, payload=None):
    """Publish to selected repository."""
    repo_name = repository.name.lower()

    if repo_name == "zenodo":
        return zenodo.publish_zenodo_deposition(file_instance, payload)

    raise NotImplementedError(f"Repository '{repository.name}' is not yet supported.")
