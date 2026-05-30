# Energy-Truth — Python rapportgenerator

Dit is het Python-deel van Energy-Truth. Het neemt de slimme-meterdata van een klant, rekent uit of een thuisbatterij voor die klant interessant is, en maakt daar een leesbaar PDF-rapport van.

## Wat doet het, in gewone taal?

Per klant gebeurt er, in volgorde, het volgende:

1. **Data ophalen.** De meetgegevens van de klant (verbruik en teruglevering per kwartier) staan al in de database; de import-pipeline van het team schrijft ze daar weg. De worker leest ze rechtstreeks uit de database, strikt voor de batch die net is aangemeld. Er wordt geen CSV meer ingelezen.
2. **Datakwaliteit checken.** Klopt de data? Zijn er gaten? Hoe betrouwbaar is wat we hebben? Daar komt een rapportcijfer (0–100) uit, berekend over diezelfde batch-data.
3. **Periode bepalen.** We rekenen altijd met het laatst beschikbare jaar aan data van die batch (rolling year).
4. **Scenario's doorrekenen.** Voor elke combinatie van energieleverancier en batterij-strategie (zelfverbruik, dynamisch handelen, slimme mix, …) berekent het systeem wat de klant in dat jaar zou hebben betaald.
5. **Beste batterij kiezen.** Uit de catalogus van beschikbare thuisbatterijen wordt gerangschikt welke het beste uitkomt — op basis van terugverdientijd, netto opbrengst en kosten per kWh.
6. **PDF maken.** De resultaten worden samengevat in een klantvriendelijk rapport.

Eén Python-script (`worker.py`) start dit hele proces automatisch zodra er nieuwe data binnenkomt.

## Wat heb je nodig om het te draaien?

- Python 3.11 of nieuwer
- Een PostgreSQL database (het schema en de seed-data staan in de `sql/`-map elders in deze repo)
- Een paar standaard Python-pakketten: `psycopg2`, `pandas`, `numpy`, `reportlab`

## Hoe stel je het in?

De database-gegevens (host, gebruikersnaam, wachtwoord) zet je in environment variables. Een voorbeeld-template hiervoor staat in het project (niet in deze publieke map). Vraag een teamgenoot om de juiste waarden voor de test-omgeving.

## Hoe start je het?

```bash
python worker.py
```

Dat is alles. Het script blijft draaien, kijkt steeds of er nieuwe klanten in de wachtrij staan, en verwerkt ze één voor één.

## Wat zit er in deze map?

| Bestand | Waar is het voor? |
|---|---|
| `worker.py` | Het startpunt — pakt nieuwe opdrachten op en doorloopt de hele keten. |
| `data_quality.py` | Geeft de meetdata een betrouwbaarheidsscore (per batch). |
| `period_selector.py` | Bepaalt welk jaar aan data we gebruiken. |
| `scenario_engine.py` | Rekent alle combinaties van leverancier × batterij-strategie door. |
| `battery_simulator.py` | Simuleert kwartier voor kwartier hoe een batterij zich gedraagt. |
| `cost_calculator.py` | Rekent uit wat de klant betaalt — met en zonder batterij. |
| `battery_catalog.py` | Haalt de lijst beschikbare batterijen uit de database. |
| `battery_sizing.py` | Kiest welke batterij financieel het slimst is. |
| `report_generator.py` | Bouwt het uiteindelijke PDF-rapport. |
| `reference_data.py` | Haalt energieprijzen en provider-marges op. |
| `simulation_config.py` | De instellingen-container voor één klantberekening. |
| `db_connection.py` | Verbinding met de database. |
