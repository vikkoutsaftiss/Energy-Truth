"""
reference_data.py - Prijsdata ophalen en marges berekenen voor Energy-Truth.

Werkt uitsluitend met data in de DB:
  - Nettoprijzen uit Net_Prijzen (geimporteerd via import_net_prices.py)
  - Aanbiederprijzen uit Uurprijzen (Enever via n8n)
  - Marges berekenen en opslaan in Marges_per_Aanbieder
  - Historische aanbiederprijzen reconstrueren via marges

Gebruik:
    from reference_data import get_net_prices, calculate_margins
    net = get_net_prices('2025-01-01', '2025-12-31')
    margins = calculate_margins()
"""

import pandas as pd
from db_connection import get_client


# ============================================================
# 1. NETTOPRIJZEN OPHALEN
# ============================================================

def get_net_prices(start_date=None, end_date=None):
    """
    Haalt nettoprijzen (beursprijzen) op uit de Net_Prijzen tabel.

    Args:
        start_date: optioneel startdatum (string of datetime)
        end_date: optioneel einddatum (string of datetime)

    Returns:
        DataFrame met Geldig_Van en Prijs_per_kWh
    """
    client = get_client()
    # ERD: tabel heet nu "Netbeheer_Tarieven", kolom "Tarief_Per_kWh".
    # We hernoemen de output naar Prijs_per_kWh zodat downstream code
    # (scenario_engine, cost_calculator) ongewijzigd blijft werken.
    query = client.table('Netbeheer_Tarieven').select('Geldig_Van, Tarief_Per_kWh').order('Geldig_Van')

    if start_date:
        query = query.gte('Geldig_Van', str(start_date))
    if end_date:
        query = query.lte('Geldig_Van', str(end_date))

    all_records = _fetch_paginated(query)

    if not all_records:
        return pd.DataFrame(columns=['valid_from', 'price'])

    df = pd.DataFrame(all_records)
    # Interne conventie: valid_from + price (zoals battery_simulator/cost_calculator verwachten).
    df = df.rename(columns={'Geldig_Van': 'valid_from', 'Tarief_Per_kWh': 'price'})
    df['valid_from'] = pd.to_datetime(df['valid_from'], utc=True)
    df['price'] = df['price'].astype(float)
    # Bescherming tegen dubbele timestamps in de bron (bv. een niet-idempotente
    # prijs-import). Zonder dedup matcht elk verbruikskwartier met meerdere
    # prijsrijen in de kostenmerge en wordt het verbruik dubbel geteld.
    df = df.sort_values('valid_from').drop_duplicates(subset='valid_from', keep='last').reset_index(drop=True)
    return df


# ============================================================
# 2. AANBIEDERPRIJZEN OPHALEN
# ============================================================

def get_provider_prices(provider, start_date=None, end_date=None):
    """
    Haalt aanbiederprijzen op uit de Uurprijzen tabel (Enever data via n8n).

    Args:
        provider: int4 (Net_Aanbieder.ID) OF varchar (Net_Aanbieder.Afkorting)
                  Bij string-waarde wordt eerst de Afkorting -> ID lookup gedaan.
        start_date: optioneel startdatum
        end_date: optioneel einddatum

    Returns:
        DataFrame met Geldig_Van (= valid_from kolom uit Uurprijzen) en Prijs_per_kWh
    """
    client = get_client()

    # Mapping Afkorting -> ID voor backward compat met scenario_engine
    if isinstance(provider, str):
        na = client.table('Net_Aanbieder').select('ID').eq('Afkorting', provider).limit(1).execute()
        if not na.data:
            return pd.DataFrame(columns=['valid_from', 'price'])
        net_aanbieder_id = na.data[0]['ID']
    else:
        net_aanbieder_id = int(provider)

    query = (
        client.table('Uurprijzen')
        .select('valid_from, Prijs_per_kWh')
        .eq('Net_Aanbieder_ID', net_aanbieder_id)
        .order('valid_from')
    )

    if start_date:
        query = query.gte('valid_from', str(start_date))
    if end_date:
        query = query.lte('valid_from', str(end_date))

    all_records = _fetch_paginated(query)

    if not all_records:
        return pd.DataFrame(columns=['valid_from', 'price'])

    df = pd.DataFrame(all_records)
    # Interne conventie: valid_from + price.
    df = df.rename(columns={'Prijs_per_kWh': 'price'})
    df['valid_from'] = pd.to_datetime(df['valid_from'], utc=True)
    df['price'] = df['price'].astype(float)
    # Zelfde dedup-bescherming als bij get_net_prices: 1 prijs per timestamp.
    df = df.sort_values('valid_from').drop_duplicates(subset='valid_from', keep='last').reset_index(drop=True)
    return df


