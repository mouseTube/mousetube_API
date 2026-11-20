# Contributing

## Set up

Follow the [README](https://github.com/mouseTube/mousetube_API#readme) to run the API with Docker, and
[Configuration](configuration.md) for the `.env`. With `DEBUG=true` and the database settings you can work
locally.

## Check your work

```bash
python manage.py test mousetube_api.tests     # the tests (in the web container)
ruff check . && ruff format --check .         # style and lint
bandit -r mousetube_api -x mousetube_api/tests -ll   # security scan
```

The CI runs ruff and bandit on every pull request. Write a test for what you add: rights, validation and
anything that writes data deserve one.

## Migrations are versioned

Change a model, then:

```bash
python manage.py makemigrations
```

Read the file it writes and **commit it**. A test fails when a model changed without its migration. The
container only runs `migrate`. Conversions of existing rows go in `normalize_data`
(`utils/data_upgrades.py`, safe to run again).

## When you change the rules

The rights are a contract with the website and with the people who script against the API.

- **A new route, or a change of who may use one**: decide its row in [Rights and statuses](rights.md) first, then
  test it. The catalogs are in `test_rights_matrix.py`, the sessions in `test_session_rights.py`.
- **A route that shows a session or what it uses**: it must hide what nobody validated. Add it to the routes
  `test_public_visibility.py` reads with sentinels, and the test will tell you if it leaks.
- **A new moderated catalog**: give it `status` and `created_by`, use `visible_to` in its queryset,
  `IsCreatorOrReadOnly` for changes and the `ModerationMixin` in its serializer, and add it to
  `CatalogRightsTests`.

## Write these pages

The documentation is a [MkDocs Material](https://squidfunk.github.io/mkdocs-material/) site in `docs/`,
published on GitHub Pages by `.github/workflows/docs.yml` when `main` changes.

```bash
pip install -r requirements-docs.txt
mkdocs serve            # http://127.0.0.1:8000 with live reload
mkdocs build --strict   # what the CI runs: a broken link or a missing page fails it
```

- **Two languages.** A page `name.md` is English and `name.fr.md` its French version, side by side. A page
  with no French file shows the English one. Keep both in step.
- **The user guide** is in `docs/user/`, the developer documentation in `docs/dev/`.
- **The database schema** is `docs/assets/schema/schema-en.json` and `schema-fr.json`. A test fails when a
  table or a field of `models.py` is not described in both: add its description (in both languages) when you
  change a model.
- **The Python reference** is generated from the docstrings (`::: mousetube_api.utils.module`). Write a
  docstring when you add a public function; use `Args:` / `Returns:` when the parameters need naming.
- **Screenshots** are in `docs/assets/img/` (PNG, about 1200 px wide). Give each one a useful `alt` text.
- **Accessibility.** One `#` title per page, headings in order, links that say where they go, no information
  carried by colour alone.
