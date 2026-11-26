# Checking the download links

The files of mouseTube are mostly hosted elsewhere (Zenodo, other servers): a link can stop answering.
`File.is_valid_link` says whether it did the last time it was looked at.

## From the website (administrators)

The profile of an administrator has a **Check links** button next to *Review*; it opens `/check-links`. The
page starts the check in the background, shows a progress bar with the time left and the counts (answer,
do not answer, not checked, busy), and lists the links that do not answer. It can be left and opened again:
it finds the check where it is. The page, like the routes it uses, is for administrators only.

- `POST /api/admin/link-check/` starts the check (`check_dead_links` task, Celery); `409` while one is
  running (one at a time).
- `GET /api/admin/link-check/` gives its state, the number of valid links and the first 200 that do not
  answer. The state is kept in the cache (shared by the API and the worker) for a week; the lock of a check
  that died is released after 6 hours at most.

## How a link is looked at

One request a second (the servers, Zenodo first, must not be overwhelmed), `HEAD` first, then `GET` if the
server refuses it. Each file ends in one of four states:

- **answers** (status below 400): the file is valid again if it was not;
- **does not answer** (error or status 400 and above): the file is marked not valid;
- **not checked**: a link that is not `http(s)` or leads to an address that is not public, redirects
  included (localhost, private network, link-local): the links are written by users, the server must not be
  made to look at its own network;
- **busy** (429): the server asked to slow down, nothing is concluded.

The pause is only taken after a link that was really looked at: a check takes at least about one second per such link (more than half an hour for 1600 links).

## From the command line

`python manage.py check_dead_links` does the same, with the same code, and `--fill_name` also takes the name
of the file from the answer when it has none.

## Links to a whole Zenodo record

A link `.../api/records/<id>/files-archive` is the zip of **every** file of a record (the tables of the detection tools
too), and Zenodo no longer gives it to programs (403): the check marks the file as invalid and the button of the site
fails. `python manage.py fix_zenodo_archive_links` shows the rows concerned and the link of the file that would replace
each one; `--apply` writes them. The name is read in the record, because Zenodo tells capitals apart (`cage` in the row,
`Cage` in the record); a row whose file is not in the record is left as it is. Run `check_dead_links` afterwards. The DOI
of the row is the one of the whole record and is not changed.
