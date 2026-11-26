# Configuration

The settings read `.env` at the root of the project, then `/etc/mousetube/mousetube.env` if there is no `.env`.
Copy the example and fill it in (`cp .env.example .env`): see also the [README](https://github.com/mouseTube/mousetube_API#2-create-a-env-file).

## Environment variables

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
| `DRF_NUM_PROXIES` | **yes behind proxies** | `0` | Number of reverse proxies in front of Django (HAProxy + nginx = `2`). With `0` every visitor shares the proxy's IP, so the login limit (10/min) applies to the whole site (the container warns at start when it is `0` outside debug). Check that your proxy sets `X-Forwarded-For`. |
| `SECURE_HSTS_SECONDS` | no | `31536000` | Only applied when `DEBUG` is false. |
| `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `FRONT_SCHEME` | no | `true` (redirect: `true` unless `DEBUG`), `true`, `true`, `https` unless `DEBUG` | Only for a site served over plain **http** on an internal network, where no proxy adds https: set the first three to `false` and `FRONT_SCHEME=http`. Without it the API redirects every request to https, the browser drops the session and CSRF cookies (so the admin and ORCID sign-in do not work) and the links of the e-mails start with `https`. Cookies are then `SameSite=Lax`, which is enough when the site and the API are behind the same address. Never in production. |
| `USE_X_FORWARDED_HOST` | no | `false` | |
| `ZENODO_API`, `ZENODO_TOKEN` | to publish | sandbox URL, empty | The token is sent as a Bearer header, never in a URL. |
| `CLIENT_ID`, `CLIENT_SECRET` | for ORCID login | empty | ORCID OAuth application. |
| `REQUIRE_INSTITUTIONAL_EMAIL` | no | `true` | Registration is refused for personal addresses (Gmail, Outlook...), see `mousetube_api/utils/email_domains.py`. Set `false` in local development if you only have a personal address. |
| `MAX_UPLOAD_SIZE` | no | `5368709120` (5 GiB) | Ceiling of one uploaded file, in bytes. Keep nginx `client_max_body_size` at least as large. |
| `UPLOAD_FREE_SPACE_RESERVE` | no | `1073741824` (1 GiB) | Free disk space an upload always leaves. What a file may weigh at a given moment is the lower of `MAX_UPLOAD_SIZE` and what the disk holds (halved when the temporary copy and `media/` share a disk, minus the uploads being received and this reserve): `GET /api/file/upload-limit/` gives it, and the file form checks it before sending. |
| `DATASET_ZIP_MAX_FILES`, `DATASET_ZIP_MAX_BYTES`, `DATASET_ZIP_PARALLEL` | no | `500`, `21474836480` (20 GiB), `2` | The zip of a dataset (signed-in users only) comes in two kinds, chosen by the user: the recordings only, or every file of the Zenodo records of the recordings (the tables and images that go with them too), one folder per record. It is sent while it is made: nothing is written on the server, so there is no disk space to count and nothing to clean. These limit the files and the bytes of one zip (checked before it starts) and how many zips the whole server makes at the same time (one per user). |
| `ORCID_BASE_DOMAIN` | no | `orcid.org` | Use `sandbox.orcid.org` with a sandbox application. |
| `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_USER`, `EMAIL_PASSWORD`, `EMAIL_USE_TLS` | **yes in production** | no `EMAIL_HOST` = e-mails are printed in the logs | SMTP server. Needed for the confirmation e-mails below. |
| `DEFAULT_ADMIN_EMAIL`, `DEFAULT_FROM_EMAIL` | yes in production | `mousetube@igbmc.fr`, `no-reply@mousetube.com` | The admin address receives the account requests. |
| `ADMIN_BASE_URL` | no | `http://localhost:8000` in debug, otherwise `https://FRONT_DOMAIN` | Base of the admin link written in the e-mail to the admin. |
| `DJOSER_SEND_ACTIVATION_EMAIL` | no | `true` | Keep it on: it sends the confirmation link to new users. |

## Docker-only variables

`RESET_DB=true` recreates the database. It is refused unless `DEBUG=true` (an unset `DEBUG` counts as false). The migrations are versioned (`mousetube_api/migrations/`) and applied when the container starts (`migrate`); the conversions of existing rows that a structure change needs are done by `python manage.py normalize_data`, which the container runs after `migrate` (it is safe to run again).
