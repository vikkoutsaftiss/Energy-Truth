"""
data_quality.py — Betrouwbaarheidsscore (0-100) voor Energy-Truth meterdata.

Berekent een kwaliteitsscore op basis van vier componenten:
  - Dekkingsgraad (30%): gewogen telling — 15-min=1pt, uur=0.6pt, dag=0.2pt
  - Seizoensspreiding (30%): proportionele dekking per seizoen (maanden/3)
  - Consistentie (20%): alleen gaps, geen dubbele straf voor opgesplitste data
  - Input-type (20%): originele 15-min data vs. uur- of dagdata

Prijskwaliteit is bewust geen onderdeel — de score meet de kwaliteit van
de meterdata van de klant, niet de volledigheid van onze prijsdatabase.

Gebruik:
    # Vanuit DataFrame (bijv. direct na CSV-import):
    from data_quality import calculate_quality_from_dataframe
    score = calculate_quality_from_dataframe(df)

    # Vanuit database (strikt per ImportBatch):
    from data_quality import calculate_quality_score
    score = calculate_quality_score(import_batch_id)
"""

import pandas as pd
from db_connection import get_client

# ============================================================
# CONSTANTEN
# ============================================================

WEIGHTS = {
    'dekkingsgraad': 0.30,
    'seizoensspreiding': 0.30,
    'consistentie': 0.20,
    'input_type': 0.20,
}

# Seizoenen: maandnummers per seizoen (Nederlands klimaat)
SEASONS = {
    'winter': {12, 1, 2},
    'lente': {3, 4, 5},
    'zomer': {6, 7, 8},
    'herfst': {9, 10, 11},
}

# Score per original_interval (gebruikt voor input-type én dekkingsgraad).
# Sleutels zijn INTEGER-minuten, passend bij de DB-kolom
# Verbruiksdata.Origineel_Interval_Min (int): 15 = kwartier, 60 = uur, 1440 = dag.
INTERVAL_SCORES = {
    15: 100,
    60: 60,
    1440: 20,
}

# Wegingsfactor per interval voor dekkingsgraad
# Originele 15-min = 1.0 punt, uurdata = 0.6 punt, dagdata = 0.2 punt
COVERAGE_WEIGHT = {
    15: 1.0,
    60: 0.6,
    1440: 0.2,
}

QUARTERS_PER_HOUR = 4
QUARTERS_PER_DAY = 96
EXPECTED_INTERVAL_MINUTES = 15

# Bekende intervallen (minuten) waarop we een gemeten gat afronden.
KNOWN_INTERVALS = (15, 60, 1440)


# ============================================================
# INTERVAL-DETECTIE (vangnet voor lege Origineel_Interval_Min)
# ============================================================

def _detect_interval_from_timestamps(ts_series):
    """
    Leidt het werkelijke meetinterval (in minuten) af uit de tijdstempels.

    Bedoeld als VANGNET wanneer de import de kolom Origineel_Interval_Min
    leeg (NULL) laat: de data zelf bewijst het interval. We nemen het
    mediane gat tussen opeenvolgende metingen en ronden dat af naar het
    dichtstbijzijnde bekende interval (15 / 60 / 1440). Dit is meten, geen
    aanname; bij te weinig of te grillige data geven we None terug en
    verzinnen we dus niets.

    Returns:
        int (15, 60 of 1440) of None als het interval niet betrouwbaar
        bepaald kan worden.
    """
    ts = pd.to_datetime(ts_series, utc=True).dropna().sort_values()
    if len(ts) < 3:
        return None

    gaps = ts.diff().dt.total_seconds().dropna() / 60.0
    gaps = gaps[gaps > 0]
    if gaps.empty:
        return None

    mediaan = float(gaps.median())

    # Snap naar het dichtstbijzijnde bekende interval, maar alleen als het
    # redelijk dichtbij ligt (binnen 25% relatieve afwijking). Anders None.
    dichtstbij = min(KNOWN_INTERVALS, key=lambda k: abs(k - mediaan))
    if abs(dichtstbij - mediaan) / dichtstbij <= 0.25:
        return dichtstbij
    return None


