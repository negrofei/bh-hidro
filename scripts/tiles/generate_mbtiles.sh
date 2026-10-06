#!/usr/bin/env bash
# GeoJSON → MBTiles in the staging dir (tiles_dir_local, default /output/tmp).
set -euo pipefail

this_dir="$(cd "$(dirname "$0")" && pwd)"
if [[ -f "${this_dir}/tiles.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "${this_dir}/tiles.env"
  set +a
fi

MINIMUM_ZOOM="${MINIMUM_ZOOM:-5}"
MAXIMUM_ZOOM="${MAXIMUM_ZOOM:-9}"
tiles_dir_local="${tiles_dir_local:-${TILES_DIR_LOCAL:-/output/tmp}}"
geojson_file="${1:-}"

if [[ -z "$geojson_file" || ! -f "$geojson_file" ]]; then
  echo "usage: generate_mbtiles.sh <file.geojson>" >&2
  exit 1
fi
if ! command -v tippecanoe >/dev/null 2>&1; then
  echo "tippecanoe not on PATH" >&2
  exit 1
fi

mkdir -p "$tiles_dir_local"
mbtiles_file="${geojson_file%.geojson}.mbtiles"
echo "tippecanoe $(basename "$geojson_file") → $(basename "$mbtiles_file") (z${MINIMUM_ZOOM}-${MAXIMUM_ZOOM})"
tippecanoe -o "$mbtiles_file" "$geojson_file" \
  --minimum-zoom="${MINIMUM_ZOOM}" \
  --maximum-zoom="${MAXIMUM_ZOOM}" \
  --force
mv -v "$mbtiles_file" "$tiles_dir_local/"
