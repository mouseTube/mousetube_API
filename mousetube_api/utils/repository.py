import importlib

from mousetube_api.models import File


def get_repository_handler(repository):
    """
    Return the handler module for a repository based on its name.
    Assumes a module exists in mousetube_api.utils with the same name in lowercase.
    """
    repo_name = repository.name.lower().strip()
    try:
        module = importlib.import_module(f"mousetube_api.utils.{repo_name}")
        return module
    except ModuleNotFoundError:
        raise NotImplementedError(
            f"Repository '{repository.name}' is not yet supported."
        )


def get_repository_metadata_schema(repository):
    """
    Return metadata schema definition for a repository.
    """
    handler = get_repository_handler(repository)
    return getattr(handler, "METADATA_SCHEMA", None)


def build_repository_metadata_payload(repository, recording_session, files=None):
    """
    Build metadata payload for the repository.
    """
    handler = get_repository_handler(repository)

    if files is None:
        files = File.objects.filter(recording_session=recording_session).exclude(
            status__in=["pending", "processing", "error"]
        )

    build_func = getattr(handler, "build_metadata_payload", None)
    if not callable(build_func):
        raise NotImplementedError(
            f"Repository '{repository.name}' does not implement 'build_metadata_payload'"
        )

    return build_func(recording_session, files)


def prepare_repository_deposition_for_session(
    repository, recording_session, file_instance
):
    """
    Prepare a deposition for the repository.
    """
    handler = get_repository_handler(repository)
    func = getattr(handler, "prepare_deposition_for_session", None)
    if not callable(func):
        raise NotImplementedError(
            f"Repository '{repository.name}' does not implement 'prepare_deposition_for_session'"
        )
    return func(recording_session, file_instance)


def delete_repository_file(repository, file_instance):
    """
    Delete a file from the repository.
    """
    handler = get_repository_handler(repository)
    func = getattr(handler, "delete_file", None)
    if not callable(func):
        raise NotImplementedError(
            f"Repository '{repository.name}' does not implement 'delete_file'"
        )
    return func(file_instance)


def publish_repository_deposition(repository, recording_session, payload=None):
    """
    Publish a deposition to the repository.
    """
    handler = get_repository_handler(repository)
    func = getattr(handler, "publish_deposition", None)
    if not callable(func):
        raise NotImplementedError(
            f"Repository '{repository.name}' does not implement 'publish_deposition'"
        )
    return func(recording_session, payload)