def _normalize_interval_column(df):
    """
    Zorgt dat de kolom original_interval bruikbaar is voor de scoring.

    Drie gevallen:
      1. Kolom ontbreekt volledig  -> afleiden uit tijdstempels, anders 15.
      2. Kolom bestaat maar is (deels) NULL -> de NULL-rijen invullen met het
         uit de tijdstempels gemeten interval.
      3. Kolom volledig gevuld -> ongemoeid laten.

    Lost de bug op waarbij een import wel de meetwaarden maar niet het
    interval-label wegschrijft: NULL leidde tot input-type 0/100 en
    dekkingsgraad 50/100, terwijl het gewoon kwartierdata was.
    """
    df = df.copy()
    inferred = _detect_interval_from_timestamps(df['timestamp_from'])

    if 'original_interval' not in df.columns:
        df['original_interval'] = inferred if inferred is not None else 15
        return df

    null_mask = df['original_interval'].isna()
    if null_mask.any() and inferred is not None:
        df.loc[null_mask, 'original_interval'] = inferred

    # Naar hele getallen waar mogelijk (psycopg2 geeft int, maar fillna kan
    # naar float promoveren); houd niet-invulbare NULLs als NA.
    df['original_interval'] = pd.to_numeric(
        df['original_interval'], errors='coerce'
    ).round().astype('Int64')
    return df


# ============================================================
# COMPONENT 1: DEKKINGSGRAAD (35%)
# ============================================================

def _calculate_dekkingsgraad(df):
    """
    Gewogen dekkingsgraad op kwartierniveau.

    Originele 15-min meting telt als 1.0 punt.
    Opgesplitst uit uurdata telt als 0.6 punt.
    Opgesplitst uit dagdata telt als 0.2 punt.

    Dit voorkomt dat dagdata (365 metingen → 35.040 kwartieren)
    onterecht een 100% dekkingsgraad krijgt.
    """
    if df.empty:
        return 0.0, {'gewogen_punten': 0, 'verwacht': 0, 'percentage': 0.0}

    ts = df['timestamp_from'].sort_values()
    eerste = ts.iloc[0]
    laatste = ts.iloc[-1]

    # Verwacht aantal kwartieren in deze periode
    totale_minuten = (laatste - eerste).total_seconds() / 60
    verwacht = int(totale_minuten / EXPECTED_INTERVAL_MINUTES) + 1

    if verwacht == 0:
        return 0.0, {'gewogen_punten': 0, 'verwacht': 0, 'percentage': 0.0}

    # Gewogen punten: elke record krijgt een gewicht op basis van original_interval
    if 'original_interval' in df.columns:
        gewichten = df['original_interval'].map(COVERAGE_WEIGHT).fillna(0.5)
        gewogen_punten = gewichten.sum()
    else:
        # Geen interval-info → neem aan dat alles origineel 15-min is
        gewogen_punten = float(len(df))

    percentage = min(gewogen_punten / verwacht, 1.0) * 100  # max 100%

    return percentage, {
        'records': len(df),
        'gewogen_punten': round(gewogen_punten, 1),
        'verwacht': verwacht,
        'percentage': round(percentage, 1),
    }


# ============================================================
# COMPONENT 2: SEIZOENSSPREIDING (25%)
# ============================================================

def _calculate_seizoensspreiding(df):
    """
    Proportionele seizoensdekking.

    Per seizoen (3 maanden) wordt berekend hoeveel maanden data bevatten.
    Score = gemiddelde dekking over alle 4 seizoenen × 100.

    Voorbeeld jan-mrt: winter=2/3 (67%), lente=1/3 (33%), rest=0%.
    Score = (67+33+0+0)/4 = 25%.
    """
    if df.empty:
        return 0.0, {'per_seizoen': {}, 'gemiddelde': 0.0}

    maanden_aanwezig = set(df['timestamp_from'].dt.month.unique())

    per_seizoen = {}
    totaal_dekking = 0

    for seizoen, maanden in SEASONS.items():
        overlap = maanden_aanwezig & maanden
        dekking = len(overlap) / 3  # 3 maanden per seizoen
        per_seizoen[seizoen] = {
            'maanden': sorted(overlap),
            'dekking': round(dekking * 100, 1),
        }
        totaal_dekking += dekking

    score = (totaal_dekking / 4) * 100  # gemiddelde over 4 seizoenen

    return score, {
        'per_seizoen': per_seizoen,
        'gemiddelde': round(score, 1),
    }


# ============================================================
# COMPONENT 3: CONSISTENTIE (20%)
# ============================================================

