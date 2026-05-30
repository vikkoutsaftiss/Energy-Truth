"""
scenario_engine.py — Orchestratie over alle aanbieders en strategieën.

Itereert over elke combinatie van aanbieder × strategie, roept
battery_simulator en cost_calculator aan, en levert een ranking-DataFrame.

Gebruik:
    from scenario_engine import run_scenarios, run_all_scenarios
    results = run_all_scenarios("config.json")
    print(results.to_string())

Of per aanbieder:
    from scenario_engine import run_single_provider
    result = run_single_provider(meter_data, "ANWB", battery, net_prices, strategy="D")
"""
from __future__ import annotations  # maakt list[dict] etc. bruikbaar op Python 3.8+

import time
import logging
import pandas as pd
import numpy as np
from typing import Optional

from simulation_config import SimulationConfig, BatteryConfig
from data_ingestion import load_meter_csv, save_to_database
from reference_data import get_provider_prices, get_net_prices, reconstruct_historical_prices
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
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# HTTP-libraries stil zetten (Supabase/httpx spam onderdrukken)
for _lib in ("httpx", "httpcore", "hpack", "urllib3"):
    logging.getLogger(_lib).setLevel(logging.WARNING)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _refresh_margins_if_stale(max_age_hours: int = 24) -> None:
    """
    Herbereken provider_margins als de laatst berekende waarde ouder is
    dan max_age_hours uur.  Zo blijven margins up-to-date als er dagelijks
    nieuwe Enever-data binnenkomt via n8n.
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
                print(f"  ✅ Margins zijn actueel (< {max_age_hours}u) — overgeslagen")
                return
            print(f"  ⏳ Margins zijn verouderd (> {max_age_hours}u) — herberekening gestart")
        else:
            print("  ⚠️  Geen margins of timestamp gevonden — herberekening")

        from reference_data import calculate_margins
        calculate_margins()
        print("  ✅ Margins succesvol herberekend")

    except Exception as e:
        print(f"  ❌ Margin-refresh mislukt: {e}")
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
            - list[dict] met {"code": ..., "name": ...} voor 2×N aanbieders
            - dict met selectie-info voor rapportage:
              {"cheapest": [...], "expensive": [...], "margins": {code: margin}}
    """
    client = get_client()

    # Marges ophalen (gekoppeld aan Net_Aanbieder via ID); haal direct ook Afkorting op
    # via een tweede query omdat Supabase-client geen JOIN syntax heeft.
    # ERD-kolomnaam in Marges_Per_Aanbieder is "Net_AanbiederID" (zonder underscore).
    margins = client.table("Marges_Per_Aanbieder").select("Net_AanbiederID, Gemiddelde_Marge").execute()
    if not margins.data:
        logger.warning("Geen marges beschikbaar -- kan geen selectie maken")
        return [], {}

    # Mapping Net_AanbiederID -> Afkorting + Naam
    aanbieders = client.table("Net_Aanbieder").select("ID, Afkorting, Naam").execute().data or []
    # Sleutels als string zodat de koppeling werkt of Net_AanbiederID nu
    # int of text is (schema.sql zegt int, sommige servers hebben text).
    id_to_code = {str(a["ID"]): a["Afkorting"] for a in aanbieders}
    id_to_name = {str(a["ID"]): a["Naam"] for a in aanbieders}

    df = pd.DataFrame(margins.data)
    df["Gemiddelde_Marge"] = pd.to_numeric(df["Gemiddelde_Marge"])
    df["provider_code"] = df["Net_AanbiederID"].astype(str).map(id_to_code)
    df = df.dropna(subset=["provider_code"]).sort_values("Gemiddelde_Marge")

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
    Supabase-prijzen zijn UTC-aware, meterdata kan tz-naive zijn.
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


