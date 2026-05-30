"""
window_functions.py — Window function voor Energy-Truth (servercode).

Bevat de gapdetectie die de data-ingestie gebruikt om ontbrekende
kwartieren in de meterdata op te sporen.

Let op: dit bestand bevatte eerder een bredere set pandas-equivalenten
van SQL window functions (LAG, LEAD, SUM/AVG/COUNT/STDDEV OVER, RANK).
Die zijn verwijderd omdat de servercode ze niet gebruikt; de bewijslast
voor de LO4-module "Window functions SQL + Python" staat in het
betreffende bewijsstuk.

Gebruik:
    from window_functions import detect_gaps
    df['has_gap'] = detect_gaps(df, 'timestamp_from')
"""

import pandas as pd


# ---------------------------------------------------------------------------
# GAP DETECTION — Gapdetectie op timestamps (specifiek voor Energy-Truth)
# ---------------------------------------------------------------------------
def detect_gaps(
    df: pd.DataFrame,
    timestamp_column: str = "timestamp_from",
    expected_interval_minutes: int = 15,
) -> pd.Series:
    """
    Combineert een tijdverschilberekening (LAG via shift) met het verwachte
    interval om ontbrekende kwartieren te detecteren.

    Retourneert een boolean Series: True waar een gap groter is dan
    het verwachte interval.

    Voorbeelden:
        df['has_gap'] = detect_gaps(df, 'timestamp_from')
        gaps = df[df['has_gap']]  # alleen rijen na een gap
    """
    prev_ts = df[timestamp_column].shift(1)
    gap_minutes = (df[timestamp_column] - prev_ts).dt.total_seconds() / 60
    return gap_minutes > expected_interval_minutes
