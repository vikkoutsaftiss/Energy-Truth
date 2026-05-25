"""
battery_simulator.py — Batterijsimulatie per kwartier voor Energy-Truth.

Vier laadstrategieën:
  A. Zelfverbruik       — overschot opslaan, tekort uit batterij dekken (geen prijsinfo)
  B. Arbitrage          — puur prijsgestuurd, batterij ONAFHANKELIJK van huishouden
  C. Hybride (A+B)      — eigen verbruik ALTIJD voor, daarna slim bij-/verkopen van net
  D. Slim Zelfverbruik  — alleen eigen zon, maar PRIJSBEWUST opslaan/ontladen

Strategie B (puur arbitrage):
  - Huishouden → altijd via net (geen zelfverbruik-optimalisatie)
  - Lage prijs → kopen van net en batterij laden
  - Hoge prijs → ontladen: eerst eigen verbruik dekken, overschot naar net
  - Normaal → batterij doet niets
  - Zon-overschot → altijd naar net (niet opgeslagen)

Strategie C (hybride):
  Stap 1: eigen overschot → batterij laden / eigen tekort → batterij ontladen
  Stap 2: prijs laag + nog ruimte in batterij → bijkopen van net
  Stap 3: prijs hoog + nog energie in batterij → extra ontladen en terugleveren

Strategie D (slim zelfverbruik):
  Alleen eigen zon-energie, GEEN bijkopen van net → opgeslagen kWh is BELASTINGVRIJ.
  Zon-overschot:
    - Prijs HOOG → verkopen aan net (goede prijs pakken)
    - Prijs normaal/laag → opslaan in batterij (bewaren voor dure uren)
  Eigen tekort:
    - Prijs HOOG → ontladen uit batterij (vermijd dure stroom + belasting kopen)
    - Prijs LAAG → kopen van net (goedkoop, zelfs met belasting), batterij bewaren

  Belastingvoordeel: elke kWh uit eigen zon die je zelf verbruikt bespaart de volle
  all-in prijs (incl. EB+ODE+btw), terwijl verkopen alleen de beursprijs oplevert.

Dynamische drempels:
  - Laaddrempel = percentiel gebaseerd op laadtijd (capacity / charge_rate)
  - Ontlaaddrempel = percentiel gebaseerd op ontlaadtijd (capacity / discharge_rate)
  - Minimum spread check: arbitrage alleen als spread > round-trip efficiëntieverlies

Gebruik:
    from battery_simulator import simulate_battery
    result = simulate_battery(meter_data, battery_config, prices, strategy='D')
"""

import pandas as pd
import numpy as np
from simulation_config import BatteryConfig


# ============================================================
# 1. DYNAMISCHE PRIJSDREMPELS
# ============================================================

def calculate_dynamic_thresholds(prices_df, battery):
    """
    Bereken per dag dynamische laad- en ontlaaddrempels op basis van
    batterijcapaciteit en laad/ontlaadvermogen.

    Logica:
      - charge_quarters = bruikbare capaciteit / laden per kwartier
        → hoeveel goedkope kwartieren heb je nodig om vol te laden?
      - discharge_quarters = bruikbare capaciteit / ontladen per kwartier
        → hoeveel dure kwartieren heb je nodig om leeg te ontladen?
      - low_pct = charge_quarters / 96 × 100
      - high_pct = 100 − discharge_quarters / 96 × 100
      - min_spread_ok: alleen arbitrage als spread > round-trip verlies

    Voorbeeld (10 kWh, 20-80%, 2.5 kW laden, 3.68 kW ontladen):
      bruikbaar = 6.0 kWh
      charge_quarters = 6.0 / 0.594 ≈ 10 → low_pct ≈ 10.4%
      discharge_quarters = 6.0 / 0.874 ≈ 7 → high_pct ≈ 92.8%

    Args:
        prices_df: DataFrame met valid_from en price
        battery: BatteryConfig object

    Returns:
        tuple: (thresholds_dict, low_pct, high_pct)
        thresholds_dict: date → {'low': float, 'high': float, 'min_spread_ok': bool}
    """
    # Hoeveel kwartieren nodig om batterij vol te laden / leeg te ontladen
    charge_quarters = battery.usable_capacity_kwh / battery.max_charge_per_quarter_kwh
    discharge_quarters = battery.usable_capacity_kwh / battery.max_discharge_per_quarter_kwh

    # Percentielen (begrensd: min 2%, max 98%)
    low_pct = min(max(charge_quarters / 96 * 100, 2), 50)
    high_pct = max(min(100 - discharge_quarters / 96 * 100, 98), 50)

    # Round-trip efficiency voor minimum spread check
    round_trip_eff = battery.charge_efficiency * battery.discharge_efficiency

    df = prices_df.copy()
    df['date'] = df['valid_from'].dt.date

    thresholds = {}
    for date, group in df.groupby('date'):
        prices = group['price'].values
        low = float(np.percentile(prices, low_pct))
        high = float(np.percentile(prices, high_pct))

        # Spread moet groter zijn dan round-trip verlies
        # high_price > low_price / round_trip_eff  →  spread > ~10.8%
        if low > 0:
            min_spread_ok = high > low / round_trip_eff
        else:
            min_spread_ok = high > 0  # negatieve/gratis stroom → altijd laden

        thresholds[date] = {
            'low': low,
            'high': high,
            'min_spread_ok': min_spread_ok,
        }

    return thresholds, low_pct, high_pct