def _calculate_consistentie(df):
    """
    Berekent consistentie: alleen gaps (ontbrekende kwartieren).

    Opgesplitste records (is_interpolated=TRUE) worden NIET meegeteld —
    die straf zit al in dekkingsgraad + input-type.
    Score = 1 − ontbrekende_kwartieren / totaal_verwacht × 100.
    """
    if df.empty:
        return 0.0, {'gaps': 0, 'verwacht': 0}

    ts = df['timestamp_from'].sort_values()
    eerste = ts.iloc[0]
    laatste = ts.iloc[-1]
    totale_minuten = (laatste - eerste).total_seconds() / 60
    verwacht = int(totale_minuten / EXPECTED_INTERVAL_MINUTES) + 1

    if verwacht == 0:
        return 0.0, {'gaps': 0, 'verwacht': 0}

    # Gaps detecteren via LAG (shift)
    df_sorted = df.sort_values('timestamp_from').copy()
    df_sorted['prev_ts'] = df_sorted['timestamp_from'].shift(1)
    df_sorted['gap_minuten'] = (
        (df_sorted['timestamp_from'] - df_sorted['prev_ts'])
        .dt.total_seconds() / 60
    )

    # Elke gap groter dan 15 min = ontbrekende kwartieren
    gap_rows = df_sorted[df_sorted['gap_minuten'] > EXPECTED_INTERVAL_MINUTES].copy()
    ontbrekende_kwartieren = 0
    for _, row in gap_rows.iterrows():
        gap_min = row['gap_minuten']
        missend = int(gap_min / EXPECTED_INTERVAL_MINUTES) - 1
        ontbrekende_kwartieren += missend

    # Score: alleen gaps als aftrek
    score = max(0, (1 - ontbrekende_kwartieren / verwacht)) * 100

    return score, {
        'gaps': ontbrekende_kwartieren,
        'verwacht': verwacht,
        'percentage': round(score, 1),
    }


# ============================================================
# COMPONENT 4: INPUT-TYPE (20%)
# ============================================================

def _calculate_input_type(df):
    """
    Gewogen score op basis van original_interval.
    15min = 100%, 60min = 60%, 1440min = 20%.
    Gewogen gemiddelde over alle records.
    """
    if df.empty:
        return 0.0, {'verdeling': {}}

    if 'original_interval' not in df.columns:
        # Geen interval-info → neem aan dat alles 15-min (kwartier) is
        return 100.0, {'verdeling': {15: len(df)}}

    verdeling = df['original_interval'].value_counts().to_dict()
    totaal = len(df)

    gewogen_score = 0
    for interval, aantal in verdeling.items():
        interval_score = INTERVAL_SCORES.get(interval, 50)  # onbekend = 50
        gewogen_score += (aantal / totaal) * interval_score

    return gewogen_score, {
        'verdeling': {k: int(v) for k, v in verdeling.items()},
        'gewogen_score': round(gewogen_score, 1),
    }


# ============================================================
# INTERPRETATIE
# ============================================================

def _interpretatie(score):
    """Geeft tekstuele interpretatie van de totaalscore."""
    if score >= 80:
        return "Zeer betrouwbaar — solide advies"
    elif score >= 60:
        return "Goed bruikbaar — kleine beperkingen"
    elif score >= 40:
        return "Voorzichtig interpreteren — indicatief advies"
    else:
        return "Onbetrouwbaar — meer data nodig"


# ============================================================
# HOOFDFUNCTIES
# ============================================================