# ============================================================
# 3. MARGIN-BEREKENING PER AANBIEDER
# ============================================================

def calculate_margins():
    """
    Berekent de gemiddelde marge per aanbieder.

    Marge = aanbiederprijzen - nettoprijzen op overlappende timestamps.
    Slaat resultaat op in Marges_per_Aanbieder tabel.

    Returns:
        DataFrame met Net_Aanbieder_ID, Afkorting, Naam, Gemiddelde_Marge, Aantal_Samples
    """
    client = get_client()

    # Alle aanbieders ophalen
    aanbieders = client.table('Net_Aanbieder').select('ID, Afkorting, Naam').execute().data
    if not aanbieders:
        print("Let op: geen aanbieders gevonden in database")
        return pd.DataFrame()

    # Nettoprijzen ophalen
    net_prices = get_net_prices()
    if net_prices.empty:
        print("Let op: geen nettoprijzen - draai eerst: python import_net_prices.py <csv>")
        return pd.DataFrame()

    print(f"Marges berekenen voor {len(aanbieders)} aanbieders...")
    print(f"  Nettoprijzen: {len(net_prices)} records")

    results = []

    for aanbieder in aanbieders:
        na_id = aanbieder['ID']
        afkorting = aanbieder['Afkorting']
        naam = aanbieder['Naam']

        provider_prices = get_provider_prices(na_id)
        if provider_prices.empty:
            continue

        # Merge op timestamp (overlap-periode)
        merged = pd.merge(
            provider_prices, net_prices,
            on='valid_from', suffixes=('_provider', '_net')
        )

        if merged.empty:
            continue

        # Marge berekenen
        merged['marge'] = merged['price_provider'] - merged['price_net']
        avg_margin = merged['marge'].mean()
        sample_count = len(merged)

        results.append({
            'Net_Aanbieder_ID': na_id,
            'Afkorting': afkorting,
            'Naam': naam,
            'Gemiddelde_Marge': round(avg_margin, 6),
            'Aantal_Samples': sample_count,
        })

        print(f"  {afkorting} ({naam}): EUR {avg_margin:.4f}/kWh (n={sample_count})")

    if not results:
        print("Let op: geen marges berekend - geen overlap tussen prijzen")
        return pd.DataFrame()

    # Opslaan (upsert) met expliciete timestamp
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()

    df_margins = pd.DataFrame(results)
    # Plaats = rang op marge, oplopend (1 = laagste marge = goedkoopst voor
    # de consument). Zo hoeft de top/bottom-selectie niet per rapport opnieuw
    # gesorteerd te worden; de worker leest gewoon deze kolom.
    df_margins = df_margins.sort_values('Gemiddelde_Marge').reset_index(drop=True)
    df_margins['Plaats'] = range(1, len(df_margins) + 1)

    for _, row in df_margins.iterrows():
        client.table('Marges_Per_Aanbieder').upsert({
            'Net_AanbiederID': int(row['Net_Aanbieder_ID']),
            'Gemiddelde_Marge': float(row['Gemiddelde_Marge']),
            'Aantal_Samples': int(row['Aantal_Samples']),
            'Plaats': int(row['Plaats']),
            'Berekend_Op': now,
        }, on_conflict='Net_AanbiederID').execute()

    print(f"\n  Klaar: marges + Plaats opgeslagen voor {len(df_margins)} aanbieders")
    return df_margins


# ============================================================
# 4. HISTORISCHE PRIJZEN RECONSTRUEREN
# ============================================================

