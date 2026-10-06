#!/usr/bin/env bash
# Operative pipeline: download → imerg → balance → GeoJSON → MBTiles → tileserver config.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
TILES_SCRIPTS="${ROOT}/scripts/tiles"

if [[ -f /.dockerenv ]]; then
  GEOJSON_DIR="${GEOJSON_DIR:-/output}"
  TILES_TMP="${TILES_DIR_LOCAL:-/output/tmp}"
  TILES_FINAL="${TILES_DIR_FINAL:-/output/tiles}"
  LOG_DIR="${LOG_DIR:-/logs}"
else
  GEOJSON_DIR="${GEOJSON_DIR:-${ROOT}/output}"
  TILES_TMP="${TILES_DIR_LOCAL:-${ROOT}/output/tmp}"
  TILES_FINAL="${TILES_DIR_FINAL:-${ROOT}/output/tiles}"
  LOG_DIR="${LOG_DIR:-${ROOT}/logs}"
fi

export tiles_dir_local="$TILES_TMP"
export TILES_DIR="$TILES_TMP"
mkdir -p "$GEOJSON_DIR" "$TILES_TMP" "$TILES_FINAL" "$LOG_DIR"

RUN_LOG="${LOG_DIR}/run_$(date +%Y%m%d).log"
log() {
  local ts
  ts="$(date '+%Y-%m-%d %H:%M:%S')"
  echo "[$ts] $*" | tee -a "$RUN_LOG"
}

log "== bh-hidro operativo =="
log "geojson=$GEOJSON_DIR tmp=$TILES_TMP tiles=$TILES_FINAL logs=$LOG_DIR"

log "1. download  (ERALand / WRF)"
bh-hidro download
log "2. imerg     (precipitación Late/Early 0p1)"
bh-hidro imerg
log "3. balance   (0p1 calendario)"
bh-hidro balance
log "4. output    (GeoJSON)"
bh-hidro output

log "5. mbtiles + config.json"
shopt -s nullglob
geojson_files=("${GEOJSON_DIR}"/*.geojson)
if [[ ${#geojson_files[@]} -eq 0 ]]; then
  log "no GeoJSON in $GEOJSON_DIR; skipping tiles"
else
  for file in "${geojson_files[@]}"; do
    base="$(basename "$file" .geojson)"
    if [[ -f "${TILES_TMP}/${base}.mbtiles" ]]; then
      log "mbtiles already in tmp: ${base}.mbtiles"
      rm -f "$file"
      continue
    fi
    log "tippecanoe $(basename "$file")"
    bash "${TILES_SCRIPTS}/generate_mbtiles.sh" "$file"
    rm -f "$file"
    log "removed $(basename "$file")"
  done
  bash "${TILES_SCRIPTS}/generate_config.sh"
  log "publishing tiles to $TILES_FINAL"
  if compgen -G "${TILES_TMP}/*.mbtiles" > /dev/null; then
    cp -v "${TILES_TMP}"/*.mbtiles "$TILES_FINAL/"
  fi
  if [[ -f "${TILES_TMP}/config.json" ]]; then
    cp -v "${TILES_TMP}/config.json" "$TILES_FINAL/"
  fi
  for published in "${TILES_FINAL}"/agua-util_*.mbtiles "${TILES_FINAL}"/deficit_*.mbtiles; do
    [[ -e "$published" ]] || continue
    name="$(basename "$published")"
    if [[ ! -f "${TILES_TMP}/${name}" ]]; then
      rm -f "$published"
      log "removed stale tile $name"
    fi
  done
fi

log "== bh-hidro operativo listo =="
