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
- it only works for records that mouseTube published itself: a session imported with the DOI of
  a record made elsewhere has no version to follow