def reconstruct_historical_prices(provider, start_date, end_date):
    """
    Reconstrueert historische aanbiederprijzen via marge-methode.
    geschatte_prijs = nettoprijzen + gemiddelde_marge

    Waar echte aanbiederprijzen bestaan worden die gebruikt.

    Args:
        provider: int4 (Net_Aanbieder.ID) OF varchar (Net_Aanbieder.Afkorting)
        start_date: startdatum
        end_date: einddatum

    Returns:
        DataFrame met Geldig_Van, Prijs_per_kWh, is_estimated, Net_Aanbieder_ID
    """
    client = get_client()

    # Mapping Afkorting -> ID voor backward compat
    if isinstance(provider, str):
        na = client.table('Net_Aanbieder').select('ID').eq('Afkorting', provider).limit(1).execute()
        if not na.data:
            print(f"Let op: onbekende Afkorting '{provider}'")
            return pd.DataFrame()
        net_aanbieder_id = na.data[0]['ID']
    else:
        net_aanbieder_id = int(provider)

    # Marge ophalen
    margin_response = (
        client.table('Marges_Per_Aanbieder')
        .select('Gemiddelde_Marge, Aantal_Samples')
        .eq('Net_AanbiederID', net_aanbieder_id)
        .execute()
    )

    if not margin_response.data:
        print(f"Let op: geen marge voor Net_Aanbieder_ID={net_aanbieder_id} - draai eerst calculate_margins()")
        return pd.DataFrame()

    margin = margin_response.data[0]
    avg_margin = float(margin['Gemiddelde_Marge'])

    print(f"Prijzen reconstrueren voor Net_Aanbieder_ID={net_aanbieder_id}:")
    print(f"  Marge: EUR {avg_margin:.4f}/kWh (n={margin['Aantal_Samples']})")

    # Nettoprijzen + echte aanbiederprijzen ophalen
    net_prices = get_net_prices(start_date, end_date)
    real_prices = get_provider_prices(net_aanbieder_id, start_date, end_date)

    if net_prices.empty:
        print(f"Let op: geen nettoprijzen voor {start_date} t/m {end_date}")
        return pd.DataFrame()

    # Schatting: nettoprijzen + marge
    estimated = net_prices.copy()
    estimated['price'] = estimated['price'] + avg_margin
    estimated['is_estimated'] = True
    estimated['Net_Aanbieder_ID'] = net_aanbieder_id

    # Waar echte prijzen bestaan: die gebruiken
    if not real_prices.empty:
        real_set = set(real_prices['valid_from'])
        estimated.loc[estimated['valid_from'].isin(real_set), 'is_estimated'] = False

        # Echte prijzen invullen
        real_dict = dict(zip(real_prices['valid_from'], real_prices['price']))
        for ts, prijs in real_dict.items():
            estimated.loc[estimated['valid_from'] == ts, 'price'] = prijs

    echt = len(estimated[~estimated['is_estimated']])
    geschat = len(estimated[estimated['is_estimated']])
    print(f"  {echt} echte + {geschat} geschatte = {len(estimated)} totaal")

    return estimated[['valid_from', 'price', 'is_estimated', 'Net_Aanbieder_ID']]


# ============================================================
# 4b. ALL-IN PRIJZEN MATERIALISEREN (refresher, 1x per dag)
# ============================================================

ALLIN_TABLE = 'Aanbieder_Allin_Prijzen_per24u'


def _full_price_window():
    """Min/max Geldig_Van uit Netbeheer_Tarieven -> (start, end) als string."""
    client = get_client()
    lo = client.table('Netbeheer_Tarieven').select('Geldig_Van').order('Geldig_Van').limit(1).execute()
    hi = client.table('Netbeheer_Tarieven').select('Geldig_Van').order('Geldig_Van', desc=True).limit(1).execute()
    if not lo.data or not hi.data:
        return None, None
    return lo.data[0]['Geldig_Van'], hi.data[0]['Geldig_Van']


