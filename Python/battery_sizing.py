"""
battery_sizing.py - Optimal battery selection voor een huishouden.

Loopt over alle actieve batterijen uit markt_product (via
battery_catalog), draait simulaties voor elke (batterij x
strategie) combinatie, en levert een ranking op basis van:
  - NPV over horizon (default 10 jaar, 3% discount)
  - Payback period in jaren (simple, geen discount)
  - LCOE_storage uit echte EFC in de simulatie
  - GO/NOGO toetsing: payback < garantiejaren

Methodologie geinspireerd op Hudelist, Maussner, Teppan & Wiegelmann
(2026), "Simulation-Based Optimization of Demand Flexibility and
Storage Capacity in Distributed Solar Energy Systems", ICAART 2026,
DOI 10.5220/0014445900004052. iLESS Battery Simulator code (MIT)
beschikbaar op https://codeberg.org/FraunhoferAustria/iLESS_Battery_Simulator.

Originele bijdrage: dynamische EPEX-prijzen, vier strategieen (i.p.v.
greedy self-consumption alleen), GO/NOGO op kalendergarantie i.p.v.
cycli-garantie, en LCOE op werkelijke gesimuleerde EFC.

Gebruik:
    from battery_sizing import find_optimal_battery
    results = find_optimal_battery(meter_data, provider_code='BE')
    print(results.to_string())
"""

from __future__ import annotations

import math
from dataclasses import dataclass, asdict
from typing import Optional

import pandas as pd

from battery_catalog import (
    BatteryCatalogEntry,
    USER_BATTERY_ID,
    entry_from_battery_config,
    get_battery_catalog,
    to_battery_config,
)
from battery_simulator import simulate_battery
from cost_calculator import (
    calculate_costs_no_battery,
    calculate_costs_with_battery,
    calculate_savings_summary,
)
from reference_data import (
    get_net_prices,
    get_provider_prices,
    reconstruct_historical_prices,
    get_allin_prices,
)
from scenario_engine import _normalize_timestamps

# ============================================================
# DEFAULTS
# ============================================================

DEFAULT_HORIZON_YEARS = 10       # sluit aan op typische kalendergarantie
DEFAULT_DISCOUNT_RATE = 0.03     # ECB/hypotheekrente-achtige aanname
GO_NOGO_GRENS_MARGE = 1.2        # ONZEKER-gebied: 20% over de garantie
EFC_NOMINAAL = 250               # praktijk EFC/jaar als fallback


# ============================================================
# DATACLASS RESULTAAT
# ============================================================

@dataclass
class SizingResult:
    """KPI's voor een (batterij x strategie) combinatie."""

    battery_id: int
    productnaam: str
    chemie: Optional[str]
    capaciteit_kwh: float
    bruikbare_kwh: float
    strategie: str

    # Investering
    aanschafprijs_eur: float
    installatiekosten_eur: float
    totale_capex_eur: float

    # Operationeel (jaarbasis, seizoensgewogen)
    jaarlijkse_besparing_eur: float
    besparing_pct: float

    # Financiele KPI's
    npv_eur: float
    payback_jaren: Optional[float]

    # Praktijk
    efc_per_jaar: float
    lcoe_storage_eur_per_kwh: float

    # Garantie en advies
    garantiejaren: float
    go_nogo: str
    go_nogo_reden: str

    # Visual (voor PDF-rapport)
    foto_url: Optional[str] = None

    # Metadata
    horizon_jaren: int = 10
    discount_rate: float = 0.03


# ============================================================
# KPI-HELPERS
# ============================================================

def calculate_npv(
    annual_savings: float,
    capex: float,
    horizon_years: int,
    discount_rate: float,
) -> float:
    """
    Net Present Value van een batterij-investering.
    Formule: NPV = -CAPEX + besparing * annuity_factor
    """
    if annual_savings <= 0:
        return -capex
    if discount_rate > 0:
        pv_factor = (1 - (1 + discount_rate) ** -horizon_years) / discount_rate
    else:
        pv_factor = horizon_years
    return -capex + annual_savings * pv_factor


def calculate_payback(annual_savings: float, capex: float) -> Optional[float]:
    """Simple payback in jaren (geen discounting)."""
    if annual_savings <= 0:
        return None
    return capex / annual_savings


def calculate_efc_per_year(simulated_df: pd.DataFrame, usable_capacity_kwh: float) -> float:
    """
    Equivalent Full Cycles per jaar uit simulatie.
    EFC = totale ontlaad-kWh / bruikbare capaciteit, schaal naar 365 dagen.
    """
    if "soc" not in simulated_df.columns or usable_capacity_kwh <= 0:
        return 0.0
    soc_diff = simulated_df["soc"].diff()
    discharge_kwh = -soc_diff.clip(upper=0).sum()  # alleen negative deltas
    efc_periode = float(discharge_kwh) / usable_capacity_kwh

    # Schaal naar jaarbasis
    ts = simulated_df["timestamp_from"]
    if len(ts) < 2:
        return efc_periode
    duur_dagen = (ts.max() - ts.min()).total_seconds() / 86400
    if duur_dagen <= 0:
        return efc_periode
    return efc_periode * (365.0 / duur_dagen)


