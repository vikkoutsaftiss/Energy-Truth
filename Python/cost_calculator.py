"""
cost_calculator.py - Kostenberekening per kwartier voor Energy-Truth.

Berekent energiekosten per 15-minuten interval, zowel zonder als met batterij.

Prijsmodel:
  - Afname (kopen):           all-in prijs (beursprijs + EB + ODE + btw + opslag)
  - Teruglevering (verkopen): kale beursprijs (nettoprijzen)
  - Je krijgt energiebelasting, ODE en btw NIET terug bij teruglevering!

Een leverancier-specifieke teruglever-malus is bewust NIET gemodelleerd; zie de
hook in calculate_feed_in_price als dat ooit nodig wordt.

Gebruik:
    from cost_calculator import calculate_costs_no_battery, calculate_costs_with_battery
"""

import pandas as pd

# ============================================================
# FEED-IN PRIJS BEREKENEN
# ============================================================

def calculate_feed_in_price(net_price):
    """
    Terugleverprijs = de kale beursprijs (nettoprijzen), afgekapt op >= 0.

    Bij teruglevering krijg je energiebelasting, ODE en btw NIET terug, dus we
    rekenen met de kale beursprijs, niet de all-in consumentenprijs.

    Een leverancier-specifieke teruglever-malus is bewust NIET gemodelleerd
    (niet voorzien in het datamodel). Mocht dat ooit nodig worden (bijv. na het
    wegvallen van de saldering), dan is dit de plek: trek de malus hier van
    net_price af.

    Args:
        net_price: kale beursprijs / nettoprijzen (EUR/kWh), EXCL belastingen

    Returns:
        feed_in_price (EUR/kWh), minimaal 0
    """
    return max(0.0, net_price)


# ============================================================
# 3. KOSTEN ZONDER BATTERIJ
# ============================================================

def calculate_costs_no_battery(meter_data, prices, provider_code, net_prices=None):
    """
    Bereken energiekosten per kwartier ZONDER batterij.

    Formule: kosten = verbruik * all-in prijs - teruglevering * terugleverprijs
    Terugleverprijs = kale beursprijs (nettoprijzen)

    Args:
        meter_data: DataFrame met timestamp_from, consumption_kwh, feed_in_kwh
        prices: DataFrame met valid_from, price (all-in aanbiederprijzen)
        provider_code: bijv. 'ANWB'
        net_prices: DataFrame met valid_from, price (kale beursprijzen).
                    Als None: gebruikt all-in prijs voor teruglevering (legacy, te hoog!)

    Returns:
        DataFrame met extra kolommen: price, net_price, feed_in_price, cost_no_battery
    """
    # Merge meterdata met all-in prijzen op timestamp
    merged = pd.merge(
        meter_data,
        prices[['valid_from', 'price']],
        left_on='timestamp_from',
        right_on='valid_from',
        how='inner'
    )

    if merged.empty:
        print(f"Let op: geen overlap tussen meterdata en prijzen voor {provider_code}")
        return merged

    # Nettoprijzen mergen (voor terugleverprijs)
    if net_prices is not None:
        merged = pd.merge(
            merged,
            net_prices[['valid_from', 'price']].rename(columns={'price': 'net_price'}),
            left_on='timestamp_from',
            right_on='valid_from',
            how='left',
            suffixes=('', '_net')
        )
        # Waar geen nettoprijzen: terugvallen op all-in (beter dan NaN)
        merged['net_price'] = merged['net_price'].fillna(merged['price'])
        # Opruimen dubbele valid_from kolommen
        for col in merged.columns:
            if col.endswith('_net'):
                merged.drop(columns=[col], inplace=True, errors='ignore')
    else:
        # Legacy: geen nettoprijzen meegegeven -> all-in prijs als terugval
        merged['net_price'] = merged['price']

    # Terugleverprijs = kale beursprijs (geen teruglever-malus gemodelleerd).
    # Hook: een eventuele leverancier-malus zou hier op net_price toegepast worden.
    # Gevectoriseerd (geen iterrows): scheelt fors over ~tienduizenden rijen.
    merged['feed_in_price'] = merged['net_price'].clip(lower=0)

    # Kosten = verbruik * all-in prijs - teruglevering * terugleverprijs
    merged['cost_no_battery'] = (
        merged['consumption_kwh'] * merged['price']
        - merged['feed_in_kwh'] * merged['feed_in_price']
    )

    return merged


# ============================================================
# 4. KOSTEN MET BATTERIJ
# ============================================================

