#!/usr/bin/env bash
# Operative pipeline.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "== bh-hidro operativo =="
echo "1. download  (ERALand / WRF)"
bh-hidro download
echo "2. imerg     (precipitación Late/Early 0p1)"
bh-hidro imerg
echo "3. balance   (0p1 calendario)"
bh-hidro balance
echo "4. output    (GeoJSON → tiles)"
bh-hidro output
