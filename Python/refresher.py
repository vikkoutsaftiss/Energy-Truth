"""
refresher.py -- Dagelijkse voorberekening voor Energy-Truth.

Sommige berekeningen zijn klant-onafhankelijk en veranderen hooguit 1x per
dag (zodra n8n nieuwe Enever/netprijzen binnenhaalt). Die hoeven niet per
rapport in de worker te draaien. Dit script berekent ze 1x per dag voor en
slaat het resultaat op in de database, zodat de worker ze alleen nog hoeft
te lezen.

Bedoeld om als dagelijkse taak te draaien (cron / k8s CronJob), naast
worker.py. Net als de worker leest het de DB-gegevens uit de environment
(.env / Kubernetes secret) via db_connection.

Huidige dagtaken:
    1. Marges per aanbieder herberekenen + rang (Plaats) bijwerken.
    2. All-in prijzen per aanbieder materialiseren.

Nieuwe dagtaken voeg je toe aan de lijst TASKS onderaan; ze draaien dan
automatisch mee en falen onafhankelijk van elkaar.

Gebruik (VPN aan, .env wijst naar de DB):
    python refresher.py            # draai alle dagtaken
    python refresher.py --list     # toon de geregistreerde taken
"""

from __future__ import annotations

import argparse
import sys
import time
import traceback
from datetime import datetime


# ---------------------------------------------------------------------------
# Dagtaken. Elke taak is (naam, functie). De functie heeft geen argumenten
# en regelt zelf zijn DB-toegang via db_connection (zoals reference_data doet).
# ---------------------------------------------------------------------------

def task_margins_en_plaats() -> str:
    """Herbereken de marges per aanbieder en de rang (Plaats) op marge."""
    from reference_data import calculate_margins
    df = calculate_margins()
    return f"{len(df)} aanbieders bijgewerkt (marge + Plaats)"


def task_allin_prijzen() -> str:
    """Materialiseer de all-in prijsreeks per aanbieder over het hele venster."""
    from reference_data import build_allin_prices
    n = build_allin_prices()
    return f"{n} all-in prijsrijen weggeschreven"


# Registratie. Voeg hier nieuwe dagtaken toe: ("korte naam", functie).
TASKS = [
    ("marges + plaats", task_margins_en_plaats),
    ("all-in prijzen", task_allin_prijzen),
]


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def run_all() -> int:
    """Draai alle dagtaken. Een falende taak stopt de rest niet.

    Returns:
        Aantal gefaalde taken (0 = alles goed).
    """
    print(f"[refresher] Start {datetime.now():%Y-%m-%d %H:%M:%S} -- {len(TASKS)} dagtaken")
    mislukt = 0

    for naam, func in TASKS:
        print(f"\n[refresher] >>> Taak: {naam}")
        t0 = time.time()
        try:
            resultaat = func()
            dt = round(time.time() - t0, 1)
            print(f"[refresher] OK  '{naam}' ({dt}s): {resultaat}")
        except Exception as e:
            mislukt += 1
            print(f"[refresher] FOUT in '{naam}': {type(e).__name__}: {e}")
            traceback.print_exc()

    status = "alles geslaagd" if mislukt == 0 else f"{mislukt} taak/taken gefaald"
    print(f"\n[refresher] Klaar -- {status}.")
    return mislukt


def main() -> None:
    p = argparse.ArgumentParser(description="Dagelijkse voorberekening Energy-Truth")
    p.add_argument("--list", action="store_true", help="toon de geregistreerde dagtaken en stop")
    args = p.parse_args()

    if args.list:
        print("Geregistreerde dagtaken:")
        for naam, func in TASKS:
            print(f"  - {naam}  ({func.__name__})")
        return

    mislukt = run_all()
    sys.exit(1 if mislukt else 0)


if __name__ == "__main__":
    main()