def calculate_quality_from_dataframe(df):
    """
    Berekent betrouwbaarheidsscore vanuit een pandas DataFrame.

    Verwacht kolommen: timestamp_from, is_interpolated, original_interval.

    Returns:
        dict met 'totaalscore', 'interpretatie', en per component details.
    """
    # Zorg dat timestamp_from een datetime is
    if not pd.api.types.is_datetime64_any_dtype(df['timestamp_from']):
        df = df.copy()
        df['timestamp_from'] = pd.to_datetime(df['timestamp_from'], utc=True)

    # Vangnet: vul een lege/ontbrekende interval-kolom met het werkelijk
    # gemeten interval, zodat een import die alleen meetwaarden maar geen
    # interval-label wegschrijft niet onterecht 0/50 scoort.
    df = _normalize_interval_column(df)

    # Bereken alle componenten
    dekking_score, dekking_details = _calculate_dekkingsgraad(df)
    seizoen_score, seizoen_details = _calculate_seizoensspreiding(df)
    consist_score, consist_details = _calculate_consistentie(df)
    input_score, input_details = _calculate_input_type(df)

    # Gewogen totaalscore (ruw, voor cap)
    totaal_ruw = (
        dekking_score * WEIGHTS['dekkingsgraad']
        + seizoen_score * WEIGHTS['seizoensspreiding']
        + consist_score * WEIGHTS['consistentie']
        + input_score * WEIGHTS['input_type']
    )

    # CAP op basis van seizoensdekking.
    # De totaalscore kan nooit hoger zijn dan (aantal_aanwezige_seizoenen / 4) * 100.
    # Bij 2 van 4 seizoenen geldt dus max 50/100, ongeacht de overige componenten.
    # Reden: zonder lente/zomer of zonder herfst/winter is een advies per definitie
    # niet "solide". De simulatie projecteert ontbrekende seizoenen wel naar een
    # jaarschatting, maar de score moet duidelijk maken dat dat een schatting is.
    seizoenen_aanwezig = sum(
        1 for info in seizoen_details.get('per_seizoen', {}).values()
        if info.get('maanden')
    )
    score_cap = (seizoenen_aanwezig / 4.0) * 100.0
    cap_actief = totaal_ruw > score_cap

    totaal = round(min(totaal_ruw, score_cap), 1)

    return {
        'totaalscore': totaal,
        'totaalscore_voor_cap': round(totaal_ruw, 1),
        'cap_actief': cap_actief,
        'cap_grens': round(score_cap, 1),
        'seizoenen_aanwezig': seizoenen_aanwezig,
        'interpretatie': _interpretatie(totaal),
        'componenten': {
            'dekkingsgraad': {
                'score': round(dekking_score, 1),
                'gewicht': f"{int(WEIGHTS['dekkingsgraad'] * 100)}%",
                'bijdrage': round(dekking_score * WEIGHTS['dekkingsgraad'], 1),
                **dekking_details,
            },
            'seizoensspreiding': {
                'score': round(seizoen_score, 1),
                'gewicht': f"{int(WEIGHTS['seizoensspreiding'] * 100)}%",
                'bijdrage': round(seizoen_score * WEIGHTS['seizoensspreiding'], 1),
                **seizoen_details,
            },
            'consistentie': {
                'score': round(consist_score, 1),
                'gewicht': f"{int(WEIGHTS['consistentie'] * 100)}%",
                'bijdrage': round(consist_score * WEIGHTS['consistentie'], 1),
                **consist_details,
            },
            'input_type': {
                'score': round(input_score, 1),
                'gewicht': f"{int(WEIGHTS['input_type'] * 100)}%",
                'bijdrage': round(input_score * WEIGHTS['input_type'], 1),
                **input_details,
            },
        },
    }


