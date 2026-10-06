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
HOST="${DB_HOST:-${PGHOST:-db}}"
PORT_NUM="${DB_PORT:-${PGPORT:-5432}}"
USER="${DB_USER:-${PGUSER:-odoo}}"
PASSWORD="${DB_PASSWORD:-${PGPASSWORD:-odoo}}"
DATABASE="${DB_NAME:-${PGDATABASE:-}}"

# Resolve HTTP listening port (Railway dynamically injects $PORT)
HTTP_PORT="${PORT:-8069}"

# Master database management password
ADMIN_PWD="${ODOO_ADMIN_PASSWORD:-${ADMIN_PASSWORD:-admin}}"

# Addons paths: include official addons and custom extra-addons
ADDONS_PATH="/usr/lib/python3/dist-packages/odoo/addons,/mnt/extra-addons"

# Ensure local data directory structure exists
mkdir -p /var/lib/odoo/filestore /var/lib/odoo/sessions 2>/dev/null || true

# Odoo deliberately aborts with an error if db_user is 'postgres':
# "Using the database user 'postgres' is a security risk, aborting."
# If connecting as 'postgres', automatically provision a dedicated 'odoo' role in PostgreSQL.
DB_IS_INITIALIZED=0
if [ -n "$HOST" ]; then
    echo "Connecting to PostgreSQL ($HOST:$PORT_NUM) to verify user and database state..."
    eval $(python3 -c "
import os, sys, time

host = '$HOST'
port = int('$PORT_NUM')
user = '$USER'
password = '$PASSWORD'
default_db = '$DATABASE' or 'postgres'

conn = None
for attempt in range(15):
    try:
        try:
            import psycopg2 as pg
            from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
            conn = pg.connect(host=host, port=port, user=user, password=password, dbname=default_db, connect_timeout=5)
            conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        except ImportError:
            import psycopg as pg
            conn = pg.connect(f'host={host} port={port} user={user} password={password} dbname={default_db} connect_timeout=5', autocommit=True)
        break
    except Exception as e:
        time.sleep(1)

if not conn:
    print('echo \"Notice: Could not connect to PostgreSQL within timeout. Starting with given settings...\";', file=sys.stderr)
else:
    try:
        cur = conn.cursor()
        if user == 'postgres':
            cur.execute(\"SELECT 1 FROM pg_roles WHERE rolname = 'odoo'\")
            escaped_pw = password.replace(\"'\", \"''\")
            if not cur.fetchone():
                cur.execute(f\"CREATE ROLE odoo WITH LOGIN PASSWORD '{escaped_pw}' CREATEDB SUPERUSER;\")
            else:
                cur.execute(f\"ALTER ROLE odoo WITH LOGIN PASSWORD '{escaped_pw}' CREATEDB SUPERUSER;\")
            print('USER=odoo;')
            print('echo \"Dedicated PostgreSQL role odoo provisioned successfully.\";')

        # Find all databases and clear any broken asset bundle caches + auto-migrate talenthub schema
        cur.execute(\"SELECT datname FROM pg_database WHERE datistemplate = false AND datname NOT IN ('postgres')\")
        dbs = [row[0] for row in cur.fetchall()]
        cur.close()
        conn.close()

        # Connect to each user database
        for db in dbs:
            try:
                try:
                    import psycopg2 as pg
                    dconn = pg.connect(host=host, port=port, user='odoo' if user == 'postgres' else user, password=password, dbname=db, connect_timeout=5)
                    dconn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
                except ImportError:
                    import psycopg as pg
                    dconn = pg.connect(f'host={host} port={port} user={\"odoo\" if user == \"postgres\" else user} password={password} dbname={db} connect_timeout=5', autocommit=True)
                dcur = dconn.cursor()
                dcur.execute(\"SELECT 1 FROM information_schema.tables WHERE table_name = 'ir_module_module'\")
                if dcur.fetchone():
                    dcur.execute(\"DELETE FROM ir_attachment WHERE url LIKE '/web/assets/%'\")

                    # Ensure new schema columns exist in PostgreSQL so imports never fail with UndefinedColumn
                    dcur.execute(\"\"\"
                        ALTER TABLE IF EXISTS talenthub_position 
                            ADD COLUMN IF NOT EXISTS cv_count integer DEFAULT 0,
                            ADD COLUMN IF NOT EXISTS generated_at timestamp without time zone;

                        ALTER TABLE IF EXISTS talenthub_attribute_result 
                            ADD COLUMN IF NOT EXISTS aggregation_kind varchar,
                            ADD COLUMN IF NOT EXISTS true_percentage double precision,
                            ADD COLUMN IF NOT EXISTS date_min varchar,
                            ADD COLUMN IF NOT EXISTS date_max varchar,
                            ADD COLUMN IF NOT EXISTS summary_info varchar;
                    \"\"\")
                dcur.close()
                dconn.close()
            except Exception:
                pass
    except Exception as exc:
        print(f'echo \"PostgreSQL init notice: {exc}\";', file=sys.stderr)
" 2>/dev/null || true)
fi

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
list_db = True
proxy_mode = True
EOF

echo "=================================================="
echo " Starting TalentHub Odoo 19"
echo " HTTP Port:      ${HTTP_PORT}"
echo " Database Host:  ${HOST}:${PORT_NUM}"
echo " Database User:  ${USER}"
echo " Addons Path:    ${ADDONS_PATH}"
echo " Proxy Mode:     True"
echo "=================================================="

# Execute Odoo with our generated configuration
if [ "$1" = 'odoo' ]; then
    shift
    exec odoo -c "$CONFIG_FILE" "$@"
elif [ "${1:0:1}" = '-' ]; then
    exec odoo -c "$CONFIG_FILE" "$@"
fi

exec "$@"
