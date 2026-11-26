# REST API

mouseTube is a **JSON REST API** (Django REST framework). The website is only one of its clients: everything
you can do on the site, you can do from a script.

| | |
|---|---|
| **Base URL** | `https://<your mouseTube>/api/` (locally `http://localhost:8000/api/`) |
| **Interactive docs (Swagger)** | `/swagger/` on the same host: try every route in the browser |
| **OpenAPI schema** | `/schema/` (YAML), to generate a client |
| **Format** | JSON in, JSON out. Files are sent as `multipart/form-data`. |
| **Version of the API** | `GET /api/version/` |

!!! tip "Swagger or this page?"
    Swagger lists **every route and field**, always up to date. These pages add what it does not say: **what
    to call to reach a goal** ([Recipes](recipes.md)), **who is allowed to** ([Rights and statuses](../rights.md))
    and the order of the steps (describe, add files, share, publish).

## Authentication

Reading the public data needs **no token**. Everything else needs a **JWT access token**, sent in a header:

```http
Authorization: Bearer <access token>
```

=== "Get a token (curl)"

    ```bash
    curl -s -X POST "$HOST/auth/jwt/create/" \
         -H "Content-Type: application/json" \
         -d '{"username": "alice", "password": "…"}'
    # {"refresh": "eyJ…", "access": "eyJ…"}
    ```

=== "Python"

    ```python
    import requests

    HOST = "http://localhost:8000"  # no /api here: /auth/ is next to /api/
    tokens = requests.post(
        f"{HOST}/auth/jwt/create/", json={"username": "alice", "password": "…"}
    ).json()
    headers = {"Authorization": f"Bearer {tokens['access']}"}
    ```

- The **access token lasts one hour**. Renew it with `POST /auth/jwt/refresh/` and `{"refresh": "…"}`; the
  refresh token lasts longer.
- On the website, **Account → API token** shows the access token of your current session, for a quick test.
- `GET /auth/users/me/` answers who you are (`id`, `username`, `is_staff`…).
- An account that is **not active yet** (e-mail not confirmed, or not accepted by an administrator) gets a
  **401** with `account_status`: `awaiting_email_confirmation` or `awaiting_review`.
- Registration is `POST /auth/users/` (an **institutional** e-mail is required), then the user confirms the
  e-mail and an administrator activates the account. See [Account requests](../accounts.md).
- A sign-in can be **revoked**: `POST /auth/logout_all/` ends every sign-in of the user, and a new password does too.
  The access and the refresh token of a revoked sign-in answer **401**; sign in again. See
  [Log out of all devices](../accounts.md#log-out-of-all-devices).

!!! warning "Token = you"
    Whoever has your token acts as you. Keep it out of code others can read.

## Conventions

### Pagination

Lists are paginated: `?page=2&page_size=20` (default 10, at most 100).

```json
{ "count": 1620, "next": "…/api/file/?page=2&page_size=1", "previous": null, "results": [ … ] }
```

Some short lists (repositories, species used by a form…) answer a plain array: Swagger tells which.

### Search, filters, ordering

`?search=` looks in the text fields of the object and of what it points to; several words must all be found.
Filters are named by what they mean (`species`, `sex`, `age`, `file_format`, `repository`, `type`, `status`…).
Each list says which in Swagger and in the [recipes](recipes.md).

### Statuses and visibility

The lists show **what you may see**: validated entries and your own. An object that is private to someone else
is **404**, not 403. See [Rights and statuses](../rights.md).

### Errors

| Code | Meaning | Body |
|---|---|---|
| **400** | The data is not valid | `{"field": ["message"]}` or `{"non_field_errors": […]}` |
| **401** | Missing or invalid token, or inactive account | `{"detail": "…"}` |
| **403** | You may see it but not do that | `{"detail": "…"}` |
| **404** | Does not exist, or is private to someone else | `{"detail": "…"}` |
| **409** | The state forbids it (nothing new to publish, entries waiting for validation…) | `{"detail": "…"}` |
| **413** | The file is too large | `{"error": "…", "limit": bytes}` |
| **429** | Too many requests (rate limit) | `{"detail": "…"}` |

!!! info "Rate limits"
    Per address: logins and token requests 10 per minute, registrations 20 per hour, vocabulary search 60 per
    minute. A script that gets a 429 must wait.

## Main resources

| Resource | Route | Read | Write |
|---|---|---|---|
| Files (vocalizations) | `/api/file/` | everybody (public sessions) | author |
| Recording sessions | `/api/recording-session/` | their author | their author |
| Protocols | `/api/protocol/` | validated + own | any user (validated at once) |
| Animal profiles, strains, species | `/api/animalprofile/`, `/api/strain/`, `/api/species/` | validated + own | any user (species: administrators) |
| Hardware, software | `/api/hardware/`, `/api/software/` | validated + own | any user |
| Laboratories, references, contacts | `/api/laboratory/`, `/api/reference/`, `/api/contact/` | validated + own | any user |
| Studies | `/api/study/` | their author | their author |
| Datasets | `/api/dataset/` | everybody | administrators |
| Repositories | `/api/repository/` | everybody | Django admin |
| Detection results (USV) | `/api/file/<id>/usv-detections/`, `/api/usv-detection/<id>/` | public files | file author |
| Review (administrators) | `/api/review/…` | administrators | administrators |
| Vocabulary search | `/api/ontology/search/` | signed in | |

Next: [Recipes](recipes.md).