def _load_meter_data_from_db(klant_id: int, start_date: str, end_date: str) -> pd.DataFrame:
    """
    Laad meterdata rechtstreeks uit de DB (Verbruiksdata tabel).

    Werkwijze (schema 26 mei 2026):
      Verbruiksdata heeft GEEN Gebouw_ID-kolom. De koppeling naar het
      Gebouw loopt via ImportBatch: Verbruiksdata.ImportBatchID ->
      ImportBatch.ID, ImportBatch.GebouwID -> Gebouw.ID. We joinen daarom
      Verbruiksdata -> ImportBatch -> Gebouw en filteren op Klant_ID +
      datumrange. Dit gebeurt in één SQL-statement via een directe
      psycopg2-connectie (de .table()-wrapper kent geen JOIN-syntax).

      De Yan-stijl kolomnamen worden hernoemd naar de pandas-conventie
      die de rest van de simulator gebruikt (timestamp_from,
      consumption_kwh, feed_in_kwh), zodat battery_simulator +
      cost_calculator ongewijzigd blijven werken.

    Returns:
        DataFrame met timestamp_from, consumption_kwh, feed_in_kwh (UTC-aware)
        Lege DataFrame als geen data gevonden.
    """
    sql = """
        SELECT v."MeetDatumTijd"               AS "MeetDatumTijd",
               v."Stroom_Gekocht_Net_kWh"      AS "Stroom_Gekocht_Net_kWh",
               v."Stroom_Verkocht_Net_kWh"     AS "Stroom_Verkocht_Net_kWh"
        FROM "Verbruiksdata" v
        JOIN "ImportBatch" b ON v."ImportBatchID" = b."ID"
        JOIN "Gebouw"      g ON b."GebouwID"      = g."ID"
        WHERE g."Klant_ID" = %s
          AND v."MeetDatumTijd" >= %s
          AND v."MeetDatumTijd" <= %s
        ORDER BY v."MeetDatumTijd"
    """
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (
                klant_id,
                f"{start_date} 00:00:00",
                f"{end_date} 23:59:59",
            ))
            all_records = [dict(r) for r in cur.fetchall()]

    if not all_records:
        return pd.DataFrame()

    df = pd.DataFrame(all_records)
    # Hernoem naar interne pandas-conventie
    df = df.rename(columns={
        "MeetDatumTijd": "timestamp_from",
        "Stroom_Gekocht_Net_kWh": "consumption_kwh",
        "Stroom_Verkocht_Net_kWh": "feed_in_kwh",
    })
    df["timestamp_from"] = pd.to_datetime(df["timestamp_from"], utc=True)
    df["consumption_kwh"] = pd.to_numeric(df["consumption_kwh"])
    df["feed_in_kwh"] = pd.to_numeric(df["feed_in_kwh"])
    return df


def _load_meter_data(config: SimulationConfig) -> pd.DataFrame:
    """
    Laad meterdata uit Supabase.
    Indien niet aanwezig: lees CSV in via data_ingestion, sla op in Supabase,
    en lees daarna alsnog uit Supabase. Geen directe CSV-fallback.
    """
    start = config.simulation.start_date
    end = config.simulation.end_date

    # Stap 1: Probeer Supabase
    df = _load_meter_data_from_db(config.klant_id, start, end)
    if not df.empty:
        logger.info(
            f"Meterdata uit Supabase: {len(df)} kwartieren "
            f"({start} t/m {end})"
        )
        return df

    # Stap 2: Geen data in Supabase — CSV inlezen en opslaan
    if not config.csv_file:
        raise ValueError(
            f"Geen meterdata in de DB voor klant {config.klant_id} "
            f"en geen csv_file geconfigureerd."
        )

    logger.info(
        "Geen meterdata in Supabase — CSV wordt ingelezen en opgeslagen"
    )
    csv_df = load_meter_csv(config.csv_file, klant_id=config.klant_id)
    result = save_to_database(csv_df, klant_id=config.klant_id)
    logger.info(
        f"CSV ingestie voltooid: {result.get('inserted', '?')} records "
        f"opgeslagen in Supabase"
    )

    # Stap 3: Opnieuw uit Supabase laden (single source of truth)
    df = _load_meter_data_from_db(config.klant_id, start, end)
    if df.empty:
        raise ValueError(
            f"Na CSV-ingestie nog steeds geen meterdata in Supabase "
            f"voor periode {start} t/m {end}."
        )

    logger.info(
        f"Meterdata uit Supabase (na ingestie): {len(df)} kwartieren "
        f"({start} t/m {end})"
    )
    return df


# ---------------------------------------------------------------------------
# Per-aanbieder simulatie
# ---------------------------------------------------------------------------

