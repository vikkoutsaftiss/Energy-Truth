"""
data_ingestion.py — CSV-inlader voor Energy-Truth.

Leest slimme-meter CSV-bestanden in, verwerkt ze tot schone 15-min data,
en schrijft ze naar de meter_readings tabel in Supabase.

Werkt altijd via config.json (of een SimulationConfig object):
    - user_id wordt meegegeven bij elke import
    - duplicaatdetectie voorkomt dubbele records
    - bestaande data voor dezelfde timestamps wordt overgeslagen

Ondersteunde CSV-formaten:
    Formaat A (Enexis/standaard):  From, To, Levering, Teruglevering (kWh)
    Formaat B (P1/HomeWizard):     time, Import T1 kWh, Import T2 kWh, Export T1 kWh, Export T2 kWh, ...

    Nieuwe formaten kunnen worden toegevoegd in _standardize_columns().
    Onbekende formaten geven een duidelijke foutmelding.

Verwerkingsstappen:
    1. CSV inlezen, formaat herkennen en kolommen standaardiseren
    2. Intervaldetectie (15-min, 60-min of 24-uurs)
    3. Uur-/dagdata opsplitsen naar kwartierdata (indien nodig)
    4. Validatie (negatieve waarden, logische checks)
    5. Gapdetectie (ontbrekende kwartieren rapporteren, NIET interpoleren)
    6. Duplicaatdetectie (bestaande timestamps overslaan)
    7. Naar Supabase schrijven

    NB: Gaps worden NIET geïnterpoleerd. De CSV bevat nettoverbruik per
    interval — een ontbrekend kwartier betekent onbekend verbruik.
    Interpoleren zou nepdata creëren. Gaps worden overgeslagen in de
    simulatie en verlagen de betrouwbaarheidsscore.

Gebruik:
    from data_ingestion import ingest_csv
    result = ingest_csv("config.json")
"""

import pandas as pd
import numpy as np
from pathlib import Path
from window_functions import detect_gaps, rolling_avg
from simulation_config import SimulationConfig
from db_connection import get_client


# ---------------------------------------------------------------------------
# HOOFDFUNCTIE — CSV inladen via config en naar database schrijven
# ---------------------------------------------------------------------------
def ingest_csv(config_path: str = "config.json") -> dict:
    """
    Volledige import-pipeline: config laden → CSV verwerken → naar Supabase.

    Parameters:
        config_path     Pad naar config.json

    Returns:
        dict met samenvatting (records, nieuwe/overgeslagen, etc.)
    """
    # Config laden
    config = SimulationConfig.from_json(config_path)

    if not config.csv_file:
        raise ValueError("Geen csv_file opgegeven in config.json")

    print(f"Config geladen — user_id: {config.user_id}")
    print(f"CSV bestand: {config.csv_file}")

    # Stap 1-5: CSV inlezen en verwerken
    df = load_meter_csv(config.csv_file, user_id=config.user_id)
    summary = get_ingestion_summary(df)

    print(f"\nVerwerkt: {summary['total_records']} records")
    print(f"Periode: {summary['date_range'][0]} t/m {summary['date_range'][1]}")
    print(f"Records uit opsplitsing: {summary.get('records_from_split', 0)}")
    print(f"Gaps gedetecteerd: {summary.get('gaps_detected', 0)}")

    # Stap 6-7: Duplicaatdetectie + naar database schrijven
    db_result = save_to_database(df, config.user_id)

    summary.update(db_result)
    return summary


