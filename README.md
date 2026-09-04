# bh-hidro

Evolución de [bhERA5](https://github.com/negrofei/bhERA5). Mismo producto (balance hídrico de suelo a 0.1° sobre el Litoral y Uruguay), código transferido módulo a módulo.

bhERA5 sigue siendo el sistema en producción hasta que este repo lo reemplace.

## Qué hay ahora

Esqueleto: paquete Python, CLI, conexión MySQL async, Docker de dos contenedores, configs de ejemplo. **Ningún paso del pipeline está implementado todavía.**

```
src/bh_hidro/
  config.py
  db/
    models/          # contrato ORM 0p1 (tablas prod, sin 0p25/ERA5/GFS)
  ingest/download/   # ERALand / WRF  (pendiente)
  ingest/imerg/      # precipitación NASA + calib (pendiente)
  balance/           # motor FAO + Kc calendario | GDD (pendiente)
  output/            # GeoJSON → MBTiles (pendiente)
```

Los modelos mapean las tablas de producción 0.1°. No incluyen `__initialize__` (shapefiles / cartopy): eso es carga inicial, no el cron. Fuera de este corte: ERA5, GFS, 0.25°, NoAgr, estaciones.

Orden de transferencia desde bhERA5:

1. Modelos de BD (`schemas`) — hecho
2. Descarga ERALand / WRF
3. IMERG
4. Balance 0p1 (calendario; GDD como estrategia de Kc)
5. Outputs (GeoJSON → tiles; PNG fuera del cron)
6. Ops (monitor, backups, cron)

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
