"""
period_selector.py -- Bepaalt de simulatieperiode (rolling year).

Regels (afspraak met Andre, 26 mei 2026):

1. Standaard wordt de simulatie altijd over de laatste 365 dagen
   gedraaid, gerekend vanaf de meest recente MeetDatumTijd in
   Verbruiksdata van de geclaimde ImportBatch.

2. Als er meer dan 365 dagen aan data zijn: alleen het laatste jaar
   wordt gebruikt. De oudere data blijft in de DB maar telt niet mee.

3. Als er minder dan 365 dagen zijn: alle beschikbare data wordt
   gebruikt. De betrouwbaarheidsscore krijgt dan een cap, conform de
   bestaande logica in data_quality.py (aantal seizoenen / 4 * 100).

Het oude config.json met start_date en end_date is voor productie
niet meer relevant. Lokaal testen kan nog wel met config.json door
expliciet een SimulationPeriod te overschrijven.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional


ROLLING_YEAR_DAYS = 365


@dataclass
class PeriodSelection:
    """Resultaat van bepaal_periode()."""

    start_date: datetime
    end_date: datetime
    days_available: int           # aantal dagen aan data tussen MIN en MAX
    days_used: int                # aantal dagen dat in de simulatie meedoet
    is_partial_year: bool         # True als minder dan 365 dagen beschikbaar

    @property
    def coverage_fraction(self) -> float:
        """0.0 - 1.0, voor cap op betrouwbaarheidsscore."""
        return min(self.days_used / ROLLING_YEAR_DAYS, 1.0)

    def summary(self) -> str:
        flag = " (partial)" if self.is_partial_year else ""
        return (
            f"Periode: {self.start_date:%Y-%m-%d} t/m {self.end_date:%Y-%m-%d}"
            f"{flag}, {self.days_used} dagen gebruikt"
        )


def bepaal_periode(
    conn,
    import_batch_id: int,
    rolling_days: int = ROLLING_YEAR_DAYS,
) -> Optional[PeriodSelection]:
    """
    Lees MIN en MAX MeetDatumTijd uit Verbruiksdata voor EEN ImportBatch
    via een directe SQL-query op een psycopg2-connectie.

    De rolling year wordt strikt afgeleid van de verbruiksdata van de
    geclaimde batch (ImportBatchID), niet van het hele gebouw. Meerdere
    uploads van hetzelfde gebouw lopen zo niet door elkaar.

    Returns:
        PeriodSelection, of None als er geen data is voor deze batch.
    """
    sql = """
        SELECT MIN("MeetDatumTijd") AS min_dt,
               MAX("MeetDatumTijd") AS max_dt
        FROM "Verbruiksdata" v
        WHERE v."ImportBatchID" = %s
    """
    with conn.cursor() as cur:
        cur.execute(sql, (import_batch_id,))
        row = cur.fetchone()

    if not row or row[0] is None or row[1] is None:
        return None

    min_dt, max_dt = row
    span_days = (max_dt - min_dt).days + 1  # inclusief beide eindpunten

    if span_days >= rolling_days:
        # Volledig jaar: knip op de laatste 365 dagen
        start = max_dt - timedelta(days=rolling_days - 1)
        end = max_dt
        return PeriodSelection(
            start_date=start,
            end_date=end,
            days_available=span_days,
            days_used=rolling_days,
            is_partial_year=False,
        )

    # Minder dan een jaar: alles gebruiken, maar wel als partial markeren
    return PeriodSelection(
        start_date=min_dt,
        end_date=max_dt,
        days_available=span_days,
        days_used=span_days,
        is_partial_year=True,
    )


# ---------------------------------------------------------------------------
# MAIN -- handmatig testen
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys
    from db_connection import get_psycopg2_connection  # nog te schrijven

    if len(sys.argv) < 2:
        print("Gebruik: python period_selector.py <import_batch_id>")
        sys.exit(1)

    import_batch_id = int(sys.argv[1])
    with get_psycopg2_connection() as conn:
        period = bepaal_periode(conn, import_batch_id)

    if period is None:
        print(f"Geen verbruiksdata gevonden voor ImportBatchID {import_batch_id}")
    else:
        print(period.summary())