def calculate_daily_thresholds(prices_df, low_pct=25, high_pct=75):
    """
    LEGACY: Vaste percentielen. Gebruik calculate_dynamic_thresholds() voor
    dynamische drempels op basis van batterijcapaciteit.
    """
    df = prices_df.copy()
    df['date'] = df['valid_from'].dt.date

    thresholds = {}
    for date, group in df.groupby('date'):
        thresholds[date] = {
            'low': float(np.percentile(group['price'], low_pct)),
            'high': float(np.percentile(group['price'], high_pct)),
            'min_spread_ok': True,  # legacy: geen check
        }

    return thresholds


# ============================================================
# 2. SIMULATIE PER KWARTIER — STRATEGIE A (ZELFVERBRUIK)
# ============================================================

def _simulate_quarter_a(consumption, feed_in, soc, battery):
    """
    Strategie A: Zelfverbruik.
    Overschot → laden, tekort → ontladen. Geen prijsinformatie nodig.
    """
    net = consumption - feed_in

    if net > 0:
        # Tekort → ontladen
        available_stored = soc - battery.min_soc_pct * battery.capacity_kwh
        # Correctie: beschikbare OUTPUT rekening houdend met efficiëntieverlies
        available_output = max(0, available_stored) * battery.discharge_efficiency
        discharge = min(net, available_output, battery.max_discharge_per_quarter_kwh)
        discharge = max(0, discharge)

        new_soc = soc - discharge / battery.discharge_efficiency
        grid_consumption = net - discharge
        grid_feed_in = 0.0
        grid_bought = 0.0
    else:
        # Overschot → laden
        surplus = abs(net)
        room = battery.max_soc_pct * battery.capacity_kwh - soc
        # room = hoeveel kWh er nog in de batterij past (in SoC-termen)
        # max input = room / efficiency (hoeveel input levert die room op)
        max_input = max(0, room) / battery.charge_efficiency if battery.charge_efficiency > 0 else 0
        charge = min(surplus, max_input, battery.max_charge_per_quarter_kwh)
        charge = max(0, charge)

        new_soc = soc + charge * battery.charge_efficiency
        grid_consumption = 0.0
        grid_feed_in = surplus - charge
        grid_bought = 0.0

    return new_soc, grid_consumption, grid_feed_in, grid_bought


# ============================================================
# 3. SIMULATIE PER KWARTIER — STRATEGIE B (PUUR ARBITRAGE)
# ============================================================

def _simulate_quarter_b(consumption, feed_in, soc, battery, price,
                        low_threshold, high_threshold, min_spread_ok):
    """
    Strategie B: Puur prijsarbitrage.

    De batterij opereert ONAFHANKELIJK van het huishouden.
    Het huishouden gaat standaard volledig via het net:
      - Verbruik → kopen van net
      - Zon-overschot → terugleveren aan net (NIET opslaan)

    De batterij reageert alleen op prijs:
      - Lage prijs → kopen van net en laden
      - Hoge prijs → ontladen: eerst eigen verbruik dekken (bespaart dure
        stroom), overschot terugleveren aan net
      - Normale prijs → batterij doet niets
      - Geen spread → batterij doet niets (min_spread_ok=False)

    Dit is fundamenteel anders dan C: zon-overschot wordt NIET opgeslagen,
    en bij normale prijzen wordt het eigen tekort NIET uit de batterij gedekt.
    """
    # Huishouden gaat standaard volledig via net
    grid_consumption = consumption
    grid_feed_in = feed_in
    grid_bought = 0.0
    new_soc = soc

    if not min_spread_ok:
        # Spread te klein voor winstgevende arbitrage → batterij doet niets
        return new_soc, grid_consumption, grid_feed_in, grid_bought

    if price >= high_threshold:
        # === VERKOOP DUUR: batterij ontladen ===
        available_stored = new_soc - battery.min_soc_pct * battery.capacity_kwh
        available_output = max(0, available_stored) * battery.discharge_efficiency
        discharge = min(available_output, battery.max_discharge_per_quarter_kwh)

        if discharge > 0.001:
            # Eerst eigen verbruik dekken (bespaart kopen tegen hoge prijs)
            own_use = min(discharge, grid_consumption)
            grid_consumption -= own_use

            # Overschot naar net terugleveren
            surplus_to_grid = discharge - own_use
            grid_feed_in += surplus_to_grid

            # SoC update
            new_soc -= discharge / battery.discharge_efficiency

    elif price <= low_threshold:
        # === KOOP GOEDKOOP: batterij laden van net ===
        room = battery.max_soc_pct * battery.capacity_kwh - new_soc
        max_input = max(0, room) / battery.charge_efficiency if battery.charge_efficiency > 0 else 0
        charge = min(max_input, battery.max_charge_per_quarter_kwh)

        if charge > 0.001:
            grid_consumption += charge
            grid_bought = charge
            new_soc += charge * battery.charge_efficiency

    # Normale prijs → batterij doet NIETS

    return new_soc, grid_consumption, grid_feed_in, grid_bought


# ============================================================
# 4. SIMULATIE PER KWARTIER — STRATEGIE C (HYBRIDE)
# ============================================================