# ---------------------------------------------------------------------------
# CSV VERWERKING (stap 1-5)
# ---------------------------------------------------------------------------
def load_meter_csv(filepath: str, user_id: str = None) -> pd.DataFrame:
    """
    Laadt een slimme-meter CSV en retourneert een schoon 15-min DataFrame.

    Parameters:
        filepath    Pad naar het CSV-bestand.
        user_id     UUID van de gebruiker (uit config.json).

    Returns:
        DataFrame met kolommen:
            - timestamp_from (datetime)
            - timestamp_to (datetime)
            - consumption_kwh (float)
            - feed_in_kwh (float)
            - is_interpolated (bool)
            - original_interval (str)
            - user_id (str)
    """
    # Stap 1: CSV inlezen
    df = _read_csv(filepath)

    # Stap 2: Intervaldetectie
    interval = _detect_interval(df)
    df["original_interval"] = interval

    # Stap 3: Uur- of dagdata opsplitsen (indien nodig)
    if interval == "1440min":
        print(f"  Dagdata gedetecteerd — {len(df)} dagen → {len(df) * 96} kwartieren")
        df = _split_daily_to_quarters(df)
    elif interval == "60min":
        df = _split_hourly_to_quarters(df)

    # Stap 4: Validatie (na opsplitsing, zodat drempels kloppen voor kwartierdata)
    df = _validate_data(df)

    # Stap 5: Gapdetectie (alleen detecteren + rapporteren, NIET interpoleren)
    # Reden: CSV bevat nettoverbruik per interval, geen cumulatieve meterstanden.
    # Een ontbrekend kwartier betekent onbekend verbruik — interpoleren geeft nepdata.
    # Gaps worden overgeslagen in de simulatie en verlagen de betrouwbaarheidsscore.
    df = _detect_and_report_gaps(df)

    # User ID toevoegen
    if user_id:
        df["user_id"] = user_id

    # Sorteren en opschonen
    df = df.sort_values("timestamp_from").reset_index(drop=True)

    return df


# ---------------------------------------------------------------------------
# DATABASE SCHRIJVEN (stap 6-7)
# ---------------------------------------------------------------------------
def save_to_database(df: pd.DataFrame, user_id: str) -> dict:
    """
    Schrijft meterdata naar Supabase met duplicaatdetectie.

    Controleert welke timestamps al bestaan voor deze user_id.
    Schrijft alleen nieuwe records.

    Returns:
        dict met: new_records, skipped_records, total_in_db
    """
    client = get_client()

    # Stap 6: Bestaande timestamps ophalen voor deze user
    print(f"\nDuplicaatcheck voor user {user_id}...")
    existing = _get_existing_timestamps(client, user_id)
    print(f"  Bestaande records in database: {len(existing)}")

    # Filter: alleen rijen met timestamps die nog niet bestaan
    df["ts_key"] = df["timestamp_from"].dt.strftime("%Y-%m-%dT%H:%M:%S")
    new_rows = df[~df["ts_key"].isin(existing)].copy()
    skipped = len(df) - len(new_rows)

    print(f"  Nieuwe records: {len(new_rows)}")
    print(f"  Overgeslagen (duplicaat): {skipped}")

    if len(new_rows) == 0:
        print("\nGeen nieuwe data om te schrijven.")
        return {
            "new_records": 0,
            "skipped_records": skipped,
            "total_in_db": len(existing),
        }

    # Stap 7: Naar database schrijven (in batches van 500)
    records = _prepare_records(new_rows)
    batch_size = 500
    total_written = 0

    print(f"\nSchrijven naar database ({len(records)} records)...")
    for i in range(0, len(records), batch_size):
        batch = records[i : i + batch_size]
        try:
            client.table("meter_readings").insert(batch).execute()
            total_written += len(batch)
            print(f"  Batch {i // batch_size + 1}: {len(batch)} records geschreven")
        except Exception as e:
            print(f"  ❌ Fout bij batch {i // batch_size + 1}: {e}")
            break

    total_in_db = len(existing) + total_written
    print(f"\n✅ Klaar! Totaal in database: {total_in_db} records voor deze user")

    return {
        "new_records": total_written,
        "skipped_records": skipped,
        "total_in_db": total_in_db,
    }


def _get_existing_timestamps(client, user_id: str) -> set:
    """
    Haalt alle bestaande timestamp_from waarden op voor een user.
    Retourneert een set van timestamp-strings voor snelle lookup.
    """
    existing = set()
    offset = 0
    page_size = 1000

    while True:
        result = (
            client.table("meter_readings")
            .select("timestamp_from")
            .eq("user_id", user_id)
            .range(offset, offset + page_size - 1)
            .execute()
        )
        if not result.data:
            break

        for row in result.data:
            # Normaliseer timestamp voor vergelijking
            ts = row["timestamp_from"]
            # Verwijder timezone info voor vergelijking
            if "+" in ts:
                ts = ts.split("+")[0]
            if "T" in ts:
                existing.add(ts)

        if len(result.data) < page_size:
            break
        offset += page_size

    return existing


