# Published sessions and versions

A published session keeps living (the record in the repository is the one of its session):

- the author can **edit it**; the description and keywords of its record in the repository
  follow, in the background (`update_published_record`), without a new version: the record is
  unlocked, updated and published again with the same DOI. The state is shown on the session
  (`zenodo_state`: up to date, in progress, waiting, failed). If the edit makes it use entries
  nobody validated yet, the update waits for their validation (`blocked`) and runs by itself when
  an administrator validates them, so the public never reads about an unvalidated entry. Two edits
  in a row never update the record at the same time (one update per session, the next one waits),
  and a repository that is unreachable or answers 5xx/429 is tried again with a growing delay
  (the state stays `pending`; a refusal is `failed` at once)
- the author can **add files**: they go to the draft of a **new version** of the record (the
  draft holds the files of the version before); *Publish a new version* publishes it. Each
  version has its own DOI (`PublicationVersion`), the DOI of the whole is `concept_doi`;
  a file of a published version cannot be removed, by anyone (administrators included: the
  repository would refuse), a file waiting for the next version can
- the author can ask to **send the tables of the detection tools and the images of a file** (spectrogram,
  plot) with the record: a box on each, unticked by default (see [detections](usv-detections.md) and
  [datasets](datasets.md)). They are put in the draft just before it is published (the first publication
  and every new version), named like the file (`<file>_<tool>.csv`, `<file>_spectrogram.png`,
  `<file>_plot.png`), and only for the files that mouseTube itself sent to that record. Something ticked
  after a record is published goes with the next version; editing the description does not send it
- it only works for records that mouseTube published itself: a session imported with the DOI of
  a record made elsewhere has no version to follow

## Publication after validation

A session that uses entries nobody validated yet waits for an administrator (see [moderation](moderation.md)).
Its author can ask, with the box *Publish automatically once validated* next to *Share this session*, for it to
be published by itself once it is shared. It only matters when the session has to wait: a session that is shared
at once is published with its own button.

1. The session goes to *waiting validation* and the preview of the publication opens (the same one as the
   *Publish* button: title, description, keywords, people, license). The author checks it, edits it if they want,
   and approves it (`POST /api/recording-session/<id>/auto-publish/` with `repository_id` and the `payload`;
   only the author, only while the session waits). Closing the preview without approving means no automatic
   publication.
2. When an administrator validates the session (the review page, the admin action, or by validating the last
   entry it was waiting for), the metadata that would be published now is compared with the one the author
   looked at (a fingerprint kept at the approval). **If it is the same**, the session is published as approved
   (`auto_publish_session` task) and the author gets an e-mail with the DOI. **If it changed** (an administrator
   corrected something meanwhile), nothing goes out: the state becomes `stale`, the author is told, and publishes
   by hand with a new preview.
3. A failure (the repository is busy, a file is missing...) leaves the session shared, with the state `failed`
   and the reason, and the author is told by e-mail: they can publish from the session page.

`auto_publish_state` (`approved`, `stale`, `publishing`, `done`, `failed`) and `auto_publish_message` are shown
with the session; the approved metadata itself is never sent back to the page. Withdrawing the request, or
*Cancel automatic publication* (`DELETE` on the same route), removes the approval. The Celery worker must be
restarted for the new task (see [updating a deployment](deployment.md)).
