# Energy-Truth — Python rapportgenerator

Dit is het Python-deel van Energy-Truth. Het neemt de slimme-meterdata van een klant, rekent uit of een thuisbatterij voor die klant interessant is, en maakt daar een leesbaar PDF-rapport van.

## Wat doet het, in gewone taal?

Per klant gebeurt er, in volgorde, het volgende:

1. **Data ophalen.** De meetgegevens van de klant (verbruik en teruglevering per kwartier) staan al in de database; de import-pipeline van het team schrijft ze daar weg. De worker leest ze rechtstreeks uit de database, strikt voor de batch die net is aangemeld. Er wordt geen CSV meer ingelezen.
2. **Datakwaliteit checken.** Klopt de data? Zijn er gaten? Hoe betrouwbaar is wat we hebben? Daar komt een rapportcijfer (0-100) uit, berekend over diezelfde batch-data. Ontbreekt het interval-label (15/60/1440 min) in de aangeleverde data, dan leidt het systeem het werkelijke interval af uit de tijdstempels en vult het meteen terug in de database, zodat de score klopt.
3. **Periode bepalen.** We rekenen altijd met het laatst beschikbare jaar aan data van die batch (rolling year).
4. **Beste batterij kiezen.** Uit de catalogus van beschikbare thuisbatterijen wordt gerangschikt welke het beste uitkomt, op basis van terugverdientijd, netto opbrengst en kosten per kWh.
5. **Scenario's doorrekenen.** Voor die aanbevolen batterij wordt elke combinatie van energieleverancier en strategie (zelfverbruik, dynamisch handelen, slimme mix, ...) doorgerekend. Door de sizing vóór de scenario's te doen, gaan het advies op pagina 1 en de leverancier- en strategievergelijking verderop over precies dezelfde batterij.
6. **PDF maken.** De resultaten worden samengevat in een klantvriendelijk rapport.

Eén Python-script (`worker.py`) start dit hele proces automatisch zodra er nieuwe data binnenkomt. De energieprijzen en leveranciersmarges worden dagelijks losstaand voorberekend door `refresher.py`; de worker herberekent ze niet zelf (alleen een vangnet als ze ontbreken of ouder dan een week zijn).

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
| `cost_calculator.py` | Rekent uit wat de klant betaalt, met en zonder batterij. |
| `battery_catalog.py` | Haalt de lijst beschikbare batterijen uit de database. |
| `battery_sizing.py` | Kiest welke batterij financieel het slimst is. |
| `report_generator.py` | Bouwt het uiteindelijke PDF-rapport. |
| `reference_data.py` | Haalt energieprijzen en provider-marges op. |
| `refresher.py` | Berekent dagelijks de marges en all-in prijzen voor, los van een klantberekening. |
| `simulation_config.py` | De instellingen-container voor één klantberekening. |
| `db_connection.py` | Verbinding met de database. |