def _prepare_records(df: pd.DataFrame) -> list:
    """Zet DataFrame om naar een lijst van dicts voor Supabase insert."""
    records = []
    for _, row in df.iterrows():
        records.append({
            "user_id": row["user_id"],
            "timestamp_from": row["timestamp_from"].isoformat(),
            "timestamp_to": row["timestamp_to"].isoformat(),
            "consumption_kwh": round(float(row["consumption_kwh"]), 6),
            "feed_in_kwh": round(float(row["feed_in_kwh"]), 6),
            "is_interpolated": bool(row["is_interpolated"]),
            "original_interval": row["original_interval"],
        })
    return records


# ---------------------------------------------------------------------------
# CSV VERWERKING — Interne functies
# ---------------------------------------------------------------------------
def _parse_timestamps(series: pd.Series) -> pd.Series:
    """
    Parst timestamps uit diverse formaten:
        - ISO: 2025-01-13 00:00 (YYYY-MM-DD)
        - NL:  01/11/2025 00:00 (DD/MM/YYYY)
        - US:  11/01/2025 00:00 (MM/DD/YYYY)

    Probeert eerst ISO8601, dan mixed met dayfirst.
    """
    # Probeer ISO8601 eerst (meest betrouwbaar)
    try:
        return pd.to_datetime(series, format="ISO8601")
    except (ValueError, TypeError):
        pass

    # Probeer mixed formaat met dayfirst (voor NL exports: DD/MM/YYYY)
    try:
        return pd.to_datetime(series, format="mixed", dayfirst=True)
    except (ValueError, TypeError):
        pass

    # Laatste poging: laat pandas het zelf uitzoeken
    return pd.to_datetime(series, infer_datetime_format=True)


def _read_csv(filepath: str) -> pd.DataFrame:
    """Leest de CSV in, detecteert het formaat en standaardiseert kolomnamen."""
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"CSV-bestand niet gevonden: {filepath}")

    # Probeer komma als scheidingsteken, anders puntkomma
    try:
        df = pd.read_csv(path, sep=",")
        if len(df.columns) < 3:
            df = pd.read_csv(path, sep=";")
    except Exception:
        df = pd.read_csv(path, sep=";")

    # Formaat herkennen en standaardiseren
    df = _standardize_columns(df)

    # Timestamps parsen — automatisch formaat detecteren
    df["timestamp_from"] = _parse_timestamps(df["timestamp_from"])

    # timestamp_to: als die er niet is (formaat B), bereken uit interval
    if "timestamp_to" not in df.columns:
        # Detecteer interval uit eerste twee timestamps
        if len(df) >= 2:
            diff = (df["timestamp_from"].iloc[1] - df["timestamp_from"].iloc[0])
            df["timestamp_to"] = df["timestamp_from"] + diff
        else:
            df["timestamp_to"] = df["timestamp_from"] + pd.Timedelta(minutes=15)
    else:
        df["timestamp_to"] = _parse_timestamps(df["timestamp_to"])

    # Zorg dat numerieke kolommen floats zijn
    df["consumption_kwh"] = pd.to_numeric(df["consumption_kwh"], errors="coerce").fillna(0.0)
    df["feed_in_kwh"] = pd.to_numeric(df["feed_in_kwh"], errors="coerce").fillna(0.0)

    # Initialiseer tracking-kolom
    df["is_interpolated"] = False

    # Validatie wordt later gedraaid in load_meter_csv() (na opsplitsing)
    return df


