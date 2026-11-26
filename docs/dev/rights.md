# Rights and statuses

This page says, for every kind of object, **who may read, change, delete and publish it, and how that
depends on its status**. It is the reference for the website, for the API and for the Django admin: they
all apply the same rules. Each rule below is checked by a test (see [Where the rules live](#where-the-rules-live)).

!!! tip "Reading the answers of the API"
    - **401** – you are not signed in (visitors cannot do it at all).
    - **403** – you may see the object but not do that.
    - **404** – you may not even see it: an object that is private to someone else answers "not found", as if
      it did not exist.

## The four roles

| Role | Who | How the API knows |
|---|---|---|
| **Visitor** | Anybody, without an account | No token |
| **User** | Signed in, active account | A valid token (the account was confirmed by e-mail, then activated by an administrator) |
| **Author** | The user who created the object | `created_by` is the user |
| **Administrator** | Staff of mouseTube | `is_staff` (given in the Django admin, never through the API) |

An administrator may do everything a user may, and more. They moderate through the
[review page and the Django admin](moderation.md); the catalog API also accepts their changes.

## The statuses

=== "Catalog entries"

    Laboratory, reference, contact, hardware, software, strain, animal profile (and, without review, study):

    <span class="pill grey">draft</span> → <span class="pill blue">waiting validation</span> → <span class="pill green">validated</span>

    - the author creates it as **draft** and may send it for review (**waiting validation**) or take it back;
    - only an administrator makes it **validated** (or sends it back to draft with a reason);
    - a **validated** entry is public and locked for its author.

=== "Recording sessions"

    <span class="pill grey">draft</span> → <span class="pill blue">waiting validation</span> → <span class="pill green">shared</span> → <span class="pill red">published</span>

    - **draft**: private work in progress;
    - **waiting validation**: the author asked to share a session that uses entries nobody validated yet;
      it stays private and is locked while an administrator reads it;
    - **shared**: public; the author keeps editing it;
    - **published**: shared *and* deposited in a repository (Zenodo) with a DOI.

=== "Files"

    A file has no moderation status of its own. It follows its session: private while the session is a draft or
    waits for review, public once it is shared. Its `status` (`pending`, `processing`, `done`, `error`) is only the
    state of its processing and upload.

## Catalog entries

The same rule applies to the seven moderated catalogs. It is checked cell by cell for each of them by
`test_rights_matrix.py`.

<table>
<thead>
<tr><th>Status of the entry</th><th>Visitor</th><th>Other user</th><th>Author</th><th>Administrator</th></tr>
</thead>
<tbody>
<tr><td><span class="pill grey">draft</span></td>
<td><span class="no">nothing (404)</span></td>
<td><span class="no">nothing (404)</span></td>
<td><span class="yes">read, change, delete</span>, send for review</td>
<td><span class="yes">everything</span></td></tr>
<tr><td><span class="pill blue">waiting validation</span></td>
<td><span class="no">nothing (404)</span></td>
<td><span class="no">nothing (404)</span></td>
<td><span class="yes">read, change</span>, withdraw. <span class="no">Not delete (403)</span></td>
<td><span class="yes">everything</span>, validates or sends back</td></tr>
<tr><td><span class="pill green">validated</span></td>
<td><span class="yes">read</span></td>
<td><span class="yes">read</span>, use it in a session</td>
<td><span class="yes">read</span>. <span class="no">Not change, not delete (403)</span></td>
<td><span class="yes">everything</span></td></tr>
</tbody>
</table>

More precisely:

| Action | Rule |
|---|---|
| **List** | Everybody sees the validated entries. A signed-in user also sees their own. An administrator sees all. Asking for a status (`?status=draft`) only narrows what you may already see. |
| **Create** | Any signed-in user. The entry starts as `draft`. A visitor gets 401. |
| **Change** | The author while the entry is `draft` or `waiting validation`; an administrator always. Nobody else. |
| **Delete** | The author while it is a `draft` (not once submitted: withdraw it first); an administrator always. |
| **Change the status** | The author moves it between `draft` and `waiting validation`. Only an administrator sets `validated` (anyone else gets 400 "Only administrators can validate"). |
| **Use it in a session** | Any user may attach a `validated` entry or one of their own. The API refuses another user's draft. |

### What differs from the rule

| Object | Difference |
|---|---|
| **Study** | Private to its author (and the administrators): nobody else lists, picks or opens it. It is **never reviewed**, so it stays `draft`. Its name is still shown on a shared session. A visitor gets 401. |
| **Protocol** | Its name is a code built from its fields and it has no free text, so it is **validated as soon as it is saved**. Creating one that already exists returns the existing one. It is then locked for its author like any validated entry. |
| **Strain from an ontology** | Validated at once: its term is checked at the source (EFO, Rat Strain Ontology). There is only one strain per term: asking again returns it. |
| **Species** | Everybody reads. Only an administrator creates, changes or deletes. |
| **Software** | An extra lock: a software or a version that **sessions of other people use** cannot be changed or deleted, not even by an administrator (change it in the Django admin if it is really needed). Deleting the last version of a software deletes the software. |
| **Contact** | Readable like the others, but the **e-mail is hidden from visitors** (and cannot be searched by them). |
| **Subject** (an individual animal) | Has no status. A subject is listed with the files that are visible: a visitor only meets those of public sessions; the author meets their own; an administrator all. |
| **Favorite** | Each user only sees and removes their own favorites. Allowed targets: protocol, hardware, software, animal profile, strain, laboratory, reference, contact. |
| **User profile** | A user sees and edits **their own** profile only; an administrator sees all (profiles hold e-mails). |
| **Repository** | Everybody reads the list. It is managed in the Django admin. |

## Recording sessions

A session is the centre of the data: protocol, animals, equipment and files hang from it. Its rules are
decided in one place, `utils/session_rights.py`, and the API sends them with each session (the `rights` field),
so the website only follows them.

<table>
<thead>
<tr><th>Status</th><th>Visitor / other user</th><th>Author</th><th>Administrator</th></tr>
</thead>
<tbody>
<tr><td><span class="pill grey">draft</span></td>
<td><span class="no">nothing</span> (the session and its files are private)</td>
<td><span class="yes">edit</span>, <span class="yes">share</span>, <span class="yes">delete</span>, add files</td>
<td><span class="yes">everything</span> (Django admin, review page)</td></tr>
<tr><td><span class="pill blue">waiting validation</span></td>
<td><span class="no">nothing</span></td>
<td><span class="no">cannot edit (403)</span>; <span class="yes">withdraw</span> (back to draft); <span class="no">cannot delete</span>; may still add files</td>
<td><span class="yes">everything</span>: validates the session with what it uses, or sends it back</td></tr>
<tr><td><span class="pill green">shared</span></td>
<td><span class="yes">read</span> (validated parts only)</td>
<td><span class="yes">edit</span> (it stays public), <span class="yes">publish in a repository</span>, add files; <span class="no">cannot delete, cannot unshare</span></td>
<td><span class="yes">everything</span></td></tr>
<tr><td><span class="pill red">published</span></td>
<td><span class="yes">read</span> (validated parts only), DOI</td>
<td><span class="yes">edit</span> (its record in the repository follows), <span class="yes">new version</span> by adding files; <span class="no">cannot delete</span></td>
<td><span class="yes">everything</span></td></tr>
</tbody>
</table>

### Sharing

When the author asks to share a draft:

- if **everything the session uses is validated**, it becomes `shared` at once;
- otherwise it becomes `waiting validation` (private, locked) and an administrator is e-mailed. It becomes
  `shared` when an administrator validates it **with** what it uses, or as soon as the last missing entry is
  validated one by one. The author is told by e-mail. An administrator may also send it back to draft with a
  reason.

The author can withdraw a session that waits for review, then edit it. A shared session cannot be taken back
to a draft by its author.

### A public session is edited without being hidden

A **shared or published session stays editable by its author and stays public**. What it uses and nobody
validated yet (a new microphone, an animal profile, a strain…) is simply **not shown to the others** until an
administrator validates it. The author and the administrators see everything.

What "not shown" covers, on every public route: the list and the detail of the files, the datasets and their
metadata export, the search (a hidden entry cannot be found by its name), the subjects, and the state of the
record in the repository. Hidden for the others: the protocol or the laboratory if they are not validated,
every animal profile, equipment or reference that is not validated, and the unvalidated references or contacts
of a validated equipment.

While something is hidden, the session **cannot be deposited in a repository** (409): the public must never
read in the description of a record what the site itself hides. A published session keeps its record, whose
update waits for the validation (`zenodo_state` = `blocked`) and then runs by itself.

### Where the session API sends you

| Request | Result |
|---|---|
| `GET /api/recording-session/` | The **author's own** sessions (this route is the author's workspace; public sessions are read through the files and datasets). |
| `PATCH` a session under review | 403 with the reason, unless the request only sets `status: "draft"` (withdraw). |
| `DELETE` a session that is not a draft | 403. |
| `POST /api/file/publish_session/` | The author (or an administrator); 409 if the session uses unvalidated entries, or is not shared, or has nothing new. |
| `POST /api/recording-session/<id>/auto-publish/` | The author, while the session waits for review: approves the preview so it is published when validated. |

## Files

| Action | Visitor | Other user | Author | Administrator |
|---|---|---|---|---|
| **See** the file (list, detail, download counter) | <span class="yes">if its session is shared or published</span> | same | <span class="yes">always</span> | <span class="yes">always</span> |
| **Add** a file | <span class="no">401</span> | <span class="no">403</span> (not their session) | <span class="yes">to their own session</span> | <span class="yes">yes</span> |
| **Change** the file | <span class="no">401</span> | <span class="no">403 / 404</span> | <span class="yes">yes</span> | <span class="yes">yes</span> |
| **Delete** the file | <span class="no">401</span> | <span class="no">403 / 404</span> | <span class="yes">yes</span>, except a file of a published version (409) | same |
| **Spectrogram and plot** | no | no | <span class="no">no (403)</span> | <span class="yes">yes</span> |
| **Add detection results** (USV) | no | no | <span class="yes">yes</span>, on their own file | <span class="yes">yes</span> |
| **Count a download** | <span class="yes">yes</span>, once per visitor, file and hour | same | same | same |
| **See the files of the Zenodo record** (`GET /api/file/<id>/zenodo-files/`) | <span class="yes">if its session is shared or published</span> | same | <span class="yes">always</span> | <span class="yes">always</span> |
| **Zip of a record** (`POST /api/file/<id>/record-download/`) | <span class="no">401</span> | <span class="yes">of the files they may see</span> | <span class="yes">yes</span> | <span class="yes">yes</span> |
| **Zip of a dataset** (`POST /api/dataset/<id>/download/`) | <span class="no">401</span> | <span class="yes">what the page shows them</span> | same | <span class="yes">yes</span>, drafts too |

A file of a draft or of a session under review answers **404** to everybody but its author and the
administrators.

## Administrator-only surfaces

| Surface | What it does |
|---|---|
| **Django admin** (`/admin/`) | Moderation of every type, accounts, repositories. Saving a session as *shared* validates what it uses. |
| **`/api/review/…`** | The review page of the website: lists what waits, validates or sends back, accounts requests. 403 for everybody else. |
| **`/api/admin/link-check/`** | Check of the download links. |
| **Datasets** | Create, change and delete are administrator-only; reading is open (a draft session put in a dataset stays private). |
| **Species** | Create, change, delete. |
| **Spectrogram and plot of a file** | Set or remove. |

## Accounts

A visitor registers with an institutional e-mail address. The account is **inactive** until the user confirms
the e-mail **and** an administrator activates it; an inactive account gets no token. ORCID is linked by a signed
proof, never typed. See [Account requests](accounts.md).

## Where the rules live

| Rule | Code | Test |
|---|---|---|
| Who sees, changes and deletes a catalog entry | `views.py` (`visible_to`, `IsCreatorOrReadOnly`, the `ModerationMixin` of the serializers) | `test_rights_matrix.py` |
| What a user may do with a session | `utils/session_rights.py` (`session_rights`), applied by the serializer and `IsCreatorOrReadOnly` | `test_session_rights.py` (every status and role) |
| What the public sees of a public session | `utils/moderation.py` (`public_session_data`, `sees_everything`), `views.py` (`visible_files`) | `test_public_visibility.py` (reads every public route with sentinels) |
| Status changes and review | `utils/moderation.py` (`validate_session`, `promote_ready_sessions`, `send_back`) | `test_security.py` (`ModerationTests`) |
| Publication in a repository | `utils/publication.py`, `tasks.py` | `test_security.py` (`PublishSessionTests`, `AutoPublishTests`) |

!!! note "When you add an object or a route"
    Decide its row in these tables first. A new moderated catalog joins `CatalogRightsTests`; a new public
    route that shows a session or its entries must be added to the routes `test_public_visibility.py` reads.
