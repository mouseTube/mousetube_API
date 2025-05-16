<h1 align="center">MouseTube API</h1>

![Build Passing](https://img.shields.io/github/actions/workflow/status/mouseTube/mousetube_API/ci.yml?branch=main)
[![Python 3.8+](https://img.shields.io/badge/Python-3.8%2B-blue.svg)](https://www.python.org/downloads/release/python-380/)
[![Django 4.0+](https://img.shields.io/badge/Django-4.0%2B-blue.svg)](https://www.djangoproject.com/download/)
[![Django REST framework 3.12+](https://img.shields.io/badge/Django%20REST%20framework-3.12%2B-blue.svg)](https://www.django-rest-framework.org/community/3.12.0/)
[![Documentation](https://img.shields.io/badge/docs-available-brightgreen)](https://mousetube.github.io/mousetube_APIv0-5/)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)

<p align="center">
  <img src="https://mousetube.pasteur.fr/images/logo_mousetube_big.png" alt="Mousetube" width="50%">
</p>

## What is mouseTube?

**MouseTube** is a database designed to facilitate sharing, archiving, and analyzing raw recording files of rodent ultrasonic vocalizations following the FAIR (Findable, Accessible, Interoperable, Reusable) principles ([Wilkinson et al., 2016](https://doi.org/10.1038/sdata.2016.18)).

## Installation

### 1. Create a Python environment

We recommend creating a virtual environment to isolate the project's dependencies.

```bash
# Create a virtual environment
python3 -m venv .venv

# Activate it
# On Linux/macOS:
source .venv/bin/activate
```

### 2. Create a `.env` file

Create a `.env` file at the root of the project and fill in the following variables:

```env
DEBUG=
ALLOWED_HOSTS=
DB_ENGINE=django.db.backends.mysql
DB_ROOT_PASS=
DB_NAME=
DB_USER=
DB_PASSWORD=
DB_HOST=127.0.0.1
DB_PORT=3306
DB_SSL=True
```

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

### 4. Install system dependencies

You will need to install some system dependencies before installing **mousetube_api**:

```bash
# Install necessary dependencies for MariaDB integration
sudo apt-get install pkg-config
sudo apt-get install libmariadb-dev
```

### 5. Install Python dependencies

Once the system dependencies are installed, install **mousetube_api** and its Python dependencies:

```bash
pip install -e .
```

### 6. Run the server in development mode

Finally, start the Django development server:

```bash
mousetube_api runserver
```

## Docker Alternative FullStack Installation

1. Clone the repositories:

   ```bash
   git clone https://github.com/mouseTube/mousetube_APIv0-5.git
   git clone https://github.com/mouseTube/mousetube_frontendv0-5.git
   ```

2. Add a .env file in the mousetube_APIv0-5 folder as described earlier in the section "2. Create a .env file".

3. Add a .env file in the mousetube_frontendv0-5 folder with the following content:

   ```env
   DEBUG=true
   NUXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000/api
   ```

4. Navigate to the mousetube_APIv0-5 folder and run the following command to build the Docker image and start all required services:

   ```bash
   docker compose up --build
   ```

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
