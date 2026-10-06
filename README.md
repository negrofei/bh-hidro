# bh-hidro

Evolución de [bhERA5](https://github.com/negrofei/bhERA5). Mismo producto (balance hídrico de suelo a 0.1° sobre el Litoral y Uruguay), código transferido módulo a módulo.

bhERA5 sigue siendo el sistema en producción hasta que este repo lo reemplace. La base que ya corre es `bh-mysql-prod` (host **3308** → 3306). Este repo usa **esa misma instancia** y un schema nuevo `bh_hidro`; no levanta otro MySQL y no escribe en `fdc_database`.

## Qué hay ahora

Pipeline diario 0.1°: ERALand/WRF/GFS → IMERG Late/Early → balance calendario FAO → GeoJSON → tippecanoe (`config.json` para el tileserver). Bootstrap copia solo referencia. Cron diario / Calib semanal / backup de operativo están en `scripts/`.

```
src/bh_hidro/
  physics/penman.py  # FAO Penman-Monteith (sin reescribir la cuenta)
  db/models/         # contrato ORM 0p1
  db/bootstrap.py    # CREATE bh_hidro + INSERT…SELECT de referencia
  ingest/download/   # CDS ERALand + S3 WRF + NOMADS GFS → MySQL
  ingest/imerg/      # NASA PPS Late/Early + FTP Calib → imerg0p1
  balance/           # FAO bucket + CalendarKc (GddKc para campañas)
  output/            # GeoJSON → tippecanoe + config.json
```

```bash
bh-hidro bootstrap --dry-run
bh-hidro download --start-date 20260820 --end-date 20260822
bh-hidro imerg --start-date 20260820 --end-date 20260822
bh-hidro imerg --calib
bh-hidro balance --start-date 20260820 --end-date 20260822
bh-hidro output --start-date 20260820 --end-date 20260822
./scripts/run.sh                 # pipeline completo, incluye tiles
```

Hace falta CDO, un `.cdsapirc` vía `CDSAPI_RC`, y `IMERG_USER` / `IMERG_PASSWORD` (el email de NASA PPS en ambos). Calib semanal pide `IMERG_FTP_*`. La imagen de app instala `tippecanoe`; en el host, sin él `bh-hidro output` deja GeoJSON y `run.sh` no puede publicar tiles.

Cada comando escribe su propio log en `LOG_DIR` (`/logs` en el contenedor, `./logs` en el host): `descarga_*`, `reportes_*`, `balance_*`, `output_*`. El balance además deja `process_balance_cult{id}_prov{id}_*.log` por par cultivo×provincia.

ERA5 / 0.25° / NoAgr / PNG quedan fuera del primer corte.

## MySQL que ya está andando

No hace falta un contenedor 3309. `bh-mysql-prod` ya escucha en el host en **3308** y en la red Docker `python3mysql_liberagro` (alias `bh-mysql-prod` / `db`).

| Quién | Host | Puerto | Schema |
| --- | --- | --- | --- |
| CLI en el host (venv) | `127.0.0.1` | 3308 | `bh_hidro` |
| App en Compose | `bh-mysql-prod` | 3306 | `bh_hidro` |
| Producción bhERA5 (no tocar) | igual | igual | `fdc_database` |

Bootstrap crea `bh_hidro` (si `operativo` no tiene `CREATE`, usa `MYSQL_ROOT_PASSWORD` o `scripts/ensure_database.sh`) y copia **solo** tablas de referencia (`provincias`, `formitas_merge_0p1`, grillas, Kc, …). Las series operativas (`datos_eraland`, `wrf0p1`, `imerg*`, `balance_*`) quedan vacías. Si origen y destino son el mismo schema, se niega a copiar.

```bash
cp .env.example .env          # passwords de prod, DATABASE_NAME=bh_hidro
# opcional, si operativo no puede CREATE DATABASE:
export MYSQL_ROOT_PASSWORD=...
./scripts/ensure_database.sh
.venv/bin/bh-hidro bootstrap --dry-run
.venv/bin/bh-hidro bootstrap
```

`--force` trunca las tablas de referencia destino y vuelve a copiar. No hay `--force` que tire `fdc_database`.

## Arranque

```bash
cp .env.example .env          # editar passwords; host 3308 para el CLI
docker compose up --build -d  # solo app, red python3mysql_liberagro
docker compose exec app bh-hidro status
docker compose exec app bh-hidro bootstrap
```

Compose pisa `DATABASE_HOST`/`DATABASE_PORT` y las rutas (`/logs`, `/descargas`, `/output`) adentro del contenedor. `./logs` queda bind-mount a `/logs`. Los tiles publicados van a `${TILES_HOST_DIR:-./output/tiles}` (en prod, el dir que monta el tileserver, p.ej. `/var/www/liberagro/geodata/tiles`).

El venv del host **sí** corre `status` / `bootstrap` / el pipeline. `/logs` es ruta de contenedor: si el `.env` todavía la tiene, el CLI la traduce a `./logs`. También podés ejecutar lo mismo adentro con `docker compose exec app bh-hidro …`. La imagen trae `vim`, `htop` y `tippecanoe`.

Si no hubiera `bh-mysql-prod` (máquina limpia), el opt-in es `docker compose -f docker-compose.embedded.yml up --build -d` (MySQL en **3309**). No lo uses en este servidor.

Local, sin Docker:

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/bh-hidro status
.venv/bin/pytest
```

La app queda idle (`tail -f /dev/null`), igual que en prod. `scripts/run.sh` es el cron diario (incluye tippecanoe + `config.json`). `scripts/run_weekly.sh` es Calib. `scripts/backup_operativo.sh` hace mysqldump solo de las tablas operativas. Ejemplos de crontab en `scripts/cron.example`.
