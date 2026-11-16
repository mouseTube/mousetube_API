# Datasets

A dataset is a set of recording sessions; the page shows the files of those sessions.

- **Metadata JSON (public):** `GET /api/dataset/<id>/metadata/` gives one dataset, `GET /api/dataset/metadata/` all of them. It lists the sessions with protocol, laboratory, animals, equipment, references and files (DOI, repository). Contact e-mails are never included.
- **Add a dataset (admins only):** in the admin, *Mousetube_Api > Datasets > Add*, or on the website, page *Dataset*, button *Add a dataset*. The API (`POST /api/dataset/`) refuses everyone else.
