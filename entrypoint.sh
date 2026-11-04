#!/bin/bash

if [ -z "$DB_ROOT_PASS" ]; then
    echo "❌ DB_ROOT_PASS is not set."
    exit 1
fi

echo "⏳ Waiting for MariaDB to be ready..."
until mariadb -h db -u root -p"$DB_ROOT_PASS" -e "SELECT 1" &>/dev/null || mariadb -h db -u root -e "SELECT 1" &>/dev/null; do
    echo "⏳ MariaDB is not ready yet, retrying in 5 seconds..."
    sleep 5
done
echo "✅ MariaDB is ready!"

echo "🔍 Checking root access..."
if mariadb -h db -u root -p"$DB_ROOT_PASS" -e "SELECT 1" &>/dev/null; then
    echo "✅ Root password is already set. Proceeding..."
else
    echo "⚠️ No root password detected. Setting a new password..."

    mariadb -h db -u root <<EOF
ALTER USER 'root'@'localhost' IDENTIFIED BY '$DB_ROOT_PASS';
FLUSH PRIVILEGES;
EOF
    if [ $? -ne 0 ]; then
        echo "❌ Failed to set root password."
        exit 1
    fi
    echo "✅ Root password successfully set."
fi

if [ -z "$DB_NAME" ] || [ -z "$DB_USER" ] || [ -z "$DB_PASSWORD" ]; then
    echo "❌ DB_NAME, DB_USER, or DB_PASSWORD is not set."
    exit 1
fi

if [ "$RESET_DB" = "true" ]; then
    echo "🚀 RESET_DB=true → Recreating the database..."
    mariadb -h db -u root -p"$DB_ROOT_PASS" <<EOF
DROP DATABASE IF EXISTS $DB_NAME;
CREATE DATABASE $DB_NAME;
CREATE USER IF NOT EXISTS '$DB_USER'@'localhost' IDENTIFIED BY '$DB_PASSWORD';
GRANT ALL PRIVILEGES ON $DB_NAME.* TO '$DB_USER'@'localhost';
FLUSH PRIVILEGES;
EOF
else
    echo "🛠️ RESET_DB=false → Ensuring database $DB_NAME exists..."
    mariadb -h db -u root -p"$DB_ROOT_PASS" -e "CREATE DATABASE IF NOT EXISTS $DB_NAME;"
    mariadb -h db -u root -p"$DB_ROOT_PASS" -e "CREATE USER IF NOT EXISTS '$DB_USER'@'localhost' IDENTIFIED BY '$DB_PASSWORD';"
    mariadb -h db -u root -p"$DB_ROOT_PASS" -e "GRANT ALL PRIVILEGES ON $DB_NAME.* TO '$DB_USER'@'localhost'; FLUSH PRIVILEGES;"
fi

echo "🛠️ Running makemigrations..."
python3 manage.py makemigrations mousetube_api --noinput

echo "📦 Applying migrations..."
python3 manage.py migrate --noinput

# 🚨 Explicit check of critical tables before loading data
echo "🔍 Verifying that all required tables exist before loading fixtures..."
REQUIRED_TABLE="mousetube_api_protocol"
TABLE_EXISTS=$(echo "SHOW TABLES LIKE '$REQUIRED_TABLE';" | mariadb -h db -u "$DB_USER" -p"$DB_PASSWORD" "$DB_NAME")

if echo "$TABLE_EXISTS" | grep -q "$REQUIRED_TABLE"; then
    echo "✅ Table $REQUIRED_TABLE found, safe to load fixture."
else
    echo "❌ Required table $REQUIRED_TABLE does not exist. Migration may have failed. Aborting fixture load."
    exit 1
fi

# ✅ Loading fixtures if the table is empty
if [ -n "$FIXTURE_FILE" ] && [ -f "$FIXTURE_FILE" ]; then
    echo "🔍 Checking if the corresponding table is empty before loading fixture..."

    TABLE_NAME="mousetube_api_protocol"

    ROW_COUNT=$(echo "SELECT COUNT(*) FROM $TABLE_NAME;" | mariadb -h db -u "$DB_USER" -p"$DB_PASSWORD" "$DB_NAME" -N)

    if [ "$ROW_COUNT" -eq 0 ]; then
        echo "📥 Table $TABLE_NAME is empty. Loading fixture from $FIXTURE_FILE..."
        python3 manage.py loaddata "$FIXTURE_FILE"
    else
        echo "✅ Table $TABLE_NAME already contains data ($ROW_COUNT rows). Skipping fixture loading."
    fi
else
    echo "⚠️ Fixture file not found or not defined. Skipping fixture loading."
fi

# ✅ Always collect static files so nginx can serve /static/ (admin CSS, DRF browsable API)
echo "🧪 Collecting static files..."
python3 manage.py collectstatic --noinput

# ✅ Starting the server
if [ "$(echo "$DEBUG" | tr '[:upper:]' '[:lower:]')" = "false" ]; then
    echo "🚀 Starting Gunicorn server..."
    exec gunicorn mousetube_api.asgi:application --bind 0.0.0.0:8000 --timeout 420 -k uvicorn.workers.UvicornWorker
else
    echo "⚙️ Starting development server..."
    exec python3 manage.py runserver 0.0.0.0:8000
fi