def _simulate_quarter_c(consumption, feed_in, soc, battery, price,
                        low_threshold, high_threshold, min_spread_ok):
    """
    Strategie C: Hybride (eigen verbruik + arbitrage).

    Prioriteit:
      1. Eigen verbruik gaat ALTIJD voor (tekort → ontladen uit batterij)
      2. Eigen overschot → batterij laden
      3. Prijs laag + nog ruimte → bijkopen van net (alleen als spread OK)
      4. Prijs hoog + nog energie → extra ontladen en terugleveren (alleen als spread OK)

    Het verschil met B: eigen verbruik wordt ALTIJD geoptimaliseerd, ook bij
    normale prijzen. Zon-overschot wordt altijd eerst opgeslagen.
    Arbitrage is een BONUS bovenop eigen verbruik.
    """
    net = consumption - feed_in
    grid_bought = 0.0
    discharge_used = 0.0
    charge_used = 0.0

    if net > 0:
        # Stap 1: Eigen tekort → ontladen uit batterij (ALTIJD, ongeacht prijs)
        available_stored = soc - battery.min_soc_pct * battery.capacity_kwh
        available_output = max(0, available_stored) * battery.discharge_efficiency
        discharge = min(net, available_output, battery.max_discharge_per_quarter_kwh)
        discharge = max(0, discharge)
        discharge_used = discharge

        new_soc = soc - discharge / battery.discharge_efficiency
        grid_consumption = net - discharge
        grid_feed_in = 0.0

    else:
        # Stap 2: Eigen overschot → laden (ALTIJD, ongeacht prijs)
        surplus = abs(net)
        room = battery.max_soc_pct * battery.capacity_kwh - soc
        max_input = max(0, room) / battery.charge_efficiency if battery.charge_efficiency > 0 else 0
        charge = min(surplus, max_input, battery.max_charge_per_quarter_kwh)
        charge = max(0, charge)
        charge_used = charge

        new_soc = soc + charge * battery.charge_efficiency
        grid_consumption = 0.0
        grid_feed_in = surplus - charge

    # Stap 3+4: Arbitrage (alleen als spread groot genoeg is)
    if min_spread_ok:
        # Stap 4: Prijs hoog → extra ontladen en terugleveren
        if price >= high_threshold:
            extra_available_stored = new_soc - battery.min_soc_pct * battery.capacity_kwh
            extra_available_output = max(0, extra_available_stored) * battery.discharge_efficiency
            remaining_capacity = battery.max_discharge_per_quarter_kwh - discharge_used
            extra_discharge = min(extra_available_output, max(0, remaining_capacity))
            extra_discharge = max(0, extra_discharge)

            if extra_discharge > 0.001:
                new_soc = new_soc - extra_discharge / battery.discharge_efficiency
                grid_feed_in += extra_discharge

        # Stap 3: Prijs laag → bijkopen van net om batterij bij te vullen
        if price <= low_threshold:
            room = battery.max_soc_pct * battery.capacity_kwh - new_soc
            max_input = max(0, room) / battery.charge_efficiency if battery.charge_efficiency > 0 else 0
            remaining_charge = battery.max_charge_per_quarter_kwh - charge_used
            extra_buy = min(max_input, max(0, remaining_charge))
            extra_buy = max(0, extra_buy)

            if extra_buy > 0.001:
                new_soc = new_soc + extra_buy * battery.charge_efficiency
                grid_consumption += extra_buy
                grid_bought = extra_buy

    return new_soc, grid_consumption, grid_feed_in, grid_bought


# ============================================================
# 4b. SIMULATIE PER KWARTIER — STRATEGIE D (SLIM ZELFVERBRUIK)
# ============================================================

def _simulate_quarter_d(consumption, feed_in, soc, battery, price,
                        low_threshold, high_threshold):
    """
    Strategie D: Slim Zelfverbruik (prijsbewust, alleen eigen zon).

    Alleen eigen zon-energie wordt opgeslagen — GEEN bijkopen van net.
    Daardoor is opgeslagen energie BELASTINGVRIJ (geen EB/ODE/btw).

    Zon-overschot:
      - Prijs >= hoog → VERKOPEN aan net (goede prijs nu pakken)
      - Prijs < hoog  → OPSLAAN in batterij (bewaren voor dure uren)

    Eigen tekort:
      - Prijs >= hoog → ONTLADEN uit batterij (vermijd dure stroom + belasting)
      - Prijs < laag  → KOPEN van net (goedkoop), batterij bewaren voor later
      - Prijs normaal → ONTLADEN uit batterij (standaard zelfverbruik)

    Verschil met A: prijsbewust — bewaart batterij voor dure uren.
    Verschil met B/C: GEEN bijkopen van net → geen belasting op opgeslagen kWh.
    """
    net = consumption - feed_in
    grid_bought = 0.0  # altijd 0 bij D — we kopen nooit voor de batterij

    if net > 0:
        # Tekort: eigen verbruik hoger dan zonne-opbrengst
        if price <= low_threshold:
            # Prijs LAAG → kopen van net (goedkoop), batterij bewaren
            grid_consumption = net
            grid_feed_in = 0.0
            new_soc = soc
        else:
            # Prijs NORMAAL of HOOG → ontladen uit batterij
            available_stored = soc - battery.min_soc_pct * battery.capacity_kwh
            available_output = max(0, available_stored) * battery.discharge_efficiency
            discharge = min(net, available_output, battery.max_discharge_per_quarter_kwh)
            discharge = max(0, discharge)

            new_soc = soc - discharge / battery.discharge_efficiency
            grid_consumption = net - discharge
            grid_feed_in = 0.0

    else:
        # Overschot: zonne-opbrengst hoger dan verbruik
        surplus = abs(net)

        if price >= high_threshold:
            # Prijs HOOG → verkopen aan net (goede prijs pakken)
            grid_consumption = 0.0
            grid_feed_in = surplus
            new_soc = soc
        else:
            # Prijs NORMAAL of LAAG → opslaan in batterij
            room = battery.max_soc_pct * battery.capacity_kwh - soc
            max_input = max(0, room) / battery.charge_efficiency if battery.charge_efficiency > 0 else 0
            charge = min(surplus, max_input, battery.max_charge_per_quarter_kwh)
            charge = max(0, charge)

            new_soc = soc + charge * battery.charge_efficiency
            grid_consumption = 0.0
            grid_feed_in = surplus - charge

    return new_soc, grid_consumption, grid_feed_in, grid_bought


