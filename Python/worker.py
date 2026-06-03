"""
worker.py -- Polling-worker voor Energy-Truth algoritme.

Loop:
    1. Pol "ImportBatch" op Status='ready', pak EEN rij (FOR UPDATE SKIP LOCKED).
    2. Zet die rij op Status='processing'.
    3. Bepaal Gebouw + Klant + rolling-year periode (period_selector).
    4. Bouw een dynamische SimulationConfig (geen config.json) met:
         - default placeholder-batterij (alleen nodig voor own_battery)
         - de periode uit de data
    5. Draai run_all_scenarios + find_optimal_battery (alle batterijen
       uit Markt_Product) + generate_report -> PDF in het geheugen.
    6. Bewaar de PDF-bytes als bytea in "SimulatieRapport_PDF" (geen bestand).
    7. Zet ImportBatch.Status='done' (of 'failed' + Error_Message).

Lokaal draaien via VPN naar de DB:
    python worker.py            -> loopt continu, polled elke POLL_INTERVAL_SECONDS
    python worker.py --once     -> pakt 1 batch en stopt (handmatig testen)

Een batch klaarzetten doe je vanuit psql of een DB-tool:
    UPDATE "ImportBatch" SET "Status"='ready' WHERE "ID" = <batch_id>;
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import traceback
import uuid
from datetime import datetime
from typing import Optional

import psycopg2.extras

from db_connection import get_connection


POLL_INTERVAL_SECONDS = int(os.environ.get("POLL_INTERVAL_SECONDS", "30"))


# ---------------------------------------------------------------------------
# De tabel "SimulatieRapport_PDF" wordt BEWUST NIET door de worker aangemaakt.
# Least privilege: het worker-account hoort alleen lees/schrijf-rechten te
# hebben (SELECT/INSERT/UPDATE), geen DDL. De tabel staat in het schema
# (sql-actueel/schema.sql) en wordt via de database-migraties van het team
# aangemaakt. Bestaat de tabel niet, dan faalt store_pdf met een nette fout.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Atomair een batch claimen.
# ---------------------------------------------------------------------------
CLAIM_SQL = """
UPDATE "ImportBatch"
SET "Status" = 'processing'
WHERE "ID" = (
    SELECT "ID" FROM "ImportBatch"
    WHERE "Status" = 'ready'
    ORDER BY "ImportedAt" ASC
    FOR UPDATE SKIP LOCKED
    LIMIT 1
)
RETURNING "ID", "GebouwID", "ImportedAt", "Eigen_Batterij";
"""

def claim_next_batch() -> Optional[dict]:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(CLAIM_SQL)
            row = cur.fetchone()
        conn.commit()
    return dict(row) if row else None


def mark_done(batch_id: int, note: Optional[str] = None) -> None:
    """Zet de batch op 'done'. Als we iets aan de data hebben gedaan
    (bijv. onmogelijke meetwaarden bijgesteld naar 0), zetten we die notitie in
    Error_Message zodat het zichtbaar is in de ImportBatch-tabel. Het is geen
    fout, maar wel een logboek van wat er met de data gebeurd is."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            if note:
                cur.execute(
                    'UPDATE "ImportBatch" SET "Status"=%s, "Processed_At"=%s, '
                    '"Error_Message"=%s WHERE "ID"=%s',
                    ("done", datetime.utcnow(), note[:4000], batch_id),
                )
            else:
                cur.execute(
                    'UPDATE "ImportBatch" SET "Status"=%s, "Processed_At"=%s WHERE "ID"=%s',
                    ("done", datetime.utcnow(), batch_id),
                )
        conn.commit()


def mark_failed(batch_id: int, message: str) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                'UPDATE "ImportBatch" SET "Status"=%s, "Processed_At"=%s, "Error_Message"=%s WHERE "ID"=%s',
                ("failed", datetime.utcnow(), message[:4000], batch_id),
            )
        conn.commit()


# ---------------------------------------------------------------------------
# Klant_ID achterhalen via Gebouw.
# ---------------------------------------------------------------------------
def get_klant_id(gebouw_id: int) -> Optional[int]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT "Klant_ID" FROM "Gebouw" WHERE "ID" = %s', (gebouw_id,))
            row = cur.fetchone()
    return int(row[0]) if row else None