def calculate_costs_with_battery(simulated_data, provider_code, net_prices=None):
    """
    Bereken energiekosten per kwartier MET batterij.

    Verwacht dat battery_simulator al grid_consumption en grid_feed_in
    heeft berekend. Deze functie voegt alleen de kostenkolom toe.

    Formule: kosten = grid_consumption * all-in prijs - grid_feed_in * terugleverprijs
    Terugleverprijs = kale beursprijs (nettoprijzen)

    Args:
        simulated_data: DataFrame met timestamp_from, price,
                        grid_consumption, grid_feed_in
        provider_code: bijv. 'ANWB'
        net_prices: DataFrame met valid_from, price (kale beursprijzen).
                    Als None: gebruikt all-in prijs voor teruglevering (legacy)

    Returns:
        DataFrame met extra kolommen: net_price, feed_in_price_battery, cost_with_battery
    """
    if simulated_data.empty:
        return simulated_data

    # Nettoprijzen mergen als beschikbaar
    if net_prices is not None and 'net_price' not in simulated_data.columns:
        simulated_data = pd.merge(
            simulated_data,
            net_prices[['valid_from', 'price']].rename(columns={'price': 'net_price'}),
            left_on='timestamp_from',
            right_on='valid_from',
            how='left',
            suffixes=('', '_net')
        )
        simulated_data['net_price'] = simulated_data['net_price'].fillna(simulated_data['price'])
        for col in simulated_data.columns:
            if col.endswith('_net'):
                simulated_data.drop(columns=[col], inplace=True, errors='ignore')
    elif 'net_price' not in simulated_data.columns:
        simulated_data['net_price'] = simulated_data['price']

    # Terugleverprijs = kale beursprijs (geen teruglever-malus). Gevectoriseerd.
    simulated_data['feed_in_price_battery'] = simulated_data['net_price'].clip(lower=0)

    # Kosten = netverbruik * all-in prijs - netto-teruglevering * terugleverprijs
    simulated_data['cost_with_battery'] = (
        simulated_data['grid_consumption'] * simulated_data['price']
        - simulated_data['grid_feed_in'] * simulated_data['feed_in_price_battery']
    )

    return simulated_data


# ============================================================
# 5. SEIZOENSGEWOGEN JAARPROJECTIE
# ============================================================

# Seizoenen (consistent met data_quality.py)
SEASONS = {
    'winter': {12, 1, 2},
    'lente':  {3, 4, 5},
    'zomer':  {6, 7, 8},
    'herfst': {9, 10, 11},
}
DAYS_PER_SEASON = 365.25 / 4  # 91,3125 dagen per seizoen


def _month_to_season(month):
    """Map maandnummer (1-12) naar seizoen-naam."""
    for naam, maanden in SEASONS.items():
        if month in maanden:
            return naam
    return None


