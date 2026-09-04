# bh-hidro

Evolución de [bhERA5](https://github.com/negrofei/bhERA5). Mismo producto (balance hídrico de suelo a 0.1° sobre el Litoral y Uruguay), código transferido módulo a módulo.

bhERA5 sigue siendo el sistema en producción hasta que este repo lo reemplace.

## Qué hay ahora

Esqueleto + contrato ORM 0p1 + ingest ERALand/WRF (secuencial). IMERG, balance y tiles siguen pendientes.

```
src/bh_hidro/
  physics/penman.py  # FAO Penman-Monteith (sin reescribir la cuenta)
  db/models/         # contrato ORM 0p1
  ingest/download/   # CDS ERALand + S3 WRF → MySQL
  ingest/imerg/      # pendiente
  balance/           # pendiente
  output/            # pendiente
```

Geografía (shapefiles → formitas) es `bootstrap`, no el cron. Backups de operativo separados de la referencia versionada.

Orden de transferencia:

1. Modelos de BD — hecho
2. Descarga ERALand / WRF — hecho (secuencial; WRF solo a grilla land)
3. IMERG
4. Balance 0p1
5. Outputs
6. Ops

```bash
bh-hidro download --dry-run
bh-hidro download --start-date 20260820 --end-date 20260822
```

Hace falta CDO en el sistema (la imagen Docker lo instala) y un `.cdsapirc` vía `CDSAPI_RC`.

ERA5 / 0.25° queda fuera del primer corte.

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

La app queda idle (`tail -f /dev/null`), igual que en prod. `scripts/run.sh` es un placeholder hasta que existan los módulos.