def _validate_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Valideert de ingeladen data en geeft waarschuwingen bij problemen.

    Checks:
        1. Geen negatieve waarden voor verbruik/teruglevering
        2. Timestamps op chronologische volgorde
        3. Geen extreem hoge waarden (>10 kWh per kwartier)
        4. timestamp_from < timestamp_to
    """
    issues = []

    # Check 1: Negatieve waarden → zet op 0
    neg_consumption = (df["consumption_kwh"] < 0).sum()
    neg_feed_in = (df["feed_in_kwh"] < 0).sum()
    if neg_consumption > 0:
        issues.append(f"  ⚠️  {neg_consumption} negatieve verbruikswaarden → op 0 gezet")
        df.loc[df["consumption_kwh"] < 0, "consumption_kwh"] = 0.0
    if neg_feed_in > 0:
        issues.append(f"  ⚠️  {neg_feed_in} negatieve terugleverwaarden → op 0 gezet")
        df.loc[df["feed_in_kwh"] < 0, "feed_in_kwh"] = 0.0

    # Check 2: Chronologische volgorde
    df = df.sort_values("timestamp_from").reset_index(drop=True)

    # Check 3: Extreem hoge waarden (>10 kWh per 15 min = >40 kW gemiddeld)
    extreme_consumption = (df["consumption_kwh"] > 10).sum()
    extreme_feed_in = (df["feed_in_kwh"] > 10).sum()
    if extreme_consumption > 0:
        issues.append(f"  ⚠️  {extreme_consumption} records met verbruik >10 kWh/kwartier (ongewoon hoog)")
    if extreme_feed_in > 0:
        issues.append(f"  ⚠️  {extreme_feed_in} records met teruglevering >10 kWh/kwartier (ongewoon hoog)")

    # Check 4: timestamp_from < timestamp_to
    invalid_ts = (df["timestamp_from"] >= df["timestamp_to"]).sum()
    if invalid_ts > 0:
        issues.append(f"  ⚠️  {invalid_ts} records waar timestamp_from >= timestamp_to → verwijderd")
        df = df[df["timestamp_from"] < df["timestamp_to"]].reset_index(drop=True)

    # Rapporteer
    if issues:
        print("\nValidatie:")
        for issue in issues:
            print(issue)
    else:
        print("\n  ✅ Validatie OK — geen problemen gevonden")

    return df


def _standardize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Herkent verschillende CSV-formaten en standaardiseert ze.

    Ondersteunde formaten:
        A) Enexis/standaard: From, To, Levering, Teruglevering (kWh)
        B) P1/HomeWizard:    time, Import T1 kWh, Import T2 kWh, Export T1 kWh, Export T2 kWh, ...
        C) Varianten:        Van/Tot, Consumption/Feed-in, etc.

    Nieuwe formaten: voeg een detectie-blok toe in deze functie.
    """
    col_lower_map = {col: col.strip().lower() for col in df.columns}

    # --- Detectie: welk formaat is dit? ---
    detected_format = _detect_csv_format(col_lower_map)
    print(f"  CSV-formaat gedetecteerd: {detected_format}")

    if detected_format == "A_standard":
        df = _standardize_format_a(df, col_lower_map)
    elif detected_format == "B_t1t2":
        df = _standardize_format_b(df, col_lower_map)
    else:
        raise ValueError(
            f"CSV-formaat niet herkend.\n"
            f"Gevonden kolommen: {list(df.columns)}\n\n"
            f"Ondersteunde formaten:\n"
            f"  A) From, To, Levering, Teruglevering (kWh)\n"
            f"  B) time, Import T1 kWh, Import T2 kWh, Export T1 kWh, Export T2 kWh\n\n"
            f"Controleer je CSV-bestand of neem contact op met het team."
        )

    # Valideer dat alle vereiste kolommen aanwezig zijn
    required = {"timestamp_from", "consumption_kwh", "feed_in_kwh"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Na standaardisatie ontbreken kolommen: {missing}")

    return df


def _detect_csv_format(col_lower_map: dict) -> str:
    """
    Detecteert het CSV-formaat op basis van kolomnamen.

    Returns:
        'A_standard' — Enexis/standaard (From/To/Levering/Teruglevering)
        'B_t1t2'     — P1/HomeWizard (time/Import T1/T2/Export T1/T2)
        'unknown'    — Niet herkend
    """
    lower_cols = set(col_lower_map.values())

    # Formaat B: T1/T2 kolommen (P1-monitor, HomeWizard, etc.)
    has_import_t1 = any("import" in c and "t1" in c for c in lower_cols)
    has_export_t1 = any("export" in c and "t1" in c for c in lower_cols)
    has_time = any(c in ("time", "timestamp", "datetime") for c in lower_cols)
    if has_import_t1 and has_export_t1 and has_time:
        return "B_t1t2"

    # Formaat A: Standaard (From/To of Van/Tot + Levering + Teruglevering)
    has_from = any(c in ("from", "van", "vanaf", "start", "timestamp_from") for c in lower_cols)
    has_levering = any("levering" in c and "terug" not in c for c in lower_cols)
    has_teruglevering = any("teruglevering" in c or ("feed" in c and "in" in c) for c in lower_cols)
    has_consumption = any(c in ("consumption", "verbruik") for c in lower_cols)
    if has_from and (has_levering or has_consumption):
        return "A_standard"

    return "unknown"


def _standardize_format_a(df: pd.DataFrame, col_lower_map: dict) -> pd.DataFrame:
    """
    Formaat A: Enexis/standaard.
    Kolommen: From, To, Levering, Teruglevering (kWh)
    """
    column_map = {}
    for col, col_lower in col_lower_map.items():
        if col_lower in ("from", "van", "vanaf", "timestamp_from", "start"):
            column_map[col] = "timestamp_from"
        elif col_lower in ("to", "tot", "timestamp_to", "end", "eind"):
            column_map[col] = "timestamp_to"
        elif "levering" in col_lower and "terug" not in col_lower:
            column_map[col] = "consumption_kwh"
        elif "teruglevering" in col_lower or ("feed" in col_lower and "in" in col_lower):
            column_map[col] = "feed_in_kwh"
        elif col_lower in ("consumption", "verbruik"):
            column_map[col] = "consumption_kwh"

    df = df.rename(columns=column_map)

    # Als feed_in_kwh ontbreekt, zet op 0 (geen zonnepanelen)
    if "feed_in_kwh" not in df.columns:
        df["feed_in_kwh"] = 0.0

    return df


def _standardize_format_b(df: pd.DataFrame, col_lower_map: dict) -> pd.DataFrame:
    """
    Formaat B: P1-monitor / HomeWizard.
    Kolommen: time, Import T1 kWh, Import T2 kWh, Export T1 kWh, Export T2 kWh, [L1/L2/L3 max W]

    Detecteert automatisch of waarden cumulatieve meterstanden zijn
    (monotoon stijgend) of intervalverbruik. Bij cumulatief worden de
    waarden omgezet naar verbruik per interval via diff().

    T1 + T2 worden opgeteld (bij dynamisch tarief maakt dal/piek niet uit).
    L1/L2/L3 fase-vermogen wordt genegeerd.
    timestamp_to wordt berekend uit het interval.
    """
    # Vind de juiste kolommen
    time_col = None
    import_cols = []
    export_cols = []

    for col, col_lower in col_lower_map.items():
        if col_lower in ("time", "timestamp", "datetime"):
            time_col = col
        elif "import" in col_lower and "kwh" in col_lower:
            import_cols.append(col)
        elif "export" in col_lower and "kwh" in col_lower:
            export_cols.append(col)
        # L1/L2/L3 max W kolommen worden genegeerd

    if not time_col:
        raise ValueError("Formaat B: 'time' kolom niet gevonden")
    if not import_cols:
        raise ValueError("Formaat B: geen 'Import ... kWh' kolommen gevonden")

    # Zorg dat numerieke kolommen floats zijn
    for col in import_cols + export_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    # Tel T1 + T2 (+ eventueel T3, T4) op
    df["timestamp_from"] = df[time_col]
    import_total = df[import_cols].sum(axis=1)
    export_total = df[export_cols].sum(axis=1) if export_cols else pd.Series(0.0, index=df.index)

    # Detecteer of data cumulatief is (meterstanden) of intervalverbruik
    is_cumulative = _is_cumulative(import_total)

    if is_cumulative:
        print("  Cumulatieve meterstanden gedetecteerd → omzetten naar verbruik via diff()")
        df["consumption_kwh"] = import_total.diff()
        df["feed_in_kwh"] = export_total.diff()

        # Eerste rij heeft NaN door diff() → verwijderen
        df = df.iloc[1:].copy()

        # Negatieve diffs kunnen voorkomen bij meterwissel → op 0 zetten
        df.loc[df["consumption_kwh"] < 0, "consumption_kwh"] = 0.0
        df.loc[df["feed_in_kwh"] < 0, "feed_in_kwh"] = 0.0

        print(f"  Verbruik: {df['consumption_kwh'].sum():.0f} kWh | "
              f"Teruglevering: {df['feed_in_kwh'].sum():.0f} kWh")
    else:
        print("  Intervalverbruik gedetecteerd (geen cumulatieve standen)")
        df["consumption_kwh"] = import_total
        df["feed_in_kwh"] = export_total

    # Verwijder originele kolommen die we niet meer nodig hebben
    cols_to_keep = ["timestamp_from", "consumption_kwh", "feed_in_kwh"]
    df = df[cols_to_keep].copy()

    return df


def _is_cumulative(series: pd.Series) -> bool:
    """
    Detecteert of een reeks cumulatieve meterstanden bevat.

    Heuristiek:
      1. Waarden zijn (bijna) monotoon niet-dalend (>95% van de diffs >= 0)
      2. Laatste waarde is veel groter dan het gemiddelde verschil
         (cumulatief: 7000 vs dagverbruik: 18)

    Returns:
        True als de data cumulatief lijkt, False bij intervalverbruik
    """
    if len(series) < 3:
        return False

    diffs = series.diff().dropna()

    # Check 1: bijna alle diffs zijn >= 0 (stijgend)
    pct_non_negative = (diffs >= 0).mean()
    if pct_non_negative < 0.90:
        return False

    # Check 2: eerste waarde >> gemiddeld verschil
    # Bij cumulatief: eerste waarde is bijv. 5000, verschil is bijv. 18
    # Bij interval: eerste waarde is bijv. 18, verschil is bijv. 0.5
    first_value = series.iloc[0]
    avg_diff = diffs[diffs > 0].mean() if (diffs > 0).any() else 0

    if avg_diff > 0 and first_value > avg_diff * 10:
        return True

    return False


def _detect_interval(df: pd.DataFrame) -> str:
    """
    Detecteert of de data 15-min, 60-min of 24-uurs intervallen heeft.

    Returns:
        '15min', '60min' of '1440min' (dagdata)
    """
    intervals = (df["timestamp_to"] - df["timestamp_from"]).dt.total_seconds() / 60
    most_common = intervals.mode().iloc[0]

    if most_common <= 20:
        return "15min"
    elif most_common <= 65:
        return "60min"
    elif most_common <= 1500:
        return "1440min"
    else:
        raise ValueError(
            f"Onverwacht interval: {most_common} minuten. Verwacht: 15, 60 of 1440 (dag)."
        )


def _split_hourly_to_quarters(df: pd.DataFrame) -> pd.DataFrame:
    """Splitst 60-min records op in 4 gelijke 15-min records."""
    rows = []
    for _, row in df.iterrows():
        quarter_consumption = row["consumption_kwh"] / 4
        quarter_feed_in = row["feed_in_kwh"] / 4

        for i in range(4):
            offset = pd.Timedelta(minutes=15 * i)
            rows.append({
                "timestamp_from": row["timestamp_from"] + offset,
                "timestamp_to": row["timestamp_from"] + offset + pd.Timedelta(minutes=15),
                "consumption_kwh": quarter_consumption,
                "feed_in_kwh": quarter_feed_in,
                "is_interpolated": True,
                "original_interval": "60min",
            })

    return pd.DataFrame(rows)


def _split_daily_to_quarters(df: pd.DataFrame) -> pd.DataFrame:
    """
    Splitst 24-uurs (dag) records op in 96 gelijke 15-min records.

    Elke kWh-waarde wordt door 96 gedeeld (gelijkmatige verdeling).
    is_interpolated = True omdat de kwartierwaarden geschat zijn.
    original_interval = '1440min' zodat de data_quality score
    het verschil kan zien (lagere score dan uurdata of kwartierdata).
    """
    rows = []
    for _, row in df.iterrows():
        quarter_consumption = row["consumption_kwh"] / 96
        quarter_feed_in = row["feed_in_kwh"] / 96

        for i in range(96):
            offset = pd.Timedelta(minutes=15 * i)
            rows.append({
                "timestamp_from": row["timestamp_from"] + offset,
                "timestamp_to": row["timestamp_from"] + offset + pd.Timedelta(minutes=15),
                "consumption_kwh": round(quarter_consumption, 6),
                "feed_in_kwh": round(quarter_feed_in, 6),
                "is_interpolated": True,
                "original_interval": "1440min",
            })

    return pd.DataFrame(rows)


def _detect_and_report_gaps(df: pd.DataFrame) -> pd.DataFrame:
    """
    Detecteert ontbrekende 15-min intervallen en rapporteert ze.

    NIET interpoleren: de CSV bevat nettoverbruik per interval, geen
    cumulatieve meterstanden. Een ontbrekend kwartier = onbekend verbruik.
    Interpoleren zou nepdata creëren die eruitziet als echte metingen.

    Gaps worden:
        - Gedetecteerd en gerapporteerd (aantal + tijdstippen)
        - Overgeslagen in de simulatie (geen kosten berekend)
        - Meegenomen in de betrouwbaarheidsscore (lagere score)
    """
    df = df.sort_values("timestamp_from").reset_index(drop=True)
    df["has_gap"] = detect_gaps(df, "timestamp_from", expected_interval_minutes=15)

    gap_rows = df[df["has_gap"]].copy()

    if len(gap_rows) == 0:
        print("  ✅ Geen gaps gedetecteerd — data is aaneengesloten")
    else:
        # Tel het totaal aantal ontbrekende kwartieren
        total_missing = 0
        for idx in gap_rows.index:
            if idx == 0:
                continue
            prev_ts = df.loc[idx - 1, "timestamp_to"]
            curr_ts = df.loc[idx, "timestamp_from"]
            missing = int((curr_ts - prev_ts).total_seconds() / 900)  # 900s = 15min
            total_missing += missing

        print(f"  ⚠️  {len(gap_rows)} gap(s) gedetecteerd — {total_missing} kwartieren ontbreken")
        print(f"     Eerste gap: na {gap_rows.iloc[0]['timestamp_from']}")
        if len(gap_rows) > 1:
            print(f"     Laatste gap: na {gap_rows.iloc[-1]['timestamp_from']}")

    df = df.drop(columns=["has_gap"], errors="ignore")
    return df


# ---------------------------------------------------------------------------
# HULPFUNCTIES
# ---------------------------------------------------------------------------
def get_ingestion_summary(df: pd.DataFrame) -> dict:
    """Geeft een samenvatting van de ingeladen data."""
    return {
        "total_records": len(df),
        "date_range": (
            df["timestamp_from"].min().strftime("%Y-%m-%d"),
            df["timestamp_from"].max().strftime("%Y-%m-%d"),
        ),
        "original_interval": df["original_interval"].iloc[0] if "original_interval" in df.columns else "unknown",
        "records_from_split": int(df["is_interpolated"].sum()) if "is_interpolated" in df.columns else 0,
        "total_consumption_kwh": round(df["consumption_kwh"].sum(), 2),
        "total_feed_in_kwh": round(df["feed_in_kwh"].sum(), 2),
        "coverage_days": (df["timestamp_from"].max() - df["timestamp_from"].min()).days,
    }


# ---------------------------------------------------------------------------
# MAIN — Direct uitvoeren
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys

    config_path = sys.argv[1] if len(sys.argv) > 1 else "config.json"
    result = ingest_csv(config_path)

    print(f"\n=== Resultaat ===")
    print(f"Nieuwe records:     {result['new_records']}")
    print(f"Overgeslagen:       {result['skipped_records']}")
    print(f"Totaal in database: {result['total_in_db']}")
