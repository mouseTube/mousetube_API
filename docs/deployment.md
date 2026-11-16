# Updating a deployment

Both repositories (`mousetube_API` and `mousetube_frontend`) go together: deploy them at the same time. An
old frontend does not work with this API (registration payload, download counter route, status format,
and an access token that now lasts one hour and is renewed by the new frontend).

1. Get the new code in both folders (`git pull`), then rebuild: `docker compose -f docker-compose.prod.yml up -d --build`
   (`update.sh` does the pull, the build and a cleanup).
2. **Restart the Celery worker** if you do not rebuild: it does not reload its code, and a stale worker fails on
   new models and tasks.
3. Migrations are generated and applied when the `web` container starts (they are not versioned: keep the
   working folder, its `migrations/` directory belongs to the machine). Conversions of existing rows are done
   by `python manage.py normalize_data`, which the entrypoint runs after `migrate` and which is safe to run again
   (run it by hand if the container is started without the entrypoint).
4. Set `DRF_NUM_PROXIES` to the number of reverse proxies (nginx, HAProxy): with `0`, every visitor shares one
   address and the rate limits apply to the whole site. The container warns at start when it is `0` outside debug.
5. `DEBUG` defaults to false: a development environment needs a `.env` (see `.env.example`). `RESET_DB=true` is
   refused unless `DEBUG=true`. In production the frontend container needs `DEBUG=false` or no `DEBUG`, never `true`.
6. Take a dump of the database before a big update (`docker compose exec db mariadb-dump ...`).