def _backfill_interval_in_db(import_batch_id, interval):
    """
    Schrijft het gemeten interval terug naar de NULL-rijen van een batch.

    Repareert de bron: imports die wel meetwaarden maar geen
    Origineel_Interval_Min wegschrijven (bijv. bron 'HomeWizard') laten de
    kolom NULL. Hier vullen we die NULL-rijen met het uit de tijdstempels
    gemeten interval, zodat de kolom voortaan in de DB klopt. Idempotent:
    al gevulde rijen blijven ongemoeid, een volgende run vindt niets meer.

    Returns:
        Aantal bijgewerkte rijen.
    """
    from db_connection import get_connection
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE "Verbruiksdata"
                SET "Origineel_Interval_Min" = %s
                WHERE "ImportBatchID" = %s
                  AND "Origineel_Interval_Min" IS NULL
            """, (interval, import_batch_id))
            n = cur.rowcount
        conn.commit()
        return n
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def calculate_quality_score(import_batch_id, backfill_nulls=True):
    """
    Haalt meterdata op uit Verbruiksdata voor EEN ImportBatch en berekent
    de score.

    Strikt batch-scoped (30 mei 2026), net als
    scenario_engine._load_meter_data_from_db en period_selector. Zo gaan de
    betrouwbaarheidsscore en het rapport gegarandeerd over precies dezelfde
    meterdata; meerdere uploads van dezelfde klant lopen niet door elkaar.

    backfill_nulls (default True): is Origineel_Interval_Min leeg (NULL) en
    kunnen we het interval eenduidig uit de tijdstempels meten, dan schrijven
    we die waarde meteen terug naar de DB. Zo heelt de keten zichzelf bij elke
    run. Zet op False voor een puur lezende berekening.

    Returns:
        dict met 'totaalscore', 'interpretatie', en per component details.
    """
    from db_connection import get_connection
    import psycopg2.extras

    sql = """
        SELECT v."MeetDatumTijd"          AS "MeetDatumTijd",
               v."Is_Geinterpoleerd"      AS "Is_Geinterpoleerd",
               v."Origineel_Interval_Min" AS "Origineel_Interval_Min"
        FROM "Verbruiksdata" v
        WHERE v."ImportBatchID" = %s
        ORDER BY v."MeetDatumTijd"
    """
    print(f"Data ophalen voor ImportBatch {import_batch_id}...")
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (import_batch_id,))
            all_records = [dict(r) for r in cur.fetchall()]

    if not all_records:
        print("⚠️  Geen meterdata gevonden voor deze ImportBatch!")
        return {
            'totaalscore': 0,
            'interpretatie': _interpretatie(0),
            'componenten': {},
            'records': 0,
        }

    print(f"  {len(all_records)} records opgehaald")

    # Naar DataFrame — hernoem terug naar interne pandas-conventie
    df = pd.DataFrame(all_records)
    df = df.rename(columns={
        'MeetDatumTijd': 'timestamp_from',
        'Is_Geinterpoleerd': 'is_interpolated',
        'Origineel_Interval_Min': 'original_interval',
    })
    df['timestamp_from'] = pd.to_datetime(df['timestamp_from'], utc=True)

    # Bron-reparatie: vul lege Origineel_Interval_Min in de DB met het
    # gemeten interval. Alleen als er NULL-rijen zijn én het interval
    # eenduidig bepaald kan worden (anders niets schrijven).
    if backfill_nulls and df['original_interval'].isna().any():
        inferred = _detect_interval_from_timestamps(df['timestamp_from'])
        if inferred is not None:
            try:
                n = _backfill_interval_in_db(import_batch_id, inferred)
                if n:
                    print(f"  ↻ {n} rijen met lege Origineel_Interval_Min "
                          f"bijgewerkt naar {inferred} (gemeten interval).")
            except Exception as e:
                print(f"  ⚠️  Backfill van Origineel_Interval_Min overgeslagen: {e}")
        else:
            print("  ⚠️  Origineel_Interval_Min leeg, maar interval niet "
                  "eenduidig te meten — niets weggeschreven.")

    result = calculate_quality_from_dataframe(df)
    result['records'] = len(all_records)
    return result


# ============================================================
# PRINT RAPPORT
# ============================================================

def print_quality_report(result):
    """Print een leesbaar rapport van de betrouwbaarheidsscore."""
    print("\n" + "=" * 55)
    print(f"  BETROUWBAARHEIDSSCORE: {result['totaalscore']}/100")
    print(f"  {result['interpretatie']}")
    if result.get('cap_actief'):
        print(f"  ! Gecapt op {result['cap_grens']}/100 wegens "
              f"{result['seizoenen_aanwezig']}/4 seizoenen "
              f"(ruwe score zou {result['totaalscore_voor_cap']} zijn)")
    print("=" * 55)

    if not result.get('componenten'):
        print("  Geen data beschikbaar.")
        return

    for naam, details in result['componenten'].items():
        print(f"\n  {naam.upper()} (gewicht: {details['gewicht']})")
        print(f"    Score: {details['score']}/100 → bijdrage: {details['bijdrage']} punten")

        if naam == 'dekkingsgraad':
            print(f"    Records: {details['records']} → gewogen punten: {details['gewogen_punten']} / {details['verwacht']} verwacht")

        elif naam == 'seizoensspreiding':
            for seizoen, info in details.get('per_seizoen', {}).items():
                maanden_str = ', '.join(str(m) for m in info['maanden']) if info['maanden'] else '-'
                print(f"    {seizoen}: {info['dekking']}% (maanden: {maanden_str})")

        elif naam == 'consistentie':
            print(f"    Gaps (ontbrekend): {details['gaps']} kwartieren")

        elif naam == 'input_type':
            for interval, aantal in details.get('verdeling', {}).items():
                label = INTERVAL_SCORES.get(interval, '?')
                print(f"    {interval}: {aantal} records (score: {label}%)")

    print("\n" + "=" * 55)


# ============================================================
# STANDALONE TEST
# ============================================================

if __name__ == "__main__":
    import sys

    # Standalone test: geef het ImportBatchID als argument mee.
    #   python data_quality.py <import_batch_id>
    if len(sys.argv) < 2:
        print("Gebruik: python data_quality.py <import_batch_id>")
        sys.exit(1)

    import_batch_id = int(sys.argv[1])
    result = calculate_quality_score(import_batch_id)
    print_quality_report(result)
