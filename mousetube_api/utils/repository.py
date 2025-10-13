from mousetube_api.utils import zenodo


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


def publish_repository_deposition(repository, file_instance):
    """Publish to selected repository."""
    repo_name = repository.name.lower()

    if repo_name == "zenodo":
        return zenodo.publish_zenodo_deposition(file_instance)

    raise NotImplementedError(f"Repository '{repository.name}' is not yet supported.")
