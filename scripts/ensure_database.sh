#!/usr/bin/env bash
# CREATE DATABASE bh_hidro on the already-running MySQL container. Does not touch fdc_database.
set -euo pipefail

CONTAINER="${MYSQL_CONTAINER:-bh-mysql-prod}"
DB="${DATABASE_NAME:-bh_hidro}"
USER="${DATABASE_USER:-operativo}"

if [[ -z "${MYSQL_ROOT_PASSWORD:-}" ]]; then
  echo "Exportá MYSQL_ROOT_PASSWORD (root del contenedor ${CONTAINER})." >&2
  exit 1
fi

docker exec "$CONTAINER" mysql -uroot -p"${MYSQL_ROOT_PASSWORD}" -e "
CREATE DATABASE IF NOT EXISTS \`${DB}\` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
GRANT ALL PRIVILEGES ON \`${DB}\`.* TO '${USER}'@'%';
FLUSH PRIVILEGES;
"
echo "ok: ${DB} on ${CONTAINER} (user ${USER})"
