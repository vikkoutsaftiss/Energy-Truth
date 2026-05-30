"""
battery_catalog.py — Catalog van thuisbatterijen ophalen uit de DB.

Werkt op de tabel `Markt_Product` (Categorie_Batterij = 'Batterij') zoals
uitgebreid via sql/migrations/001_uitbreiding_markt_product.sql.

Levert per actieve batterij een BatteryCatalogEntry op met alle
specs die nodig zijn voor de battery_sizing module:
  - BatteryConfig-equivalent (capaciteit, vermogen, efficiency)
  - Economische velden (prijs, installatiekosten)
  - Garantie-velden (kalendergarantie, cycli) voor GO/NOGO

Gebruik:
    from battery_catalog import get_battery_catalog, to_battery_config

    catalog = get_battery_catalog()
    for entry in catalog:
        battery_config = to_battery_config(entry)
        # ... voer simulatie uit met battery_config ...
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from db_connection import get_client
from simulation_config import BatteryConfig

# Defaults voor catalog-batterijen waar bepaalde velden in de DB ontbreken.
# Bij ontbreken wordt een sensible default toegepast in plaats van de
# batterij stil over te slaan.
DEFAULT_CATALOG_DOD_PCT = 0.90              # 90% van capaciteit als bruikbaar
DEFAULT_CATALOG_ROUND_TRIP_EFFICIENCY = 0.90  # LiFePO4 typische waarde


# ============================================================
# DATACLASS
# ============================================================

@dataclass
class BatteryCatalogEntry:
    """Eén rij uit Markt_Product, Categorie_Batterij = 'Batterij'."""

    id: int
    productnaam: str
    aanschafprijs: float
    capaciteit_kwh: float
    bruikbare_capaciteit_kwh: float
    gegarandeerde_laadcycli: float
    garantiejaren: float
    max_laden_kw: float
    max_ontladen_kw: float
    round_trip_efficiency: float
    installatiekosten_eur: float
    chemie: Optional[str]
    bron_url: Optional[str]
    foto_url: Optional[str] = None

    @property
    def laad_ontlaad_vermogen_kw(self) -> float:
        """Backwards-compatibele alias: het kleinste van de twee vermogens."""
        return min(self.max_laden_kw, self.max_ontladen_kw)

    @property
    def totale_investering_eur(self) -> float:
        """Aanschaf + installatie."""
        return float(self.aanschafprijs) + float(self.installatiekosten_eur or 0)

    @property
    def dod_pct(self) -> float:
        """Depth of Discharge percentage (bruikbaar / bruto)."""
        if not self.capaciteit_kwh:
            return 0.0
        return float(self.bruikbare_capaciteit_kwh) / float(self.capaciteit_kwh)

    @property
    def label(self) -> str:
        """Korte label voor logs/plots."""
        return f"{self.productnaam} ({self.capaciteit_kwh:.1f} kWh)"


# ============================================================
# CATALOG OPHALEN
# ============================================================

def get_battery_catalog(
    only_active: bool = True,
    min_capacity_kwh: Optional[float] = None,
    max_capacity_kwh: Optional[float] = None,
) -> list[BatteryCatalogEntry]:
    """
    Haal alle actieve thuisbatterijen op uit Markt_Product.

    Args:
        only_active: alleen rijen met Actief = TRUE (default True)
        min_capacity_kwh: optioneel ondergrens op capaciteit
        max_capacity_kwh: optioneel bovengrens op capaciteit

    Returns:
        Lijst met BatteryCatalogEntry, oplopend op capaciteit.
    """
    client = get_client()
    query = (
        client.table("Markt_Product")
        .select(
            "ID, ProductNaam, Aanschafprijs, Capaciteit_kWh, "
            "Bruikbare_CapaciteitkW, Gegarandeerde_laadcycli, "
            "garantiejaren, Max_Laden_kW, Max_Ontladen_kW, "
            "Round_Trip_Efficiency, Installatiekosten_EUR, "
            "Chemie, Bron_URL, Foto_URL"
        )
        .eq("Categorie_Batterij", "Batterij")
        .order("Capaciteit_kWh")
    )

    if only_active:
        query = query.eq("Actief", True)
    if min_capacity_kwh is not None:
        query = query.gte("Capaciteit_kWh", min_capacity_kwh)
    if max_capacity_kwh is not None:
        query = query.lte("Capaciteit_kWh", max_capacity_kwh)

    response = query.execute()
    records = response.data or []

    catalog = []
    for r in records:
        # Echt-verplichte specs: zonder deze kan de batterij niet worden gesimuleerd
        hard_required = [
            "Capaciteit_kWh",
            "Max_Laden_kW", "Max_Ontladen_kW",
            "garantiejaren", "Gegarandeerde_laadcycli",
            "Aanschafprijs",
        ]
        missing = [k for k in hard_required if r.get(k) is None]
        if missing:
            naam = r.get("ProductNaam") or f"Product {r.get('ID')}"
            print(f"  Batterij '{naam}' overgeslagen: ontbrekende velden {missing}")
            continue

        # Optionele specs met sensible defaults: geen reden om te skippen.
        # ERD-kolom is "Bruikbare_CapaciteitkW" (zonder underscore, met kW).
        # In Python en in de simulator blijven we het correct "kwh" noemen.
        bruikbaar = r.get("Bruikbare_CapaciteitkW")
        if bruikbaar is None:
            bruikbaar = float(r["Capaciteit_kWh"]) * DEFAULT_CATALOG_DOD_PCT
            naam = r.get("ProductNaam") or f"Product {r.get('ID')}"
            print(
                f"  '{naam}': Bruikbare_CapaciteitkW ontbreekt, default toegepast "
                f"({DEFAULT_CATALOG_DOD_PCT*100:.0f}% van "
                f"{float(r['Capaciteit_kWh']):.1f} kWh = {bruikbaar:.2f} kWh)"
            )

        rte = r.get("Round_Trip_Efficiency")
        if rte is None:
            rte = DEFAULT_CATALOG_ROUND_TRIP_EFFICIENCY
            naam = r.get("ProductNaam") or f"Product {r.get('ID')}"
            print(
                f"  '{naam}': Round_Trip_Efficiency ontbreekt, default toegepast "
                f"({DEFAULT_CATALOG_ROUND_TRIP_EFFICIENCY:.2f})"
            )

        catalog.append(BatteryCatalogEntry(
            id=int(r["ID"]),
            productnaam=r.get("ProductNaam") or f"Product {r['ID']}",
            aanschafprijs=float(r["Aanschafprijs"]),
            capaciteit_kwh=float(r["Capaciteit_kWh"]),
            bruikbare_capaciteit_kwh=float(bruikbaar),
            gegarandeerde_laadcycli=float(r["Gegarandeerde_laadcycli"]),
            garantiejaren=float(r["garantiejaren"]),
            max_laden_kw=float(r["Max_Laden_kW"]),
            max_ontladen_kw=float(r["Max_Ontladen_kW"]),
            round_trip_efficiency=float(rte),
            installatiekosten_eur=float(r.get("Installatiekosten_EUR") or 0),
            chemie=r.get("Chemie"),
            bron_url=r.get("Bron_URL"),
            foto_url=r.get("Foto_URL"),
        ))

    return catalog


# ============================================================
# CONVERSIE VANUIT BatteryConfig (config.json -> CatalogEntry)
# ============================================================

# Defaults voor sizing als de gebruiker ze niet opgeeft.
# Conservatief gekozen zodat geen GO ten onrechte uit afgegeven wordt.
DEFAULT_GARANTIEJAREN = 10
DEFAULT_GEGARANDEERDE_LAADCYCLI = 6000
DEFAULT_INSTALLATIEKOSTEN_EUR = 0
USER_BATTERY_ID = -1  # sentinel-id voor "Eigen batterij" uit config.json


def entry_from_battery_config(battery, label: Optional[str] = None) -> Optional[BatteryCatalogEntry]:
    """
    Maakt een synthetische BatteryCatalogEntry van een BatteryConfig
    (typisch uit config.json). Bedoeld om de eigen batterij van de
    gebruiker mee te kunnen nemen in battery_sizing.find_optimal_battery
    naast de officiele catalog.

    Args:
        battery: BatteryConfig (uit SimulationConfig.battery)
        label: optionele override voor productnaam

    Returns:
        BatteryCatalogEntry met id = USER_BATTERY_ID (-1), of None
        als de essentiele velden ontbreken (geen aanschafprijs of capaciteit).
    """
    # Essentieel: prijs en capaciteit moeten er zijn
    if battery.battery_price_eur is None or not battery.capacity_kwh:
        return None

    # Bruikbare capaciteit afleiden uit min/max SoC
    bruikbaar = battery.capacity_kwh * (battery.max_soc_pct - battery.min_soc_pct)

    # Round-trip eff = charge_eff * discharge_eff
    round_trip = float(battery.charge_efficiency) * float(battery.discharge_efficiency)

    # Naamgeving
    productnaam = label or battery.productnaam or "Eigen batterij (uit config)"

    # Defaults als sizing-velden niet ingevuld zijn
    garantiejaren = float(battery.garantiejaren or DEFAULT_GARANTIEJAREN)
    cycli = float(battery.gegarandeerde_laadcycli or DEFAULT_GEGARANDEERDE_LAADCYCLI)
    installatie = float(battery.installatiekosten_eur or DEFAULT_INSTALLATIEKOSTEN_EUR)

    return BatteryCatalogEntry(
        id=USER_BATTERY_ID,
        productnaam=productnaam,
        aanschafprijs=float(battery.battery_price_eur),
        capaciteit_kwh=float(battery.capacity_kwh),
        bruikbare_capaciteit_kwh=float(bruikbaar),
        gegarandeerde_laadcycli=cycli,
        garantiejaren=garantiejaren,
        max_laden_kw=float(battery.max_charge_kw),
        max_ontladen_kw=float(battery.max_discharge_kw),
        round_trip_efficiency=float(round_trip),
        installatiekosten_eur=installatie,
        chemie=battery.chemie,
        bron_url=None,
        foto_url=None,
    )


# ============================================================
# CONVERSIE NAAR BatteryConfig
# ============================================================

def to_battery_config(
    entry: BatteryCatalogEntry,
    min_soc_pct: Optional[float] = None,
    max_soc_pct: Optional[float] = None,
) -> BatteryConfig:
    """
    Converteer een catalog-entry naar een BatteryConfig die de
    battery_simulator kan gebruiken.

    Args:
        entry: BatteryCatalogEntry
        min_soc_pct: optionele override; default afgeleid uit DoD
        max_soc_pct: optionele override; default 1.0

    Returns:
        BatteryConfig
    """
    # DoD-bepaling: als bruikbaar < bruto, plaats de "verloren" capaciteit
    # symmetrisch tussen min en max SoC. Bij 90% DoD wordt min_soc = 5%
    # en max_soc = 95%. Tenzij expliciet overschreven.
    if min_soc_pct is None or max_soc_pct is None:
        if entry.dod_pct >= 0.999:
            default_min = 0.0
            default_max = 1.0
        else:
            slack = (1.0 - entry.dod_pct) / 2
            default_min = slack
            default_max = 1.0 - slack
        if min_soc_pct is None:
            min_soc_pct = default_min
        if max_soc_pct is None:
            max_soc_pct = default_max

    # Round-trip splitsen symmetrisch (zoals iLESS): eta_c = eta_d = sqrt(eta_rt)
    import math
    eta_rt = entry.round_trip_efficiency
    eta_half = math.sqrt(max(eta_rt, 0.0001))

    return BatteryConfig(
        capacity_kwh=entry.capaciteit_kwh,
        max_charge_kw=entry.max_laden_kw,
        max_discharge_kw=entry.max_ontladen_kw,
        charge_efficiency=eta_half,
        discharge_efficiency=eta_half,
        min_soc_pct=min_soc_pct,
        max_soc_pct=max_soc_pct,
        battery_price_eur=entry.aanschafprijs,
    )


# ============================================================
# CLI-TEST
# ============================================================

if __name__ == "__main__":
    print("=" * 70)
    print("  BATTERY CATALOG - DUMP")
    print("=" * 70)

    catalog = get_battery_catalog()
    if not catalog:
        print("  Geen actieve batterijen gevonden in Markt_Product.")
        print("  Run eerst de SQL migraties + seed.")
        raise SystemExit(1)

    print(f"\n  {len(catalog)} actieve batterijen gevonden:\n")
    header = (
        f"  {'Product':<38} "
        f"{'kWh':>5} "
        f"{'lad':>5} "
        f"{'ont':>5} "
        f"{'eff':>5} "
        f"{'gar':>5} "
        f"{'cycli':>7} "
        f"{'prijs':>7} "
        f"{'inst':>6}"
    )
    print(header)
    print("  " + "-" * (len(header) - 2))

    for e in catalog:
        print(
            f"  {e.productnaam[:36]:<38} "
            f"{e.capaciteit_kwh:>5.1f} "
            f"{e.max_laden_kw:>5.1f} "
            f"{e.max_ontladen_kw:>5.1f} "
            f"{e.round_trip_efficiency:>5.2f} "
            f"{e.garantiejaren:>5.1f} "
            f"{int(e.gegarandeerde_laadcycli):>7d} "
            f"{e.aanschafprijs:>7.0f} "
            f"{e.installatiekosten_eur:>6.0f}"
        )

    print("\n  --- BatteryConfig conversie test ---")
    sample = catalog[0]
    cfg = to_battery_config(sample)
    print(f"  {sample.label}")
    print(f"    capacity_kwh      = {cfg.capacity_kwh}")
    print(f"    max_charge_kw     = {cfg.max_charge_kw}")
    print(f"    charge_efficiency = {cfg.charge_efficiency:.4f}")
    print(f"    min_soc_pct       = {cfg.min_soc_pct:.4f}")
    print(f"    max_soc_pct       = {cfg.max_soc_pct:.4f}")
    print(f"    bruikbaar         = {cfg.usable_capacity_kwh:.2f} kWh")