# ============================================================
# 5. VOLLEDIGE SIMULATIE OVER DATAFRAME
# ============================================================

def simulate_battery(meter_data, battery, prices=None, strategy='A', start_soc=None):
    """
    Simuleer batterijgedrag over een volledig DataFrame.

    Args:
        meter_data: DataFrame met timestamp_from, consumption_kwh, feed_in_kwh
        battery: BatteryConfig object
        prices: DataFrame met valid_from, price (vereist voor B en C)
        strategy: 'A' (zelfverbruik), 'B' (arbitrage), 'C' (hybride)
        start_soc: initiële SoC in kWh (default: minimum SoC)

    Returns:
        DataFrame met extra kolommen: soc, grid_consumption, grid_feed_in, grid_bought
    """
    strategy = strategy.upper()
    if strategy not in ('A', 'B', 'C', 'D'):
        raise ValueError(f"Onbekende strategie: {strategy}. Kies A, B, C of D.")

    if strategy in ('B', 'C', 'D') and prices is None:
        raise ValueError(f"Strategie {strategy} vereist prijsdata (prices parameter)")

    if meter_data.empty:
        return meter_data

    # Sorteer op tijd
    df = meter_data.sort_values('timestamp_from').reset_index(drop=True)

    # Prijzen mergen als nodig
    if strategy in ('B', 'C', 'D'):
        df = pd.merge(
            df,
            prices[['valid_from', 'price']],
            left_on='timestamp_from',
            right_on='valid_from',
            how='inner'
        )
        if df.empty:
            print(f"  Geen overlap tussen meterdata en prijzen!")
            return df

        # Dynamische drempels berekenen op basis van batterijcapaciteit
        thresholds, low_pct, high_pct = calculate_dynamic_thresholds(
            df[['timestamp_from', 'price']].rename(columns={'timestamp_from': 'valid_from'}),
            battery
        )
        print(f"  Dynamische drempels: laag P{low_pct:.1f} / hoog P{high_pct:.1f} "
              f"(laadtijd: {battery.usable_capacity_kwh / battery.max_charge_per_quarter_kwh:.0f} kwartieren, "
              f"ontlaadtijd: {battery.usable_capacity_kwh / battery.max_discharge_per_quarter_kwh:.0f} kwartieren)")

    # Start SoC
    if start_soc is None:
        start_soc = battery.min_soc_pct * battery.capacity_kwh

    # Arrays voor resultaten
    n = len(df)
    soc_arr = np.zeros(n)
    grid_cons_arr = np.zeros(n)
    grid_feed_arr = np.zeros(n)
    grid_bought_arr = np.zeros(n)

    soc = start_soc

    for i in range(n):
        cons = float(df.at[i, 'consumption_kwh'])
        feed = float(df.at[i, 'feed_in_kwh'])

        if strategy == 'A':
            soc, gc, gf, gb = _simulate_quarter_a(cons, feed, soc, battery)
        else:
            price = float(df.at[i, 'price'])
            date_key = df.at[i, 'timestamp_from']
            if hasattr(date_key, 'date'):
                date_key = date_key.date()
            thresh = thresholds.get(date_key, {'low': 0, 'high': 999, 'min_spread_ok': True})

            if strategy == 'B':
                soc, gc, gf, gb = _simulate_quarter_b(
                    cons, feed, soc, battery, price,
                    thresh['low'], thresh['high'], thresh['min_spread_ok']
                )
            elif strategy == 'C':
                soc, gc, gf, gb = _simulate_quarter_c(
                    cons, feed, soc, battery, price,
                    thresh['low'], thresh['high'], thresh['min_spread_ok']
                )
            else:  # D
                soc, gc, gf, gb = _simulate_quarter_d(
                    cons, feed, soc, battery, price,
                    thresh['low'], thresh['high']
                )

        soc_arr[i] = soc
        grid_cons_arr[i] = gc
        grid_feed_arr[i] = gf
        grid_bought_arr[i] = gb

    df['soc'] = soc_arr
    df['grid_consumption'] = grid_cons_arr
    df['grid_feed_in'] = grid_feed_arr
    df['grid_bought'] = grid_bought_arr

    return df


# ============================================================
# 6. SAMENVATTING
# ============================================================

