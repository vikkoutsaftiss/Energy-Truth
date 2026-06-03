"""
scenario_engine.py - Orchestratie over alle aanbieders en strategieen.

Itereert over elke combinatie van aanbieder x strategie, roept
battery_simulator en cost_calculator aan, en levert een ranking-DataFrame.

Gebruik:
    from scenario_engine import run_all_scenarios
    results, price_cache, selection_info = run_all_scenarios("config.json")
    print(results.to_string())
"""
from __future__ import annotations  # maakt list[dict] etc. bruikbaar op Python 3.8+

import os
import time
import logging
import pandas as pd
from typing import Optional

from simulation_config import SimulationConfig, BatteryConfig
from reference_data import get_net_prices, get_allin_prices
from battery_simulator import simulate_battery, get_simulation_summary
from cost_calculator import (
    calculate_costs_no_battery,
    calculate_costs_with_battery,
    calculate_savings_summary,
)
import psycopg2.extras

from db_connection import get_client, get_connection

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Resultaat van de laatste meterdata-validatie (gevuld door
# _load_meter_data_from_db). De worker leest dit uit om het aantal afgekeurde
# rijen in de samenvatting/message te zetten.
LAATSTE_DATA_VALIDATIE: dict = {
    'rijen_in': 0, 'bijgesteld': 0, 'negatief_verbruik': 0,
    'negatief_teruglevering': 0, 'absurd_hoog': 0,
    'bericht': 'Nog geen meterdata gevalideerd.',
}

# DoS-vangnet: bovengrens op het aantal meetrijen dat een run laadt. Een
# gebouw-rolling-jaar is normaal ~35.000 kwartieren; deze grens trekt alleen
# bij een opgeblazen of dubbele import. De harde geheugen-/CPU-grens hoort
# daarnaast in de Kubernetes resources.limits te staan (zie infra).
MAX_METERDATA_RIJEN = 5_000_000


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _refresh_margins_if_stale(max_age_hours: int = 24) -> None:
    """
    VANGNET, niet de primaire route. De marges + Plaats worden dagelijks
    door refresher.py (calculate_margins) voorberekend. Deze functie draait
    de herberekening alleen nog als de marges ONTBREKEN of ouder zijn dan
    max_age_hours (standaard een ruime drempel), zodat de worker zelfstandig
    blijft werken als de refresher (nog) niet gedraaid heeft. In normale
    dagelijkse werking wordt hier niets herberekend.
    """
    from datetime import datetime, timezone, timedelta
    client = get_client()

    try:
        # Check Berekend_Op van de meest recente marge-rij
        print("Marge-refresh: Berekend_Op ophalen...")
        resp = (
            client.table("Marges_Per_Aanbieder")
            .select("Berekend_Op")
            .order("Berekend_Op", desc=True)
            .limit(1)
            .execute()
        )
        print(f"  Response: {resp.data}")

        if resp.data and resp.data[0].get("Berekend_Op"):
            last_update = pd.to_datetime(resp.data[0]["Berekend_Op"], utc=True)
            age = datetime.now(timezone.utc) - last_update
            age_hours = age.total_seconds() / 3600
            print(f"  Laatste berekening: {last_update} ({age_hours:.1f}u geleden)")
            if age < timedelta(hours=max_age_hours):
                print(f"  Margins zijn actueel (< {max_age_hours}u) - overgeslagen")
                return
            print(f"  Margins zijn verouderd (> {max_age_hours}u) - herberekening gestart")
        else:
            print("  Geen margins of timestamp gevonden - herberekening")

        from reference_data import calculate_margins
        calculate_margins()
        print("  Margins succesvol herberekend")

    except Exception as e:
        print(f"  Margin-refresh mislukt: {e}")
        logger.warning(f"Margin-refresh mislukt (simulatie gaat door met bestaande data): {e}")


def _get_providers(config: SimulationConfig) -> list[dict]:
    """
    Haal de lijst van aanbieders op uit Net_Aanbieder.
    Als config.providers == "all", haal alles op.
    Anders filter op de opgegeven afkortingen.

    Retourneert dicts met keys 'id', 'code', 'name' (= ID, Afkorting, Naam)
    zodat de bestaande call sites in deze module blijven werken.
    """
    client = get_client()
    query = client.table("Net_Aanbieder").select("ID, Afkorting, Naam")

    if config.providers != "all":
        # config.providers kan een komma-gescheiden string of een lijst zijn
        if isinstance(config.providers, str):
            codes = [c.strip() for c in config.providers.split(",")]
        else:
            codes = list(config.providers)
        query = query.in_("Afkorting", codes)

    result = query.execute()
    rows = result.data if result.data else []
    providers = [
        {"id": r["ID"], "code": r["Afkorting"], "name": r["Naam"]}
        for r in rows
    ]
    logger.info(f"{len(providers)} aanbieders opgehaald uit database")
    return providers


def _select_top_bottom_providers(n: int = 3) -> tuple:
    """
    Selecteer de N goedkoopste en N duurste aanbieders op basis van
    hun gemiddelde margin (uit provider_margins tabel).

    Laagste margin = goedkoopst voor de consument.
    Hoogste margin = duurst voor de consument.

    Returns:
        tuple(list[dict], dict):
            - list[dict] met {"code": ..., "name": ...} voor 2xN aanbieders
            - dict met selectie-info voor rapportage:
              {"cheapest": [...], "expensive": [...], "margins": {code: margin}}
    """
    client = get_client()

    # Marges ophalen (gekoppeld aan Net_Aanbieder via ID); haal direct ook Afkorting op
    # via een tweede query omdat de DB-client geen JOIN syntax heeft.
    # ERD-kolomnaam in Marges_Per_Aanbieder is "Net_AanbiederID" (zonder underscore).
    # Plaats (rang op marge) wordt door refresher.py gezet; gebruik die als
    # die er is, val anders terug op live sorteren op marge.
    try:
        margins = client.table("Marges_Per_Aanbieder").select(
            "Net_AanbiederID, Gemiddelde_Marge, Plaats"
        ).execute()
    except Exception:
        margins = client.table("Marges_Per_Aanbieder").select(
            "Net_AanbiederID, Gemiddelde_Marge"
        ).execute()
    if not margins.data:
        logger.warning("Geen marges beschikbaar -- kan geen selectie maken")
        return [], {}

    # Mapping Net_AanbiederID -> Afkorting + Naam
    aanbieders = client.table("Net_Aanbieder").select("ID, Afkorting, Naam").execute().data or []
    # Sleutels als string zodat de koppeling werkt of Net_AanbiederID nu
    # int of text is (schema.sql zegt int, sommige servers hebben text).
    id_to_code = {str(a["ID"]): a["Afkorting"] for a in aanbieders}

    df = pd.DataFrame(margins.data)
    df["Gemiddelde_Marge"] = pd.to_numeric(df["Gemiddelde_Marge"])
    df["provider_code"] = df["Net_AanbiederID"].astype(str).map(id_to_code)
    df = df.dropna(subset=["provider_code"])
    # Voorberekende rang (Plaats) gebruiken als die compleet is, anders live op marge.
    if "Plaats" in df.columns and df["Plaats"].notna().all():
        df = df.sort_values("Plaats")
    else:
        df = df.sort_values("Gemiddelde_Marge")

    # Top N goedkoopst + top N duurst (unieke codes)
    cheapest = df.head(n)["provider_code"].tolist()
    expensive = df.tail(n)["provider_code"].tolist()
    selected_codes = list(dict.fromkeys(cheapest + expensive))  # bewaar volgorde, geen dubbelen

    # Marges dict voor rapportage (afkorting -> marge)
    margins_dict = dict(zip(df["provider_code"], df["Gemiddelde_Marge"]))

    # Lijst opbouwen met code/name/id voor de geselecteerde aanbieders
    provider_list = []
    for code in selected_codes:
        # Vind de ID die bij deze afkorting hoort
        match = next((a for a in aanbieders if a["Afkorting"] == code), None)
        if match:
            provider_list.append({
                "id": match["ID"],
                "code": match["Afkorting"],
                "name": match["Naam"],
            })

    cheap_names = ", ".join(cheapest)
    exp_names = ", ".join(expensive)
    logger.info(f"Smart selectie: goedkoopst [{cheap_names}] + duurst [{exp_names}]")

    selection_info = {
        "cheapest": cheapest,
        "expensive": expensive,
        "margins": margins_dict,
    }

    return provider_list, selection_info


def _normalize_timestamps(df: pd.DataFrame, col: str = "timestamp_from") -> pd.DataFrame:
    """
    Zorg dat timestamps UTC-aware zijn.
    DB-prijzen zijn UTC-aware, meterdata kan tz-naive zijn.
    Door alles naar UTC te brengen, matchen de merges correct.
    """
    if col not in df.columns:
        return df
    # Zorg dat het datetime is (kan nog object/str zijn na CSV-inladen)
    if not pd.api.types.is_datetime64_any_dtype(df[col]):
        df[col] = pd.to_datetime(df[col], utc=True)
    elif df[col].dt.tz is None:
        df[col] = df[col].dt.tz_localize("UTC")
    else:
        df[col] = df[col].dt.tz_convert("UTC")
    return df


def _load_meter_data_from_db(import_batch_id: int, start_date: str, end_date: str) -> pd.DataFrame:
    """
    Laad meterdata rechtstreeks uit de DB (Verbruiksdata tabel).

    Werkwijze (gebouw-scope, 30 mei 2026, herzien):
      De meegegeven ImportBatch is de TRIGGER. We lezen alle Verbruiksdata van
      het GEBOUW dat die batch bezit (join op ImportBatch.GebouwID), binnen de
      rolling-year-periode. Sinds de import incrementeel en ontdubbeld is, vullen
      meerdere batches van een gebouw elkaar aan; zo mist er geen historie meer.
      Overlappende tijdstempels worden ontdubbeld met DISTINCT ON: per
      meetmoment wint de rij uit de hoogste ImportBatchID (nieuwste upload).

      Daarna draait valideer_meterdata: fysiek onmogelijke rijen (negatief of
      absurd hoog, bijv. een meterstand-reset) worden verwijderd, zodat ze de
      kosten- en grafiekberekening niet vergiftigen. Het resultaat wordt in
      LAATSTE_DATA_VALIDATIE gezet zodat de worker het in de samenvatting kan
      melden.

      De Yan-stijl kolomnamen worden hernoemd naar de pandas-conventie
      (timestamp_from, consumption_kwh, feed_in_kwh).

    Returns:
        DataFrame met timestamp_from, consumption_kwh, feed_in_kwh (UTC-aware)
        Lege DataFrame als geen data gevonden.
    """
    global LAATSTE_DATA_VALIDATIE
    # Bewust NIET in SQL ontdubbelen. We halen ALLE gebouw-rijen op (incl.
    # ImportBatchID), zetten onmogelijke meetwaarden bij naar 0 (valideren) en
    # ontdubbelen daarna in pandas op tijdstempel (nieuwste batch wint).
    sql = """
        SELECT v."MeetDatumTijd"               AS "MeetDatumTijd",
               v."ImportBatchID"               AS "ImportBatchID",
               v."Stroom_Gekocht_Net_kWh"      AS "Stroom_Gekocht_Net_kWh",
               v."Stroom_Verkocht_Net_kWh"     AS "Stroom_Verkocht_Net_kWh"
        FROM "Verbruiksdata" v
        JOIN "ImportBatch" b ON v."ImportBatchID" = b."ID"
        WHERE b."GebouwID" = (
            SELECT "GebouwID" FROM "ImportBatch" WHERE "ID" = %s
        )
          AND v."MeetDatumTijd" >= %s
          AND v."MeetDatumTijd" <= %s
        ORDER BY v."MeetDatumTijd", v."ImportBatchID" DESC
    """
    params = (
        import_batch_id,
        f"{start_date} 00:00:00",
        f"{end_date} 23:59:59",
    )
    with get_connection() as conn:
        # DoS-vangnet: tel eerst (goedkoop) hoeveel rijen we zouden laden en
        # weiger bij een onrealistisch grote dataset, zodat een opgeblazen of
        # dubbele import de pod niet het geheugen laat opmaken. We materialiseren
        # de grote set dus NIET als hij over de grens is.
        count_sql = (
            'SELECT count(*) FROM "Verbruiksdata" v '
            'JOIN "ImportBatch" b ON v."ImportBatchID" = b."ID" '
            'WHERE b."GebouwID" = (SELECT "GebouwID" FROM "ImportBatch" WHERE "ID" = %s) '
            'AND v."MeetDatumTijd" >= %s AND v."MeetDatumTijd" <= %s'
        )
        with conn.cursor() as cur:
            cur.execute(count_sql, params)
            n_rijen = cur.fetchone()[0]
        if n_rijen > MAX_METERDATA_RIJEN:
            raise ValueError(
                f"Te veel meetrijen voor dit gebouw in de periode: {n_rijen:,} "
                f"(maximum {MAX_METERDATA_RIJEN:,}). Waarschijnlijk een opgeblazen "
                f"of dubbele import; de run is gestopt om geheugen en CPU te sparen."
            )
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            all_records = [dict(r) for r in cur.fetchall()]

    if not all_records:
        return pd.DataFrame()

    df = pd.DataFrame(all_records)
    # Hernoem naar interne pandas-conventie (ImportBatchID tijdelijk bewaren
    # voor de ontdubbeling).
    df = df.rename(columns={
        "MeetDatumTijd": "timestamp_from",
        "ImportBatchID": "_batch_id",
        "Stroom_Gekocht_Net_kWh": "consumption_kwh",
        "Stroom_Verkocht_Net_kWh": "feed_in_kwh",
    })
    df["timestamp_from"] = pd.to_datetime(df["timestamp_from"], utc=True)
    df["consumption_kwh"] = pd.to_numeric(df["consumption_kwh"])
    df["feed_in_kwh"] = pd.to_numeric(df["feed_in_kwh"])

    # 1) Valideren: zet fysiek onmogelijke meetwaarden bij naar 0 (negatieve
    #    ruis/reset of absurd hoog). Rijen blijven behouden.
    from data_quality import valideer_meterdata
    df, LAATSTE_DATA_VALIDATIE = valideer_meterdata(df)
    if LAATSTE_DATA_VALIDATIE.get("bijgesteld"):
        logger.warning("Meterdata-validatie: %s", LAATSTE_DATA_VALIDATIE["bericht"])

    # 2) Ontdubbelen: per tijdstempel de nieuwste meting houden (hoogste
    #    ImportBatchID wint bij overlappende batches).
    if not df.empty:
        df = (
            df.sort_values(["timestamp_from", "_batch_id"], ascending=[True, False])
              .drop_duplicates(subset="timestamp_from", keep="first")
              .reset_index(drop=True)
        )
    df = df.drop(columns=["_batch_id"], errors="ignore")
    return df


def _load_meter_data(config: SimulationConfig) -> pd.DataFrame:
    """
    Laad meterdata rechtstreeks uit de database (Verbruiksdata).

    Geen CSV-fallback meer: de worker draait puur op serverdata die door
    de import-pipeline (Vik) in de DB is gezet. Als er voor deze klant en
    periode niets staat, is dat een fout, geen reden om een CSV in te lezen.
    """
    start = config.simulation.start_date
    end = config.simulation.end_date

    if config.import_batch_id is None:
        raise ValueError(
            "Geen import_batch_id in de config. De worker moet de geclaimde "
            "ImportBatch doorgeven zodat de meterdata batch-scoped geladen wordt."
        )

    df = _load_meter_data_from_db(config.import_batch_id, start, end)
    if df.empty:
        raise ValueError(
            f"Geen meterdata in de database voor ImportBatch "
            f"{config.import_batch_id} in periode {start} t/m {end}."
        )

    logger.info(
        f"Meterdata uit database (batch {config.import_batch_id}): "
        f"{len(df)} kwartieren ({start} t/m {end})"
    )
    return df


# ---------------------------------------------------------------------------
# Per-aanbieder simulatie
# ---------------------------------------------------------------------------

def _prepare_provider_inputs(
    meter_data: pd.DataFrame,
    provider_code: str,
    prices: pd.DataFrame,
    net_prices: pd.DataFrame,
) -> dict:
    """
    Strategie-ONAFHANKELIJK voorwerk, een keer per aanbieder.

    Prijzen normaliseren, meterdata filteren op de kwartieren waarvoor een
    prijs bestaat, en de kosten ZONDER batterij berekenen. Die kosten hangen
    niet van de laadstrategie af, dus het is verspilling om dit voor elke van
    de vier strategieen opnieuw te doen (zoals voorheen). Resultaat wordt
    hergebruikt door _run_single_with_prices voor A/B/C/D.

    Returns:
        dict met 'prices_norm', 'net_prices_norm', 'meter_filtered',
        'costs_no_bat'. Bij geen data: dict met alleen 'error'.
    """
    if prices is None or prices.empty:
        return {"error": "geen prijsdata"}

    prices_norm = _normalize_timestamps(prices.copy(), "valid_from")
    net_prices_norm = _normalize_timestamps(net_prices.copy(), "valid_from") if net_prices is not None else None

    price_timestamps = set(prices_norm["valid_from"])
    meter_filtered = meter_data[meter_data["timestamp_from"].isin(price_timestamps)].copy()
    meter_filtered = meter_filtered.sort_values("timestamp_from").reset_index(drop=True)

    if meter_filtered.empty:
        return {"error": "geen overlap meterdata/prijzen"}

    costs_no_bat = calculate_costs_no_battery(
        meter_filtered, prices_norm, provider_code, net_prices=net_prices_norm
    )

    return {
        "prices_norm": prices_norm,
        "net_prices_norm": net_prices_norm,
        "meter_filtered": meter_filtered,
        "costs_no_bat": costs_no_bat,
    }


def _run_single_with_prices(
    prep: dict,
    provider_code: str,
    battery: BatteryConfig,
    strategy: str = "A",
) -> dict:
    """
    Draait een strategie voor een aanbieder bovenop het voorbewerkte,
    strategie-onafhankelijke materiaal uit _prepare_provider_inputs.
    Voert dus alleen nog het strategie-afhankelijke deel uit: de
    batterijsimulatie, de kosten MET batterij, en de samenvatting.
    """
    if prep.get("error"):
        return {
            "provider_code": provider_code,
            "strategy": strategy,
            "cost_no_battery": None,
            "cost_with_battery": None,
            "savings_eur": None,
            "savings_pct": None,
            "quarters": 0,
            "error": prep["error"],
        }

    prices_norm = prep["prices_norm"]
    net_prices_norm = prep["net_prices_norm"]
    meter_filtered = prep["meter_filtered"]
    costs_no_bat = prep["costs_no_bat"]

    # Batterijsimulatie
    simulated = simulate_battery(
        meter_filtered, battery, prices=prices_norm, strategy=strategy
    )

    # Merge prijzen in gesimuleerde data
    if "price" not in simulated.columns:
        simulated = simulated.merge(
            prices_norm[["valid_from", "price"]],
            left_on="timestamp_from",
            right_on="valid_from",
            how="left",
        )

    # Kosten MET batterij
    costs_with_bat = calculate_costs_with_battery(
        simulated, provider_code, net_prices=net_prices_norm
    )

    # Combineer
    combined = costs_no_bat.copy()
    if "cost_with_battery" in costs_with_bat.columns:
        combined = combined.reset_index(drop=True)
        costs_with_bat = costs_with_bat.reset_index(drop=True)
        combined["cost_with_battery"] = costs_with_bat["cost_with_battery"]

    summary = calculate_savings_summary(combined)
    sim_summary = get_simulation_summary(simulated, battery, strategy=strategy)
    seasonal_info = summary.get("seasonal_info", {})

    return {
        "provider_code": provider_code,
        "strategy": strategy,
        # Jaarbasis (seizoensgewogen, met opvulling voor ontbrekende seizoenen)
        "cost_no_battery": summary.get("total_cost_no_battery", 0),
        "cost_with_battery": summary.get("total_cost_with_battery", 0),
        "savings_eur": summary.get("total_savings", 0),
        "savings_pct": summary.get("savings_percentage", 0),
        # Ruwe som over aangeleverde data (transparantie)
        "cost_no_battery_raw": summary.get("total_cost_no_battery_raw", 0),
        "cost_with_battery_raw": summary.get("total_cost_with_battery_raw", 0),
        "savings_eur_raw": summary.get("total_savings_raw", 0),
        # Seizoensmetadata
        "year_coverage": seasonal_info.get("year_coverage", 0),
        "seasons_present": seasonal_info.get("seasons_present", []),
        "seasons_estimated": seasonal_info.get("seasons_estimated", []),
        "seasonal_info": seasonal_info,
        "quarters": summary.get("quarters_calculated", 0),
        "sim_summary": sim_summary,
    }


# ---------------------------------------------------------------------------
# Multi-aanbieder, multi-strategie
# ---------------------------------------------------------------------------

def run_scenarios(
    meter_data: pd.DataFrame,
    battery: BatteryConfig,
    providers: list[dict],
    net_prices: pd.DataFrame,
    strategies: list[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> pd.DataFrame:
    """
    Draai simulaties voor meerdere aanbieders x meerdere strategieen.

    Parameters
    ----------
    meter_data : DataFrame
        Kwartierdata.
    battery : BatteryConfig
        Batterijconfiguratie.
    providers : list[dict]
        Lijst van {"code": "ANWB", "name": "ANWB Energie"}.
    net_prices : DataFrame
        Kale beursprijzen.
    strategies : list[str]
        Welke strategieen te draaien. Standaard ["A", "B", "C", "D"].
    start_date, end_date : str, optional
        Datumfilters.

    Returns
    -------
    tuple(DataFrame, dict)
        DataFrame met ranking (gesorteerd op savings_eur, hoogste eerst),
        en een dict {provider_code: DataFrame} met de gebruikte prijsdata.
    """
    if strategies is None:
        strategies = ["A", "B", "C", "D"]

    results = []
    total = len(providers) * len(strategies)
    done = 0

    # Cache: per aanbieder de gereconstrueerde prijzen opslaan
    # zodat we ze niet per strategie opnieuw ophalen
    _price_cache = {}

    for provider in providers:
        code = provider["code"]
        name = provider.get("name", code)

        # Prijzen 1x per aanbieder uit de voorberekende all-in tabel
        # (refresher.py). get_allin_prices valt intern terug op live
        # reconstructie als de tabel voor deze aanbieder nog leeg is.
        if code not in _price_cache:
            _price_cache[code] = get_allin_prices(code, start_date, end_date)

        # Strategie-onafhankelijk voorwerk (prijzen normaliseren, meterdata
        # filteren, kosten-zonder-batterij) een keer per aanbieder.
        prep = _prepare_provider_inputs(
            meter_data=meter_data,
            provider_code=code,
            prices=_price_cache[code],
            net_prices=net_prices,
        )

        for strategy in strategies:
            done += 1
            logger.info(f"[{done}/{total}] {name} ({code}) - Strategie {strategy}")
            t0 = time.time()

            try:
                result = _run_single_with_prices(
                    prep=prep,
                    provider_code=code,
                    battery=battery,
                    strategy=strategy,
                )
                result["provider_name"] = name
                result["duration_s"] = round(time.time() - t0, 2)
                results.append(result)

            except Exception as e:
                logger.error(f"Fout bij {code} strategie {strategy}: {e}")
                results.append({
                    "provider_code": code,
                    "provider_name": name,
                    "strategy": strategy,
                    "cost_no_battery": None,
                    "cost_with_battery": None,
                    "savings_eur": None,
                    "savings_pct": None,
                    "quarters": 0,
                    "error": str(e),
                    "duration_s": round(time.time() - t0, 2),
                })

    df = pd.DataFrame(results)

    # Sorteer op laagste kosten met batterij (wat de consument betaalt)
    if not df.empty and "cost_with_battery" in df.columns:
        df = df.sort_values("cost_with_battery", ascending=True, na_position="last")
        df = df.reset_index(drop=True)
        df.index = df.index + 1  # Ranking begint bij 1
        df.index.name = "rank"

    return df, _price_cache


# ---------------------------------------------------------------------------
# All-in-one: van config.json tot ranking
# ---------------------------------------------------------------------------

def run_all_scenarios(
    config_path: str = "config.json",
    strategies: list[str] = None,
    smart_select: int = 3,
) -> pd.DataFrame:
    """
    Volledig geautomatiseerde run: laad config, meterdata, aanbieders,
    draai alle simulaties, en retourneer een ranking-tabel.

    Parameters
    ----------
    config_path : str
        Pad naar config.json.
    strategies : list[str]
        Strategieen om te testen. Standaard alle vier: ["A", "B", "C", "D"].
    smart_select : int
        Selecteer de N goedkoopste + N duurste aanbieders op basis van margin.
        Standaard 3 (= 6 aanbieders x 4 strategieen = 24 runs).
        Zet op 0 om alle aanbieders te draaien (uit config).

    Returns
    -------
    DataFrame met ranking per aanbieder x strategie.
    """
    logger.info("=" * 60)
    logger.info("ENERGY-TRUTH SCENARIO ENGINE - START")
    logger.info("=" * 60)
    t_start = time.time()

    # 1. Config laden: accepteer pad (lokaal testen) of bestaand
    #    SimulationConfig object (vanuit worker.py met dynamische periode).
    if isinstance(config_path, SimulationConfig):
        config = config_path
    else:
        config = SimulationConfig.from_json(config_path)
    logger.info(f"Config geladen: {config.summary()}")

    # 2. Meterdata laden
    meter_data = _load_meter_data(config)
    if meter_data.empty:
        logger.error("Geen meterdata gevonden voor de opgegeven periode")
        return pd.DataFrame()

    # 2b. Marges + Plaats (rang goedkoopst/duurst) zijn eigendom van
    #     refresher.py (dagelijkse run); die berekent ze klant-onafhankelijk
    #     voor. GEEN herberekening per rapport meer. We houden alleen een
    #     vangnet: heeft de refresher (nog) niet gedraaid -- marges ontbreken
    #     of zijn > 1 week oud -- dan bootstrapt de worker ze eenmalig, zodat
    #     hij niet zonder aanbiederselectie komt te zitten.
    _refresh_margins_if_stale(max_age_hours=168)

    # 3. Aanbieders ophalen
    selection_info = {}
    if smart_select > 0 and config.providers == "all":
        providers, selection_info = _select_top_bottom_providers(n=smart_select)
    else:
        providers = _get_providers(config)
    if not providers:
        logger.error("Geen aanbieders gevonden")
        return pd.DataFrame(), {}, {}

    # 4. Nettoprijzen ophalen
    net_prices = get_net_prices(
        start_date=config.simulation.start_date,
        end_date=config.simulation.end_date,
    )
    logger.info(f"Nettoprijzen geladen: {len(net_prices)} uurprijzen")

    # 5. Simulaties draaien
    results, price_cache = run_scenarios(
        meter_data=meter_data,
        battery=config.battery,
        providers=providers,
        net_prices=net_prices,
        strategies=strategies,
        start_date=config.simulation.start_date,
        end_date=config.simulation.end_date,
    )

    elapsed = round(time.time() - t_start, 1)
    logger.info("=" * 60)
    logger.info(f"KLAAR - {len(results)} scenario's in {elapsed}s")
    logger.info("=" * 60)

    return results, price_cache, selection_info