def build_allin_prices():
    """
    Bouwt de all-in prijsreeks (netprijs + marge, of de echte prijs waar
    beschikbaar) per aanbieder over het VOLLEDIGE beschikbare prijsvenster
    en schrijft die weg in Aanbieder_Allin_Prijzen_per24u (upsert per
    (aanbieder, tijdstip)).

    Bedoeld om 1x per dag door refresher.py gedraaid te worden. De all-in
    prijs per tijdstip is klant-onafhankelijk; de worker leest later alleen
    nog het benodigde venster (rolling year) uit deze tabel.

    Returns:
        Aantal weggeschreven rijen.
    """
    client = get_client()
    start, end = _full_price_window()
    if not start:
        print("Let op: geen netprijzen - kan all-in prijzen niet opbouwen")
        return 0

    aanbieders = client.table('Net_Aanbieder').select('ID, Afkorting, Naam').execute().data or []
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    totaal = 0

    for a in aanbieders:
        na_id = a['ID']
        prijzen = reconstruct_historical_prices(na_id, start, end)
        if prijzen.empty:
            continue

        rows = []
        for _, r in prijzen.iterrows():
            vf = r['valid_from']
            rows.append({
                'Net_Aanbieder_ID': int(na_id),
                'Geldig_Van': vf.isoformat() if hasattr(vf, 'isoformat') else str(vf),
                'Prijs_per_kWh': float(r['price']),
                'Is_Geschat': bool(r['is_estimated']),
                'Berekend_Op': now,
            })

        # In batches upserten (begrenst payload/geheugen per call).
        for i in range(0, len(rows), 500):
            client.table(ALLIN_TABLE).upsert(
                rows[i:i + 500], on_conflict='Net_Aanbieder_ID,Geldig_Van'
            ).execute()

        totaal += len(rows)
        print(f"  {a['Afkorting']}: {len(rows)} all-in prijzen weggeschreven")

    print(f"\n  Klaar: all-in prijzen opgeslagen: {totaal} rijen voor {len(aanbieders)} aanbieders")
    return totaal


def get_allin_prices(provider, start_date, end_date):
    """
    Leest de voorberekende all-in prijzen uit Aanbieder_Allin_Prijzen_per24u
    voor het gevraagde venster.

    Valt automatisch terug op reconstruct_historical_prices als er voor deze
    aanbieder (nog) geen voorberekende rijen zijn, zodat de worker altijd
    werkt -- ook voordat refresher.py voor het eerst gedraaid heeft.

    Returns:
        DataFrame met valid_from, price, is_estimated (interne conventie),
        net als reconstruct_historical_prices.
    """
    client = get_client()

    if isinstance(provider, str):
        na = client.table('Net_Aanbieder').select('ID').eq('Afkorting', provider).limit(1).execute()
        if not na.data:
            return pd.DataFrame(columns=['valid_from', 'price', 'is_estimated'])
        na_id = na.data[0]['ID']
    else:
        na_id = int(provider)

    query = (
        client.table(ALLIN_TABLE)
        .select('Geldig_Van, Prijs_per_kWh, Is_Geschat')
        .eq('Net_Aanbieder_ID', na_id)
        .order('Geldig_Van')
    )
    if start_date:
        query = query.gte('Geldig_Van', str(start_date))
    if end_date:
        query = query.lte('Geldig_Van', str(end_date))

    records = _fetch_paginated(query)
    if not records:
        # Nog niet voorberekend -> live reconstrueren (fallback).
        return reconstruct_historical_prices(na_id, start_date, end_date)

    df = pd.DataFrame(records)
    df = df.rename(columns={
        'Geldig_Van': 'valid_from',
        'Prijs_per_kWh': 'price',
        'Is_Geschat': 'is_estimated',
    })
    df['valid_from'] = pd.to_datetime(df['valid_from'], utc=True)
    df['price'] = df['price'].astype(float)
    return df


# ============================================================
# HELPER
# ============================================================

def _fetch_paginated(query, page_size=1000):
    """Haalt alle records op via paginering."""
    all_records = []
    offset = 0

    while True:
        response = query.range(offset, offset + page_size - 1).execute()
        batch = response.data
        if not batch:
            break
        all_records.extend(batch)
        if len(batch) < page_size:
            break
        offset += page_size

    return all_records
