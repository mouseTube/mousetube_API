# Python reference

The helpers of the API, written once and used by the views, the serializers, the Django admin and the
Celery tasks. They are documented from their **docstrings**: this reference is generated, so it never drifts
from the code.

| Module | What it does |
|---|---|
| [Rights and moderation](rights-moderation.md) | `session_rights`, the statuses, the validation of entries and sessions, what the public sees, publication after validation, the data of the review page |
| [Vocabularies](vocabularies.md) | Ontology terms checked at their source (EBI OLS, ROR) |
| [Files and repositories](files-repositories.md) | Uploads, the deposit in Zenodo, the description of a record, the check of links, detection tools |
| [Datasets](datasets.md) | Export and import of the metadata of a dataset |
| [Accounts](accounts.md) | Registration, e-mail domains, ORCID proof, e-mails |
| [Tasks and utilities](tasks.md) | The Celery tasks, the signals, the data upgrades |

!!! tip "Looking for a rule rather than a function?"
    The rights of each role are in [Rights and statuses](../rights.md); the HTTP routes in the
    [REST API](../api/index.md).

## Conventions

- Docstrings are in English and follow the Google style (`Args:`, `Returns:`, `Raises:`) when a function has
  parameters worth naming.
- A function whose name starts with `_` is internal and is not listed.
- Run `mkdocs serve` to read this reference locally (see [Contributing](../contributing.md)).
