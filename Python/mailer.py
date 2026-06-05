#!/usr/bin/env python3
"""
Energy-Truth rapport-mailer.

Verstuurt de PDF uit de tabel "SimulatieRapport_PDF" als bijlage via een
externe SMTP-relay (Brevo). De ontvanger wordt per gebouw bepaald:

    SimulatieRapport_PDF.Gebouw_ID -> Gebouw.ID
    Gebouw.Klant_ID                -> Klant.ID
    Klant.Email                    = ontvanger

Twee modi:
  * Test:       python mailer.py --id 42        (stuurt 1 rapport, stempelt NIET)
  * Productie:  python mailer.py                 (stuurt alle rijen waar
                                                   Verzonden_Op IS NULL en
                                                   stempelt Verzonden_Op = now())

Alle configuratie komt uit environment-variabelen (zie .env.example),
zodat er niets gevoeligs in de code staat. In de pod komen deze als secret.

De DB-verbinding loopt via db_connection.get_connection(), net als worker.py,
zodat beide scripts dezelfde .env en dezelfde DB-credentials delen. Het
importeren van db_connection laadt ook de lokale .env in os.environ, waardoor
de SMTP-/MAIL_-variabelen hieronder uit diezelfde .env beschikbaar zijn.
"""

import argparse
import datetime
import html
import logging
import os
import smtplib
import ssl
import sys
from email.message import EmailMessage
from email.utils import formataddr
from pathlib import Path
from string import Template

from db_connection import get_connection

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("mailer")


# --------------------------------------------------------------------------- #
# Configuratie uit environment
# --------------------------------------------------------------------------- #
def env(name, default=None, required=False):
    val = os.environ.get(name, default)
    if required and (val is None or val == ""):
        log.error("Verplichte environment-variabele ontbreekt: %s", name)
        sys.exit(2)
    return val


def _mask_email(addr):
    """Maskeer een e-mailadres voor de logs (AVG): foo@bar.nl -> f***@bar.nl.

    Houdt het domein zichtbaar voor debug, maar verbergt de persoon. Het
    rapport_id staat sowieso al in elke logregel voor de koppeling.
    """
    if not addr or "@" not in addr:
        return "<onbekend>"
    local, _, domain = addr.partition("@")
    zichtbaar = local[0] if local else ""
    return f"{zichtbaar}***@{domain}"


# Database: gedeeld met worker.py via db_connection.get_connection().
# De DB-credentials (DATABASE_IP, POSTGRES_DB, ...) staan in dezelfde .env.

# SMTP (Brevo). Voor de test: smtp-relay.brevo.com / 587.
SMTP_HOST = env("SMTP_HOST", "smtp-relay.brevo.com")
SMTP_PORT = int(env("SMTP_PORT", "587"))
SMTP_USER = env("SMTP_USER", required=True)
SMTP_PASS = env("SMTP_PASS", required=True)

# Afzender. Voor de test: rapporten@mierlofirst.org.
# Later: rapporten@energytruth.nl (alleen deze regel + DKIM hoeft te wijzigen).
MAIL_FROM = env("MAIL_FROM", required=True)
MAIL_FROM_NAME = env("MAIL_FROM_NAME", "Energy-Truth")
MAIL_SUBJECT = env("MAIL_SUBJECT", "Uw Energy-Truth simulatierapport")

# Alleen versturen naar geverifieerde e-mailadressen? (Klant.Email_verifieerd)
REQUIRE_VERIFIED = env("REQUIRE_VERIFIED", "false").lower() in ("1", "true", "yes")


# --------------------------------------------------------------------------- #
# Database
# --------------------------------------------------------------------------- #
# Identifiers zijn dubbel-gequote omdat de tabellen/kolommen met hoofdletters
# zijn aangemaakt (PostgreSQL vouwt anders naar lowercase).
SELECT_COLUMNS = """
    SELECT r."ID"            AS rapport_id,
           r."Bestandsnaam"  AS bestandsnaam,
           r."PDF_Bytes"     AS pdf_bytes,
           r."Gebouw_ID"     AS gebouw_id,
           k."Email"         AS email,
           k."Email_verifieerd" AS email_verifieerd,
           k."Bedrijfsnaam"  AS bedrijfsnaam
    FROM "SimulatieRapport_PDF" r
    JOIN "Gebouw" g ON g."ID"  = r."Gebouw_ID"
    JOIN "Klant"  k ON k."ID"  = g."Klant_ID"
"""


def fetch_pending(cur):
    cur.execute(SELECT_COLUMNS + ' WHERE r."Verzonden_Op" IS NULL ORDER BY r."ID";')
    return cur.fetchall()


def fetch_by_id(cur, rapport_id):
    cur.execute(SELECT_COLUMNS + ' WHERE r."ID" = %s;', (rapport_id,))
    return cur.fetchall()


def mark_sent(cur, rapport_id):
    cur.execute(
        'UPDATE "SimulatieRapport_PDF" SET "Verzonden_Op" = now() WHERE "ID" = %s;',
        (rapport_id,),
    )


# --------------------------------------------------------------------------- #
# E-mail
# --------------------------------------------------------------------------- #
# De inhoud van de mail staat in losse sjabloonbestanden naast dit script.
# Wil je de opmaak/tekst wijzigen? Pas alleen die bestanden aan, niet de code.
_HERE = Path(__file__).parent
HTML_TEMPLATE = _HERE / "mail_template.html"
TEXT_TEMPLATE = _HERE / "mail_template.txt"


