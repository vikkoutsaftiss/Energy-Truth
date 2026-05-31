# Energy-Truth - Python rapportgenerator

Dit is het Python-deel van Energy-Truth. Het neemt de slimme-meterdata van een klant, rekent uit of een thuisbatterij voor die klant interessant is, en maakt daar een leesbaar PDF-rapport van.

Het algoritme koppelt **alleen via de database**: het krijgt zijn werk binnen als een ImportBatch en schrijft het resultaat (de PDF-bytes en een samenvatting) terug in de database. Er is geen direct verkeer met de backend of de frontend.

## Wat doet het, in gewone taal?

Per klant gebeurt er, in volgorde, het volgende:

1. **Data ophalen en opschonen.** De meetgegevens (verbruik en teruglevering per kwartier) staan al in de database; de import-pipeline van het team schrijft ze daar weg. De binnenkomende batch is het startsein, maar we lezen alle meetdata van het hele **gebouw** binnen het rekenjaar, over meerdere uploads heen, zodat er geen historie mist. Komt eenzelfde meetmoment in meerdere uploads voor, dan houden we de nieuwste geldige meting aan. Fysiek onmogelijke metingen (negatief, of absurd hoog door bijvoorbeeld een meterstand-reset) zetten we bij naar 0 voor de berekening; hoeveel er zijn bijgesteld leggen we vast in de samenvatting en in de ImportBatch-tabel. Er wordt geen CSV meer ingelezen.
2. **Datakwaliteit checken.** Klopt de data? Zijn er gaten? Hoe betrouwbaar is wat we hebben? Daar komt een rapportcijfer (0-100) uit, berekend over de gebouw-data van datzelfde rekenjaar. Ontbreekt het interval-label (15/60/1440 min) in de aangeleverde data, dan leidt het systeem het werkelijke interval af uit de tijdstempels en vult het meteen terug in de database, zodat de score klopt.
3. **Periode bepalen.** We rekenen altijd met het laatst beschikbare jaar aan data van het gebouw (rolling year).
4. **Beste batterij kiezen.** Uit de catalogus van beschikbare thuisbatterijen wordt gerangschikt welke het beste uitkomt, op basis van terugverdientijd, netto opbrengst en kosten per kWh. Heeft de gebruiker zelf een batterij opgegeven, dan telt die als extra kandidaat mee en kan hij als beste uit de bus komen.
5. **Scenario's doorrekenen.** Voor die aanbevolen batterij wordt elke combinatie van energieleverancier en strategie (zelfverbruik, dynamisch handelen, slimme mix, ...) doorgerekend. Door de sizing voor de scenario's te doen, gaan het advies op pagina 1 en de leverancier- en strategievergelijking verderop over precies dezelfde batterij. Afname rekenen we tegen de all-in prijs, teruglevering tegen de kale beursprijs (energiebelasting/ODE/btw krijg je niet terug).
6. **PDF maken.** De resultaten worden samengevat in een klantvriendelijk rapport. De PDF wordt niet op schijf gezet maar als bytes in de database opgeslagen (`SimulatieRapport_PDF`), omdat meterdata een persoonsgegeven is (AVG).

Een Python-script (`worker.py`) start dit hele proces automatisch zodra er nieuwe data binnenkomt. De energieprijzen en leveranciersmarges worden dagelijks losstaand voorberekend door `refresher.py`; de worker herberekent ze niet zelf (alleen een vangnet als ze ontbreken of ouder dan een week zijn).

Een gebruiker kan optioneel een **eigen batterij** meegeven via het veld `Eigen_Batterij` (JSON) op de ImportBatch. Die telt alleen voor zijn eigen berekening en wordt naast de catalogus meegenomen; staat het veld leeg, dan rekenen we alleen met de catalogus.

## Wat heb je nodig om het te draaien?

- **Python 3.12** (de versie waarop dit getest is). Minimaal Python 3.11, want pandas 3.0 en numpy 2.4 ondersteunen geen oudere versie.
- Een PostgreSQL database (het schema en de seed-data staan in de `sql/`-map elders in deze repo).
- De Python-pakketten met vaste versies uit `requirements.txt`. Installeer ze met:

  ```
  pip install -r requirements.txt
  ```

  (matplotlib, numpy, pandas, psycopg2-binary, reportlab; exact gepind voor reproduceerbare builds)

## Configuratie (environment variables)

De database-gegevens en wat gedrags-instellingen komen uit environment variables. Lokaal zet je ze in een `.env`-bestand naast de code (zie `.env.example`); in Kubernetes komen ze uit het `db-auth` Secret en de Deployment-env. De `.env` staat in `.gitignore` en hoort nooit in Git.

