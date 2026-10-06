#!/bin/sh
# Tileserver config.json from agua-util_*.mbtiles / deficit_*.mbtiles in TILES_DIR.
# Static layers (provincias, dptos, uruguay) are served from the tileserver image.
set -e

TILES_DIR="${TILES_DIR:-${tiles_dir_local:-/output/tmp}}"
CONFIG_PATH="$TILES_DIR/config.json"

mkdir -p "$TILES_DIR"
tmp="${CONFIG_PATH}.tmp"

{
  echo '{'
  echo '  "options": {'
  echo '    "paths": {'
  echo '      "root": "/data"'
  echo '    }'
  echo '  },'
  echo '  "data": {'
  echo '    "provincias": {'
  echo '      "mbtiles": "provincias.mbtiles"'
  echo '    },'
  echo '    "dptos": {'
  echo '      "mbtiles": "dptos.mbtiles"'
  echo '    },'
  echo '    "uruguay": {'
  echo '      "mbtiles": "uruguay.mbtiles"'
  echo '    }'

  find "$TILES_DIR" -maxdepth 1 -type f \( -name "agua-util_*.mbtiles" -o -name "deficit_*.mbtiles" \) | sort | while IFS= read -r tilefile; do
    filename=$(basename "$tilefile")
    layer_name="${filename%.mbtiles}"
    date_part=$(echo "$layer_name" | sed -n 's/^\(agua-util\|deficit\)_\([0-9]\{4\}-[0-9]\{2\}-[0-9]\{2\}\)_.*/\2/p')
    if [ -n "$date_part" ]; then
      echo ','
      echo "    \"$layer_name\": {"
      echo "      \"mbtiles\": \"$filename\","
      echo "      \"date\": \"$date_part\""
      echo -n "    }"
    fi
  done

  echo
  echo '  }'
  echo '}'
} > "$tmp"

mv "$tmp" "$CONFIG_PATH"
echo "config.json generated at $CONFIG_PATH"