def _run_single_with_prices(
    meter_data: pd.DataFrame,
    provider_code: str,
    battery: BatteryConfig,
    prices: pd.DataFrame,
    net_prices: pd.DataFrame,
    strategy: str = "A",
) -> dict:
    """
    Interne versie van run_single_provider die al-opgehaalde prijzen accepteert.
    Voorkomt dat prijzen per strategie opnieuw worden opgehaald.
    """
    if prices.empty:
        return {
            "provider_code": provider_code,
            "strategy": strategy,
            "cost_no_battery": None,
            "cost_with_battery": None,
            "savings_eur": None,
            "savings_pct": None,
            "quarters": 0,
            "error": "geen prijsdata",
        }

    # Normaliseer timestamps
    prices_norm = _normalize_timestamps(prices.copy(), "valid_from")
    net_prices_norm = _normalize_timestamps(net_prices.copy(), "valid_from") if net_prices is not None else None

    # Filter meterdata op kwartieren waarvoor prijzen beschikbaar zijn
    price_timestamps = set(prices_norm["valid_from"])
    meter_filtered = meter_data[meter_data["timestamp_from"].isin(price_timestamps)].copy()
    meter_filtered = meter_filtered.sort_values("timestamp_from").reset_index(drop=True)

    if meter_filtered.empty:
        return {
            "provider_code": provider_code,
            "strategy": strategy,
            "cost_no_battery": None,
            "cost_with_battery": None,
            "savings_eur": None,
            "savings_pct": None,
            "quarters": 0,
            "error": "geen overlap meterdata/prijzen",
        }

    # Kosten ZONDER batterij
    costs_no_bat = calculate_costs_no_battery(
        meter_filtered, prices_norm, provider_code, net_prices=net_prices_norm
    )

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


