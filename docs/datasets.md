# Datasets

A dataset is a set of recording sessions; the page shows the files of those sessions.

- **Metadata JSON (public):** `GET /api/dataset/<id>/metadata/` gives one dataset, `GET /api/dataset/metadata/` all of them. It lists the sessions with protocol, laboratory, animals, equipment, references and files (DOI, repository). Contact e-mails are never included.
- **Add a dataset (admins only):** in the admin, *Mousetube_Api > Datasets > Add*, or on the website, page *Dataset*, button *Add a dataset*. The API (`POST /api/dataset/`) refuses everyone else.
- **Change or delete a dataset (admins only):** on the page *Dataset*, the pencil edits the name, the description and the sessions (`PATCH /api/dataset/<id>/` with `recording_session_ids`), the bin deletes it after a confirmation (`DELETE`). A file belongs to its session, so adding a session adds all its files and taking it out removes them from the dataset only: the sessions and files stay in the vocalizations. Deleting a dataset removes nothing else.
- **What visitors see:** only the sessions that are *shared* or *published*. A draft put in a dataset by an administrator stays private (in the page and in the metadata JSON) until it is shared; administrators see everything.
- **Images of a file (admins only):** each file of the page has a spectrogram and a plot. The button on its row sets, replaces or removes them (`POST` / `DELETE /api/file/<id>/images/?field=plot`), whoever created the file; they must be real images (PNG, JPEG, WebP), 10 MB at most. A box *Also send these images to Zenodo* (unticked by default) puts them in the record when the session is published, see [published sessions](publication.md).
