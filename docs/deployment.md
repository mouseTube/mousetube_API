# Updating a deployment

Both repositories (`mousetube_API` and `mousetube_frontend`) go together: deploy them at the same time. An
old frontend does not work with this API (registration payload, download counter route, status format,
and an access token that now lasts one hour and is renewed by the new frontend).

1. Get the new code in both folders (`git pull`), then rebuild: `docker compose -f docker-compose.prod.yml up -d --build`
   (`update.sh` does the pull, the build and a cleanup).
2. **Restart the Celery worker** if you do not rebuild: it does not reload its code, and a stale worker fails on
   new models and tasks.
3. The migrations are versioned (`mousetube_api/migrations/`): the `web` container applies them when it starts
   (`migrate`); it never generates any. After a change of the models, run `python manage.py makemigrations`,
   read the file and commit it (a test fails when a model changed without its migration). Conversions of
   existing rows are done by `python manage.py normalize_data`, which the entrypoint runs after `migrate` and
   which is safe to run again (run it by hand if the container is started without the entrypoint).
4. Set `DRF_NUM_PROXIES` to the number of reverse proxies (nginx, HAProxy): with `0`, every visitor shares one
   address and the rate limits apply to the whole site. The container warns at start when it is `0` outside debug.
5. `DEBUG` defaults to false: a development environment needs a `.env` (see `.env.example`). `RESET_DB=true` is
   refused unless `DEBUG=true`. In production the frontend container needs `DEBUG=false` or no `DEBUG`, never `true`.
6. Take a dump of the database before a big update (`docker compose exec db mariadb-dump ...`).
7. Rebuild the image when a dependency is added (`defusedxml` reads the tables of the detection tools); `--build` does it. The Celery worker must know the tasks of the new version (the check of the links is one).
8. The tables that authors chose to send to Zenodo are kept in `media/usv_results/` until they are published: include `media/` in the backups.
9. The version of the API is the one of `pyproject.toml` (the documentation and `GET /api/version/` give it); the one of the website is in its `package.json`. The footer of the site shows both.
