#!/usr/bin/env bash
set -e

# Parse DATABASE_URL if provided (common in Railway PostgreSQL service)
if [ -n "$DATABASE_URL" ]; then
    eval $(python3 -c "
import urllib.parse, os
url = os.environ.get('DATABASE_URL', '')
if url:
    p = urllib.parse.urlparse(url)
    if p.hostname and not os.environ.get('DB_HOST') and not os.environ.get('PGHOST'):
        print(f'DB_HOST={p.hostname}')
    if p.port and not os.environ.get('DB_PORT') and not os.environ.get('PGPORT'):
        print(f'DB_PORT={p.port}')
    if p.username and not os.environ.get('DB_USER') and not os.environ.get('PGUSER'):
        print(f'DB_USER={p.username}')
    if p.password and not os.environ.get('DB_PASSWORD') and not os.environ.get('PGPASSWORD'):
        print(f'DB_PASSWORD=\"{p.password}\"')
    db = p.path.lstrip('/')
    if db and not os.environ.get('DB_NAME') and not os.environ.get('PGDATABASE'):
        print(f'DB_NAME={db}')
")
fi

# Resolve Database connection settings
# Order of preference: DB_* > PG* > default
HOST="${DB_HOST:-${PGHOST:-db}}"
PORT_NUM="${DB_PORT:-${PGPORT:-5432}}"
USER="${DB_USER:-${PGUSER:-odoo}}"
PASSWORD="${DB_PASSWORD:-${PGPASSWORD:-odoo}}"
DATABASE="${DB_NAME:-${PGDATABASE:-odoo}}"

# Resolve HTTP listening port (Railway dynamically injects $PORT)
HTTP_PORT="${PORT:-8069}"

# Master database management password
ADMIN_PWD="${ODOO_ADMIN_PASSWORD:-${ADMIN_PASSWORD:-admin}}"

# Addons paths: include official addons and custom extra-addons
ADDONS_PATH="/usr/lib/python3/dist-packages/odoo/addons,/mnt/extra-addons"

# Generate runtime configuration file
CONFIG_FILE="/tmp/odoo.conf"
cat <<EOF > "$CONFIG_FILE"
[options]
addons_path = ${ADDONS_PATH}
data_dir = /var/lib/odoo
admin_passwd = ${ADMIN_PWD}
http_interface = 0.0.0.0
http_port = ${HTTP_PORT}
db_host = ${HOST}
db_port = ${PORT_NUM}
db_user = ${USER}
db_password = ${PASSWORD}
EOF

if [ -n "${DATABASE}" ]; then
    echo "db_name = ${DATABASE}" >> "$CONFIG_FILE"
fi

echo "=================================================="
echo " Starting TalentHub Odoo 19"
echo " HTTP Port:      ${HTTP_PORT}"
echo " Database Host:  ${HOST}:${PORT_NUM}"
echo " Database User:  ${USER}"
echo " Database Name:  ${DATABASE}"
echo " Addons Path:    ${ADDONS_PATH}"
echo "=================================================="

# Execute Odoo with our generated configuration
if [ "$1" = 'odoo' ]; then
    shift
    exec odoo -c "$CONFIG_FILE" "$@"
elif [ "${1:0:1}" = '-' ]; then
    exec odoo -c "$CONFIG_FILE" "$@"
fi

exec "$@"