def annualize_costs_seasonal(costs_df, cost_columns=None):
    """
    Projecteert kosten naar een vol jaar via seizoensgewogen schatting.

    AANPAK
    ------
    Per aanwezig seizoen: gemiddelde kost per dag * 91,3 dagen.
    Voor ontbrekende seizoenen: opvullen met het overall gemiddelde per dag
    over alle aanwezige data * 91,3 dagen. Deze opgevulde seizoenen worden
    geflagd als 'is_estimated': True.

    Hierdoor krijgt de klant altijd een jaarschatting die hij kan interpreteren,
    ook bij gedeeltelijke meterdata. De betrouwbaarheidsscore zorgt voor de
    waarschuwing dat de schatting minder hard is (zie data_quality.py).

    Args:
        costs_df: DataFrame met timestamp_from en kostkolommen.
        cost_columns: kolommen om te annualiseren. Default:
                      ['cost_no_battery', 'cost_with_battery'] als aanwezig.

    Returns:
        dict met:
          - 'totals_annualized':   {kolom: euro op jaarbasis (incl. opvulling)}
          - 'per_season':          {seizoen: {'days_present', 'is_estimated',
                                              'cost_per_day_*', 'annualized_*'}}
          - 'seasons_present':     seizoenen met eigen data
          - 'seasons_estimated':   seizoenen opgevuld via overall gemiddelde
          - 'year_coverage':       fractie (0..1) van vol jaar met eigen data
          - 'days_in_data':        totaal aantal unieke dagen met data
    """
    empty_result = {
        'totals_annualized': {},
        'per_season': {},
        'seasons_present': [],
        'seasons_estimated': list(SEASONS.keys()),
        'year_coverage': 0.0,
        'days_in_data': 0,
    }

    if costs_df.empty or 'timestamp_from' not in costs_df.columns:
        return empty_result

    if cost_columns is None:
        cost_columns = [c for c in ('cost_no_battery', 'cost_with_battery')
                        if c in costs_df.columns]
    if not cost_columns:
        return empty_result

    df = costs_df.copy()
    df['__date'] = df['timestamp_from'].dt.date
    df['__season'] = df['timestamp_from'].dt.month.map(_month_to_season)

    # Per dag aggregeren - robuust tegen ontbrekende kwartieren binnen een dag
    agg_dict = {col: 'sum' for col in cost_columns}
    daily = df.groupby(['__season', '__date']).agg(agg_dict).reset_index()

    if daily.empty:
        return empty_result

    # Overall gemiddelde per dag over alle aanwezige data (voor opvulling)
    overall_avg_per_day = {col: daily[col].mean() for col in cost_columns}
    total_days_data = int(daily['__date'].nunique())

    per_season = {}
    totals_annualized = {col: 0.0 for col in cost_columns}
    seasons_present = []
    seasons_estimated = []

    for seizoen in SEASONS.keys():
        seizoen_df = daily[daily['__season'] == seizoen]
        days_present = len(seizoen_df)

        seizoen_info = {'days_present': int(days_present)}

        if days_present > 0:
            # Eigen data beschikbaar -> projecteer per seizoen
            seizoen_info['is_estimated'] = False
            for col in cost_columns:
                cost_per_day = seizoen_df[col].sum() / days_present
                annualized = cost_per_day * DAYS_PER_SEASON
                seizoen_info[f'cost_per_day_{col}'] = round(cost_per_day, 4)
                seizoen_info[f'annualized_{col}'] = round(annualized, 2)
                totals_annualized[col] += annualized
            seasons_present.append(seizoen)
        else:
            # Ontbrekend -> opvullen met overall gemiddelde
            seizoen_info['is_estimated'] = True
            for col in cost_columns:
                cost_per_day = overall_avg_per_day[col]
                annualized = cost_per_day * DAYS_PER_SEASON
                seizoen_info[f'cost_per_day_{col}'] = round(cost_per_day, 4)
                seizoen_info[f'annualized_{col}'] = round(annualized, 2)
                totals_annualized[col] += annualized
            seasons_estimated.append(seizoen)

        per_season[seizoen] = seizoen_info

    year_coverage = len(seasons_present) / 4.0

    return {
        'totals_annualized': {k: round(v, 2) for k, v in totals_annualized.items()},
        'per_season': per_season,
        'seasons_present': seasons_present,
        'seasons_estimated': seasons_estimated,
        'year_coverage': round(year_coverage, 3),
        'days_in_data': total_days_data,
    }


# ============================================================
# 6. BESPARINGSSAMENVATTING
# ============================================================

def calculate_savings_summary(costs_df):
    """
    Bereken totale besparing uit een DataFrame met beide kostenkolommen.

    Naast de ruwe som over de meterdata wordt een seizoensgewogen jaar-
    projectie geretourneerd (zie annualize_costs_seasonal). De jaarbasis
    is primair voor het consumentenrapport; de ruwe som blijft beschikbaar
    voor transparantie en debug.

    Returns:
        dict met:
          - total_cost_*:     seizoensgewogen jaarbasis (primair)
          - total_cost_*_raw: som over aangeleverde meterdata
          - total_savings, savings_percentage: jaarbasis
          - seasonal_info:    dict met seizoensdetail + year_coverage
    """
    if costs_df.empty or 'cost_no_battery' not in costs_df.columns:
        return {}

    total_no_battery_raw = costs_df['cost_no_battery'].sum()

    seasonal_info = annualize_costs_seasonal(costs_df)
    annualized = seasonal_info.get('totals_annualized', {})

    total_no_battery_year = annualized.get('cost_no_battery', total_no_battery_raw)

    result = {
        'total_cost_no_battery': round(total_no_battery_year, 2),
        'total_cost_no_battery_raw': round(total_no_battery_raw, 2),
        'quarters_calculated': len(costs_df),
        'seasonal_info': seasonal_info,
    }

    if 'cost_with_battery' in costs_df.columns:
        total_with_battery_raw = costs_df['cost_with_battery'].sum()
        total_with_battery_year = annualized.get(
            'cost_with_battery', total_with_battery_raw
        )
        savings_year = total_no_battery_year - total_with_battery_year

        result.update({
            'total_cost_with_battery': round(total_with_battery_year, 2),
            'total_cost_with_battery_raw': round(total_with_battery_raw, 2),
            'total_savings': round(savings_year, 2),
            'total_savings_raw': round(
                total_no_battery_raw - total_with_battery_raw, 2
            ),
            'savings_percentage': round(
                (savings_year / total_no_battery_year * 100)
                if total_no_battery_year != 0 else 0, 1
            ),
        })

    return result
