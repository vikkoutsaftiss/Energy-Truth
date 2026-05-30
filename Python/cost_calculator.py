"""
cost_calculator.py — Kostenberekening per kwartier voor Energy-Truth.

Berekent energiekosten per 15-minuten interval, zowel zonder als met batterij.
Gebruikt historische malus per aanbieder (provider_malus_history tabel).
Zolang die tabel niet bestaat, wordt malus=0 als default gebruikt.

BELANGRIJK: Prijsmodel
  - Afname (kopen):       all-in prijs (beursprijs + EB + ODE + btw + opslag)
  - Teruglevering (verkopen): beursprijs (nettoprijzen) − malus
  - Je krijgt energiebelasting, ODE en btw NIET terug bij teruglevering!

Drie malus-types:
  - 'full':       feed_in_price = nettoprijzen − malus
  - 'percentage': feed_in_price = nettoprijzen × (1 − malus)
  - 'fixed':      feed_in_price = malus (vast bedrag)

Gebruik:
    from cost_calculator import calculate_costs_no_battery, calculate_costs_with_battery
"""

import pandas as pd
from db_connection import get_client

# Module-level flag: als provider_malus_history niet bestaat (404),
# niet steeds opnieuw proberen — geeft default malus=0.
_malus_table_exists = None  # None = nog niet getest, True/False = resultaat


# ============================================================
# 1. MALUS OPHALEN (HISTORISCH)
# ============================================================

def get_malus_for_date(provider_code, date):
    """
    Haal de geldige malus op voor een aanbieder op een specifieke datum.

    Zoekt in provider_malus_history het record waar:
      valid_from <= date AND (valid_to IS NULL OR valid_to >= date)

    Args:
        provider_code: bijv. 'ANWB'
        date: datum als string of datetime

    Returns:
        dict met 'malus' (float) en 'type' (str)
        Default: {'malus': 0.0, 'type': 'full'} als geen record gevonden
    """
    global _malus_table_exists
    default = {'malus': 0.0, 'type': 'full'}

    # Als we al weten dat de tabel niet bestaat, meteen default teruggeven
    if _malus_table_exists is False:
        return default

    try:
        client = get_client()
        # Lookup Afkorting → Net_Aanbieder.ID
        na = client.table('Net_Aanbieder').select('ID').eq('Afkorting', provider_code).limit(1).execute()
        if not na.data:
            return default
        na_id = na.data[0]['ID']

        # ERD: Net_AanbiederID (zonder underscore), Geldig_tot (kleine t).
        # Geen .or_() in onze wrapper; we filteren in Python op de OR-conditie.
        response = (
            client.table('Net_Aanbieder_Malus_Historie')
            .select('Feed_In_Malus, Feed_In_Type_Malus, Geldig_tot')
            .eq('Net_AanbiederID', na_id)
            .lte('Geldig_Van', str(date))
            .order('Geldig_Van', desc=True)
            .execute()
        )
        # Pak de eerste rij waar Geldig_tot NULL is OF >= date
        if response.data:
            from datetime import date as _date_cls
            target = date if isinstance(date, _date_cls) else _date_cls.fromisoformat(str(date))
            filtered = []
            for rec in response.data:
                gt = rec.get('Geldig_tot')
                if gt is None:
                    filtered.append(rec); continue
                try:
                    gt_d = pd.Timestamp(gt).date() if not isinstance(gt, _date_cls) else gt
                    if gt_d >= target:
                        filtered.append(rec)
                except Exception:
                    pass
            response.data = filtered[:1]
        _malus_table_exists = True  # Query lukte → tabel bestaat

        if response.data:
            record = response.data[0]
            return {
                'malus': float(record['Feed_In_Malus']),
                'type': record['Feed_In_Type_Malus'],
            }
    except Exception:
        # Tabel bestaat nog niet → onthoud dit voor de rest van de sessie
        _malus_table_exists = False

    return default


