#!/bin/bash

set -e

FIXTURE_FILE=./exported_data.json
DEPLOY=false
UPDATE=false
RESET_DB=false

# Parse arguments
for arg in "$@"; do
    if [[ "$arg" == "deploy" ]]; then
        DEPLOY=true
    elif [[ "$arg" == "update" ]]; then
        UPDATE=true
    elif [[ "$arg" == "reset" ]]; then
        RESET_DB=true
    fi
done

echo "Fixture file to load: $FIXTURE_FILE"

echo "🔧 Checking for MariaDB dependencies..."

# Check dependencies
REQUIRED_PKGS=(
    pkg-config
    libmariadb-dev
    python3-dev
    build-essential
    libssl-dev
    libffi-dev
    python3-pip
)

for pkg in "${REQUIRED_PKGS[@]}"; do
    if ! dpkg -s "$pkg" &>/dev/null; then
        echo "📦 Installing $pkg..."
        sudo apt-get update
        sudo apt-get install -y "$pkg"
    else
        echo "✅ $pkg already installed."
    fi
done

# Check MariaDB server
if ! systemctl is-active --quiet mariadb; then
    echo "🔧 Installing MariaDB server..."
    sudo apt install -y mariadb-server
    echo "🔧 Starting MariaDB server..."
    sudo systemctl start mariadb
else
    echo "✅ MariaDB server is already running."
fi

echo "⏳ Waiting for MariaDB to be ready..."
until sudo mariadb -u root -e "SELECT 1" &>/dev/null; do
    echo "⏳ MariaDB is not ready yet, retrying in 5 seconds..."
    sleep 5
done
echo "✅ MariaDB is ready!"

# Load env
if [ -f mousetube.env ]; then
    export $(grep -v '^#' mousetube.env | xargs)
elif [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
else
    echo "No .env or mousetube.env file found!"
    exit 1
fi

# Check DB vars
if [ -z "$DB_NAME" ] || [ -z "$DB_USER" ] || [ -z "$DB_PASSWORD" ]; then
    echo "❌ DB_NAME, DB_USER or DB_PASSWORD is not set."
    exit 1
fi

# Check and set root password
echo "DB_ROOT_PASS=$DB_ROOT_PASS"
echo "🔍 Checking root access..."
if mariadb -u root -p"$DB_ROOT_PASS" -e "SELECT 1" &>/dev/null; then
    echo "✅ Root password is already set. Proceeding..."
else
    echo "⚠️ No root password detected or invalid. Attempting to set password..."

    if [ -z "$DB_ROOT_PASS" ]; then
        echo "❌ DB_ROOT_PASS is not set."
        exit 1
    fi

    sudo mariadb <<EOF
SET PASSWORD FOR 'root'@'localhost' = PASSWORD('$DB_ROOT_PASS');
FLUSH PRIVILEGES;
EOF

    if [ $? -ne 0 ]; then
        echo "❌ Failed to set root password."
        exit 1
    fi
    echo "✅ Root password successfully set."
fi

# Reset or create DB
if [ "$RESET_DB" = true ]; then
    echo "🚀 RESET_DB=true → Recreating the database '$DB_NAME'..."
    sudo mariadb -u root -p"$DB_ROOT_PASS" <<EOF
DROP DATABASE IF EXISTS $DB_NAME;
CREATE DATABASE $DB_NAME;
CREATE USER IF NOT EXISTS '$DB_USER'@'localhost' IDENTIFIED BY '$DB_PASSWORD';
GRANT ALL PRIVILEGES ON $DB_NAME.* TO '$DB_USER'@'localhost';
FLUSH PRIVILEGES;
EOF
else
    echo "🔍 Checking if database '$DB_NAME' exists and has tables..."
    DB_TABLE_COUNT=$(mysql -u root -p"$DB_ROOT_PASS" -N -B -e "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = '$DB_NAME';")
    if [ "$DB_TABLE_COUNT" -eq 0 ]; then
        echo "⚠️ Database is empty. Creating DB and user..."
        sudo mariadb -u root -p"$DB_ROOT_PASS" <<EOF
CREATE DATABASE IF NOT EXISTS $DB_NAME;
CREATE USER IF NOT EXISTS '$DB_USER'@'localhost' IDENTIFIED BY '$DB_PASSWORD';
GRANT ALL PRIVILEGES ON $DB_NAME.* TO '$DB_USER'@'localhost';
FLUSH PRIVILEGES;
EOF
    else
        echo "✅ Database '$DB_NAME' already contains tables. Skipping creation."
    fi
fi

# Install Python deps
if [ "$UPDATE" == true ] || ! python3 -c "import mousetube_api" &>/dev/null || ! python3 -c "import django" &>/dev/null; then
    echo "📦 Installing/reinstalling Python dependencies..."
    pip install --upgrade pip
    pip install -e .
else
    echo "✅ Python dependencies already installed."
fi

# Migrations
echo "🐍 Running Django migrations..."
python3 manage.py makemigrations mousetube_api --noinput
python3 manage.py migrate --noinput

# Fixtures (conditional load)
if [ -f "$FIXTURE_FILE" ]; then
    echo "🔍 Checking if the table is empty before loading fixture..."
    ROW_COUNT=$(echo "SELECT COUNT(*) FROM mousetube_api_protocol;" | mariadb -u "$DB_USER" -p"$DB_PASSWORD" "$DB_NAME" -N)

    if [ "$ROW_COUNT" -eq 0 ]; then
        echo "📥 Table is empty. Loading fixture from $FIXTURE_FILE..."
        python3 manage.py loaddata "$FIXTURE_FILE"
    else
        echo "✅ Table already contains $ROW_COUNT rows. Skipping fixture loading."
    fi
else
    echo "⚠️ Fixture file not found. Skipping fixture loading."
fi

# Static files (production only)
if [ "$DEBUG" == "false" ]; then
    echo "📦 Collecting static files..."
    python3 manage.py collectstatic --noinput
fi

# Run server
if [ "$DEPLOY" == "true" ]; then
    if [ "$DEBUG" == "false" ]; then
        echo "🚀 Starting Gunicorn server..."
        exec gunicorn mousetube_api.asgi:application --bind 0.0.0.0:8000 --timeout 420 -k uvicorn.workers.UvicornWorker
    else
        echo "⚙️ Starting development server..."
        exec python3 manage.py runserver 0.0.0.0:8000
    fi
else
    echo "✅ Setup complete. Server not started (no 'deploy' flag)."
fi
