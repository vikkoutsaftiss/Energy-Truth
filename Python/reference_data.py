"""
reference_data.py — Prijsdata ophalen en marges berekenen voor Energy-Truth.

Werkt uitsluitend met data in de DB:
  - Nettoprijzen uit Net_Prijzen (geïmporteerd via import_net_prices.py)
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
    return df


# ============================================================
# 2. AANBIEDERPRIJZEN OPHALEN
# ============================================================

def get_provider_prices(provider, start_date=None, end_date=None):
    """
    Haalt aanbiederprijzen op uit de Uurprijzen tabel (Enever data via n8n).

    Args:
        provider: int4 (Net_Aanbieder.ID) OF varchar (Net_Aanbieder.Afkorting)
                  Bij string-waarde wordt eerst de Afkorting → ID lookup gedaan.
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
    return df


# ============================================================
# 3. MARGIN-BEREKENING PER AANBIEDER
# ============================================================

def calculate_margins():
    """
    Berekent de gemiddelde marge per aanbieder.

    Marge = aanbiederprijzen − nettoprijzen op overlappende timestamps.
    Slaat resultaat op in Marges_per_Aanbieder tabel.

    Returns:
        DataFrame met Net_Aanbieder_ID, Afkorting, Naam, Gemiddelde_Marge, Aantal_Samples
    """
    client = get_client()

    # Alle aanbieders ophalen
    aanbieders = client.table('Net_Aanbieder').select('ID, Afkorting, Naam').execute().data
    if not aanbieders:
        print("⚠️  Geen aanbieders gevonden in database")
        return pd.DataFrame()

    # Nettoprijzen ophalen
    net_prices = get_net_prices()
    if net_prices.empty:
        print("⚠️  Geen nettoprijzen — draai eerst: python import_net_prices.py <csv>")
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

        print(f"  {afkorting} ({naam}): €{avg_margin:.4f}/kWh (n={sample_count})")

    if not results:
        print("⚠️  Geen marges berekend — geen overlap tussen prijzen")
        return pd.DataFrame()

    # Opslaan (upsert) met expliciete timestamp
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()

    df_margins = pd.DataFrame(results)
    for _, row in df_margins.iterrows():
        client.table('Marges_Per_Aanbieder').upsert({
            'Net_AanbiederID': int(row['Net_Aanbieder_ID']),
            'Gemiddelde_Marge': float(row['Gemiddelde_Marge']),
            'Aantal_Samples': int(row['Aantal_Samples']),
            'Berekend_Op': now,
        }, on_conflict='Net_AanbiederID').execute()

    print(f"\n  ✅ Marges opgeslagen voor {len(df_margins)} aanbieders")
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
            print(f"⚠️  Onbekende Afkorting '{provider}'")
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
        print(f"⚠️  Geen marge voor Net_Aanbieder_ID={net_aanbieder_id} — draai eerst calculate_margins()")
        return pd.DataFrame()

    margin = margin_response.data[0]
    avg_margin = float(margin['Gemiddelde_Marge'])

    print(f"Prijzen reconstrueren voor Net_Aanbieder_ID={net_aanbieder_id}:")
    print(f"  Marge: €{avg_margin:.4f}/kWh (n={margin['Aantal_Samples']})")

    # Nettoprijzen + echte aanbiederprijzen ophalen
    net_prices = get_net_prices(start_date, end_date)
    real_prices = get_provider_prices(net_aanbieder_id, start_date, end_date)

    if net_prices.empty:
        print(f"⚠️  Geen nettoprijzen voor {start_date} t/m {end_date}")
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
# 5. OVERZICHT
# ============================================================

def print_price_summary():
    """Print een overzicht van beschikbare prijsdata."""
    client = get_client()

    print("\n" + "=" * 55)
    print("  PRIJSDATA OVERZICHT")
    print("=" * 55)

    # Netbeheer-tarieven (voorheen Net_Prijzen)
    net_count = client.table('Netbeheer_Tarieven').select('Geldig_Van', count='exact').execute()
    if net_count.count and net_count.count > 0:
        net_first = client.table('Netbeheer_Tarieven').select('Geldig_Van').order('Geldig_Van').limit(1).execute()
        net_last = client.table('Netbeheer_Tarieven').select('Geldig_Van').order('Geldig_Van', desc=True).limit(1).execute()
        print(f"\n  NETBEHEER TARIEVEN")
        print(f"    Records: {net_count.count}")
        print(f"    Van: {net_first.data[0]['Geldig_Van']}")
        print(f"    Tot: {net_last.data[0]['Geldig_Van']}")
    else:
        print(f"\n  NETTOPRIJZEN: geen data — draai: python import_net_prices.py <csv>")

    # Aanbiederprijzen (eerste 5)
    aanbieders = client.table('Net_Aanbieder').select('ID, Afkorting, Naam').execute()
    if aanbieders.data:
        print(f"\n  AANBIEDERPRIJZEN ({len(aanbieders.data)} aanbieders)")
        for p in aanbieders.data[:5]:
            count = (
                client.table('Uurprijzen')
                .select('valid_from', count='exact')
                .eq('Net_Aanbieder_ID', p['ID'])
                .execute()
            )
            print(f"    {p['Afkorting']} ({p['Naam']}): {count.count or 0} records")
        if len(aanbieders.data) > 5:
            print(f"    ... en {len(aanbieders.data) - 5} meer")

    # Marges
    margins = client.table('Marges_Per_Aanbieder').select('*').execute()
    if margins.data:
        print(f"\n  MARGES ({len(margins.data)} aanbieders)")
        for m in margins.data[:5]:
            print(f"    Net_AanbiederID={m['Net_AanbiederID']}: €{float(m['Gemiddelde_Marge']):.4f}/kWh "
                  f"(n={m['Aantal_Samples']})")
    else:
        print(f"\n  MARGES: nog niet berekend")

    print("\n" + "=" * 55)


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


# ============================================================
# STANDALONE
# ============================================================

if __name__ == "__main__":
    print_price_summary()