def get_simulation_summary(df, battery, strategy='A'):
    """Bereken samenvatting van de simulatieresultaten."""
    if df.empty:
        return {}

    orig_consumption = df['consumption_kwh'].sum()
    orig_feed_in = df['feed_in_kwh'].sum()
    grid_consumption = df['grid_consumption'].sum()
    grid_feed_in = df['grid_feed_in'].sum()
    grid_bought = df['grid_bought'].sum() if 'grid_bought' in df.columns else 0

    return {
        'strategie': strategy,
        'kwartieren': len(df),
        'batterij': {
            'capaciteit_kwh': battery.capacity_kwh,
            'bruikbaar_kwh': battery.usable_capacity_kwh,
            'max_laden_kw': battery.max_charge_kw,
            'max_ontladen_kw': battery.max_discharge_kw,
        },
        'origineel': {
            'verbruik_kwh': round(orig_consumption, 1),
            'teruglevering_kwh': round(orig_feed_in, 1),
            'netto_kwh': round(orig_consumption - orig_feed_in, 1),
        },
        'met_batterij': {
            'grid_consumption_kwh': round(grid_consumption, 1),
            'grid_feed_in_kwh': round(grid_feed_in, 1),
            'netto_kwh': round(grid_consumption - grid_feed_in, 1),
            'bijgekocht_kwh': round(grid_bought, 1),
        },
        'besparing': {
            'minder_van_net_kwh': round(orig_consumption - grid_consumption + grid_bought, 1),
            'minder_teruggeleverd_kwh': round(orig_feed_in - grid_feed_in, 1),
            'eigenverbruik_pct': round(
                (1 - grid_feed_in / orig_feed_in) * 100 if orig_feed_in > 0 else 0, 1
            ),
        },
        'soc': {
            'gemiddeld_kwh': round(df['soc'].mean(), 2),
            'min_kwh': round(df['soc'].min(), 2),
            'max_kwh': round(df['soc'].max(), 2),
        },
    }


def print_simulation_summary(summary):
    """Print een leesbare samenvatting."""
    if not summary:
        print("Geen simulatieresultaten")
        return

    strategy_names = {'A': 'Zelfverbruik', 'B': 'Arbitrage', 'C': 'Hybride (A+B)', 'D': 'Slim Zelfverbruik'}
    strat = summary.get('strategie', '?')
    bat = summary['batterij']
    orig = summary['origineel']
    met = summary['met_batterij']
    besp = summary['besparing']
    soc = summary['soc']

    print(f"\n{'=' * 60}")
    print(f"  STRATEGIE {strat}: {strategy_names.get(strat, strat)}")
    print(f"{'=' * 60}")
    print(f"  Batterij: {bat['capaciteit_kwh']} kWh "
          f"(bruikbaar: {bat['bruikbaar_kwh']:.1f} kWh)")
    print(f"  Laden: {bat['max_laden_kw']} kW | "
          f"Ontladen: {bat['max_ontladen_kw']} kW")
    print(f"  Kwartieren: {summary['kwartieren']}")

    print(f"\n  --- Zonder batterij ---")
    print(f"  Verbruik:      {orig['verbruik_kwh']:8.1f} kWh")
    print(f"  Teruglevering: {orig['teruglevering_kwh']:8.1f} kWh")
    print(f"  Netto:         {orig['netto_kwh']:8.1f} kWh")

    print(f"\n  --- Met batterij ---")
    print(f"  Van net:       {met['grid_consumption_kwh']:8.1f} kWh")
    print(f"  Naar net:      {met['grid_feed_in_kwh']:8.1f} kWh")
    print(f"  Netto:         {met['netto_kwh']:8.1f} kWh")
    if met['bijgekocht_kwh'] > 0:
        print(f"  Bijgekocht:    {met['bijgekocht_kwh']:8.1f} kWh (arbitrage)")

    print(f"\n  --- Batterij-effect ---")
    print(f"  Minder van net:        {besp['minder_van_net_kwh']:8.1f} kWh")
    print(f"  Minder teruggeleverd:  {besp['minder_teruggeleverd_kwh']:8.1f} kWh")
    print(f"  Eigenverbruik zonne:   {besp['eigenverbruik_pct']:7.1f}%")

    print(f"\n  --- SoC ---")
    print(f"  Gem: {soc['gemiddeld_kwh']} kWh | "
          f"Min: {soc['min_kwh']} kWh | Max: {soc['max_kwh']} kWh")
    print(f"{'=' * 60}")


# ============================================================
# STANDALONE TEST
# ============================================================

def _fetch_all_meter_data(client, user_id, start_date, end_date):
    """Haal alle meterdata gepagineerd op."""
    all_records = []
    offset = 0
    while True:
        response = (
            client.table('meter_readings')
            .select('timestamp_from, consumption_kwh, feed_in_kwh')
            .eq('user_id', user_id)
            .gte('timestamp_from', f'{start_date}T00:00:00+00:00')
            .lte('timestamp_from', f'{end_date}T23:59:59+00:00')
            .order('timestamp_from')
            .range(offset, offset + 999)
            .execute()
        )
        all_records.extend(response.data)
        if len(response.data) < 1000:
            break
        offset += 1000
    return all_records