def calculate_lcoe_storage(
    capex: float,
    efc_per_year: float,
    usable_capacity_kwh: float,
    garantiejaren: float,
) -> float:
    """
    Levelized Cost of Stored Electricity in euro/kWh.
    Levensduur capped op kalendergarantie (jouw GO/NOGO uitgangspunt).
    """
    total_kwh = efc_per_year * usable_capacity_kwh * garantiejaren
    if total_kwh <= 0:
        return float("inf")
    return capex / total_kwh


def determine_go_nogo(
    payback: Optional[float],
    garantiejaren: float,
) -> tuple[str, str]:
    """
    Vergelijk payback met kalendergarantie.
    Returns: (label, reden)
    """
    if payback is None:
        return "NOGO", "Geen positieve jaarlijkse besparing"
    if payback < garantiejaren:
        return "GO", f"Payback {payback:.1f}j < garantie {garantiejaren:.0f}j"
    if payback < garantiejaren * GO_NOGO_GRENS_MARGE:
        return "ONZEKER", (
            f"Payback {payback:.1f}j net boven garantie "
            f"{garantiejaren:.0f}j (binnen 20%)"
        )
    return "NOGO", f"Payback {payback:.1f}j boven garantie {garantiejaren:.0f}j"


# ============================================================
# CORE: EEN BATTERIJ EVALUEREN
# ============================================================

def evaluate_candidate(
    meter_data: pd.DataFrame,
    candidate: BatteryCatalogEntry,
    provider_code: str,
    prices: pd.DataFrame,
    net_prices: Optional[pd.DataFrame],
    strategy: str = "D",
    horizon_years: int = DEFAULT_HORIZON_YEARS,
    discount_rate: float = DEFAULT_DISCOUNT_RATE,
) -> Optional[SizingResult]:
    """
    Evalueer een specifieke batterij met een specifieke strategie.

    Args:
        meter_data: DataFrame met timestamp_from, consumption_kwh, feed_in_kwh
        candidate: BatteryCatalogEntry uit get_battery_catalog
        provider_code: bv 'BE', 'ANWB'
        prices: all-in prijzen (DataFrame valid_from, price)
        net_prices: kale beursprijzen voor terugleverprijs
        strategy: 'A', 'B', 'C' of 'D'
        horizon_years: NPV-horizon in jaren
        discount_rate: discount rate als decimal (0.03 = 3%)

    Returns:
        SizingResult of None bij fout
    """
    battery_config = to_battery_config(candidate)

    # Filter op kwartieren met prijzen
    price_ts = set(prices["valid_from"])
    meter_filt = meter_data[meter_data["timestamp_from"].isin(price_ts)].copy()
    meter_filt = meter_filt.sort_values("timestamp_from").reset_index(drop=True)
    if meter_filt.empty:
        return None

    # Kosten zonder batterij
    costs_no_bat = calculate_costs_no_battery(
        meter_filt, prices, provider_code, net_prices=net_prices
    )

    # Simulatie
    simulated = simulate_battery(
        meter_filt, battery_config, prices=prices, strategy=strategy
    )
    if simulated.empty:
        return None

    # Merge prijzen indien nodig
    if "price" not in simulated.columns:
        simulated = simulated.merge(
            prices[["valid_from", "price"]],
            left_on="timestamp_from",
            right_on="valid_from",
            how="left",
        )

    # Kosten met batterij
    costs_with_bat = calculate_costs_with_battery(
        simulated, provider_code, net_prices=net_prices
    )

    combined = costs_no_bat.copy().reset_index(drop=True)
    costs_with_bat = costs_with_bat.reset_index(drop=True)
    if "cost_with_battery" in costs_with_bat.columns:
        combined["cost_with_battery"] = costs_with_bat["cost_with_battery"]

    summary = calculate_savings_summary(combined)
    annual_savings = float(summary.get("total_savings", 0) or 0)
    savings_pct = float(summary.get("savings_percentage", 0) or 0)

    # Investering
    capex = candidate.totale_investering_eur

    # KPI's
    npv = calculate_npv(annual_savings, capex, horizon_years, discount_rate)
    payback = calculate_payback(annual_savings, capex)

    # EFC en LCOE
    efc = calculate_efc_per_year(simulated, battery_config.usable_capacity_kwh)
    lcoe = calculate_lcoe_storage(
        capex, efc, battery_config.usable_capacity_kwh, candidate.garantiejaren
    )

    # GO/NOGO
    label, reden = determine_go_nogo(payback, candidate.garantiejaren)

    return SizingResult(
        battery_id=candidate.id,
        productnaam=candidate.productnaam,
        chemie=candidate.chemie,
        capaciteit_kwh=round(candidate.capaciteit_kwh, 2),
        bruikbare_kwh=round(candidate.bruikbare_capaciteit_kwh, 2),
        strategie=strategy,
        aanschafprijs_eur=round(candidate.aanschafprijs, 2),
        installatiekosten_eur=round(candidate.installatiekosten_eur, 2),
        totale_capex_eur=round(capex, 2),
        jaarlijkse_besparing_eur=round(annual_savings, 2),
        besparing_pct=round(savings_pct, 1),
        npv_eur=round(npv, 2),
        payback_jaren=round(payback, 2) if payback is not None else None,
        efc_per_jaar=round(efc, 1),
        lcoe_storage_eur_per_kwh=round(lcoe, 4) if math.isfinite(lcoe) else None,
        garantiejaren=float(candidate.garantiejaren),
        go_nogo=label,
        go_nogo_reden=reden,
        foto_url=candidate.foto_url,
        horizon_jaren=horizon_years,
        discount_rate=discount_rate,
    )


