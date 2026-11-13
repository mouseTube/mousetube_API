<h1 align="center">MouseTube API</h1>

![Build Passing](https://img.shields.io/github/actions/workflow/status/mouseTube/mousetube_API/ci.yml?branch=main)
[![Python 3.13](https://img.shields.io/badge/Python-3.13-blue.svg)](https://www.python.org/downloads/)
[![Django 5.2](https://img.shields.io/badge/Django-5.2%20LTS-blue.svg)](https://www.djangoproject.com/download/)
[![Django REST framework 3.18](https://img.shields.io/badge/Django%20REST%20framework-3.18-blue.svg)](https://www.django-rest-framework.org/)
[![Documentation](https://img.shields.io/badge/docs-available-brightgreen)](https://mousetube.github.io/mousetube_APIv0-5/)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)

<p align="center">
  <img src="https://mousetube.pasteur.fr/images/logo_mousetube_big.png" alt="Mousetube" width="50%">
</p>

## What is mouseTube?

**MouseTube** is a database designed to facilitate sharing, archiving, and analyzing raw recording files of rodent ultrasonic vocalizations following the FAIR (Findable, Accessible, Interoperable, Reusable) principles ([Wilkinson et al., 2016](https://doi.org/10.1038/sdata.2016.18)).

## Installation

### 1. Create a Python environment

Python **3.13** is required. We recommend creating a virtual environment to isolate the project's dependencies.

```bash
# Create a virtual environment
python3 -m venv .venv

# Activate it
# On Linux/macOS:
source .venv/bin/activate
```

### 2. Create a `.env` file

Copy the example and fill it in:

```bash
cp .env.example .env
```

The settings read `.env` at the root of the project, then `/etc/mousetube/mousetube.env` if there is no `.env`.

| Variable | Required | Default | Notes |
|---|---|---|---|
| `DEBUG` | no | `false` | `true` only for local development. |
| `SECRET_KEY` | **yes when `DEBUG` is false** | none | The app refuses to start without it. Generate one with `python -c "from django.core.management.utils import get_random_secret_key as k; print(k())"`. |
| `ALLOWED_HOSTS` | yes in production | `localhost,127.0.0.1` | Comma-separated. |
| `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS` | yes in production | localhost:3000 and mousetube.local | Comma-separated origins of the website. |
| `FRONT_DOMAIN` | yes in production | `localhost:3000` | Used in e-mail links and the ORCID redirect. |
| `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` | yes | host `127.0.0.1`, port `3306` | `DB_ROOT_PASS` is also read by the Docker entrypoint. |
| `DB_SSL`, `DB_SSL_CA`, `DB_SSL_CERT`, `DB_SSL_KEY` | no | `False` | |
| `CELERY_BROKER_URL` | yes | `redis://127.0.0.1:6379/0` | Redis, see step 4. |
| `CACHE_URL` | no | same Redis server, db `1` | Shared cache used by the rate limits. |
| `DRF_NUM_PROXIES` | **yes behind proxies** | `0` | Number of reverse proxies in front of Django (HAProxy + nginx = `2`). With `0` every visitor shares the proxy's IP, so the login limit (10/min) applies to the whole site. Check that your proxy sets `X-Forwarded-For`. |
| `SECURE_HSTS_SECONDS` | no | `31536000` | Only applied when `DEBUG` is false. |
| `USE_X_FORWARDED_HOST` | no | `false` | |
| `ZENODO_API`, `ZENODO_TOKEN` | to publish | sandbox URL, empty | The token is sent as a Bearer header, never in a URL. |
| `CLIENT_ID`, `CLIENT_SECRET` | for ORCID login | empty | ORCID OAuth application. |
| `REQUIRE_INSTITUTIONAL_EMAIL` | no | `true` | Registration is refused for personal addresses (Gmail, Outlook...), see `mousetube_api/utils/email_domains.py`. Set `false` in local development if you only have a personal address. |
| `ORCID_BASE_DOMAIN` | no | `orcid.org` | Use `sandbox.orcid.org` with a sandbox application. |
| `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_USER`, `EMAIL_PASSWORD`, `EMAIL_USE_TLS` | **yes in production** | no `EMAIL_HOST` = e-mails are printed in the logs | SMTP server. Needed for the confirmation e-mails below. |
| `DEFAULT_ADMIN_EMAIL`, `DEFAULT_FROM_EMAIL` | yes in production | `mousetube@igbmc.fr`, `no-reply@mousetube.com` | The admin address receives the account requests. |
| `ADMIN_BASE_URL` | no | `http://localhost:8000` in debug, otherwise `https://FRONT_DOMAIN` | Base of the admin link written in the e-mail to the admin. |
| `DJOSER_SEND_ACTIVATION_EMAIL` | no | `true` | Keep it on: it sends the confirmation link to new users. |

### Account requests

1. The user registers with an **institutional** e-mail address (personal providers such as Gmail are refused).
2. The account is created **inactive** and the user receives a link to confirm the address.
3. Once the link is opened, `DEFAULT_ADMIN_EMAIL` receives a message with a link to the account in the admin. Opening the link twice does not send a second message.
4. In the admin, **Users**, the filter *Account request* gives two lists: *To review (e-mail confirmed)* and *Waiting for e-mail confirmation*. The link in the e-mail to the admin opens the first one. For each request the admin can:
   - tick **Active** on the account and save, or select several and run **Activate selected accounts** (refused if the e-mail is not confirmed);
   - select them and run **Reject selected requests**: a page asks for an optional reason, then the request is deleted and the person is told by e-mail. Only inactive accounts that never logged in can be rejected; if the e-mail cannot be sent, the request is kept.
5. The user receives an e-mail saying the account is active (or the refusal, with the reason).

Docker-only variables: `RESET_DB=true` recreates the database. It is refused when `DEBUG=false`. Migrations are generated and applied when the container starts (`makemigrations`, `migrate`) and are not versioned; the conversions of existing rows that a structure change needs are done by `python manage.py normalize_data`, which the container runs after `migrate` (it is safe to run again).

### 3. Install and start MariaDB

Before proceeding, ensure that MariaDB is installed and running. If it's not installed, use the following commands:

```bash
# Install MariaDB (if not already done)
sudo apt-get update
sudo apt-get install mariadb-server

# Start the MariaDB service
sudo systemctl start mariadb

# Verify MariaDB is running
sudo systemctl status mariadb
```

### 4. Install and start Redis

Redis is needed by Celery (background tasks) and by the shared cache that backs the login rate limit. Without it, login requests fail.

```bash
sudo apt-get install redis-server
sudo systemctl start redis-server
```

### 5. Install system dependencies

You will need to install some system dependencies before installing **mousetube_api**:

```bash
# Install necessary dependencies for MariaDB integration
sudo apt-get install pkg-config
sudo apt-get install libmariadb-dev
```

### 6. Install Python dependencies

Once the system dependencies are installed, install **mousetube_api** and its Python dependencies:

```bash
pip install -e .
```

### 7. Run the server in development mode

Finally, start the Django development server:

```bash
mousetube_api runserver
```

### 8. Run the tests

The test runner creates its own database, so the database user needs the right to create one.

```bash
python manage.py test mousetube_api.tests
```

## Docker Alternative FullStack Installation

1. Clone the repositories:

   ```bash
   git clone https://github.com/mouseTube/mousetube_API.git
   git clone https://github.com/mouseTube/mousetube_frontend.git
   ```

2. Add a .env file in the mousetube_API folder as described earlier in the section "2. Create a .env file". In Docker, use `DB_HOST=db` and `CELERY_BROKER_URL=redis://redis:6379/0`. Both repositories must sit side by side (the compose file builds `../mousetube_frontend`).

3. Add a .env file in the mousetube_frontend folder with the following content:

   ```env
   DEBUG=true
   NUXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000/api
   ```

4. Navigate to the mousetube_API folder and run the following command to build the Docker image and start all required services:

   ```bash
   docker compose up --build
   ```

   This starts MariaDB, Redis, the API (http://localhost:8000), Celery, the website (http://localhost:3000) and nginx. The database and Redis ports are only published on `127.0.0.1`.

### Docker Stop and Clean Up

To stop the running containers:

```bash
docker compose down
```

To stop and remove all containers, networks, and volumes created by Docker Compose:

```bash
docker compose down -v
```

To remove all unused Docker images and free up space (optional):

```bash
docker image prune -a
```

**⚠️ Warning:** `docker image prune -a` will remove **all** images not currently used by any container. Use it only if you're sure you don't need them anymore.

## Check out mouseTube's publications:

- Torquet N., de Chaumont F., Faure P., Bourgeron T., Ey E. mouseTube – a database to collaboratively unravel mouse ultrasonic communication [version 1; peer review: 2 approved]. F1000Research 2016, 5:2332 ([F1000Research Link](https://doi.org/10.12688/f1000research.9439.1)) (2016).

## Datasets

A dataset is a set of recording sessions; the page shows the files of those sessions.

- **Metadata JSON (public):** `GET /api/dataset/<id>/metadata/` gives one dataset, `GET /api/dataset/metadata/` all of them. It lists the sessions with protocol, laboratory, animals, equipment, references and files (DOI, repository). Contact e-mails are never included.
- **Add a dataset (admins only):** in the admin, *Mousetube_Api > Datasets > Add*, or on the website, page *Dataset*, button *Add a dataset*. The API (`POST /api/dataset/`) refuses everyone else.
- **Import from mouseTube 0.5 or from another instance:**

  ```bash
  python manage.py import_dataset_metadata --url https://mousetube.fr/api/dataset/ --dry-run
  python manage.py import_dataset_metadata --url https://mousetube.fr/api/dataset/
  ```

  Add `--with-images` to also copy the spectrogram and plot image of each file from the old site into `media/` (about 100 MB for the two datasets of mouseTube 0.5; the images are files stored on the old server, not Zenodo previews). The 0.5 download counters are imported too.

  `--file` reads a saved JSON, `--created-by USERNAME` sets the owner of the created records (default: first superuser; sessions need one). Running it twice creates nothing new. Protocols are matched on their attributes because `Protocol.save()` rewrites their name.

## Moderation: statuses and review

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

### Administrator's interface (Django admin)

- The home of `/admin/` lists what waits for a decision, with the account requests.
- Each type has a status filter and the actions *Validate the selected entries* and
  *Send back to draft (with a reason)*. The owner is told by e-mail (when we have an
  address), and the administrator is told when something is submitted.
- A session shows the entries it still needs validated.

### Review page (website, administrators only)

`/review` on the website does the same decisions in one place: one tab per kind (account
requests, sessions, software, hardware, laboratories, references, contacts, studies, strains,
animal profiles) with the number waiting, the oldest first. Each item can be validated or
sent back with a reason, one by one or several at once; an account request is activated or
rejected (only a brand-new one can be rejected). A session is validated with everything it
uses. The link, with the count, is in the *Add* menu of the header for administrators.
It uses `GET /api/review/`, `GET /api/review/<kind>/` and
`POST /api/review/<kind>/decision/` (`{"action": "validate" | "send_back", "ids": [...],
"reason": "..."}`), which are for staff only.

## Published sessions and versions

A published session keeps living (the record in the repository is the one of its session):

- the author can **edit it**; the description and keywords of its record in the repository
  follow, in the background (`update_published_record`), without a new version: the record is
  unlocked, updated and published again with the same DOI. The state is shown on the session
  (`zenodo_state`: up to date, in progress, waiting, failed). If the edit makes it use entries
  nobody validated yet, the update waits for their validation (`blocked`) and runs by itself when
  an administrator validates them, so the public never reads about an unvalidated entry
- the author can **add files**: they go to the draft of a **new version** of the record (the
  draft holds the files of the version before); *Publish a new version* publishes it. Each
  version has its own DOI (`PublicationVersion`), the DOI of the whole is `concept_doi`;
  a file of a published version cannot be removed, a file waiting for the next version can
- it only works for records that mouseTube published itself: a session imported with the DOI of
  a record made elsewhere has no version to follow

## Vocabularies (ontologies)

Some fields point to a term of a controlled vocabulary next to their free text. The term is
checked at its source (EBI Ontology Lookup Service, ROR registry) before it is stored.

| Field | Vocabulary |
|---|---|
| Species | NCBI Taxonomy |
| Strain | Experimental Factor Ontology (EFO) for mice, e.g. C57BL/6J `EFO:0000606`; Rat Strain Ontology (RS) for rats (`&ontology=rs` in the search) |
| Sex of an animal profile | PATO (filled from male / female) |
| Developmental stage | Mouse Developmental Stages (MmusDv) for mice; generic stages of Uberon for other species (filled from pup / juvenile / adult) |
| Treatment compound | ChEBI |
| Behaviors of a session | Neuro Behavior Ontology (NBO) |
| Organization of a laboratory | ROR registry |

`GET /api/ontology/search/?field=<field>&q=<text>` (signed-in users, 60/min) feeds the
autocomplete. The units of the numeric fields are documented with the Units Ontology
(hertz `UO:0000106`, second `UO:0000010`, degree Celsius `UO:0000027`, lux `UO:0000116`).
