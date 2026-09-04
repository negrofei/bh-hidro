# bh-hidro

Evolución de [bhERA5](https://github.com/negrofei/bhERA5). Mismo producto (balance hídrico de suelo a 0.1° sobre el Litoral y Uruguay), código transferido módulo a módulo.

bhERA5 sigue siendo el sistema en producción hasta que este repo lo reemplace.

## Qué hay ahora

Pipeline diario 0.1°: ERALand/WRF → IMERG Late/Early → balance calendario FAO → GeoJSON (y MBTiles si hay `tippecanoe`). Ops (cron, backups, Calib semanal) queda después.

```
src/bh_hidro/
  physics/penman.py  # FAO Penman-Monteith (sin reescribir la cuenta)
  db/models/         # contrato ORM 0p1
  ingest/download/   # CDS ERALand + S3 WRF → MySQL
  ingest/imerg/      # NASA PPS Late/Early → imerg0p1
  balance/           # FAO bucket + CalendarKc (GddKc para campañas)
  output/            # GeoJSON → tippecanoe
```

Geografía (shapefiles → formitas) es `bootstrap`, no el cron. Backups de operativo separados de la referencia versionada.

```bash
bh-hidro run --dry-run
bh-hidro download --start-date 20260820 --end-date 20260822
bh-hidro imerg --start-date 20260820 --end-date 20260822
bh-hidro balance --start-date 20260820 --end-date 20260822
bh-hidro output --start-date 20260820 --end-date 20260822
```

Hace falta CDO, un `.cdsapirc` vía `CDSAPI_RC`, y `IMERG_USER` / `IMERG_PASSWORD` (el email de NASA PPS en ambos). `tippecanoe` es opcional: sin él se escribe GeoJSON y se salta el MBTiles.

ERA5 / 0.25° / NoAgr / PNG quedan fuera del primer corte.

## Arranque

MySQL del esqueleto publica **3309** en el host (bhERA5 prod usa 3308).

```bash
cp .env.example .env          # editar passwords
docker compose up --build -d
docker compose exec app bh-hidro status
```

Local, sin Docker:

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/bh-hidro status
.venv/bin/pytest
```

La app queda idle (`tail -f /dev/null`), igual que en prod. `scripts/run.sh` corre download → imerg → balance → output.
