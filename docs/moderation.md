# Moderation: statuses and review

Everything users add to the catalogs (software, hardware, laboratory, reference, contact,
study, strain, animal profile) goes through the same states:

`draft` -> `waiting validation` -> `validated`

- The owner submits (or withdraws) an entry from the website; only an administrator
  validates. A validated entry cannot be changed by its owner any more.
- Only validated entries are visible to everybody; drafts and entries waiting for review
  are visible to their owner only.
- Protocols have no free text (a protocol *is* its attributes), so they are validated
  automatically.
- A recording session goes `draft` -> `shared` -> `published` (deposited in a repository,
  which needs a shared session). Sharing a session that uses entries nobody validated yet
  puts it in `waiting validation`: it is private and locked until an administrator
  validates it **together with what it uses** (action "Validate the sessions and
  everything they use"), or until the entries are validated one by one.

## Administrator's interface (Django admin)

- The home of `/admin/` lists what waits for a decision, with the account requests.
- Each type has a status filter and the actions *Validate the selected entries* and
  *Send back to draft (with a reason)*. The owner is told by e-mail (when we have an
  address), and the administrator is told when something is submitted.
- A session shows the entries it still needs validated.

## Review page (website, administrators only)

`/review` on the website does the same decisions in one place: one tab per kind (account
requests, sessions, software, hardware, laboratories, references, contacts, studies, strains,
animal profiles) with the number waiting, the oldest first. Each item can be validated or
sent back with a reason, one by one or several at once; an account request is activated or
rejected (only a brand-new one can be rejected). A session is validated with everything it
uses. The link, with the count, is in the *Add* menu of the header for administrators.
It uses `GET /api/review/`, `GET /api/review/<kind>/` and
`POST /api/review/<kind>/decision/` (`{"action": "validate" | "send_back", "ids": [...],
"reason": "..."}`), which are for staff only.