# ============================================================
# MULTI-CANDIDATE LOOP
# ============================================================

def find_optimal_battery(
    meter_data: pd.DataFrame,
    provider_code: str = "BE",
    strategies: Optional[list[str]] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    horizon_years: int = DEFAULT_HORIZON_YEARS,
    discount_rate: float = DEFAULT_DISCOUNT_RATE,
    min_capacity_kwh: Optional[float] = None,
    max_capacity_kwh: Optional[float] = None,
    own_battery=None,
) -> pd.DataFrame:
    """
    Loop over alle batterijen in de catalog en bepaal optimale keuze.

    Args:
        meter_data: kwartierdata
        provider_code: aanbieder voor prijsdata
        strategies: lijst strategieen, default ['D']
        start_date/end_date: datumfilters voor prijsdata
        horizon_years: NPV-horizon
        discount_rate: discount rate
        min/max_capacity_kwh: filter op catalog
        own_battery: optionele BatteryConfig (typisch uit config.json) die
            als extra kandidaat met id = USER_BATTERY_ID wordt toegevoegd.
            Krijgt label "Eigen batterij (uit config)" tenzij productnaam
            in de config is ingevuld.

    Returns:
        DataFrame met sizing-resultaten, gesorteerd op NPV desc.
    """
    if strategies is None:
        # Default: A (zelfverbruik) + C (hybride) + D (slim zelfverbruik).
        # B (puur arbitrage) is in de Nederlandse markt zelden rendabel
        # en wordt alleen meegenomen als de gebruiker er expliciet om vraagt.
        strategies = ["A", "C", "D"]

    catalog = get_battery_catalog(
        min_capacity_kwh=min_capacity_kwh,
        max_capacity_kwh=max_capacity_kwh,
    )

    # Voeg eigen batterij toe als extra kandidaat (uit config.json)
    if own_battery is not None:
        own_entry = entry_from_battery_config(own_battery)
        if own_entry is None:
            print("  Eigen batterij overgeslagen: prijs of capaciteit ontbreekt in config.json")
        else:
            print(f"  Eigen batterij toegevoegd: {own_entry.label}")
            if own_battery.garantiejaren is None or own_battery.gegarandeerde_laadcycli is None:
                print(f"    LET OP: garantiejaren en/of cycli ontbreken in config.json - "
                      f"defaults gebruikt (10j, 6000 cycli)")
            catalog = catalog + [own_entry]

    if not catalog:
        print("  Geen batterijen in catalog en geen eigen batterij.")
        return pd.DataFrame()

    # Prijzen ophalen (1x, hergebruiken voor alle batterijen). Zelfde bron als
    # scenario_engine: de voorberekende 15-min all-in reeks (get_allin_prices),
    # die intern terugvalt op reconstructie. Zo is de besparing/payback hier
    # identiek aan de leveranciersvergelijking en rekenen we op 100% van de
    # kwartieren i.p.v. alleen de uurpunten (de oude get_provider_prices-route
    # ving maar ~25% van de 15-min meterdata).
    prices = get_allin_prices(provider_code, start_date, end_date)
    if prices.empty:
        print(f"  Geen prijsdata voor {provider_code}.")
        return pd.DataFrame()

    prices = _normalize_timestamps(prices, "valid_from")
    net_prices = get_net_prices(start_date=start_date, end_date=end_date)
    net_prices_norm = (
        _normalize_timestamps(net_prices, "valid_from")
        if not net_prices.empty
        else None
    )

    results = []
    total = len(catalog) * len(strategies)
    done = 0

    print(f"  {len(catalog)} batterijen x {len(strategies)} strategieen = {total} runs")
    for candidate in catalog:
        for strategy in strategies:
            done += 1
            print(f"  [{done}/{total}] {candidate.label} - strategie {strategy}")
            try:
                result = evaluate_candidate(
                    meter_data,
                    candidate,
                    provider_code,
                    prices,
                    net_prices_norm,
                    strategy=strategy,
                    horizon_years=horizon_years,
                    discount_rate=discount_rate,
                )
                if result:
                    results.append(asdict(result))
            except Exception as e:
                print(f"    Fout: {e}")

    if not results:
        return pd.DataFrame()

    df = pd.DataFrame(results)
    df = df.sort_values("npv_eur", ascending=False).reset_index(drop=True)
    df.index = df.index + 1
    df.index.name = "rank"
    return df