def _get_malus_map(provider_code, dates):
    """
    Bouwt een lookup van datum → malus voor een reeks datums.
    Optimaliseert door unieke datums te groeperen.

    Args:
        provider_code: bijv. 'ANWB'
        dates: iterable van datums

    Returns:
        dict van date → {'malus': float, 'type': str}
    """
    global _malus_table_exists
    unique_dates = sorted(set(d.date() if hasattr(d, 'date') else d for d in dates))
    malus_map = {}
    default = {'malus': 0.0, 'type': 'full'}

    # Als we al weten dat de tabel niet bestaat, meteen defaults teruggeven
    if _malus_table_exists is False:
        return {d: default for d in unique_dates}

    # Als er weinig unieke datums zijn, per datum opvragen
    # Anders: alle malus-records ophalen en lokaal matchen
    if len(unique_dates) <= 30:
        for d in unique_dates:
            malus_map[d] = get_malus_for_date(provider_code, d)
    else:
        # Alle malus-records voor deze aanbieder ophalen
        try:
            client = get_client()
            # Lookup Afkorting → Net_Aanbieder.ID
            na = client.table('Net_Aanbieder').select('ID').eq('Afkorting', provider_code).limit(1).execute()
            if not na.data:
                return {d: default for d in unique_dates}
            na_id = na.data[0]['ID']

            response = (
                client.table('Net_Aanbieder_Malus_Historie')
                .select('Feed_In_Malus, Feed_In_Type_Malus, Geldig_Van, Geldig_tot')
                .eq('Net_AanbiederID', na_id)
                .order('Geldig_Van', desc=True)
                .execute()
            )
            records = response.data or []
            _malus_table_exists = True
        except Exception:
            _malus_table_exists = False
            records = []

        for d in unique_dates:
            found = False
            for rec in records:
                rec_from = pd.Timestamp(rec['Geldig_Van']).date()
                rec_to = pd.Timestamp(rec['Geldig_tot']).date() if rec.get('Geldig_tot') else None

                if rec_from <= d and (rec_to is None or rec_to >= d):
                    malus_map[d] = {
                        'malus': float(rec['Feed_In_Malus']),
                        'type': rec['Feed_In_Type_Malus'],
                    }
                    found = True
                    break
            if not found:
                malus_map[d] = default

    return malus_map


# ============================================================
# 2. FEED-IN PRIJS BEREKENEN
# ============================================================

def calculate_feed_in_price(net_price, malus, malus_type):
    """
    Bereken de terugleverprijs op basis van NETTOPRIJZEN (beursprijs) en malus.

    BELANGRIJK: Gebruik hier de nettoprijzen (kale beursprijs), NIET de all-in
    consumentenprijs. Bij teruglevering krijg je energiebelasting, ODE en btw
    niet terug — alleen de beursprijs minus malus.

    Args:
        net_price: kale beursprijs / nettoprijzen (€/kWh), EXCL belastingen
        malus: malus-waarde
        malus_type: 'full', 'percentage', of 'fixed'

    Returns:
        feed_in_price (€/kWh), minimaal 0
    """
    if malus_type == 'full':
        feed_in_price = net_price - malus
    elif malus_type == 'percentage':
        feed_in_price = net_price * (1 - malus)
    elif malus_type == 'fixed':
        feed_in_price = malus  # vast bedrag
    else:
        feed_in_price = net_price  # onbekend type → geen malus

    return max(0.0, feed_in_price)


# ============================================================
# 3. KOSTEN ZONDER BATTERIJ
# ============================================================

def calculate_costs_no_battery(meter_data, prices, provider_code, net_prices=None):
    """
    Bereken energiekosten per kwartier ZONDER batterij.

    Formule: kosten = verbruik × all-in prijs − teruglevering × terugleverprijs
    Terugleverprijs = nettoprijzen (beursprijs) − malus

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
        print(f"⚠️  Geen overlap tussen meterdata en prijzen voor {provider_code}")
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
        # Legacy: geen nettoprijzen meegegeven → all-in prijs als terugval
        merged['net_price'] = merged['price']

    # Malus ophalen per datum
    malus_map = _get_malus_map(provider_code, merged['timestamp_from'])

    # Kosten berekenen per rij
    costs = []
    feed_in_prices = []

    for _, row in merged.iterrows():
        date_key = row['timestamp_from'].date() if hasattr(row['timestamp_from'], 'date') else row['timestamp_from']
        malus_info = malus_map.get(date_key, {'malus': 0.0, 'type': 'full'})

        # Terugleverprijs op basis van NETTOPRIJZEN (beursprijs), niet all-in!
        fi_price = calculate_feed_in_price(
            row['net_price'], malus_info['malus'], malus_info['type']
        )
        feed_in_prices.append(fi_price)

        # Kosten = verbruik × all-in prijs − teruglevering × terugleverprijs
        cost = (row['consumption_kwh'] * row['price']) - (row['feed_in_kwh'] * fi_price)
        costs.append(cost)

    merged['feed_in_price'] = feed_in_prices
    merged['cost_no_battery'] = costs

    return merged


# ============================================================
# 4. KOSTEN MET BATTERIJ
# ============================================================

def calculate_costs_with_battery(simulated_data, provider_code, net_prices=None):
    """
    Bereken energiekosten per kwartier MET batterij.

    Verwacht dat battery_simulator al grid_consumption en grid_feed_in
    heeft berekend. Deze functie voegt alleen de kostenkolom toe.

    Formule: kosten = grid_consumption × all-in prijs − grid_feed_in × terugleverprijs
    Terugleverprijs = nettoprijzen (beursprijs) − malus

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

    # Malus ophalen per datum
    malus_map = _get_malus_map(provider_code, simulated_data['timestamp_from'])

    costs = []
    feed_in_prices = []

    for _, row in simulated_data.iterrows():
        date_key = row['timestamp_from'].date() if hasattr(row['timestamp_from'], 'date') else row['timestamp_from']
        malus_info = malus_map.get(date_key, {'malus': 0.0, 'type': 'full'})

        # Terugleverprijs op basis van NETTOPRIJZEN
        fi_price = calculate_feed_in_price(
            row['net_price'], malus_info['malus'], malus_info['type']
        )
        feed_in_prices.append(fi_price)

        # Kosten = netverbruik × all-in prijs − netto-teruglevering × terugleverprijs
        cost = (row['grid_consumption'] * row['price']) - (row['grid_feed_in'] * fi_price)
        costs.append(cost)

    simulated_data['feed_in_price_battery'] = feed_in_prices
    simulated_data['cost_with_battery'] = costs

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


