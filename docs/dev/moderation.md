# Moderation: statuses and review

Everything users add to the catalogs (software, hardware, laboratory, reference, contact,
strain, animal profile) goes through the same states:

`draft` -> `waiting validation` -> `validated`

- The owner submits (or withdraws) an entry from the website (the **Submit for review** button of
  `ReviewStatus`, in the form of the entry, in the hardware and software lists and in the profile for the
  laboratory); only an administrator validates. A validated entry cannot be changed by its owner any more.
- Only validated entries are visible to everybody; drafts and entries waiting for review
  are visible to their owner only.
- **Studies are not reviewed.** A study is private to the person who made it: each user lists,
  chooses and changes only their own studies (administrators see all), and a session can only be
  given studies of its author. Nothing waits for validation, and a session is shared without it.
  The name of the studies of a shared session is still shown with it, like the rest of what the
  session says about itself.
- A strain chosen in the ontology is validated when it is created (see [vocabularies](ontologies.md)).
- Protocols have no free text (a protocol *is* its attributes), so they are validated
  automatically.
- An animal profile has free text (genotype, treatment, diet, description), so it is reviewed, but
  nobody names it: its **fingerprint** is a hash of every field (the text without the stray spaces,
  the case kept, the strain, the chosen age stage and the treatment and diet terms; the term of the
  age class and of the sex follow the age and the sex, so they do not count) and its name is made
  from the fields plus the start of the fingerprint (`utils/animal_profiles.py`). Creating a
  profile with the fingerprint of a **validated** one gives that one back. Validating a profile
  with the fingerprint of a validated one **merges** it into that one (subjects, sessions and
  favorites follow). The slightest difference is another profile. Changing a profile to the
  fields of a validated one is refused. `rekey_animal_profiles` (preview, then `--apply`) gives
  the profiles that existed before their fingerprint and name and merges the validated copies.
- A recording session goes `draft` -> `shared` -> `published` (deposited in a repository,
  which needs a shared session). Sharing a session that uses entries nobody validated yet
  puts it in `waiting validation`: it is private and locked until an administrator
  validates it **together with what it uses** (action "Validate the sessions and
  everything they use"), or until the entries are validated one by one.
  A shared or published session stays editable by its author and stays public. What it uses
  and nobody validated yet (a new microphone, an animal profile...) is **not shown to the
  others** (lists of files, datasets, exports, search) until an administrator validates it; the
  author and the administrators see everything. A session cannot be deposited in a repository
  while it uses such entries: the 409 of `POST /api/file/publish_session/` names each entry, its state and what
  to do (`detail` and `entries`). Every kind a session needs validated can be submitted from the website by its
  owner (a protocol is validated by itself), so a session is never stuck: the way out is to submit the entry, or
  for an administrator to validate it (what an administrator creates, and what he shares, is validated at once).
  See `UnvalidatedIsNotPublicTests`, which reads every public route.

## Administrator's interface (Django admin)

- The home of `/admin/` lists what waits for a decision, with the account requests.
- Each type has a status filter and the actions *Validate the selected entries* and
  *Send back to draft (with a reason)*. The owner is told by e-mail (when we have an
  address), and the administrator is told when something is submitted.
- Sending back entries that **shared or published sessions use** warns the administrator, with the names of the
  sessions: they stay public but cannot be deposited in a repository until the entries are validated again (the
  review page shows the same warning, `warning` in the answer of the decision).
- A session shows the entries it still needs validated.

## Review page (website, administrators only)

`/review` on the website does the same decisions in one place: one tab per kind (account
requests, sessions, software, hardware, laboratories, references, contacts, strains,
animal profiles) with the number waiting, the oldest first. Each item can be validated or
sent back with a reason, one by one or several at once; an account request is activated or
rejected (only a brand-new one can be rejected). A session is validated with everything it
uses. The link, with the count, is in the *Add* menu of the header for administrators and a *Review* button in their profile; next to it, *Check links* opens the check of the download links (see [checking the links](link-check.md)).
It uses `GET /api/review/`, `GET /api/review/<kind>/` and
`POST /api/review/<kind>/decision/` (`{"action": "validate" | "send_back", "ids": [...],
"reason": "..."}`), which are for staff only.