| Variabele | Verplicht | Default | Waarvoor |
|---|---|---|---|
| `DATABASE_IP` | ja | - | Host of IP van de PostgreSQL-server |
| `DATABASE_PORT` | ja | - | Poort (bv. 5432) |
| `POSTGRES_DB` | ja | - | Databasenaam |
| `POSTGRES_USER` | ja | - | Databasegebruiker (alleen SELECT/INSERT/UPDATE nodig) |
| `POSTGRES_PASSWORD` | ja | - | Wachtwoord |
| `DB_SSLMODE` | nee | `prefer` | `prefer` / `require` / `verify-full`. Zet op `require` zodra de server SSL aan heeft. |
| `DATABASE_CONNECT_TIMEOUT` | nee | `10` | Seconden wachten op een verbinding voordat we opgeven. |
| `DATABASE_STATEMENT_TIMEOUT_MS` | nee | `60000` | Server-side limiet per query (ms); kapt een hangende query af. |
| `POLL_INTERVAL_SECONDS` | nee | `30` | Hoe vaak de worker de wachtrij controleert. |
| `LOG_LEVEL` | nee | `INFO` | `DEBUG` / `INFO` / `WARNING` / `ERROR`. |

## Lokaal draaien en testen

Continu draaien (blijft pollen):

```bash
python worker.py
```

Een enkele batch pakken en stoppen (handig om te testen):

```bash
python worker.py --once
```

Met `--once` pakt de worker precies een batch op `Status='ready'` en stopt daarna. Staat er niets klaar, dan meldt hij "Geen 'ready' batches gevonden" en stopt; dat betekent dat de DB-verbinding werkte.

Een batch klaarzetten doe je vanuit psql of een DB-tool:

```sql
UPDATE "ImportBatch" SET "Status"='ready' WHERE "ID" = <batch_id>;
```

Het gegenereerde rapport komt als bytes in `SimulatieRapport_PDF` te staan (niet als bestand op schijf). Vanuit een DB-tool (bv. DBeaver) kun je die cel naar een `.pdf` exporteren.

## Draaien in Kubernetes

De worker is een **pure poller**: hij heeft geen eigen URL of endpoint nodig. Hij draait als een Deployment en kijkt elke `POLL_INTERVAL_SECONDS` in de database of er een ImportBatch op `Status='ready'` staat.

- **Credentials** komen uit het bestaande `db-auth` Secret (dezelfde keys als Vik's backend, per key als env geinjecteerd). Zie `k8s/secret.yaml.example`. De DB is bereikbaar vanuit de pod zonder VPN.
- **Niet-geheime config** (`DB_SSLMODE`, de timeouts, `POLL_INTERVAL_SECONDS`, `LOG_LEVEL`) zet je in de Deployment-env of een ConfigMap; zonder die instellingen draait de worker op de defaults uit de tabel hierboven.
- **Geen koppeling met backend/frontend**: het algoritme krijgt zijn werk via een ImportBatch en schrijft het resultaat terug in de DB. Verder praat het met niets.
- **Logs**: zet in de Dockerfile `ENV PYTHONUNBUFFERED=1` (logs verschijnen realtime in `kubectl logs` en gaan niet verloren bij een crash) en `ENV PYTHONUTF8=1`.

De **refresher** (`refresher.py`) is bedoeld als dagelijkse **CronJob** die `python refresher.py` draait om de marges en all-in prijzen voor te berekenen. *Die CronJob moet nog gebouwd worden.* Tot die tijd is het geen probleem: de worker heeft vangnetten en herberekent de marges zelf als ze ontbreken of ouder dan een week zijn.

## Wat zit er in deze map?

| Bestand | Waar is het voor? |
|---|---|
| `worker.py` | Het startpunt: pakt nieuwe opdrachten op en doorloopt de hele keten. |
| `data_quality.py` | Geeft de meetdata een betrouwbaarheidsscore (per gebouw, rekenjaar) en schoont onmogelijke metingen op. |
| `period_selector.py` | Bepaalt welk jaar aan data we gebruiken (per gebouw). |
| `scenario_engine.py` | Laadt en ontdubbelt de meetdata en rekent alle combinaties van leverancier x batterij-strategie door. |
| `battery_simulator.py` | Simuleert kwartier voor kwartier hoe een batterij zich gedraagt. |
| `cost_calculator.py` | Rekent uit wat de klant betaalt, met en zonder batterij. |
| `battery_catalog.py` | Haalt de lijst beschikbare batterijen uit de database. |
| `battery_sizing.py` | Kiest welke batterij financieel het slimst is. |
| `report_generator.py` | Bouwt het uiteindelijke PDF-rapport. |
| `reference_data.py` | Haalt energieprijzen en provider-marges op. |
| `refresher.py` | Berekent dagelijks de marges en all-in prijzen voor, los van een klantberekening. |
| `simulation_config.py` | De instellingen-container voor een klantberekening. |
| `db_connection.py` | Verbinding met de database. |