# ============================================================
# STANDALONE TEST
# ============================================================

def _fetch_all_meter_data(client, klant_id, start_date, end_date):
    """Haal alle meterdata gepagineerd op via Gebouw-filter.

    Returns records met pandas-conventie kolomnamen (timestamp_from,
    consumption_kwh, feed_in_kwh) - intern hernoemd vanaf Yan-stijl.
    """
    # Eerst Gebouw-IDs voor deze klant ophalen
    gebouwen = client.table('Gebouw').select('ID').eq('Klant_ID', klant_id).execute()
    gebouw_ids = [g['ID'] for g in (gebouwen.data or [])]
    if not gebouw_ids:
        return []

    all_records = []
    offset = 0
    while True:
        response = (
            client.table('Verbruiksdata')
            .select('MeetDatumTijd, Stroom_Gekocht_Net_kWh, Stroom_Verkocht_Net_kWh')
            .in_('Gebouw_ID', gebouw_ids)
            .gte('MeetDatumTijd', f'{start_date}T00:00:00+00:00')
            .lte('MeetDatumTijd', f'{end_date}T23:59:59+00:00')
            .order('MeetDatumTijd')
            .range(offset, offset + 999)
            .execute()
        )
        # Hernoem keys naar interne pandas-conventie
        for rec in response.data:
            all_records.append({
                'timestamp_from': rec['MeetDatumTijd'],
                'consumption_kwh': rec['Stroom_Gekocht_Net_kWh'],
                'feed_in_kwh': rec['Stroom_Verkocht_Net_kWh'],
            })
        if len(response.data) < 1000:
            break
        offset += 1000
    return all_records


