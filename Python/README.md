# Energy-Truth — Python rapportgenerator

Dit is het Python-deel van Energy-Truth. Het neemt de slimme-meterdata van een klant, rekent uit of een thuisbatterij voor die klant interessant is, en maakt daar een leesbaar PDF-rapport van.

## Wat doet het, in gewone taal?

Per klant gebeurt er, in volgorde, het volgende:

1. **Data ophalen en opschonen.** De meetgegevens (verbruik en teruglevering per kwartier) staan al in de database; de import-pipeline van het team schrijft ze daar weg. De binnenkomende batch is het startsein, maar we lezen alle meetdata van het hele **gebouw** binnen het rekenjaar, over meerdere uploads heen, zodat er geen historie mist. Komt eenzelfde meetmoment in meerdere uploads voor, dan houden we de nieuwste geldige meting aan. Fysiek onmogelijke metingen (negatief, of absurd hoog door bijvoorbeeld een meterstand-reset) gooien we eruit vóór de berekening; hoeveel er zijn afgekeurd leggen we vast in de samenvatting en in de ImportBatch-tabel. Er wordt geen CSV meer ingelezen.
2. **Datakwaliteit checken.** Klopt de data? Zijn er gaten? Hoe betrouwbaar is wat we hebben? Daar komt een rapportcijfer (0-100) uit, berekend over de gebouw-data van datzelfde rekenjaar. Ontbreekt het interval-label (15/60/1440 min) in de aangeleverde data, dan leidt het systeem het werkelijke interval af uit de tijdstempels en vult het meteen terug in de database, zodat de score klopt.
3. **Periode bepalen.** We rekenen altijd met het laatst beschikbare jaar aan data van het gebouw (rolling year).
4. **Beste batterij kiezen.** Uit de catalogus van beschikbare thuisbatterijen wordt gerangschikt welke het beste uitkomt, op basis van terugverdientijd, netto opbrengst en kosten per kWh. Heeft de gebruiker zelf een batterij opgegeven, dan telt die als extra kandidaat mee en kan hij als beste uit de bus komen.
5. **Scenario's doorrekenen.** Voor die aanbevolen batterij wordt elke combinatie van energieleverancier en strategie (zelfverbruik, dynamisch handelen, slimme mix, ...) doorgerekend. Door de sizing vóór de scenario's te doen, gaan het advies op pagina 1 en de leverancier- en strategievergelijking verderop over precies dezelfde batterij. Afname rekenen we tegen de all-in prijs, teruglevering tegen de kale beursprijs (energiebelasting/ODE/btw krijg je niet terug).
6. **PDF maken.** De resultaten worden samengevat in een klantvriendelijk rapport.

Eén Python-script (`worker.py`) start dit hele proces automatisch zodra er nieuwe data binnenkomt. De energieprijzen en leveranciersmarges worden dagelijks losstaand voorberekend door `refresher.py`; de worker herberekent ze niet zelf (alleen een vangnet als ze ontbreken of ouder dan een week zijn).

Een gebruiker kan optioneel een **eigen batterij** meegeven via het veld `Eigen_Batterij` (JSON) op de ImportBatch. Die telt alleen voor zijn eigen berekening en wordt naast de catalogus meegenomen; staat het veld leeg, dan rekenen we alleen met de catalogus.

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
| `data_quality.py` | Geeft de meetdata een betrouwbaarheidsscore (per gebouw, rekenjaar) en schoont onmogelijke metingen op. |
| `period_selector.py` | Bepaalt welk jaar aan data we gebruiken (per gebouw). |
| `scenario_engine.py` | Laadt en ontdubbelt de meetdata en rekent alle combinaties van leverancier × batterij-strategie door. |
| `battery_simulator.py` | Simuleert kwartier voor kwartier hoe een batterij zich gedraagt. |
| `cost_calculator.py` | Rekent uit wat de klant betaalt, met en zonder batterij. |
| `battery_catalog.py` | Haalt de lijst beschikbare batterijen uit de database. |
| `battery_sizing.py` | Kiest welke batterij financieel het slimst is. |
| `report_generator.py` | Bouwt het uiteindelijke PDF-rapport. |
| `reference_data.py` | Haalt energieprijzen en provider-marges op. |
| `refresher.py` | Berekent dagelijks de marges en all-in prijzen voor, los van een klantberekening. |
| `simulation_config.py` | De instellingen-container voor één klantberekening. |
| `db_connection.py` | Verbinding met de database. |
