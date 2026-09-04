#!/usr/bin/env bash
# Operative pipeline. Steps stay stubs until each module is transferred.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "== bh-hidro operativo =="
echo "1. download  (ERALand / WRF)"
bh-hidro download
echo "2. imerg     (precipitación)     — pendiente"
echo "3. balance   (0p1 calendario)    — pendiente"
echo "4. output    (GeoJSON → tiles)   — pendiente"