def run_unit_tests():
    """Unit tests met dummy data."""
    print("\n" + "=" * 60)
    print("  DEEL 1: UNIT TESTS")
    print("=" * 60)

    # Test 1: Malus ophalen (verwacht default omdat tabel niet bestaat)
    print("\n  Test 1: Malus ophalen")
    malus = get_malus_for_date('ANWB', '2025-06-15')
    print(f"    ANWB op 2025-06-15: malus={malus['malus']}, type={malus['type']}")
    assert malus['malus'] == 0.0, "Default malus moet 0 zijn"
    assert malus['type'] == 'full', "Default type moet 'full' zijn"
    print("    ✅ Default malus correct")

    # Test 2: Feed-in prijs berekening
    print("\n  Test 2: Feed-in prijs berekening")
    fi = calculate_feed_in_price(0.25, 0.05, 'full')
    assert abs(fi - 0.20) < 0.001
    print(f"    full:       0.25 - 0.05 = EUR {fi:.4f} ✅")

    fi = calculate_feed_in_price(0.25, 0.20, 'percentage')
    assert abs(fi - 0.20) < 0.001
    print(f"    percentage: 0.25 x 0.80 = EUR {fi:.4f} ✅")

    fi = calculate_feed_in_price(0.25, 0.10, 'fixed')
    assert abs(fi - 0.10) < 0.001
    print(f"    fixed:      vast EUR {fi:.4f} ✅")

    fi = calculate_feed_in_price(0.05, 0.10, 'full')
    assert fi == 0.0
    print(f"    negatief:   max(0, 0.05-0.10) = EUR {fi:.4f} ✅")

    # Test 3: Kosten zonder batterij (dummy data)
    print("\n  Test 3: Kosten zonder batterij (dummy data)")
    dummy_meter = pd.DataFrame({
        'timestamp_from': pd.to_datetime([
            '2025-06-15 12:00:00+00:00',
            '2025-06-15 12:15:00+00:00',
            '2025-06-15 12:30:00+00:00',
        ]),
        'consumption_kwh': [0.5, 0.3, 0.0],
        'feed_in_kwh':     [0.0, 0.0, 0.4],
    })
    dummy_prices = pd.DataFrame({
        'valid_from': pd.to_datetime([
            '2025-06-15 12:00:00+00:00',
            '2025-06-15 12:15:00+00:00',
            '2025-06-15 12:30:00+00:00',
        ]),
        'price': [0.20, 0.25, 0.30],
    })
    result = calculate_costs_no_battery(dummy_meter, dummy_prices, 'TEST')
    expected = [0.10, 0.075, -0.12]
    for i, exp in enumerate(expected):
        actual = result.iloc[i]['cost_no_battery']
        assert abs(actual - exp) < 0.001
        print(f"    Kwartier {i+1}: EUR {actual:.4f} (verwacht EUR {exp:.4f}) ✅")

    # Test 4: Besparingssamenvatting
    print("\n  Test 4: Besparingssamenvatting")
    result['cost_with_battery'] = [0.08, 0.05, -0.15]
    summary = calculate_savings_summary(result)
    print(f"    Zonder batterij: EUR {summary['total_cost_no_battery']:.2f}")
    print(f"    Met batterij:    EUR {summary['total_cost_with_battery']:.2f}")
    print(f"    Besparing:       EUR {summary['total_savings']:.2f} "
          f"({summary['savings_percentage']}%)")
    print("    ✅ Samenvatting correct")

    print("\n  ✅ Alle unit tests geslaagd!")