# ---------------------------------------------------------------------------
# PDF opslaan in DB.
# ---------------------------------------------------------------------------
def store_pdf(batch_id: int, gebouw_id: int, filename: str,
              pdf_bytes: bytes, samenvatting: Optional[dict] = None) -> int:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                'INSERT INTO "SimulatieRapport_PDF" '
                '("ImportBatch_ID", "Gebouw_ID", "Bestandsnaam", "PDF_Bytes", "Samenvatting") '
                'VALUES (%s, %s, %s, %s, %s) RETURNING "ID"',
                (
                    batch_id, gebouw_id, filename,
                    psycopg2.Binary(pdf_bytes),
                    json.dumps(samenvatting or {}),
                ),
            )
            new_id = cur.fetchone()[0]
        conn.commit()
    return int(new_id)


# ---------------------------------------------------------------------------
# Eigen batterij van de gebruiker (optioneel, uit ImportBatch.Eigen_Batterij).
# ---------------------------------------------------------------------------
def _veilige_tekst(s, maxlen=80):
    """Maakt door de gebruiker opgegeven tekst veilig voor de PDF.

    ReportLab Paragraph leest een soort mini-HTML (tags als <font>, <img>).
    Door de tekst te XML-escapen (< > & -> entities) kan een opgegeven
    productnaam/chemie geen tags injecteren; de tekst wordt letterlijk getoond.
    Witruimte wordt genormaliseerd en de lengte begrensd tegen layout-breken.
    Returnt None voor lege/ontbrekende invoer.
    """
    if s is None:
        return None
    import re
    from xml.sax.saxutils import escape
    s = re.sub(r"\s+", " ", str(s).strip())[:maxlen]
    return escape(s) if s else None


def _parse_eigen_batterij(raw):
    """Bouwt een BatteryConfig uit het optionele Eigen_Batterij-JSON van de
    ImportBatch. Geeft None terug bij afwezig of ongeldig (dan rekent de worker
    gewoon alleen met de catalogus). Contract: Eigen_Batterij_JSON_voor_Vik.md.

    Alleen capaciteit_kwh en aanschafprijs_eur zijn verplicht; de rest krijgt
    dezelfde defaults als de catalogus. De bruikbare capaciteit wordt vertaald
    naar een SoC-venster en de round-trip naar laad/ontlaad-efficiency, precies
    zoals battery_catalog.to_battery_config dat voor de catalogus doet."""
    import math
    from simulation_config import BatteryConfig

    if not raw:
        return None
    data = raw if isinstance(raw, dict) else None
    if data is None:
        try:
            data = json.loads(raw)
        except Exception:
            print("[worker] Eigen_Batterij is geen geldige JSON; genegeerd.")
            return None
    if not isinstance(data, dict):
        return None

    try:
        cap = float(data["capaciteit_kwh"])
        prijs = float(data["aanschafprijs_eur"])
    except (KeyError, TypeError, ValueError):
        print("[worker] Eigen_Batterij mist capaciteit_kwh of aanschafprijs_eur; genegeerd.")
        return None

    if not (0 < cap <= 200) or not (0 <= prijs <= 1_000_000):
        print(f"[worker] Eigen_Batterij onwaarschijnlijk (capaciteit={cap}, "
              f"prijs={prijs}); genegeerd.")
        return None

    def _num(key, default):
        v = data.get(key)
        if v is None:
            return default
        try:
            return float(v)
        except (TypeError, ValueError):
            return default

    # Bruikbare capaciteit -> symmetrisch SoC-venster (zelfde logica als de
    # catalogus; default 90% DoD als niet opgegeven).
    bruikbaar = _num("bruikbare_capaciteit_kwh", cap * 0.90)
    bruikbaar = min(max(bruikbaar, 0.0), cap)
    dod = bruikbaar / cap if cap else 0.90
    slack = (1.0 - dod) / 2.0
    min_soc, max_soc = slack, 1.0 - slack

    # Round-trip -> symmetrisch over laden/ontladen (eta = sqrt(rte)).
    rte = _num("round_trip_efficiency", 0.90)
    if not (0.5 <= rte <= 1.0):
        rte = 0.90
    eta = math.sqrt(rte)

    return BatteryConfig(
        capacity_kwh=cap,
        max_charge_kw=_num("max_laden_kw", 2.5),
        max_discharge_kw=_num("max_ontladen_kw", 3.68),
        charge_efficiency=eta,
        discharge_efficiency=eta,
        min_soc_pct=min_soc,
        max_soc_pct=max_soc,
        battery_price_eur=prijs,
        productnaam=(_veilige_tekst(data.get("productnaam")) or "Mijn batterij"),
        installatiekosten_eur=_num("installatiekosten_eur", 0.0),
        garantiejaren=_num("garantiejaren", 10.0),
        gegarandeerde_laadcycli=_num("gegarandeerde_laadcycli", 6000.0),
        chemie=_veilige_tekst(data.get("chemie")),
    )


