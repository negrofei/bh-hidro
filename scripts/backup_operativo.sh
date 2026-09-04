#!/usr/bin/env bash
# Dump only operative series from bh_hidro. Never dumps fdc_database or reference tables.
set -euo pipefail

CONTAINER="${MYSQL_CONTAINER:-bh-mysql-prod}"
DB="${DATABASE_NAME:-bh_hidro}"
USER="${DATABASE_USER:-operativo}"
PASSWORD="${DATABASE_PASSWORD:-}"
STAMP="$(date +%Y%m%d)"
OUT_DIR="${BACKUP_DIR:-./backups}"
mkdir -p "$OUT_DIR"
OUT="${OUT_DIR}/${DB}_operativo_${STAMP}.sql.gz"

if [[ -z "$PASSWORD" ]]; then
  echo "Exportá DATABASE_PASSWORD." >&2
  exit 1
fi

TABLES=(
  datos_eraland
  wrf0p1
  imerg0p1
  imerg
  balance_hidrico_merge0p1
  estadisticas_departamento0p1
  balance_hidrico_custom0p1
)

docker exec "$CONTAINER" mysqldump \
  -u"$USER" -p"$PASSWORD" \
  --single-transaction --quick \
  "$DB" "${TABLES[@]}" \
  | gzip > "$OUT"

echo "ok: $OUT"
