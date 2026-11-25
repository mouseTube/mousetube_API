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

## Pre-production: a local HAProxy in front of nginx

`docker-compose.preprod.ifb.yml` starts a `haproxy` container in front of nginx, so that the pre-production has
the same chain as production (**HAProxy → nginx → Django**). It ends the TLS and sends `X-Forwarded-Proto: https`
to Django, which needs it to know that the request was https. nginx has no published port any more.

1. The self-signed certificate is made by itself: the `haproxy-cert` service writes it in the `haproxy_certs` volume
   at the first start, for the name in `DOMAIN` (`mousetube.ifb.local`), and makes it again when it expires within
   30 days or when `DOMAIN` changes (restart `haproxy` after that, it reads the certificate when it starts).
   Browsers warn about it until it is accepted.
2. Start as usual: `docker compose -f docker-compose.preprod.ifb.yml up -d --build`.
3. Two ways in, one chain: `https://mousetube.ifb.local` reaches port 443; the HAProxy of the IFB (public name) sends
   http to port 80 with `X-Forwarded-Proto: https`, which `haproxy` passes on untouched. `DRF_NUM_PROXIES` stays `2` on both.
4. In the `.env` of the API and of the website, use the address people open: `https://mousetube.ifb.local`
   (`CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS`, `FRONT_DOMAIN`, `NUXT_PUBLIC_API_BASE_URL=https://.../api`).
   Keep the security settings at their defaults: this is https, nothing has to be switched off.
