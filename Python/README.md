# Energy-Truth — Python pipeline

Python-component van het Energy-Truth project: leest slimme-meterdata in, bepaalt de optimale thuisbatterij en genereert een klantrapport (PDF).

## Entry point

[worker.py](worker.py) — polling worker die per `ImportBatch` de volledige pipeline draait:

1. **Periode bepalen** — [period_selector.py](period_selector.py)
2. **CSV-ingestion + validatie** — [data_ingestion.py](data_ingestion.py) (+ [window_functions.py](window_functions.py))
3. **Scenario-matrix (provider × strategie)** — [scenario_engine.py](scenario_engine.py)
4. **Batterij-simulatie (kwartierbasis)** — [battery_simulator.py](battery_simulator.py)
5. **Kostenberekening** — [cost_calculator.py](cost_calculator.py)
6. **Optimale batterij-selectie** — [battery_sizing.py](battery_sizing.py) (+ catalogus uit [battery_catalog.py](battery_catalog.py))
7. **Datakwaliteit-score** — [data_quality.py](data_quality.py)
8. **PDF-rapport** — [report_generator.py](report_generator.py)

Configuratie en datamodellen: [simulation_config.py](simulation_config.py). DB-toegang: [db_connection.py](db_connection.py).

## Vereisten

- Python 3.11+
- PostgreSQL (schema in [sql/schema.sql](sql/schema.sql), migrations in [sql/migrations/](sql/migrations/))
- Packages: `psycopg2`, `pandas`, `numpy`, `reportlab`

## DB-configuratie

Verbindingsgegevens via environment variables (zie [db_connection.py](db_connection.py)):

```
DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD
```

Voorbeeld Kubernetes secret: [k8s/secret.yaml.example](k8s/secret.yaml.example).

## Lokaal draaien

```bash
python worker.py
```

De worker pollt continu de `ImportBatch`-tabel en verwerkt nieuwe rijen automatisch.

## Status

Test-README — toegevoegd om de Git-flow naar de gedeelde repo te valideren.