def run_unit_tests():
    """Unit tests met dummy data."""
    print(f"\n{'=' * 60}")
    print(f"  DEEL 1: UNIT TESTS")
    print(f"{'=' * 60}")

    battery = BatteryConfig(
        capacity_kwh=10, max_charge_kw=2.5, max_discharge_kw=3.68,
        charge_efficiency=0.95, discharge_efficiency=0.95,
        min_soc_pct=0.20, max_soc_pct=0.80,
    )

    print(f"\n  Batterij: {battery.capacity_kwh} kWh, "
          f"laden {battery.max_charge_kw} kW, "
          f"ontladen {battery.max_discharge_kw} kW")
    print(f"  Bruikbaar: {battery.usable_capacity_kwh:.1f} kWh")
    print(f"  Max laden/kwartier: {battery.max_charge_per_quarter_kwh:.3f} kWh")
    print(f"  Max ontladen/kwartier: {battery.max_discharge_per_quarter_kwh:.3f} kWh")

    soc_min = battery.min_soc_pct * battery.capacity_kwh

    # Test 1: Strategie A — batterij leeg, tekort → alles van net
    print(f"\n  Test 1 (A): Batterij leeg, tekort 0.5 kWh")
    soc, gc, gf, gb = _simulate_quarter_a(0.5, 0.0, soc_min, battery)
    assert gc == 0.5 and gf == 0.0 and gb == 0.0
    print(f"    Van net: {gc} ✅")

    # Test 2: Strategie A — overschot → laden
    print(f"\n  Test 2 (A): Overschot 1.0 kWh")
    soc, gc, gf, gb = _simulate_quarter_a(0.0, 1.0, soc_min, battery)
    assert gc == 0.0 and gb == 0.0
    print(f"    Geladen: {soc - soc_min:.3f} kWh, naar net: {gf:.3f} ✅")

    # Test 3: Strategie B — lage prijs → bijkopen (puur arbitrage)
    print(f"\n  Test 3 (B): Lage prijs, geen eigen verbruik → laden")
    soc, gc, gf, gb = _simulate_quarter_b(0.0, 0.0, soc_min, battery, 0.01, 0.05, 0.20, True)
    assert gb > 0, "Moet bijkopen bij lage prijs"
    print(f"    Bijgekocht: {gb:.3f} kWh, SoC: {soc:.3f} ✅")

    # Test 4: Strategie B — hoge prijs + volle batterij → terugleveren
    print(f"\n  Test 4 (B): Hoge prijs, batterij vol → ontladen en terugleveren")
    soc_vol = 7.0
    soc, gc, gf, gb = _simulate_quarter_b(0.0, 0.0, soc_vol, battery, 0.30, 0.05, 0.20, True)
    assert gf > 0, "Moet terugleveren bij hoge prijs"
    print(f"    Teruggeleverd: {gf:.3f} kWh, SoC: {soc:.3f} ✅")

    # Test 5: Strategie B — zon-overschot bij NORMALE prijs → NIET opslaan
    print(f"\n  Test 5 (B): Zon-overschot bij normale prijs → gaat naar net, niet batterij")
    soc_start = soc_min
    soc, gc, gf, gb = _simulate_quarter_b(0.0, 1.0, soc_start, battery, 0.12, 0.05, 0.20, True)
    assert soc == soc_start, "SoC mag niet veranderen bij normale prijs"
    assert gf == 1.0, "Alles moet naar net gaan"
    print(f"    SoC onveranderd: {soc:.3f}, naar net: {gf:.3f} ✅")

    # Test 6: Strategie B — tekort bij NORMALE prijs → kopen van net (niet uit batterij)
    print(f"\n  Test 6 (B): Tekort bij normale prijs → kopen van net, batterij doet niets")
    soc_start = 5.0
    soc, gc, gf, gb = _simulate_quarter_b(0.5, 0.0, soc_start, battery, 0.12, 0.05, 0.20, True)
    assert soc == soc_start, "SoC mag niet veranderen bij normale prijs"
    assert gc == 0.5, "Alles van net kopen"
    print(f"    SoC onveranderd: {soc:.3f}, van net: {gc:.3f} ✅")

    # Test 7: Strategie B — hoge prijs + eigen verbruik → eerst eigen dekken
    print(f"\n  Test 7 (B): Hoge prijs + verbruik 0.3 kWh → batterij dekt eigen + surplus naar net")
    soc_start = 5.0
    soc, gc, gf, gb = _simulate_quarter_b(0.3, 0.0, soc_start, battery, 0.30, 0.05, 0.20, True)
    assert gc < 0.3, "Eigen verbruik moet (deels) uit batterij"
    assert gf > 0, "Overschot moet naar net"
    print(f"    Van net: {gc:.3f}, teruggeleverd: {gf:.3f} ✅")

    # Test 8: Strategie B — min_spread_ok=False → batterij doet niets
    print(f"\n  Test 8 (B): Spread te klein → batterij doet niets")
    soc_start = 5.0
    soc, gc, gf, gb = _simulate_quarter_b(0.3, 0.0, soc_start, battery, 0.01, 0.05, 0.20, False)
    assert soc == soc_start, "SoC mag niet veranderen als spread te klein"
    assert gc == 0.3, "Alles van net"
    print(f"    SoC onveranderd: {soc:.3f} ✅")

    # Test 9: Strategie C — eigen verbruik VOOR arbitrage
    print(f"\n  Test 9 (C): Overschot + lage prijs → eerst opslaan, dan bijkopen")
    soc, gc, gf, gb = _simulate_quarter_c(0.0, 0.8, soc_min, battery, 0.01, 0.05, 0.20, True)
    assert gf < 0.8, "Overschot moet (deels) geladen worden"
    print(f"    Overschot geladen, bijgekocht: {gb:.3f} kWh, naar net: {gf:.3f} ✅")

    # Test 10: Strategie C — tekort + hoge prijs → eigen verbruik + extra terugleveren
    print(f"\n  Test 10 (C): Tekort 0.3 + hoge prijs, batterij halfvol")
    soc, gc, gf, gb = _simulate_quarter_c(0.3, 0.0, 5.0, battery, 0.30, 0.05, 0.20, True)
    assert gc == 0.0, "Eigen tekort moet uit batterij"
    assert gf > 0, "Extra terugleveren bij hoge prijs"
    print(f"    Uit batterij, extra teruggeleverd: {gf:.3f} kWh ✅")

    # Test 11: Strategie C — zon-overschot bij normale prijs → WEL opslaan (verschil met B!)
    print(f"\n  Test 11 (C): Zon-overschot bij normale prijs → opslaan in batterij (≠ B)")
    soc_start = soc_min
    soc, gc, gf, gb = _simulate_quarter_c(0.0, 1.0, soc_start, battery, 0.12, 0.05, 0.20, True)
    assert soc > soc_start, "SoC moet stijgen — zon-overschot wordt opgeslagen"
    assert gf < 1.0, "Niet alles naar net — deel opgeslagen"
    print(f"    SoC: {soc_start:.3f} → {soc:.3f}, naar net: {gf:.3f} ✅ (verschil met B!)")

    # Test 12: Strategie D — zon-overschot bij HOGE prijs → verkopen, niet opslaan
    print(f"\n  Test 12 (D): Zon-overschot bij hoge prijs → verkopen aan net")
    soc_start = soc_min
    soc, gc, gf, gb = _simulate_quarter_d(0.0, 1.0, soc_start, battery, 0.30, 0.05, 0.20)
    assert soc == soc_start, "SoC mag niet veranderen — verkoop nu tegen hoge prijs"
    assert gf == 1.0, "Alles naar net bij hoge prijs"
    assert gb == 0.0, "D koopt nooit bij"
    print(f"    SoC onveranderd: {soc:.3f}, verkocht: {gf:.3f} ✅")

    # Test 13: Strategie D — zon-overschot bij LAGE prijs → opslaan
    print(f"\n  Test 13 (D): Zon-overschot bij lage prijs → opslaan in batterij")
    soc, gc, gf, gb = _simulate_quarter_d(0.0, 1.0, soc_min, battery, 0.02, 0.05, 0.20)
    assert soc > soc_min, "SoC moet stijgen — opslaan bij lage prijs"
    assert gf < 1.0, "Deel opgeslagen"
    assert gb == 0.0, "D koopt nooit bij"
    print(f"    SoC: {soc_min:.3f} → {soc:.3f}, naar net: {gf:.3f} ✅")

    # Test 14: Strategie D — tekort bij HOGE prijs → ontladen (vermijd dure stroom)
    print(f"\n  Test 14 (D): Tekort bij hoge prijs → ontladen uit batterij")
    soc_start = 5.0
    soc, gc, gf, gb = _simulate_quarter_d(0.3, 0.0, soc_start, battery, 0.30, 0.05, 0.20)
    assert gc == 0.0, "Tekort uit batterij, niet van net"
    assert gb == 0.0, "D koopt nooit bij"
    print(f"    SoC: {soc_start:.3f} → {soc:.3f}, van net: {gc:.3f} ✅")

    # Test 15: Strategie D — tekort bij LAGE prijs → kopen van net, batterij bewaren
    print(f"\n  Test 15 (D): Tekort bij lage prijs → kopen van net, batterij bewaren")
    soc_start = 5.0
    soc, gc, gf, gb = _simulate_quarter_d(0.5, 0.0, soc_start, battery, 0.02, 0.05, 0.20)
    assert soc == soc_start, "SoC onveranderd — batterij bewaren voor later"
    assert gc == 0.5, "Alles van net kopen (goedkoop)"
    assert gb == 0.0, "D koopt nooit bij"
    print(f"    SoC onveranderd: {soc:.3f}, van net: {gc:.3f} ✅ (batterij bewaard!)")

    # Test 16: Strategie D — tekort bij NORMALE prijs → ontladen (standaard zelfverbruik)
    print(f"\n  Test 16 (D): Tekort bij normale prijs → ontladen (als A)")
    soc_start = 5.0
    soc, gc, gf, gb = _simulate_quarter_d(0.3, 0.0, soc_start, battery, 0.12, 0.05, 0.20)
    assert gc == 0.0, "Tekort uit batterij bij normale prijs"
    print(f"    SoC: {soc_start:.3f} → {soc:.3f}, van net: {gc:.3f} ✅")

    # Test 17: DataFrame simulatie alle strategieën
    print(f"\n  Test 17: DataFrame met alle strategieën")
    dummy = pd.DataFrame({
        'timestamp_from': pd.to_datetime([
            '2025-06-15 10:00:00+00:00', '2025-06-15 10:15:00+00:00',
            '2025-06-15 10:30:00+00:00', '2025-06-15 10:45:00+00:00',
        ]),
        'consumption_kwh': [0.3, 0.1, 0.0, 0.5],
        'feed_in_kwh':     [0.0, 0.5, 1.0, 0.0],
    })
    dummy_prices = pd.DataFrame({
        'valid_from': pd.to_datetime([
            '2025-06-15 10:00:00+00:00', '2025-06-15 10:15:00+00:00',
            '2025-06-15 10:30:00+00:00', '2025-06-15 10:45:00+00:00',
        ]),
        'price': [0.05, 0.10, 0.02, 0.35],  # goedkoop-normaal-goedkoop-duur
    })

    for strat in ['A', 'B', 'C', 'D']:
        if strat == 'A':
            res = simulate_battery(dummy.copy(), battery, strategy='A')
        else:
            res = simulate_battery(dummy.copy(), battery, prices=dummy_prices, strategy=strat)
        assert (res['grid_consumption'] >= -0.001).all()
        assert (res['grid_feed_in'] >= -0.001).all()
        assert (res['soc'] >= battery.min_soc_pct * battery.capacity_kwh - 0.01).all()
        assert (res['soc'] <= battery.max_soc_pct * battery.capacity_kwh + 0.01).all()
        bought = res['grid_bought'].sum()
        print(f"    Strategie {strat}: grid_c={res['grid_consumption'].sum():.3f}, "
              f"grid_f={res['grid_feed_in'].sum():.3f}, "
              f"bijgekocht={bought:.3f} ✅")

    print(f"\n  ✅ Alle unit tests geslaagd!")