# ---------------------------------------------------------------------------
# Pipeline per batch -- spiegelt de report_generator-CLI na.
# ---------------------------------------------------------------------------
def process_batch(batch: dict) -> Optional[str]:
    batch_id = int(batch["ID"])
    gebouw_id = int(batch["GebouwID"])

    print(f"[worker] Batch {batch_id} opgepakt (Gebouw {gebouw_id})")

    klant_id = get_klant_id(gebouw_id)
    if klant_id is None:
        raise RuntimeError(f"Geen Klant gevonden voor Gebouw {gebouw_id}")

    # 1. Periode bepalen (rolling year, of partial). De batch is de trigger;
    #    de periode dekt alle data van het gebouw (over batches heen).
    from period_selector import bepaal_periode
    with get_connection() as conn:
        period = bepaal_periode(conn, batch_id)
    if period is None:
        raise RuntimeError(f"Geen Verbruiksdata voor ImportBatch {batch_id}")
    print(f"[worker] {period.summary()}")

    # 2. SimulationConfig opbouwen (periode + batch). De batterij zetten we pas
    #    definitief in stap 4. De scenario's (pagina 4+5) draaien namelijk op
    #    de AANBEVOLEN batterij uit de sizing, zodat de besparing daar gelijk is
    #    aan het advies op pagina 1. Voor nu een tijdelijke batterij, alleen om
    #    de meterdata te kunnen laden (die hangt niet van de batterij af).
    from simulation_config import SimulationConfig, SimulationPeriod
    from battery_catalog import get_battery_catalog, to_battery_config, USER_BATTERY_ID

    _catalog = get_battery_catalog()
    if not _catalog:
        raise RuntimeError("Geen actieve batterijen in Markt_Product")
    config = SimulationConfig(
        klant_id=klant_id,
        battery=to_battery_config(_catalog[len(_catalog) // 2]),
        simulation=SimulationPeriod(
            start_date=period.start_date.strftime("%Y-%m-%d"),
            end_date=period.end_date.strftime("%Y-%m-%d"),
        ),
        csv_file=None,
        import_batch_id=batch_id,
        providers="all",
    )

    # 3. Meterdata 1x laden.
    from scenario_engine import (
        run_all_scenarios, _load_meter_data, _select_top_bottom_providers,
    )
    meter_data = _load_meter_data(config)
    if meter_data.empty:
        raise RuntimeError("Meterdata leeg na laden")

    # 4. Sizing EERST: bepaal de aanbevolen batterij. De goedkoopste aanbieder
    #    komt uit de marge-ranking (Plaats) en hangt niet van de batterij af.
    #    Daarna draaien de scenario's op precies die aanbevolen batterij, met
    #    dezelfde strategieset, zodat de besparing op pagina 1 gelijk wordt aan
    #    de beste strategie op pagina 5 (eerder liepen die op verschillende
    #    batterijen uiteen: 5,1 kWh advies vs 10 kWh referentie).
    from battery_sizing import find_optimal_battery
    from report_generator import _select_top3_batteries

    _provs, _sel = _select_top_bottom_providers(n=3)
    sizing_provider = (_sel.get("cheapest") or ["BE"])[0] if _sel else "BE"

    # Optionele eigen batterij van de gebruiker (uit ImportBatch.Eigen_Batterij).
    # Telt alleen voor deze berekening, naast de catalogus.
    eigen_batterij = _parse_eigen_batterij(batch.get("Eigen_Batterij"))
    if eigen_batterij is not None:
        print(f"[worker] Eigen batterij van gebruiker meegenomen: "
              f"{eigen_batterij.productnaam} ({eigen_batterij.capacity_kwh} kWh)")

    sizing_results = find_optimal_battery(
        meter_data,
        provider_code=sizing_provider,
        strategies=["A", "B", "C", "D"],  # zelfde set als de scenario's
        start_date=config.simulation.start_date,
        end_date=config.simulation.end_date,
        own_battery=eigen_batterij,  # None als de gebruiker er geen opgaf
    )

    # Aanbevolen batterij = exact wat het rapport op pagina 1 kiest
    # (_select_top3_batteries.iloc[0]: GO eerst, dan laagste payback).
    top3 = _select_top3_batteries(sizing_results)
    if not top3.empty:
        _rec_id = top3.iloc[0].get("battery_id")
        if _rec_id == USER_BATTERY_ID and eigen_batterij is not None:
            # De eigen batterij van de gebruiker wint: scenario's daarop draaien.
            config.battery = eigen_batterij
            print(f"[worker] Scenario's op de eigen batterij van de gebruiker: "
                  f"{eigen_batterij.productnaam} ({eigen_batterij.capacity_kwh} kWh)")
        else:
            _rec = next((e for e in _catalog if e.id == _rec_id), None)
            if _rec is not None:
                config.battery = to_battery_config(_rec)
                print(f"[worker] Scenario's op aanbevolen batterij: "
                      f"{_rec.productnaam} ({_rec.capaciteit_kwh} kWh)")
            else:
                print("[worker] Aanbevolen batterij niet in catalog; "
                      "scenario's op referentiebatterij.")
    else:
        print("[worker] Geen sizing-resultaten; scenario's op referentiebatterij.")

    # 5. Scenario's draaien op de aanbevolen batterij.
    results, price_cache, selection_info = run_all_scenarios(config)
    if results.empty:
        raise RuntimeError("run_all_scenarios gaf 0 resultaten terug")

    # 6. Samenvatting voor frontend (handzaam JSON-blok), inclusief het
    #    meterdata-validatie-rapport (afgekeurde onmogelijke rijen).
    import scenario_engine as _se
    data_validatie = dict(getattr(_se, "LAATSTE_DATA_VALIDATIE", {}) or {})

    best = results.iloc[0].to_dict() if not results.empty else {}
    samenvatting = {
        "klant_id": klant_id,
        "gebouw_id": gebouw_id,
        "periode_start": config.simulation.start_date,
        "periode_eind": config.simulation.end_date,
        "is_partial_year": period.is_partial_year,
        "days_used": period.days_used,
        "beste_aanbieder": best.get("provider_name"),
        "beste_strategie": best.get("strategy"),
        "besparing_eur": float(best.get("savings_eur", 0) or 0),
        "besparing_pct": float(best.get("savings_pct", 0) or 0),
        "data_validatie": data_validatie,
        "data_bericht": data_validatie.get("bericht"),
    }
    if data_validatie.get("bijgesteld"):
        print(f"[worker] Datavalidatie: {data_validatie['bericht']}")

    # 7. PDF in het GEHEUGEN genereren en als bytea in de DB opslaan.
    #    Geen bestand op schijf: output_path=None laat generate_report de
    #    PDF-bytes teruggeven. AVG: een klant-PDF (meterdata = persoonsgegeven)
    #    raakt zo nooit de schijf; het rapport leeft in SimulatieRapport_PDF.
    from report_generator import generate_report

    pdf_bytes = generate_report(
        results=results,
        config=config,
        output_path=None,
        top_n=30,
        price_cache=price_cache,
        selection_info=selection_info,
        sizing_results=sizing_results,
    )
    rapport_id = store_pdf(
        batch_id, gebouw_id, f"rapport_batch_{batch_id}.pdf", pdf_bytes, samenvatting
    )
    print(f"[worker] PDF opgeslagen als SimulatieRapport_PDF.ID = {rapport_id} (alleen in DB, geen bestand)")

    # Notitie voor ImportBatch.Error_Message: alleen als we iets aan de data
    # hebben gedaan (onmogelijke meetwaarden bijgesteld naar 0). Geen fout, maar
    # een logboek.
    return data_validatie["bericht"] if data_validatie.get("bijgesteld") else None


# ---------------------------------------------------------------------------
# Hoofdlus
# ---------------------------------------------------------------------------
def main_loop(once: bool = False) -> None:
    print(f"[worker] Start. Polling elke {POLL_INTERVAL_SECONDS}s. (--once om 1 batch te doen)")
    while True:
        batch = claim_next_batch()
        if batch is None:
            if once:
                print("[worker] Geen 'ready' batches gevonden, --once dus stoppen.")
                return
            time.sleep(POLL_INTERVAL_SECONDS)
            continue

        try:
            data_note = process_batch(batch)
            mark_done(int(batch["ID"]), data_note)
            print(f"[worker] Batch {batch['ID']} klaar.")
        except Exception as e:
            # Volledige details INTERN in de log (met referentie om terug te
            # vinden). In de DB komt alleen een korte, algemene melding + die
            # referentie -- geen tabelnamen, paden of query-fragmenten.
            ref = uuid.uuid4().hex[:12]
            print(f"[worker] Batch {batch['ID']} GEFAALD (ref={ref}): {type(e).__name__}: {e}")
            traceback.print_exc()
            mark_failed(
                int(batch["ID"]),
                f"Verwerking mislukt. Referentie: {ref}. "
                f"Neem contact op met het team met deze referentie.",
            )

        if once:
            return


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--once", action="store_true", help="een batch en stoppen")
    args = p.parse_args()
    try:
        main_loop(once=args.once)
    except KeyboardInterrupt:
        print("\n[worker] Gestopt door gebruiker.")
        sys.exit(0)
