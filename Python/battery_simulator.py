"""
battery_simulator.py - Batterijsimulatie per kwartier voor Energy-Truth.

Vier laadstrategieen:
  A. Zelfverbruik       - overschot opslaan, tekort uit batterij dekken (geen prijsinfo)
  B. Arbitrage          - puur prijsgestuurd, batterij ONAFHANKELIJK van huishouden
  C. Hybride (A+B)      - eigen verbruik ALTIJD voor, daarna slim bij-/verkopen van net
  D. Slim Zelfverbruik  - alleen eigen zon, maar PRIJSBEWUST opslaan/ontladen

Strategie B (puur arbitrage):
  - Huishouden -> altijd via net (geen zelfverbruik-optimalisatie)
  - Lage prijs -> kopen van net en batterij laden
  - Hoge prijs -> ontladen: eerst eigen verbruik dekken, overschot naar net
  - Normaal -> batterij doet niets
  - Zon-overschot -> altijd naar net (niet opgeslagen)

Strategie C (hybride):
  Stap 1: eigen overschot -> batterij laden / eigen tekort -> batterij ontladen
  Stap 2: prijs laag + nog ruimte in batterij -> bijkopen van net
  Stap 3: prijs hoog + nog energie in batterij -> extra ontladen en terugleveren

Strategie D (slim zelfverbruik):
  Alleen eigen zon-energie, GEEN bijkopen van net -> opgeslagen kWh is BELASTINGVRIJ.
  Zon-overschot:
    - Prijs HOOG -> verkopen aan net (goede prijs pakken)
    - Prijs normaal/laag -> opslaan in batterij (bewaren voor dure uren)
  Eigen tekort:
    - Prijs HOOG -> ontladen uit batterij (vermijd dure stroom + belasting kopen)
    - Prijs LAAG -> kopen van net (goedkoop, zelfs met belasting), batterij bewaren

  Belastingvoordeel: elke kWh uit eigen zon die je zelf verbruikt bespaart de volle
  all-in prijs (incl. EB+ODE+btw), terwijl verkopen alleen de beursprijs oplevert.

Dynamische drempels:
  - Laaddrempel = percentiel gebaseerd op laadtijd (capacity / charge_rate)
  - Ontlaaddrempel = percentiel gebaseerd op ontlaadtijd (capacity / discharge_rate)
  - Minimum spread check: arbitrage alleen als spread > round-trip efficientieverlies

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
        -> hoeveel goedkope kwartieren heb je nodig om vol te laden?
      - discharge_quarters = bruikbare capaciteit / ontladen per kwartier
        -> hoeveel dure kwartieren heb je nodig om leeg te ontladen?
      - low_pct = charge_quarters / 96 * 100
      - high_pct = 100 - discharge_quarters / 96 * 100
      - min_spread_ok: alleen arbitrage als spread > round-trip verlies

    Voorbeeld (10 kWh, 20-80%, 2.5 kW laden, 3.68 kW ontladen):
      bruikbaar = 6.0 kWh
      charge_quarters = 6.0 / 0.594 ~ 10 -> low_pct ~ 10.4%
      discharge_quarters = 6.0 / 0.874 ~ 7 -> high_pct ~ 92.8%

    Args:
        prices_df: DataFrame met valid_from en price
        battery: BatteryConfig object

    Returns:
        tuple: (thresholds_dict, low_pct, high_pct)
        thresholds_dict: date -> {'low': float, 'high': float, 'min_spread_ok': bool}
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
        # high_price > low_price / round_trip_eff  ->  spread > ~10.8%
        if low > 0:
            min_spread_ok = high > low / round_trip_eff
        else:
            min_spread_ok = high > 0  # negatieve/gratis stroom -> altijd laden

        thresholds[date] = {
            'low': low,
            'high': high,
            'min_spread_ok': min_spread_ok,
        }

    return thresholds, low_pct, high_pct


# ============================================================
# 2. SIMULATIE PER KWARTIER - STRATEGIE A (ZELFVERBRUIK)
# ============================================================

def _simulate_quarter_a(consumption, feed_in, soc, battery):
    """
    Strategie A: Zelfverbruik.
    Overschot -> laden, tekort -> ontladen. Geen prijsinformatie nodig.
    """
    net = consumption - feed_in

    if net > 0:
        # Tekort -> ontladen
        available_stored = soc - battery.min_soc_pct * battery.capacity_kwh
        # Correctie: beschikbare OUTPUT rekening houdend met efficientieverlies
        available_output = max(0, available_stored) * battery.discharge_efficiency
        discharge = min(net, available_output, battery.max_discharge_per_quarter_kwh)
        discharge = max(0, discharge)

        new_soc = soc - discharge / battery.discharge_efficiency
        grid_consumption = net - discharge
        grid_feed_in = 0.0
        grid_bought = 0.0
    else:
        # Overschot -> laden
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
# 3. SIMULATIE PER KWARTIER - STRATEGIE B (PUUR ARBITRAGE)
# ============================================================

def _simulate_quarter_b(consumption, feed_in, soc, battery, price,
                        low_threshold, high_threshold, min_spread_ok):
    """
    Strategie B: Puur prijsarbitrage.

    De batterij opereert ONAFHANKELIJK van het huishouden.
    Het huishouden gaat standaard volledig via het net:
      - Verbruik -> kopen van net
      - Zon-overschot -> terugleveren aan net (NIET opslaan)

    De batterij reageert alleen op prijs:
      - Lage prijs -> kopen van net en laden
      - Hoge prijs -> ontladen: eerst eigen verbruik dekken (bespaart dure
        stroom), overschot terugleveren aan net
      - Normale prijs -> batterij doet niets
      - Geen spread -> batterij doet niets (min_spread_ok=False)

    Dit is fundamenteel anders dan C: zon-overschot wordt NIET opgeslagen,
    en bij normale prijzen wordt het eigen tekort NIET uit de batterij gedekt.
    """
    # Huishouden gaat standaard volledig via net
    grid_consumption = consumption
    grid_feed_in = feed_in
    grid_bought = 0.0
    new_soc = soc

    if not min_spread_ok:
        # Spread te klein voor winstgevende arbitrage -> batterij doet niets
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

    # Normale prijs -> batterij doet NIETS

    return new_soc, grid_consumption, grid_feed_in, grid_bought


# ============================================================
# 4. SIMULATIE PER KWARTIER - STRATEGIE C (HYBRIDE)
# ============================================================

def _simulate_quarter_c(consumption, feed_in, soc, battery, price,
                        low_threshold, high_threshold, min_spread_ok):
    """
    Strategie C: Hybride (eigen verbruik + arbitrage).

    Prioriteit:
      1. Eigen verbruik gaat ALTIJD voor (tekort -> ontladen uit batterij)
      2. Eigen overschot -> batterij laden
      3. Prijs laag + nog ruimte -> bijkopen van net (alleen als spread OK)
      4. Prijs hoog + nog energie -> extra ontladen en terugleveren (alleen als spread OK)

    Het verschil met B: eigen verbruik wordt ALTIJD geoptimaliseerd, ook bij
    normale prijzen. Zon-overschot wordt altijd eerst opgeslagen.
    Arbitrage is een BONUS bovenop eigen verbruik.
    """
    net = consumption - feed_in
    grid_bought = 0.0
    discharge_used = 0.0
    charge_used = 0.0

    if net > 0:
        # Stap 1: Eigen tekort -> ontladen uit batterij (ALTIJD, ongeacht prijs)
        available_stored = soc - battery.min_soc_pct * battery.capacity_kwh
        available_output = max(0, available_stored) * battery.discharge_efficiency
        discharge = min(net, available_output, battery.max_discharge_per_quarter_kwh)
        discharge = max(0, discharge)
        discharge_used = discharge

        new_soc = soc - discharge / battery.discharge_efficiency
        grid_consumption = net - discharge
        grid_feed_in = 0.0

    else:
        # Stap 2: Eigen overschot -> laden (ALTIJD, ongeacht prijs)
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
        # Stap 4: Prijs hoog -> extra ontladen en terugleveren
        if price >= high_threshold:
            extra_available_stored = new_soc - battery.min_soc_pct * battery.capacity_kwh
            extra_available_output = max(0, extra_available_stored) * battery.discharge_efficiency
            remaining_capacity = battery.max_discharge_per_quarter_kwh - discharge_used
            extra_discharge = min(extra_available_output, max(0, remaining_capacity))
            extra_discharge = max(0, extra_discharge)

            if extra_discharge > 0.001:
                new_soc = new_soc - extra_discharge / battery.discharge_efficiency
                grid_feed_in += extra_discharge

        # Stap 3: Prijs laag -> bijkopen van net om batterij bij te vullen
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
# 4b. SIMULATIE PER KWARTIER - STRATEGIE D (SLIM ZELFVERBRUIK)
# ============================================================

def _simulate_quarter_d(consumption, feed_in, soc, battery, price,
                        low_threshold, high_threshold):
    """
    Strategie D: Slim Zelfverbruik (prijsbewust, alleen eigen zon).

    Alleen eigen zon-energie wordt opgeslagen - GEEN bijkopen van net.
    Daardoor is opgeslagen energie BELASTINGVRIJ (geen EB/ODE/btw).

    Zon-overschot:
      - Prijs >= hoog -> VERKOPEN aan net (goede prijs nu pakken)
      - Prijs < hoog  -> OPSLAAN in batterij (bewaren voor dure uren)

    Eigen tekort:
      - Prijs >= hoog -> ONTLADEN uit batterij (vermijd dure stroom + belasting)
      - Prijs < laag  -> KOPEN van net (goedkoop), batterij bewaren voor later
      - Prijs normaal -> ONTLADEN uit batterij (standaard zelfverbruik)

    Verschil met A: prijsbewust - bewaart batterij voor dure uren.
    Verschil met B/C: GEEN bijkopen van net -> geen belasting op opgeslagen kWh.
    """
    net = consumption - feed_in
    grid_bought = 0.0  # altijd 0 bij D - we kopen nooit voor de batterij

    if net > 0:
        # Tekort: eigen verbruik hoger dan zonne-opbrengst
        if price <= low_threshold:
            # Prijs LAAG -> kopen van net (goedkoop), batterij bewaren
            grid_consumption = net
            grid_feed_in = 0.0
            new_soc = soc
        else:
            # Prijs NORMAAL of HOOG -> ontladen uit batterij
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
            # Prijs HOOG -> verkopen aan net (goede prijs pakken)
            grid_consumption = 0.0
            grid_feed_in = surplus
            new_soc = soc
        else:
            # Prijs NORMAAL of LAAG -> opslaan in batterij
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
        start_soc: initiele SoC in kWh (default: minimum SoC)

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

    # Kolommen een keer naar numpy-arrays trekken. Per-cel toegang via
    # df.at[i, ...] is in pandas erg traag, en deze lus draait ~11.000 keer
    # per scenario, dus dat tikt hard aan. De simulatie blijft sequentieel
    # (de SoC van elk kwartier hangt af van het vorige), maar de overhead per
    # stap verdwijnt. De uitkomst is identiek aan de oude df.at-versie.
    cons_in = df['consumption_kwh'].to_numpy(dtype=float)
    feed_in = df['feed_in_kwh'].to_numpy(dtype=float)

    if strategy == 'A':
        for i in range(n):
            soc, gc, gf, gb = _simulate_quarter_a(cons_in[i], feed_in[i], soc, battery)
            soc_arr[i] = soc
            grid_cons_arr[i] = gc
            grid_feed_arr[i] = gf
            grid_bought_arr[i] = gb
    else:
        price_in = df['price'].to_numpy(dtype=float)
        # Datum per kwartier een keer vooraf bepalen i.p.v. .date() per stap.
        date_keys = df['timestamp_from'].dt.date.to_numpy()
        _default_thresh = {'low': 0, 'high': 999, 'min_spread_ok': True}
        for i in range(n):
            thresh = thresholds.get(date_keys[i], _default_thresh)
            if strategy == 'B':
                soc, gc, gf, gb = _simulate_quarter_b(
                    cons_in[i], feed_in[i], soc, battery, price_in[i],
                    thresh['low'], thresh['high'], thresh['min_spread_ok']
                )
            elif strategy == 'C':
                soc, gc, gf, gb = _simulate_quarter_c(
                    cons_in[i], feed_in[i], soc, battery, price_in[i],
                    thresh['low'], thresh['high'], thresh['min_spread_ok']
                )
            else:  # D
                soc, gc, gf, gb = _simulate_quarter_d(
                    cons_in[i], feed_in[i], soc, battery, price_in[i],
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