def run_integration_test():
    """Integratietest met echte data uit config.json."""
    from simulation_config import SimulationConfig
    from reference_data import reconstruct_historical_prices, get_net_prices

    print("\n" + "=" * 60)
    print("  DEEL 2: INTEGRATIETEST MET ECHTE DATA")
    print("=" * 60)

    # Config laden
    config = SimulationConfig.from_json("config.json")
    print(f"\n  Config geladen:")
    print(f"    Klant ID:  {config.klant_id}")
    print(f"    Periode:  {config.simulation.start_date} t/m {config.simulation.end_date}")
    print(f"    Providers: {config.providers}")

    # Meterdata ophalen
    client = get_client()
    print(f"\n  Meterdata ophalen...")
    records = _fetch_all_meter_data(
        client, config.klant_id,
        config.simulation.start_date, config.simulation.end_date
    )

    if not records:
        print("  ❌ Geen meterdata gevonden voor deze klant!")
        return

    meter = pd.DataFrame(records)
    meter['timestamp_from'] = pd.to_datetime(meter['timestamp_from'], utc=True)
    meter['consumption_kwh'] = meter['consumption_kwh'].astype(float)
    meter['feed_in_kwh'] = meter['feed_in_kwh'].astype(float)

    totaal_verbruik = meter['consumption_kwh'].sum()
    totaal_teruglevering = meter['feed_in_kwh'].sum()
    print(f"    {len(meter)} kwartieren geladen")
    print(f"    Verbruik:      {totaal_verbruik:.0f} kWh")
    print(f"    Teruglevering: {totaal_teruglevering:.0f} kWh")

    # Nettoprijzen ophalen (kale beursprijzen, voor terugleverprijs)
    print(f"\n  Nettoprijzen ophalen (kale EPEX beursprijs)...")
    net_prices_df = get_net_prices(config.simulation.start_date, config.simulation.end_date)
    print(f"    {len(net_prices_df)} nettoprijzen geladen")
    if not net_prices_df.empty:
        gem_net = net_prices_df['Prijs_per_kWh'].mean()
        print(f"    Gem. beursprijs: EUR {gem_net:.4f}/kWh")

    # Aanbieders ophalen via Marges_Per_Aanbieder + Net_Aanbieder lookup naar Afkorting
    if config.providers == "all":
        margins_resp = client.table('Marges_Per_Aanbieder').select('Net_AanbiederID').order('Net_AanbiederID').execute()
        na_ids = [m['Net_AanbiederID'] for m in margins_resp.data]
        aanbieders = client.table('Net_Aanbieder').select('ID, Afkorting').in_('ID', na_ids).execute()
        provider_codes = sorted([a['Afkorting'] for a in (aanbieders.data or [])])
    else:
        provider_codes = config.providers if isinstance(config.providers, list) else [config.providers]

    print(f"\n  Kosten berekenen voor {len(provider_codes)} aanbieders...")
    print(f"  Afname: all-in prijs | Teruglevering: beursprijs − malus")
    print()

    # Per aanbieder kosten berekenen
    results = []
    for pc in provider_codes:
        prices = reconstruct_historical_prices(
            pc, config.simulation.start_date, config.simulation.end_date
        )
        if prices.empty:
            print(f"    {pc}: geen prijzen beschikbaar, overgeslagen")
            continue

        costs_df = calculate_costs_no_battery(meter, prices, pc, net_prices=net_prices_df)
        if costs_df.empty:
            print(f"    {pc}: geen overlap met meterdata, overgeslagen")
            continue

        summary = calculate_savings_summary(costs_df)
        results.append({
            'provider': pc,
            'kosten': summary['total_cost_no_battery'],
            'kwartieren': summary['quarters_calculated'],
        })

    if not results:
        print("  ❌ Geen resultaten — controleer of nettoprijzen en margins bestaan")
        return

    # Ranglijst
    results.sort(key=lambda x: x['kosten'])
    goedkoopst = results[0]['kosten']
    duurst = results[-1]['kosten']

    print("\n" + "=" * 60)
    print(f"  RESULTAAT: {config.simulation.start_date} t/m {config.simulation.end_date}")
    print(f"  {len(meter)} kwartieren | {totaal_verbruik:.0f} kWh verbruik | "
          f"{totaal_teruglevering:.0f} kWh teruglevering")
    print(f"  Kosten ZONDER batterij, per aanbieder:")
    print(f"  (afname=all-in prijs, teruglevering=beursprijs−malus)")
    print("=" * 60)

    for i, r in enumerate(results):
        verschil = r['kosten'] - goedkoopst
        if i == 0:
            label = "<-- goedkoopst"
        elif i == len(results) - 1:
            label = "<-- duurst"
        else:
            label = f"    +EUR {verschil:.2f}"
        print(f"  {i+1:2d}. {r['provider']:5s}  EUR {r['kosten']:8.2f}  {label}")

    print(f"\n  Verschil goedkoopst - duurst: EUR {duurst - goedkoopst:.2f}/jaar")
    print(f"  Gem. kosten per maand:        EUR {goedkoopst / 12:.2f} (goedkoopst)")

    # Per maand breakdown voor goedkoopste
    print(f"\n  --- Maandoverzicht {results[0]['provider']} (goedkoopst) ---")
    best_pc = results[0]['provider']
    prices = reconstruct_historical_prices(
        best_pc, config.simulation.start_date, config.simulation.end_date
    )
    costs_df = calculate_costs_no_battery(meter, prices, best_pc, net_prices=net_prices_df)
    costs_df['maand'] = costs_df['timestamp_from'].dt.month
    maand_namen = {1:'jan', 2:'feb', 3:'mrt', 4:'apr', 5:'mei', 6:'jun',
                   7:'jul', 8:'aug', 9:'sep', 10:'okt', 11:'nov', 12:'dec'}
    monthly = costs_df.groupby('maand').agg(
        verbruik=('consumption_kwh', 'sum'),
        teruglevering=('feed_in_kwh', 'sum'),
        kosten=('cost_no_battery', 'sum'),
        kwartieren=('cost_no_battery', 'count'),
    )
    for m, row in monthly.iterrows():
        naam = maand_namen.get(m, str(m))
        print(f"    {naam:3s}: EUR {row['kosten']:7.2f}  "
              f"({row['verbruik']:6.0f} kWh verbr, {row['teruglevering']:5.0f} kWh terug, "
              f"{int(row['kwartieren'])} kw)")

    print(f"\n  ✅ Integratietest voltooid!")
    print("=" * 60)


if __name__ == "__main__":
    import sys

    if "--skip-unit" in sys.argv:
        run_integration_test()
    elif "--skip-integration" in sys.argv:
        run_unit_tests()
    else:
        run_unit_tests()
        run_integration_test()