def run_single_provider(
    meter_data: pd.DataFrame,
    provider_code: str,
    battery: BatteryConfig,
    net_prices: pd.DataFrame,
    strategy: str = "A",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> dict:
    """
    Draai een volledige simulatie voor één aanbieder + één strategie.

    Parameters
    ----------
    meter_data : DataFrame
        Kwartierdata met timestamp_from, consumption_kwh, feed_in_kwh.
    provider_code : str
        Bijv. 'ANWB', 'TI', 'EN'.
    battery : BatteryConfig
        Batterijconfiguratie.
    net_prices : DataFrame
        Kale beursprijzen (valid_from, price).
    strategy : str
        'A', 'B', 'C' of 'D'.
    start_date, end_date : str, optional
        Optionele datumfilters voor prijsdata.

    Returns
    -------
    dict met keys:
        provider_code, strategy, cost_no_battery, cost_with_battery,
        savings_eur, savings_pct, quarters, sim_summary
    """
    # 1. Haal all-in prijzen op voor deze aanbieder
    #    Eerst echte Enever-prijzen proberen, dan reconstructie via margin-methode
    prices = get_provider_prices(provider_code, start_date=start_date, end_date=end_date)
    if prices.empty:
        logger.info(f"Geen Enever-prijzen voor {provider_code} — reconstructie via margin")
        prices = reconstruct_historical_prices(provider_code, start_date, end_date)
    elif start_date and end_date:
        # Check of echte prijzen de hele periode dekken; zo niet, aanvullen
        expected_days = (pd.Timestamp(end_date) - pd.Timestamp(start_date)).days + 1
        actual_days = prices["valid_from"].dt.date.nunique()
        if actual_days < expected_days * 0.9:  # minder dan 90% dekking
            logger.info(
                f"{provider_code}: {actual_days}/{expected_days} dagen "
                f"Enever-data — aanvullen via reconstructie"
            )
            prices = reconstruct_historical_prices(provider_code, start_date, end_date)

    if prices.empty:
        logger.warning(f"Geen prijzen voor {provider_code} (ook niet via reconstructie) — overgeslagen")
        return {
            "provider_code": provider_code,
            "strategy": strategy,
            "cost_no_battery": None,
            "cost_with_battery": None,
            "savings_eur": None,
            "savings_pct": None,
            "quarters": 0,
            "error": "geen prijsdata",
        }

    # 1b. Normaliseer timestamps zodat meterdata en prijzen matchen
    prices = _normalize_timestamps(prices, "valid_from")
    net_prices_norm = _normalize_timestamps(net_prices.copy(), "valid_from") if net_prices is not None else None

    # 1c. Filter meterdata op kwartieren waarvoor prijzen beschikbaar zijn.
    #     Zo hebben costs_no_battery, simulate_battery en costs_with_battery
    #     allemaal dezelfde rijen (voorkomt length mismatch).
    price_timestamps = set(prices["valid_from"])
    meter_filtered = meter_data[meter_data["timestamp_from"].isin(price_timestamps)].copy()
    meter_filtered = meter_filtered.sort_values("timestamp_from").reset_index(drop=True)

    if meter_filtered.empty:
        logger.warning(f"Geen overlap meterdata ↔ prijzen voor {provider_code}")
        return {
            "provider_code": provider_code,
            "strategy": strategy,
            "cost_no_battery": None,
            "cost_with_battery": None,
            "savings_eur": None,
            "savings_pct": None,
            "quarters": 0,
            "error": "geen overlap meterdata/prijzen",
        }

    dropped = len(meter_data) - len(meter_filtered)
    if dropped > 0:
        logger.debug(f"{provider_code}: {dropped} kwartieren zonder prijs overgeslagen")

    # 2. Kosten ZONDER batterij
    costs_no_bat = calculate_costs_no_battery(
        meter_filtered, prices, provider_code, net_prices=net_prices_norm
    )

    # 3. Batterijsimulatie (op dezelfde gefilterde meterdata)
    simulated = simulate_battery(
        meter_filtered, battery, prices=prices, strategy=strategy
    )

    # 4. Merge prijzen in gesimuleerde data (cost_calculator verwacht 'price' kolom)
    if "price" not in simulated.columns:
        simulated = simulated.merge(
            prices[["valid_from", "price"]],
            left_on="timestamp_from",
            right_on="valid_from",
            how="left",
        )

    # 5. Kosten MET batterij
    costs_with_bat = calculate_costs_with_battery(
        simulated, provider_code, net_prices=net_prices_norm
    )

    # 6. Combineer de twee kostenkolommen (nu gegarandeerd zelfde lengte)
    combined = costs_no_bat.copy()
    if "cost_with_battery" in costs_with_bat.columns:
        combined = combined.reset_index(drop=True)
        costs_with_bat = costs_with_bat.reset_index(drop=True)
        combined["cost_with_battery"] = costs_with_bat["cost_with_battery"]

    # 7. Besparingssamenvatting
    summary = calculate_savings_summary(combined)

    # 8. Simulatie-samenvatting (SoC, cycli, etc.)
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
        # Ruwe som over aangeleverde data
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
    Draai simulaties voor meerdere aanbieders × meerdere strategieën.

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
        Welke strategieën te draaien. Standaard ["A", "B", "C", "D"].
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

        # Prijzen 1× per aanbieder ophalen en cachen
        if code not in _price_cache:
            prices = get_provider_prices(code, start_date=start_date, end_date=end_date)
            if prices.empty:
                logger.info(f"Geen Enever-prijzen voor {code} — reconstructie via margin")
                prices = reconstruct_historical_prices(code, start_date, end_date)
            elif start_date and end_date:
                expected_days = (pd.Timestamp(end_date) - pd.Timestamp(start_date)).days + 1
                actual_days = prices["valid_from"].dt.date.nunique() if not prices.empty else 0
                if actual_days < expected_days * 0.9:
                    logger.info(f"{code}: {actual_days}/{expected_days} dagen Enever-data — aanvullen via reconstructie")
                    prices = reconstruct_historical_prices(code, start_date, end_date)
            _price_cache[code] = prices

        for strategy in strategies:
            done += 1
            logger.info(f"[{done}/{total}] {name} ({code}) — Strategie {strategy}")
            t0 = time.time()

            try:
                result = _run_single_with_prices(
                    meter_data=meter_data,
                    provider_code=code,
                    battery=battery,
                    prices=_price_cache[code],
                    net_prices=net_prices,
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
        Strategieën om te testen. Standaard alle vier: ["A", "B", "C", "D"].
    smart_select : int
        Selecteer de N goedkoopste + N duurste aanbieders op basis van margin.
        Standaard 3 (= 6 aanbieders × 4 strategieën = 24 runs).
        Zet op 0 om alle aanbieders te draaien (uit config).

    Returns
    -------
    DataFrame met ranking per aanbieder × strategie.
    """
    logger.info("=" * 60)
    logger.info("ENERGY-TRUTH SCENARIO ENGINE — START")
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

    # 2b. Margins refreshen als ze ouder zijn dan 24 uur
    _refresh_margins_if_stale(max_age_hours=12)

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
    logger.info(f"KLAAR — {len(results)} scenario's in {elapsed}s")
    logger.info("=" * 60)

    return results, price_cache, selection_info


# ---------------------------------------------------------------------------
# Resultaat-helpers
# ---------------------------------------------------------------------------

def print_ranking(results: pd.DataFrame, top_n: int = 10) -> None:
    """Print een leesbare ranking-tabel."""
    if results.empty:
        print("Geen resultaten.")
        return

    display_cols = [
        "provider_name", "strategy", "cost_no_battery",
        "cost_with_battery", "savings_eur", "savings_pct",
    ]
    # Alleen kolommen die bestaan
    display_cols = [c for c in display_cols if c in results.columns]

    print("\n" + "=" * 80)
    print("ENERGY-TRUTH — SCENARIO RANKING")
    print("=" * 80)

    df = results.head(top_n).copy()
    if "cost_no_battery" in df.columns:
        df["cost_no_battery"] = df["cost_no_battery"].apply(
            lambda x: f"€{x:,.2f}" if pd.notna(x) else "—"
        )
    if "cost_with_battery" in df.columns:
        df["cost_with_battery"] = df["cost_with_battery"].apply(
            lambda x: f"€{x:,.2f}" if pd.notna(x) else "—"
        )
    if "savings_eur" in df.columns:
        df["savings_eur"] = df["savings_eur"].apply(
            lambda x: f"€{x:,.2f}" if pd.notna(x) else "—"
        )
    if "savings_pct" in df.columns:
        df["savings_pct"] = df["savings_pct"].apply(
            lambda x: f"{x:.1f}%" if pd.notna(x) else "—"
        )

    # Hernoem voor leesbaarheid
    rename = {
        "provider_name": "Aanbieder",
        "strategy": "Strat.",
        "cost_no_battery": "Zonder batterij",
        "cost_with_battery": "Met batterij",
        "savings_eur": "Besparing",
        "savings_pct": "%",
    }
    df = df[display_cols].rename(columns=rename)
    print(df.to_string())
    print()


def get_best_scenario(results: pd.DataFrame) -> dict:
    """
    Retourneer het scenario met de hoogste besparing.

    Returns
    -------
    dict met alle kolommen van het beste scenario, of lege dict.
    """
    if results.empty:
        return {}

    valid = results.dropna(subset=["savings_eur"])
    if valid.empty:
        return {}

    best = valid.iloc[0]  # Al gesorteerd op savings_eur desc
    return best.to_dict()


def compare_strategies(results: pd.DataFrame) -> pd.DataFrame:
    """
    Vergelijk strategieën per aanbieder: draaitabel met
    strategieën als kolommen en besparing als waarden.

    Returns
    -------
    DataFrame met aanbieders als rijen, strategieën als kolommen.
    """
    if results.empty:
        return pd.DataFrame()

    pivot = results.pivot_table(
        index=["provider_code", "provider_name"],
        columns="strategy",
        values="savings_eur",
        aggfunc="first",
    )
    pivot.columns = [f"Strategie {c}" for c in pivot.columns]
    pivot = pivot.reset_index()
    pivot = pivot.sort_values(
        pivot.columns[-1], ascending=False, na_position="last"
    )
    return pivot


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    config_path = sys.argv[1] if len(sys.argv) > 1 else "config.json"

    # Optioneel: strategieën opgeven (standaard alle vier)
    strategies = None  # = ["A", "B", "C", "D"]
    if len(sys.argv) > 2:
        strategies = [s.strip().upper() for s in sys.argv[2].split(",")]

    # Optioneel: smart_select=0 voor alle aanbieders, anders top/bottom N
    smart_select = 3
    if len(sys.argv) > 3:
        smart_select = int(sys.argv[3])

    results = run_all_scenarios(
        config_path, strategies=strategies, smart_select=smart_select
    )
    print_ranking(results, top_n=30)

    print("\n--- VERGELIJKING PER AANBIEDER ---")
    comp = compare_strategies(results)
    if not comp.empty:
        print(comp.to_string())

    best = get_best_scenario(results)
    if best:
        print(f"\nBeste scenario: {best.get('provider_name')} "
              f"Strategie {best.get('strategy')} "
              f"-- besparing EUR {best.get('savings_eur', 0):.2f} "
              f"({best.get('savings_pct', 0):.1f}%)")

