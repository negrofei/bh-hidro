#!/usr/bin/env bash
# Weekly IMERG Calib (FTP Ajuste_*.tif, origin 1). Does not run Late/Early.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "== bh-hidro weekly IMERG Calib =="
bh-hidro imerg --calib