def _render(path, context):
    """Laad een sjabloon en vul de ${placeholders} in. safe_substitute laat
    onbekende ${...} ongemoeid i.p.v. een fout te geven."""
    raw = path.read_text(encoding="utf-8")
    return Template(raw).safe_substitute(context)


def build_message(to_addr, bestandsnaam, pdf_bytes, bedrijfsnaam):
    filename = bestandsnaam or "rapport.pdf"
    jaar = datetime.date.today().year

    # Platte tekst: ongewijzigde waarden. HTML: dezelfde waarden maar
    # ge-escaped, zodat een bedrijfsnaam met < > & geen HTML kan injecteren.
    text_context = {
        "bedrijfsnaam": bedrijfsnaam or "klant",
        "bestandsnaam": filename,
        "jaar": jaar,
    }
    html_context = {
        "bedrijfsnaam": html.escape(bedrijfsnaam or "klant"),
        "bestandsnaam": html.escape(filename),
        "jaar": jaar,
    }

    msg = EmailMessage()
    msg["From"] = formataddr((MAIL_FROM_NAME, MAIL_FROM))
    msg["To"] = to_addr
    msg["Subject"] = MAIL_SUBJECT

    # Eerst de platte-tekst versie (fallback), daarna de HTML als alternatief.
    # multipart/alternative: de client toont HTML, valt anders terug op tekst.
    msg.set_content(_render(TEXT_TEMPLATE, text_context))
    msg.add_alternative(_render(HTML_TEMPLATE, html_context), subtype="html")

    # bytea komt als memoryview/bytes binnen; normaliseren naar bytes.
    data = bytes(pdf_bytes)
    msg.add_attachment(
        data, maintype="application", subtype="pdf", filename=filename
    )
    return msg


def send(smtp, msg):
    smtp.send_message(msg)


# --------------------------------------------------------------------------- #
# Hoofdroutine
# --------------------------------------------------------------------------- #
def run(rapport_id=None, mark=True, dry_run=False):
    conn = get_connection()
    conn.autocommit = False
    sent, skipped, failed = 0, 0, 0
    try:
        with conn.cursor() as cur:
            rows = fetch_by_id(cur, rapport_id) if rapport_id else fetch_pending(cur)

        if not rows:
            log.info("Geen rapporten om te versturen.")
            return 0

        log.info("%d rapport(en) gevonden.", len(rows))

        smtp = None
        if not dry_run:
            smtp = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30)
            smtp.starttls(context=ssl.create_default_context())
            smtp.login(SMTP_USER, SMTP_PASS)

        try:
            for (rid, bestandsnaam, pdf_bytes, gebouw_id,
                 email, email_verifieerd, bedrijfsnaam) in rows:

                if not email:
                    log.warning("Rapport %s (gebouw %s): geen e-mailadres, overslaan.",
                                rid, gebouw_id)
                    skipped += 1
                    continue
                if REQUIRE_VERIFIED and not email_verifieerd:
                    log.warning("Rapport %s: e-mail %s niet geverifieerd, overslaan.",
                                rid, _mask_email(email))
                    skipped += 1
                    continue
                if not pdf_bytes:
                    log.warning("Rapport %s: geen PDF_Bytes, overslaan.", rid)
                    skipped += 1
                    continue

                msg = build_message(email, bestandsnaam, pdf_bytes, bedrijfsnaam)

                if dry_run:
                    log.info("[dry-run] zou rapport %s naar %s sturen (%s).",
                             rid, _mask_email(email), bestandsnaam)
                    sent += 1
                    continue

                try:
                    send(smtp, msg)
                    log.info("Rapport %s verstuurd naar %s.", rid, _mask_email(email))
                    sent += 1
                    if mark:
                        with conn.cursor() as cur:
                            mark_sent(cur, rid)
                        conn.commit()
                except Exception as exc:  # noqa: BLE001
                    conn.rollback()
                    log.error("Rapport %s mislukt: %s", rid, exc)
                    failed += 1
        finally:
            if smtp is not None:
                smtp.quit()
    finally:
        conn.close()

    log.info("Klaar. Verstuurd=%d, overgeslagen=%d, mislukt=%d.",
             sent, skipped, failed)
    return 1 if failed else 0


def main():
    p = argparse.ArgumentParser(description="Energy-Truth rapport-mailer")
    p.add_argument("--id", type=int, default=None,
                   help="Verstuur exact dit SimulatieRapport_PDF.ID (testmodus).")
    p.add_argument("--mark", dest="mark", action="store_true",
                   help="Stempel Verzonden_Op ook bij --id.")
    p.add_argument("--no-mark", dest="mark", action="store_false",
                   help="Stempel Verzonden_Op NIET (standaard bij --id).")
    p.add_argument("--dry-run", action="store_true",
                   help="Toon wat er verstuurd zou worden, zonder te mailen.")
    p.set_defaults(mark=None)
    args = p.parse_args()

    # Standaard: productie stempelt wel, losse --id test stempelt niet.
    if args.mark is None:
        mark = args.id is None
    else:
        mark = args.mark

    rc = run(rapport_id=args.id, mark=mark, dry_run=args.dry_run)
    sys.exit(rc)


if __name__ == "__main__":
    main()
