<h1 align="center">MouseTube API</h1>

![Build Passing](https://img.shields.io/github/actions/workflow/status/mouseTube/mousetube_API/ci.yml?branch=main)
[![Python 3.13](https://img.shields.io/badge/Python-3.13-blue.svg)](https://www.python.org/downloads/)
[![Django 5.2](https://img.shields.io/badge/Django-5.2%20LTS-blue.svg)](https://www.djangoproject.com/download/)
[![Django REST framework 3.18](https://img.shields.io/badge/Django%20REST%20framework-3.18-blue.svg)](https://www.django-rest-framework.org/)
[![Documentation](https://img.shields.io/badge/docs-available-brightgreen)](docs/README.md)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)

<p align="center">
  <img src="docs/images/logo_mousetube_big.png" alt="Mousetube" width="50%">
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

For local development you only need `DEBUG=true`, the database settings (`DB_NAME`, `DB_USER`, `DB_PASSWORD`; with Docker also `DB_ROOT_PASS`) and `CELERY_BROKER_URL`. Without `EMAIL_HOST`, e-mails are printed in the logs. All the variables (production, e-mail, ORCID, Zenodo, upload limits...) are described in [docs/configuration.md](docs/configuration.md).

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

`RESET_DB=true` (recreates the database, only with `DEBUG=true`) and the other Docker-only variables are in [docs/configuration.md](docs/configuration.md#docker-only-variables).

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

## Documentation

The `docs/` folder describes the configuration, how to update a deployment and the main features:
[configuration](docs/configuration.md), [updating a deployment](docs/deployment.md), [account requests](docs/accounts.md), [moderation](docs/moderation.md), [datasets](docs/datasets.md), [published sessions and versions](docs/publication.md), [vocabularies](docs/ontologies.md).