def run_integration_test():
    """Integratietest met echte data — alle 3 strategieën vergelijken."""
    from simulation_config import SimulationConfig
    from reference_data import reconstruct_historical_prices, get_net_prices
    from cost_calculator import calculate_costs_no_battery, calculate_costs_with_battery, calculate_savings_summary
    from cost_calculator import get_malus_for_date, calculate_feed_in_price
    from db_connection import get_client

    print(f"\n{'=' * 60}")
    print(f"  DEEL 2: INTEGRATIETEST — ALLE STRATEGIEEN VERGELIJKEN")
    print(f"{'=' * 60}")

    config = SimulationConfig.from_json("config.json")
    print(f"\n  Config: user={config.user_id[:8]}...")
    print(f"  Periode: {config.simulation.start_date} t/m {config.simulation.end_date}")
    print(f"  Batterij: {config.battery.capacity_kwh} kWh")

    # Meterdata ophalen
    client = get_client()
    records = _fetch_all_meter_data(
        client, config.user_id,
        config.simulation.start_date, config.simulation.end_date
    )
    if not records:
        print("  Geen meterdata gevonden!")
        return

    meter = pd.DataFrame(records)
    meter['timestamp_from'] = pd.to_datetime(meter['timestamp_from'], utc=True)
    meter['consumption_kwh'] = meter['consumption_kwh'].astype(float)
    meter['feed_in_kwh'] = meter['feed_in_kwh'].astype(float)
    print(f"  {len(meter)} kwartieren geladen")

    # Nettoprijzen ophalen (kale beursprijs — voor terugleverprijs)
    net_prices_df = get_net_prices(config.simulation.start_date, config.simulation.end_date)
    print(f"  Nettoprijzen: {len(net_prices_df)} records (gem: EUR {net_prices_df['price'].mean():.4f}/kWh)")

    # Prijzen ophalen (we gebruiken BE als voorbeeld)
    provider = 'BE'
    prices = reconstruct_historical_prices(
        provider, config.simulation.start_date, config.simulation.end_date
    )
    print(f"  All-in prijzen {provider}: {len(prices)} records (gem: EUR {prices['price'].mean():.4f}/kWh)")
    print(f"  Verschil (EB+ODE+btw+opslag): ~EUR {prices['price'].mean() - net_prices_df['price'].mean():.4f}/kWh")

    # Kosten zonder batterij
    costs_no_bat = calculate_costs_no_battery(meter, prices, provider, net_prices=net_prices_df)
    summary_no_bat = calculate_savings_summary(costs_no_bat)
    print(f"\n  Kosten ZONDER batterij ({provider}): EUR {summary_no_bat['total_cost_no_battery']:.2f}")
    print(f"  (afname=all-in, teruglevering=beursprijs−malus)")

    # Alle 3 strategieën simuleren
    print(f"\n  Simulatie draaien voor strategie A, B, C en D...")
    for strat in ['A', 'B', 'C', 'D']:
        if strat == 'A':
            sim_result = simulate_battery(meter.copy(), config.battery, strategy='A')
            # Voor A: handmatig prijzen mergen voor kostenberekening
            sim_result = pd.merge(
                sim_result, prices[['valid_from', 'price']],
                left_on='timestamp_from', right_on='valid_from', how='inner'
            )
        else:
            sim_result = simulate_battery(
                meter.copy(), config.battery, prices=prices, strategy=strat
            )

        # Nettoprijzen mergen voor terugleverprijs
        sim_result = pd.merge(
            sim_result,
            net_prices_df[['valid_from', 'price']].rename(columns={'price': 'net_price'}),
            left_on='timestamp_from',
            right_on='valid_from',
            how='left',
            suffixes=('', '_net_merge')
        )
        sim_result['net_price'] = sim_result['net_price'].fillna(sim_result['price'])
        # Opruimen dubbele valid_from kolommen
        for col in sim_result.columns:
            if col.endswith('_net_merge'):
                sim_result.drop(columns=[col], inplace=True, errors='ignore')

        # Kosten berekenen (gevectoriseerd)
        malus_info = get_malus_for_date(provider, config.simulation.start_date)
        # Terugleverprijs = nettoprijzen − malus (NIET all-in prijs!)
        fi_price = (sim_result['net_price'] - malus_info['malus']).clip(lower=0)

        sim_result['cost_no_battery'] = (
            sim_result['consumption_kwh'] * sim_result['price']
            - sim_result['feed_in_kwh'] * fi_price
        )
        sim_result['cost_with_battery'] = (
            sim_result['grid_consumption'] * sim_result['price']
            - sim_result['grid_feed_in'] * fi_price
        )
        cost_summary = calculate_savings_summary(sim_result)

        # Simulatie samenvatting
        sim_summary = get_simulation_summary(sim_result, config.battery, strat)
        print_simulation_summary(sim_summary)

        print(f"  Kosten {provider}:")
        print(f"    Zonder batterij: EUR {cost_summary['total_cost_no_battery']:.2f}")
        print(f"    Met batterij:    EUR {cost_summary['total_cost_with_battery']:.2f}")
        print(f"    Besparing:       EUR {cost_summary['total_savings']:.2f} "
              f"({cost_summary['savings_percentage']}%)")

    print(f"\n  ✅ Integratietest voltooid!")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    import sys

    if "--skip-unit" in sys.argv:
        run_integration_test()
    elif "--skip-integration" in sys.argv:
        run_unit_tests()
    else:
        run_unit_tests()
        run_integration_test()
