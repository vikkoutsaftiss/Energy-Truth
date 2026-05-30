"""
simulation_config.py — Configuratieklasse voor Energy-Truth.

Leest config.json in en biedt alle instellingen als object aan.
Dezelfde JSON-structuur wordt later door het FastAPI-endpoint gestuurd,
dus de backend-code verandert niet.

Gebruik:
    from simulation_config import SimulationConfig
    config = SimulationConfig.from_json("config.json")
    print(config.klant_id)
    print(config.battery.capacity_kwh)
    print(config.csv_file)
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List


@dataclass
class BatteryConfig:
    """
    Batterijconfiguratie — uit catalogus of handmatig.

    De extra sizing-velden (productnaam, garantiejaren, etc.) zijn
    optioneel en alleen relevant voor battery_sizing.py. Worden ze
    niet meegegeven, dan kunnen de defaults gebruikt worden of valt
    de sizing-tool terug op marktwaardes.
    """
    capacity_kwh: float
    max_charge_kw: float
    max_discharge_kw: float
    charge_efficiency: float = 0.95
    discharge_efficiency: float = 0.95
    min_soc_pct: float = 0.20
    max_soc_pct: float = 0.80
    battery_price_eur: Optional[float] = None  # aanschafprijs batterij (€)

    # --- Sizing-velden (optioneel) ---
    productnaam: Optional[str] = None
    installatiekosten_eur: Optional[float] = None
    garantiejaren: Optional[float] = None
    gegarandeerde_laadcycli: Optional[float] = None
    chemie: Optional[str] = None

    @property
    def usable_capacity_kwh(self) -> float:
        """Bruikbare capaciteit (tussen min en max SoC)."""
        return self.capacity_kwh * (self.max_soc_pct - self.min_soc_pct)

    @property
    def max_charge_per_quarter_kwh(self) -> float:
        """Max laden per kwartier (kW × 0.25 uur). Efficiency wordt APART
        toegepast in battery_simulator bij de SoC-update."""
        return self.max_charge_kw * 0.25

    @property
    def max_discharge_per_quarter_kwh(self) -> float:
        """Max ontladen per kwartier (kW × 0.25 uur). Efficiency wordt APART
        toegepast in battery_simulator bij de SoC-update."""
        return self.max_discharge_kw * 0.25


@dataclass
class SimulationPeriod:
    """Simulatieperiode."""
    start_date: str  # "2025-01-01"
    end_date: str    # "2025-12-31"


@dataclass
class SimulationConfig:
    """
    Hoofdconfiguratie voor een Energy-Truth simulatie.

    Bevat klant_id, batterij-instellingen, simulatieperiode,
    CSV-bestand en aanbieder-selectie.
    """
    klant_id: int
    battery: BatteryConfig
    simulation: SimulationPeriod
    csv_file: Optional[str] = None
    battery_id: Optional[str] = None  # UUID uit catalogus (indien gekozen)
    import_batch_id: Optional[int] = None  # geclaimde ImportBatch (worker-scope)
    providers: str = "all"            # "all" of lijst van codes

    @classmethod
    def from_json(cls, filepath: str) -> "SimulationConfig":
        """
        Laadt configuratie uit een JSON-bestand.

        Parameters:
            filepath    Pad naar config.json

        Returns:
            SimulationConfig object
        """
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"Config bestand niet gevonden: {filepath}")

        with open(path, "r") as f:
            data = json.load(f)

        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: dict) -> "SimulationConfig":
        """
        Maakt configuratie aan vanuit een dictionary.
        Dezelfde structuur als het FastAPI-endpoint later stuurt.

        Parameters:
            data    Dictionary met configuratie (uit JSON of API-request)

        Returns:
            SimulationConfig object
        """
        # Batterij: uit catalogus (battery_id) of handmatig (battery dict)
        battery_data = data.get("battery", {})
        battery = BatteryConfig(
            capacity_kwh=battery_data.get("capacity_kwh", 10),
            max_charge_kw=battery_data.get("max_charge_kw", 2.5),
            max_discharge_kw=battery_data.get("max_discharge_kw", 3.68),
            charge_efficiency=battery_data.get("charge_efficiency", 0.95),
            discharge_efficiency=battery_data.get("discharge_efficiency", 0.95),
            min_soc_pct=battery_data.get("min_soc_pct", 0.20),
            max_soc_pct=battery_data.get("max_soc_pct", 0.80),
            battery_price_eur=battery_data.get("battery_price_eur"),
            # Sizing-velden (optioneel, alleen gebruikt door battery_sizing.py)
            productnaam=battery_data.get("productnaam"),
            installatiekosten_eur=battery_data.get("installatiekosten_eur"),
            garantiejaren=battery_data.get("garantiejaren"),
            gegarandeerde_laadcycli=battery_data.get("gegarandeerde_laadcycli"),
            chemie=battery_data.get("chemie"),
        )

        # Simulatieperiode
        sim_data = data.get("simulation", {})
        simulation = SimulationPeriod(
            start_date=sim_data.get("start_date", "2025-01-01"),
            end_date=sim_data.get("end_date", "2025-12-31"),
        )

        return cls(
            klant_id=int(data["klant_id"]),
            battery=battery,
            simulation=simulation,
            csv_file=data.get("csv_file"),
            battery_id=data.get("battery_id"),
            import_batch_id=data.get("import_batch_id"),
            providers=data.get("providers", "all"),
        )

    def summary(self) -> str:
        """Geeft een leesbare samenvatting van de configuratie."""
        lines = [
            "=== Simulatie Configuratie ===",
            f"Klant ID:       {self.klant_id}",
            f"CSV bestand:    {self.csv_file or '(geen)'}",
            f"Periode:        {self.simulation.start_date} t/m {self.simulation.end_date}",
            f"Aanbieders:     {self.providers}",
            f"",
            f"--- Batterij ---",
            f"Capaciteit:     {self.battery.capacity_kwh} kWh (bruikbaar: {self.battery.usable_capacity_kwh} kWh)",
            f"Laden:          {self.battery.max_charge_kw} kW ({self.battery.max_charge_per_quarter_kwh:.3f} kWh/kwartier)",
            f"Ontladen:       {self.battery.max_discharge_kw} kW ({self.battery.max_discharge_per_quarter_kwh:.3f} kWh/kwartier)",
            f"Efficiency:     laden {self.battery.charge_efficiency}, ontladen {self.battery.discharge_efficiency}",
            f"SoC bereik:     {self.battery.min_soc_pct*100:.0f}% - {self.battery.max_soc_pct*100:.0f}%",
            f"Aanschafprijs:  {'€ ' + f'{self.battery.battery_price_eur:,.2f}' if self.battery.battery_price_eur else '(niet opgegeven)'}",
        ]
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# MAIN — Direct uitvoeren voor testen
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys

    filepath = sys.argv[1] if len(sys.argv) > 1 else "config.json"
    print(f"Config laden uit: {filepath}\n")

    config = SimulationConfig.from_json(filepath)
    print(config.summary())
