"""
report_generator.py — PDF-rapport voor Energy-Truth simulatieresultaten.

Genereert een professioneel besparingsrapport met:
  - Samenvatting (beste scenario, batterijconfig, simulatieperiode)
  - Ranking-tabel (alle scenario's)
  - Strategie-vergelijking per aanbieder
  - Configuratie-overzicht

Gebruik:
    from report_generator import generate_report
    generate_report(results_df, config, output_path="rapport.pdf")

Of via CLI:
    python report_generator.py config.json --output rapport.pdf
"""
from __future__ import annotations

import os
import sys
import logging
from datetime import datetime
from typing import Optional

import pandas as pd
import numpy as np

# Matplotlib wordt lazy geïmporteerd in de chart-helpers (pagina 2 e.v.)
# zodat pagina 1 ook draait zonder matplotlib geïnstalleerd.

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm, cm
from reportlab.lib.colors import HexColor, black, white
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, KeepTogether, HRFlowable, Image,
)
from reportlab.platypus.flowables import Flowable
from io import BytesIO

from simulation_config import SimulationConfig

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Kleuren & stijlen — fintech palet (Tikkie/BUNQ-inspired)
# ---------------------------------------------------------------------------
COLOR_INK = HexColor("#0B1220")          # hoofdtekst / merkmarkering
COLOR_MUTED = HexColor("#5B6580")        # gedempt grijs (labels)
COLOR_PRIMARY = HexColor("#06B6D4")      # cyan (merk-primair)
COLOR_SECONDARY = HexColor("#0891B2")    # cyan donker (sub-merk)
COLOR_ACCENT = HexColor("#10B981")       # emerald groen (positief/besparingen)
COLOR_WARN = HexColor("#F59E0B")         # amber (twijfel-verdict)
COLOR_NEGATIVE = HexColor("#EF4444")     # rood (no-go / verlies)
COLOR_SOFT = HexColor("#ECFEFF")         # zacht cyan voor tegel-achtergrond
COLOR_LIGHT_BG = HexColor("#F8FAFC")     # algemene achtergrond
COLOR_GREEN_SOFT = HexColor("#ECFDF5")   # zacht groen voor winnaar
COLOR_GREEN_BORDER = HexColor("#A7F3D0")
COLOR_CYAN_BORDER = HexColor("#CFFAFE")
COLOR_AMBER_SOFT = HexColor("#FEF3C7")
COLOR_AMBER_BORDER = HexColor("#FCD34D")
COLOR_RED_SOFT = HexColor("#FEE2E2")
COLOR_RED_BORDER = HexColor("#FECACA")
COLOR_AMBER_LIGHT = HexColor("#FFF7ED") # verdict twijfel achtergrond
COLOR_TABLE_HEADER = HexColor("#0B1220")
COLOR_TABLE_ALT = HexColor("#F8FAFC")
COLOR_BORDER = HexColor("#E6EAF2")


def _get_styles():
    """Bouw stijlen voor het rapport (inclusief nieuwe fintech-cover stijlen)."""
    styles = getSampleStyleSheet()

    # --- Nieuwe fintech-cover stijlen ---
    styles.add(ParagraphStyle(
        name="BrandName",
        fontName="Helvetica-Bold",
        fontSize=14,
        textColor=COLOR_INK,
        leading=16,
    ))
    styles.add(ParagraphStyle(
        name="BrandSub",
        fontName="Helvetica",
        fontSize=8.5,
        textColor=COLOR_MUTED,
        leading=11,
    ))
    styles.add(ParagraphStyle(
        name="CoverTitle",
        fontName="Helvetica-Bold",
        fontSize=28,
        textColor=COLOR_INK,
        leading=32,
        spaceAfter=2 * mm,
    ))
    styles.add(ParagraphStyle(
        name="CoverSub",
        fontName="Helvetica",
        fontSize=10,
        textColor=COLOR_MUTED,
        leading=14,
        spaceAfter=6 * mm,
    ))
    styles.add(ParagraphStyle(
        name="VerdictLabel",
        fontName="Helvetica-Bold",
        fontSize=8,
        textColor=COLOR_WARN,
        leading=10,
    ))
    styles.add(ParagraphStyle(
        name="VerdictHeadline",
        fontName="Helvetica-Bold",
        fontSize=15,
        textColor=COLOR_INK,
        leading=18,
        spaceBefore=1 * mm,
    ))
    styles.add(ParagraphStyle(
        name="VerdictBody",
        fontName="Helvetica",
        fontSize=9.5,
        textColor=HexColor("#7C2D12"),
        leading=13,
        spaceBefore=2 * mm,
    ))
    styles.add(ParagraphStyle(
        name="KpiTileLabel",
        fontName="Helvetica-Bold",
        fontSize=7,
        textColor=COLOR_SECONDARY,
        leading=9,
        alignment=TA_LEFT,
    ))
    styles.add(ParagraphStyle(
        name="KpiTileValue",
        fontName="Helvetica-Bold",
        fontSize=20,
        textColor=COLOR_INK,
        leading=22,
        alignment=TA_LEFT,
    ))
    styles.add(ParagraphStyle(
        name="KpiTileFoot",
        fontName="Helvetica",
        fontSize=8,
        textColor=COLOR_MUTED,
        leading=10,
        alignment=TA_LEFT,
    ))
    styles.add(ParagraphStyle(
        name="SectionEyebrow",
        fontName="Helvetica-Bold",
        fontSize=8,
        textColor=COLOR_SECONDARY,
        leading=11,
    ))
    styles.add(ParagraphStyle(
        name="BatteryVerdictGo",
        fontName="Helvetica-Bold",
        fontSize=7,
        textColor=HexColor("#15803D"),
        leading=9,
        alignment=TA_CENTER,
    ))
    styles.add(ParagraphStyle(
        name="BatteryVerdictNogo",
        fontName="Helvetica-Bold",
        fontSize=7,
        textColor=HexColor("#B91C1C"),
        leading=9,
        alignment=TA_CENTER,
    ))
    styles.add(ParagraphStyle(
        name="BatteryVerdictTwijfel",
        fontName="Helvetica-Bold",
        fontSize=7,
        textColor=HexColor("#B45309"),
        leading=9,
        alignment=TA_CENTER,
    ))
    styles.add(ParagraphStyle(
        name="BatteryName",
        fontName="Helvetica-Bold",
        fontSize=11,
        textColor=COLOR_INK,
        leading=13,
    ))
    styles.add(ParagraphStyle(
        name="BatteryKwh",
        fontName="Helvetica",
        fontSize=8,
        textColor=COLOR_MUTED,
        leading=11,
    ))
    styles.add(ParagraphStyle(
        name="BatteryPrice",
        fontName="Helvetica-Bold",
        fontSize=15,
        textColor=COLOR_INK,
        leading=17,
    ))
    styles.add(ParagraphStyle(
        name="BatteryStatLabel",
        fontName="Helvetica-Bold",
        fontSize=6.5,
        textColor=COLOR_MUTED,
        leading=8,
        alignment=TA_LEFT,
    ))
    styles.add(ParagraphStyle(
        name="BatteryStatValue",
        fontName="Helvetica-Bold",
        fontSize=9,
        textColor=COLOR_INK,
        leading=11,
        alignment=TA_LEFT,
    ))
    styles.add(ParagraphStyle(
        name="BatteryCrown",
        fontName="Helvetica-Bold",
        fontSize=7,
        textColor=white,
        leading=9,
        alignment=TA_CENTER,
    ))

    # --- Bestaande stijlen (legacy) ---
    styles.add(ParagraphStyle(
        name="ReportTitle",
        fontName="Helvetica-Bold",
        fontSize=22,
        textColor=COLOR_PRIMARY,
        spaceAfter=6 * mm,
        alignment=TA_LEFT,
    ))
    styles.add(ParagraphStyle(
        name="ReportSubtitle",
        fontName="Helvetica",
        fontSize=11,
        textColor=COLOR_SECONDARY,
        spaceAfter=10 * mm,
        alignment=TA_LEFT,
    ))
    styles.add(ParagraphStyle(
        name="SectionHeading",
        fontName="Helvetica-Bold",
        fontSize=14,
        textColor=COLOR_PRIMARY,
        spaceBefore=8 * mm,
        spaceAfter=4 * mm,
        alignment=TA_LEFT,
    ))
    styles.add(ParagraphStyle(
        name="BodyText2",
        fontName="Helvetica",
        fontSize=9,
        textColor=black,
        spaceAfter=3 * mm,
        leading=13,
    ))
    styles.add(ParagraphStyle(
        name="SmallNote",
        fontName="Helvetica",
        fontSize=7,
        textColor=HexColor("#7f8c8d"),
        spaceAfter=2 * mm,
    ))
    styles.add(ParagraphStyle(
        name="KPIValue",
        fontName="Helvetica-Bold",
        fontSize=14,
        textColor=COLOR_ACCENT,
        alignment=TA_CENTER,
        leading=16,
    ))
    styles.add(ParagraphStyle(
        name="KPILabel",
        fontName="Helvetica",
        fontSize=7,
        textColor=HexColor("#566573"),
        alignment=TA_CENTER,
        leading=9,
    ))
    return styles


# ---------------------------------------------------------------------------
# KPI-blok (visueel getal + label)
# ---------------------------------------------------------------------------

def _kpi_block(value_text: str, label: str, styles, color=None):
    """Maak een mini-tabel die één KPI toont."""
    val_style = ParagraphStyle(
        "kpi_val", parent=styles["KPIValue"],
        textColor=color or COLOR_ACCENT,
    )
    return [
        Paragraph(value_text, val_style),
        Paragraph(label, styles["KPILabel"]),
    ]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _format_eur(val) -> str:
    """Formatteer als Euro-bedrag."""
    if pd.isna(val):
        return "—"
    return f"\u20ac {val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _format_pct(val) -> str:
    """Formatteer als percentage."""
    if pd.isna(val):
        return "—"
    return f"{val:.1f}%"


def _strategy_name(code: str) -> str:
    """Vertaal strategiecode naar leesbare naam."""
    names = {
        "A": "Zelfverbruik",
        "B": "Prijsarbitrage",
        "C": "Hybride",
        "D": "Slim zelfverbruik",
    }
    return names.get(code, code)


# ---------------------------------------------------------------------------
# Pagina-footer
# ---------------------------------------------------------------------------

def _footer(canvas_obj, doc):
    """Voeg paginanummer, gebruikersnaam en datum toe aan elke pagina."""
    canvas_obj.saveState()
    canvas_obj.setFont("Helvetica", 7)
    canvas_obj.setFillColor(HexColor("#95a5a6"))
    page_num = canvas_obj.getPageNumber()
    user_part = f"  |  {doc.user_name}" if getattr(doc, "user_name", None) else ""
    text = (
        f"Energy-Truth Simulatierapport{user_part}"
        f"  |  Pagina {page_num}"
        f"  |  Gegenereerd: {datetime.now().strftime('%d-%m-%Y %H:%M')}"
    )
    canvas_obj.drawString(20 * mm, 10 * mm, text)
    canvas_obj.restoreState()


# ---------------------------------------------------------------------------
# Rapport-secties
# ---------------------------------------------------------------------------

def _get_user_name(klant_id) -> Optional[str]:
    """Haal de bedrijfsnaam op uit de Klant tabel."""
    if klant_id is None:
        print("⚠️  Geen klant_id — kan naam niet ophalen")
        return None
    try:
        from db_connection import get_client
        client = get_client()
        print(f"Klantnaam ophalen voor klant_id={klant_id}...")
        resp = (
            client.table("Klant")
            .select("Bedrijfsnaam")
            .eq("ID", klant_id)
            .limit(1)
            .execute()
        )
        print(f"  Klant response: {resp.data}")
        if resp.data and resp.data[0].get("Bedrijfsnaam"):
            name = resp.data[0]["Bedrijfsnaam"]
            print(f"  ✅ Bedrijfsnaam: {name}")
            return name
        else:
            print(f"  ⚠️  Geen Bedrijfsnaam gevonden in Klant tabel")
    except Exception as e:
        print(f"  ❌ Klantnaam ophalen mislukt: {e}")
    return None


# ---------------------------------------------------------------------------
# V2 — Fintech-cover helpers (pagina 1)
# ---------------------------------------------------------------------------

def _fmt_eur_short(val) -> str:
    """Korte euro-notatie zonder decimalen, voor cover-tegels."""
    if val is None or pd.isna(val):
        return "—"
    return f"€ {val:,.0f}".replace(",", ".")


def _select_top3_batteries(sizing_results: pd.DataFrame) -> pd.DataFrame:
    """
    Kies de 3 best passende batterijen uit sizing_results.

    Sortering: GO eerst (laagste payback), dan ONZEKER, dan NOGO. Per
    productnaam pakken we de beste strategie-variant. Maximaal 3 rijen terug.
    """
    if sizing_results is None or sizing_results.empty:
        return pd.DataFrame()

    df = sizing_results.copy()
    # Numerieke payback voor sortering (None → +inf)
    df["_payback_sort"] = df["payback_jaren"].fillna(9999.0)
    df["_go_sort"] = df["go_nogo"].map({"GO": 0, "ONZEKER": 1, "NOGO": 2}).fillna(3)
    df = df.sort_values(["_go_sort", "_payback_sort"])
    # 1 rij per productnaam (beste strategie)
    df_unique = df.drop_duplicates(subset=["productnaam"], keep="first")
    return df_unique.head(3).drop(columns=["_payback_sort", "_go_sort"], errors="ignore")


def _get_cover_verdict(sizing_results: pd.DataFrame, top3: pd.DataFrame) -> dict:
    """
    Bepaal verdict-info voor de cover-balk op pagina 1.

    Returns:
        dict met label, label_color, bg_color, border_color, headline (str),
        body (str), savings (float), payback (float), garantie (float).
    """
    if top3.empty:
        return {
            "label": "ONBEKEND",
            "label_color": COLOR_MUTED,
            "bg_color": COLOR_LIGHT_BG,
            "border_color": COLOR_BORDER,
            "headline": "Geen sizing-resultaten beschikbaar.",
            "body": "Voor dit rapport kon geen batterij-advies worden berekend.",
            "savings": None,
            "payback": None,
            "garantie": None,
        }

    best = top3.iloc[0]
    label_map = {
        "GO":      ("GO",        HexColor("#15803D"), COLOR_GREEN_SOFT, COLOR_GREEN_BORDER),
        "ONZEKER": ("TWIJFEL",   HexColor("#B45309"), COLOR_AMBER_LIGHT, COLOR_AMBER_BORDER),
        "NOGO":    ("NO-GO",     HexColor("#B91C1C"), COLOR_RED_SOFT, COLOR_RED_BORDER),
    }
    label, label_color, bg, border = label_map.get(
        best.get("go_nogo"), ("ONBEKEND", COLOR_MUTED, COLOR_LIGHT_BG, COLOR_BORDER)
    )

    naam = best.get("productnaam", "Deze batterij")
    payback = best.get("payback_jaren")
    garantie = best.get("garantiejaren")
    savings = best.get("jaarlijkse_besparing_eur")
    capex = best.get("totale_capex_eur") or best.get("aanschafprijs_eur")

    # De headline en body herhalen GEEN cijfers (die staan in de mini-KPIs in
    # de balk zelf). Body geeft een korte interpretatie / vervolgstap.
    if label == "GO":
        headline = f"{naam} is voor jou een goede investering."
        body = (
            "De batterij verdient zichzelf binnen de garantieperiode terug. "
            "Voor jouw verbruikspatroon de beste keuze uit onze hele catalogus."
        )
    elif label == "TWIJFEL":
        headline = f"{naam} verdient zich net niet binnen de garantie terug."
        body = (
            "Krap aan. Drie omstandigheden waaronder dit kan kantelen: "
            "een lagere aanschafprijs, een langere fabrieksgarantie, of het "
            "wegvallen van saldering in 2027. Lees pagina 5 voor het effect daarvan."
        )
    else:
        headline = "Geen van de geteste batterijen is voor jou rendabel."
        body = (
            "Bij jouw verbruikspatroon en huidige prijzen levert geen enkele batterij "
            "voldoende besparing op om binnen de garantieperiode terug te verdienen. "
            "Wachten op betere prijzen of een grotere stimuleringsregeling is de slimste keuze."
        )

    return {
        "label": label,
        "label_color": label_color,
        "bg_color": bg,
        "border_color": border,
        "headline": headline,
        "body": body,
        "savings": savings,
        "payback": payback,
        "garantie": garantie,
        "capex": capex,
    }


def _make_verdict_block(verdict: dict, styles, content_width: float) -> Table:
    """
    Verdict-balk met label, headline, 3 mini-KPIs in een rij, en korte body.
    De drie hoofdcijfers (besparing / terugverdientijd / garantie) staan
    binnen de verdict-balk zodat ze niet ook nog eens als losse tegelrij
    boven het rapport terugkomen.
    """
    label_style = ParagraphStyle(
        "verdict_label_local", parent=styles["VerdictLabel"],
        textColor=verdict["label_color"],
    )

    # Mini-KPIs binnen de balk
    savings_txt = f"{_fmt_eur_short(verdict['savings'])}/jaar" if pd.notna(verdict.get("savings")) else "—"
    payback_txt = f"{verdict['payback']:.1f} jaar" if pd.notna(verdict.get("payback")) else "—"
    garantie_txt = f"{int(verdict['garantie'])} jaar" if pd.notna(verdict.get("garantie")) else "—"

    kpi_val_style = ParagraphStyle(
        "v_kpi_val", parent=styles["KpiTileValue"],
        fontSize=17, leading=20, textColor=COLOR_INK, alignment=TA_LEFT,
    )
    kpi_lbl_style = ParagraphStyle(
        "v_kpi_lbl", parent=styles["KpiTileFoot"],
        fontSize=8, leading=10, textColor=COLOR_MUTED, alignment=TA_LEFT,
    )
    savings_val_style = ParagraphStyle(
        "v_kpi_savings", parent=kpi_val_style, textColor=COLOR_ACCENT,
    )

    kpis_row = Table(
        [[
            Table(
                [[Paragraph(savings_txt, savings_val_style)],
                 [Paragraph("wat je bespaart", kpi_lbl_style)]],
                colWidths=[None],
            ),
            Table(
                [[Paragraph(payback_txt, kpi_val_style)],
                 [Paragraph("terugverdientijd", kpi_lbl_style)]],
                colWidths=[None],
            ),
            Table(
                [[Paragraph(garantie_txt, kpi_val_style)],
                 [Paragraph("garantie", kpi_lbl_style)]],
                colWidths=[None],
            ),
        ]],
        colWidths=[(content_width - 12 * mm) / 3.0] * 3,
    )
    kpis_row.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))

    inner = [
        [Paragraph(verdict["label"], label_style)],
        [Paragraph(verdict["headline"], styles["VerdictHeadline"])],
        [kpis_row],
        [Paragraph(verdict["body"], styles["VerdictBody"])],
    ]
    t = Table(inner, colWidths=[content_width - 12 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), verdict["bg_color"]),
        ("BOX",        (0, 0), (-1, -1), 1, verdict["border_color"]),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6 * mm),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 6 * mm),
        ("TOPPADDING",    (0, 0), (0, 0),   5 * mm),
        ("BOTTOMPADDING", (0, -1), (-1, -1), 5 * mm),
        ("TOPPADDING",    (0, 1), (-1, -1), 1 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, -2), 3 * mm),
        ("ROUNDEDCORNERS", [10, 10, 10, 10]),
    ]))
    return t


def _make_kpi_tile(value: str, label: str, foot: str, value_color, bg, border, styles) -> Table:
    """Eén KPI-tegel als afgeronde Table-cel."""
    val_style = ParagraphStyle("kpi_val_local", parent=styles["KpiTileValue"], textColor=value_color)
    inner = [
        [Paragraph(label.upper(), styles["KpiTileLabel"])],
        [Paragraph(value, val_style)],
        [Paragraph(foot, styles["KpiTileFoot"])],
    ]
    t = Table(inner, colWidths=[None])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), bg),
        ("BOX",        (0, 0), (-1, -1), 0.5, border),
        ("LEFTPADDING",   (0, 0), (-1, -1), 5 * mm),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 5 * mm),
        ("TOPPADDING",    (0, 0), (0, 0),   4 * mm),
        ("BOTTOMPADDING", (0, -1), (-1, -1), 4 * mm),
        ("TOPPADDING",    (0, 1), (-1, -1), 1 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, 1),  1 * mm),
        ("ROUNDEDCORNERS", [10, 10, 10, 10]),
    ]))
    return t


def _make_kpi_row(verdict: dict, styles, content_width: float) -> Table:
    """Drie KPI-tegels naast elkaar (Besparing, Payback, Garantie)."""
    savings_txt = f"{_fmt_eur_short(verdict['savings'])}/j" if pd.notna(verdict["savings"]) else "—"
    payback_txt = f"{verdict['payback']:.1f} jaar" if pd.notna(verdict["payback"]) else "—"
    garantie_txt = f"{int(verdict['garantie'])} jaar" if pd.notna(verdict["garantie"]) else "—"

    tiles = [
        _make_kpi_tile(
            savings_txt, "Wat je bespaart",
            "Per jaar bij beste setup",
            COLOR_ACCENT, COLOR_GREEN_SOFT, COLOR_GREEN_BORDER, styles,
        ),
        _make_kpi_tile(
            payback_txt, "Terugverdientijd",
            f"Bij aanschafprijs {_fmt_eur_short(verdict.get('capex'))}",
            COLOR_INK, COLOR_SOFT, COLOR_CYAN_BORDER, styles,
        ),
        _make_kpi_tile(
            garantie_txt, "Garantie batterij",
            "Daarna risico op uitval",
            COLOR_INK, COLOR_SOFT, COLOR_CYAN_BORDER, styles,
        ),
    ]
    col_w = (content_width - 8 * mm) / 3.0
    row = Table([tiles], colWidths=[col_w] * 3)
    row.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    # Spacers tussen tegels via aparte tabel-structuur (left/right padding)
    return row


def _make_battery_card(row, is_winner: bool, styles, card_width: float) -> Table:
    """Bouw één batterij-kaart (Table) voor de top-3 grid."""
    go = row.get("go_nogo", "NOGO")
    if go == "GO":
        verdict_label = "Go"
        verdict_style = styles["BatteryVerdictGo"]
        verdict_bg = HexColor("#DCFCE7")
    elif go == "ONZEKER":
        verdict_label = "Twijfel"
        verdict_style = styles["BatteryVerdictTwijfel"]
        verdict_bg = HexColor("#FEF3C7")
    else:
        verdict_label = "No-go"
        verdict_style = styles["BatteryVerdictNogo"]
        verdict_bg = HexColor("#FEE2E2")

    naam = row.get("productnaam", "Onbekend")
    kwh = row.get("capaciteit_kwh", 0)
    prijs = row.get("totale_capex_eur") or row.get("aanschafprijs_eur", 0)
    bespaart = row.get("jaarlijkse_besparing_eur", 0)
    payback = row.get("payback_jaren")
    garantie = row.get("garantiejaren")

    # Verdict-pill als smal sub-tabelletje
    pill = Table(
        [[Paragraph(verdict_label.upper(), verdict_style)]],
        colWidths=[16 * mm],
    )
    pill.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), verdict_bg),
        ("LEFTPADDING", (0, 0), (-1, -1), 1 * mm),
        ("RIGHTPADDING", (0, 0), (-1, -1), 1 * mm),
        ("TOPPADDING", (0, 0), (-1, -1), 0.8 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0.8 * mm),
        ("ROUNDEDCORNERS", [6, 6, 6, 6]),
    ]))

    # Korte uitleg-zin per kaart (geen herhaling van de KPIs uit de verdict-balk).
    # Voorrang aan go_nogo_reden uit sizing-data; anders zelf een zin verzinnen
    # op basis van payback versus garantie.
    reden = row.get("go_nogo_reden")
    if not reden or pd.isna(reden):
        if go == "GO":
            reden = (
                f"Verdient zich in {payback:.1f} jaar terug, binnen de garantie van {int(garantie)} jaar."
                if pd.notna(payback) and pd.notna(garantie) else "Past binnen de garantie."
            )
        elif go == "ONZEKER":
            reden = (
                f"Net buiten de garantie ({payback:.1f} jaar terugverdienen vs {int(garantie)} jaar garantie)."
                if pd.notna(payback) and pd.notna(garantie) else "Krap aan."
            )
        else:
            if pd.notna(garantie) and pd.notna(payback) and garantie < 6:
                reden = f"Garantie van maar {int(garantie)} jaar is te kort om de batterij eerst terug te verdienen."
            elif pd.notna(payback) and payback > 15:
                reden = f"Terugverdientijd van {payback:.1f} jaar is te lang voor de aanschafprijs."
            else:
                reden = "Niet rendabel binnen de garantieperiode."

    reden_style = ParagraphStyle(
        "card_reden", parent=styles["KpiTileFoot"],
        fontSize=8.5, leading=12, textColor=COLOR_INK,
    )
    stats = Paragraph(reden, reden_style)

    # Cardinhoud: rij voor rij
    card_rows = []
    if is_winner:
        # Bij de winnaar tonen we alleen de crown — geen extra GO-pill (overbodig)
        crown = Table(
            [[Paragraph("AANBEVOLEN", styles["BatteryCrown"])]],
            colWidths=[28 * mm],
        )
        crown.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), COLOR_ACCENT),
            ("TOPPADDING", (0, 0), (-1, -1), 1.2 * mm),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 1.2 * mm),
            ("ROUNDEDCORNERS", [6, 6, 6, 6]),
        ]))
        card_rows.append([crown])
    else:
        card_rows.append([pill])
    card_rows.append([Paragraph(naam, styles["BatteryName"])])
    card_rows.append([Paragraph(f"{kwh:.1f} kWh capaciteit", styles["BatteryKwh"])])
    card_rows.append([Paragraph(_fmt_eur_short(prijs), styles["BatteryPrice"])])
    card_rows.append([stats])

    card = Table(card_rows, colWidths=[card_width - 6 * mm])
    bg = COLOR_GREEN_SOFT if is_winner else white
    border = COLOR_ACCENT if is_winner else COLOR_BORDER
    border_w = 1.5 if is_winner else 0.6

    card.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), bg),
        ("BOX", (0, 0), (-1, -1), border_w, border),
        ("LEFTPADDING", (0, 0), (-1, -1), 3 * mm),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3 * mm),
        ("TOPPADDING", (0, 0), (0, 0), 3 * mm),
        ("BOTTOMPADDING", (0, -1), (-1, -1), 3 * mm),
        ("TOPPADDING", (0, 1), (-1, -1), 1.5 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, -2), 1.5 * mm),
        ("ROUNDEDCORNERS", [10, 10, 10, 10]),
    ]))
    return card


def _make_battery_card_content(row, is_winner: bool, styles, card_width: float):
    """Inhoud-only versie van een batterij-kaart (zonder bg/border)."""
    go = row.get("go_nogo", "NOGO")
    if go == "GO":
        verdict_label = "Go"
        verdict_style = styles["BatteryVerdictGo"]
        verdict_bg = HexColor("#DCFCE7")
    elif go == "ONZEKER":
        verdict_label = "Twijfel"
        verdict_style = styles["BatteryVerdictTwijfel"]
        verdict_bg = HexColor("#FEF3C7")
    else:
        verdict_label = "No-go"
        verdict_style = styles["BatteryVerdictNogo"]
        verdict_bg = HexColor("#FEE2E2")

    naam = row.get("productnaam", "Onbekend")
    kwh = row.get("capaciteit_kwh", 0)
    prijs = row.get("totale_capex_eur") or row.get("aanschafprijs_eur", 0)

    # Korte uitleg per kaart (waarom wel/niet)
    payback = row.get("payback_jaren")
    garantie = row.get("garantiejaren")
    reden = row.get("go_nogo_reden")
    if not reden or pd.isna(reden):
        if go == "GO":
            reden = (
                f"Verdient zich in {payback:.1f} jaar terug, binnen de garantie van {int(garantie)} jaar."
                if pd.notna(payback) and pd.notna(garantie) else "Past binnen de garantie."
            )
        elif go == "ONZEKER":
            reden = "Net buiten de garantie terugverdiend. Krap aan."
        else:
            if pd.notna(garantie) and pd.notna(payback) and garantie < 6:
                reden = f"Garantie van maar {int(garantie)} jaar is te kort voor de prijs."
            elif pd.notna(payback) and payback > 15:
                reden = f"Terugverdientijd van {payback:.1f} jaar is te lang."
            else:
                reden = "Niet rendabel binnen de garantieperiode."

    # Pill (verdict) of crown (winnaar)
    pill = Table(
        [[Paragraph(verdict_label.upper(), verdict_style)]],
        colWidths=[16 * mm],
    )
    pill.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), verdict_bg),
        ("LEFTPADDING", (0, 0), (-1, -1), 1 * mm),
        ("RIGHTPADDING", (0, 0), (-1, -1), 1 * mm),
        ("TOPPADDING", (0, 0), (-1, -1), 0.8 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0.8 * mm),
        ("ROUNDEDCORNERS", [6, 6, 6, 6]),
    ]))

    top_marker = pill
    if is_winner:
        crown_p = Paragraph("★ AANBEVOLEN", styles["BatteryCrown"])
        top_marker = Table([[crown_p]], colWidths=[28 * mm])
        top_marker.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), COLOR_ACCENT),
            ("LEFTPADDING", (0, 0), (-1, -1), 1 * mm),
            ("RIGHTPADDING", (0, 0), (-1, -1), 1 * mm),
            ("TOPPADDING", (0, 0), (-1, -1), 1.2 * mm),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 1.2 * mm),
            ("ROUNDEDCORNERS", [6, 6, 6, 6]),
        ]))

    reden_style = ParagraphStyle(
        "card_reden", parent=styles["KpiTileFoot"],
        fontSize=8.5, leading=12, textColor=COLOR_INK,
    )

    rows = [
        [top_marker],
        [Spacer(1, 3 * mm)],
        [Paragraph(naam, styles["BatteryName"])],
        [Paragraph(f"{kwh:.1f} kWh capaciteit", styles["BatteryKwh"])],
        [Spacer(1, 2 * mm)],
        [Paragraph(_fmt_eur_short(prijs), styles["BatteryPrice"])],
        [Spacer(1, 3 * mm)],
        [Paragraph(reden, reden_style)],
    ]
    content = Table(rows, colWidths=[card_width])
    content.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    return content


def _make_top3_grid(top3: pd.DataFrame, styles, content_width: float) -> Table:
    """
    Drie batterij-kaarten naast elkaar, winnaar in midden. Achtergrond/border
    zit op de OUTER cel — alle cellen krijgen automatisch dezelfde hoogte.
    """
    if top3.empty:
        return Paragraph("Geen batterij-data beschikbaar.", styles["BodyText"])

    # Reorder: winnaar in midden (positie 1)
    rows_top = list(top3.iterrows())
    if len(rows_top) >= 3:
        ordered = [rows_top[1], rows_top[0], rows_top[2]]
    elif len(rows_top) == 2:
        ordered = [rows_top[1], rows_top[0]]
    else:
        ordered = rows_top

    n = len(ordered)
    card_w = (content_width - (n - 1) * 4 * mm) / n
    inner_w = card_w - 10 * mm
    contents = []
    winner_indexes = []
    for idx, (_, r) in enumerate(ordered):
        is_winner = (n >= 3 and idx == 1) or (n == 2 and idx == 1) or (n == 1)
        contents.append(_make_battery_card_content(r, is_winner, styles, inner_w))
        if is_winner:
            winner_indexes.append(idx)

    grid = Table([contents], colWidths=[card_w] * n)
    style_cmds = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5 * mm),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5 * mm),
        ("TOPPADDING", (0, 0), (-1, -1), 5 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6 * mm),
    ]
    for col in range(n):
        if col in winner_indexes:
            style_cmds.append(("BACKGROUND", (col, 0), (col, 0), COLOR_GREEN_SOFT))
            style_cmds.append(("BOX", (col, 0), (col, 0), 1.5, COLOR_ACCENT))
        else:
            style_cmds.append(("BACKGROUND", (col, 0), (col, 0), white))
            style_cmds.append(("BOX", (col, 0), (col, 0), 0.6, COLOR_BORDER))
    grid.setStyle(TableStyle(style_cmds))
    return grid


def _make_quality_tile(quality_score: Optional[dict], styles, content_width: float):
    """
    Hero-style score-tegel: links de grote totaalscore met een label,
    rechts vier vinkjes met component-namen. Detail-uitleg per component
    staat in de methodologie-sectie verderop in het rapport.
    """
    if not quality_score:
        return Spacer(1, 0)

    qs_val = quality_score.get("totaalscore") or quality_score.get("total_score") or 0
    comp = quality_score.get("componenten", {})

    def _comp_score(key):
        if key in comp:
            return comp[key].get("score", 0)
        flat_keys = {
            "dekkingsgraad": "coverage_score",
            "seizoensspreiding": "seasonal_score",
            "consistentie": "consistency_score",
            "input_type": "input_type_score",
        }
        return quality_score.get(flat_keys.get(key, key), 0)

    comps = [
        ("Dekkingsgraad", _comp_score("dekkingsgraad")),
        ("Seizoensspreiding", _comp_score("seizoensspreiding")),
        ("Consistentie", _comp_score("consistentie")),
        ("Input-type", _comp_score("input_type")),
    ]

    # Totaalscore kleur + label
    if qs_val >= 80:
        score_color = HexColor("#15803D")
        score_label = "zeer betrouwbaar"
    elif qs_val >= 50:
        score_color = HexColor("#B45309")
        score_label = "redelijk betrouwbaar"
    else:
        score_color = HexColor("#B91C1C")
        score_label = "beperkt betrouwbaar"

    # --- Linker hero-kolom: groot getal + label ---
    hero_big_style = ParagraphStyle(
        "qs_big", parent=styles["KpiTileValue"],
        fontSize=44, leading=46, textColor=score_color, alignment=TA_LEFT,
    )
    hero_small_style = ParagraphStyle(
        "qs_small", parent=styles["KpiTileFoot"],
        fontSize=11, leading=13, textColor=COLOR_MUTED, alignment=TA_LEFT,
    )
    hero_label_style = ParagraphStyle(
        "qs_label", parent=styles["KpiTileLabel"],
        fontSize=9, leading=11, textColor=score_color, alignment=TA_LEFT,
    )

    hero_cell = Table(
        [
            [Paragraph(f"{qs_val:.0f}<font size='14' color='#5B6580'>/100</font>", hero_big_style)],
            [Paragraph(score_label, hero_label_style)],
        ],
        colWidths=[None],
    )
    hero_cell.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (0, 0), 1 * mm),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 0),
    ]))

    # --- Rechter kolom: 2x2 vinkjes-grid + footer-verwijzing ---
    check_name_style = ParagraphStyle(
        "qs_check_name", parent=styles["BatteryStatValue"],
        fontSize=10, leading=13, textColor=COLOR_INK, alignment=TA_LEFT,
    )

    def _check_row(name, score):
        if score >= 80:
            icon = "<font color='#15803D'><b>✓</b></font>"
        elif score >= 50:
            icon = "<font color='#B45309'><b>!</b></font>"
        else:
            icon = "<font color='#B91C1C'><b>✗</b></font>"
        return Paragraph(f"{icon}&nbsp;&nbsp;{name}", check_name_style)

    # 2x2 grid (2 kolommen, 2 rijen) - rustiger dan 4 onder elkaar
    checks_grid = Table(
        [
            [_check_row(comps[0][0], comps[0][1]), _check_row(comps[1][0], comps[1][1])],
            [_check_row(comps[2][0], comps[2][1]), _check_row(comps[3][0], comps[3][1])],
        ],
        colWidths=[None, None],
    )
    checks_grid.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 1 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1 * mm),
    ]))

    ref_style = ParagraphStyle(
        "qs_ref", parent=styles["KpiTileFoot"],
        fontSize=8, leading=11, textColor=COLOR_MUTED, alignment=TA_LEFT,
    )
    ref_p = Paragraph(
        "Uitleg per component staat in de methodologie-sectie verderop in het rapport.",
        ref_style,
    )

    right_cell = Table(
        [[checks_grid], [ref_p]],
        colWidths=[None],
    )
    right_cell.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (0, 0), 2 * mm),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 0),
    ]))

    # --- Buitenste 2-koloms tegel ---
    inner_w = content_width - 8 * mm  # binnen padding
    left_w = inner_w * 0.30
    right_w = inner_w * 0.70

    outer = Table([[hero_cell, right_cell]], colWidths=[left_w, right_w])
    outer.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BACKGROUND", (0, 0), (-1, -1), COLOR_LIGHT_BG),
        ("BOX", (0, 0), (-1, -1), 0.5, COLOR_BORDER),
        ("LEFTPADDING", (0, 0), (-1, -1), 5 * mm),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5 * mm),
        ("TOPPADDING", (0, 0), (-1, -1), 5 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5 * mm),
        ("ROUNDEDCORNERS", [10, 10, 10, 10]),
    ]))
    return outer


def _build_cover_v2(
    results: pd.DataFrame,
    config: SimulationConfig,
    styles,
    quality_score: Optional[dict] = None,
    sizing_results: Optional[pd.DataFrame] = None,
    user_name: Optional[str] = None,
) -> list:
    """
    Nieuwe pagina 1: brand + cover-title + verdict + 3 KPIs + top 3 batterijen.
    Vervangt _build_title_section + _build_summary_section + _build_sizing_section
    voor de eerste pagina.
    """
    elements = []
    content_width = 210 * mm - 40 * mm  # A4 minus 20mm marges links/rechts

    # --- Brand row (alleen logo + naam links; score komt straks in tegel onderaan) ---
    brand = Table(
        [
            [Paragraph(
                '<font color="#06B6D4"><b>⚡</b></font> <b>Energy-Truth</b>',
                styles["BrandName"],
            )],
            [Paragraph("Jouw eerlijke batterij-advies", styles["BrandSub"])],
        ],
        colWidths=[content_width],
    )
    brand.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (0, 0), 1 * mm),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 6 * mm),
    ]))
    elements.append(brand)

    # --- Cover title + sub ---
    naam_str = user_name or "daar"
    elements.append(Paragraph(
        f"Hoi {naam_str},<br/>dit is jouw verdict.",
        styles["CoverTitle"],
    ))
    elements.append(Paragraph(
        f"Berekening over jouw meterdata van {config.simulation.start_date} t/m "
        f"{config.simulation.end_date}.",
        styles["CoverSub"],
    ))

    # --- Top 3 batterijen ophalen, dan verdict afleiden ---
    top3 = _select_top3_batteries(sizing_results) if sizing_results is not None else pd.DataFrame()
    verdict = _get_cover_verdict(sizing_results, top3)

    # --- Verdict-balk (bevat nu zelf de 3 hoofdcijfers; geen aparte KPI-tegelrij) ---
    elements.append(Spacer(1, 2 * mm))
    elements.append(_make_verdict_block(verdict, styles, content_width))
    elements.append(Spacer(1, 11 * mm))

    # --- Top 3 eyebrow + grid ---
    elements.append(Paragraph(
        "DE 3 BEST PASSENDE BATTERIJEN VOOR JOU",
        styles["SectionEyebrow"],
    ))
    elements.append(Spacer(1, 4 * mm))
    elements.append(_make_top3_grid(top3, styles, content_width))

    # --- Betrouwbaarheid: eyebrow + tegel ---
    elements.append(Spacer(1, 11 * mm))
    elements.append(Paragraph(
        "HOE BETROUWBAAR IS DIT ADVIES?",
        styles["SectionEyebrow"],
    ))
    elements.append(Spacer(1, 4 * mm))
    elements.append(_make_quality_tile(quality_score, styles, content_width))

    return elements


# ---------------------------------------------------------------------------
# V2 — Pagina 2: "Jouw jaar in stroom" (helpers + sectie)
# ---------------------------------------------------------------------------

# Geschatte gemiddelde prijzen voor het berekenen van handelsbalans-waarden.
# Pure NETO inkoop/teruglevering wordt gewaardeerd met deze defaults wanneer
# we geen exacte per-kwartier-prijzen meegekregen hebben.
_AVG_INKOOP_PRIJS_EUR_PER_KWH = 0.32   # all-in: EPEX + EB + ODE + btw + opslag
_AVG_VERKOOP_PRIJS_EUR_PER_KWH = 0.10  # huidige saldering: ongeveer inkoopprijs


def _compute_energy_balance(meter_data: pd.DataFrame) -> dict:
    """
    Bereken de 'handelsbalans' uit ruwe meterdata:
      - aantal kwartieren waarin teruggeleverd is (verkoop-momenten)
      - aantal kwartieren waarin van het net afgenomen is (inkoop-momenten)
      - totale teruggeleverde en ingekochte kWh
      - geschatte euro-waarde van beide stromen
    """
    if meter_data is None or meter_data.empty:
        return {}

    # Robuust: missende kolommen → 0
    feed = pd.to_numeric(meter_data.get("feed_in_kwh", pd.Series(dtype=float)), errors="coerce").fillna(0)
    cons = pd.to_numeric(meter_data.get("consumption_kwh", pd.Series(dtype=float)), errors="coerce").fillna(0)

    sell_moments = int((feed > 0).sum())
    buy_moments = int((cons > 0).sum())
    sell_kwh = float(feed.sum())
    buy_kwh = float(cons.sum())

    # Annualiseer naar 1 jaar als de simulatieperiode <> 1 jaar is
    n_quarters = len(meter_data)
    quarters_per_year = 365.25 * 24 * 4  # 35064.75
    if n_quarters > 0:
        scale = quarters_per_year / n_quarters
    else:
        scale = 1.0

    sell_moments_y = int(round(sell_moments * scale))
    buy_moments_y = int(round(buy_moments * scale))
    sell_kwh_y = sell_kwh * scale
    buy_kwh_y = buy_kwh * scale

    return {
        "sell_moments": sell_moments_y,
        "buy_moments": buy_moments_y,
        "sell_kwh": sell_kwh_y,
        "buy_kwh": buy_kwh_y,
        "sell_value_eur": sell_kwh_y * _AVG_VERKOOP_PRIJS_EUR_PER_KWH,
        "buy_value_eur": buy_kwh_y * _AVG_INKOOP_PRIJS_EUR_PER_KWH,
    }


def _make_balance_tile(label: str, big_value: str, sub_value: str,
                      bg, border, fg, styles, tile_width: float = None) -> Table:
    """Eén balance-tegel (VERKOPEN / INKOPEN). Met expliciete breedte zodat
    beide tegels in de rij even groot zijn ongeacht de inhoud."""
    label_style = ParagraphStyle(
        "bal_label", parent=styles["KpiTileLabel"],
        fontSize=10, leading=12, textColor=fg, alignment=TA_LEFT,
    )
    big_style = ParagraphStyle(
        "bal_big", parent=styles["KpiTileValue"],
        fontSize=26, leading=30, textColor=COLOR_INK, alignment=TA_LEFT,
    )
    sub_style = ParagraphStyle(
        "bal_sub", parent=styles["KpiTileFoot"],
        fontSize=11, leading=14, textColor=COLOR_MUTED, alignment=TA_LEFT,
    )
    t = Table(
        [
            [Paragraph(label, label_style)],
            [Paragraph(big_value, big_style)],
            [Paragraph(sub_value, sub_style)],
        ],
        colWidths=[tile_width],
    )
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), bg),
        ("BOX", (0, 0), (-1, -1), 0.5, border),
        ("LEFTPADDING", (0, 0), (-1, -1), 6 * mm),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6 * mm),
        ("TOPPADDING", (0, 0), (0, 0), 5 * mm),
        ("BOTTOMPADDING", (0, -1), (-1, -1), 5 * mm),
        ("TOPPADDING", (0, 1), (-1, -1), 1 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, -2), 1 * mm),
        ("ROUNDEDCORNERS", [10, 10, 10, 10]),
    ]))
    return t


def _make_balance_row(balance: dict, styles, content_width: float) -> Table:
    """Twee balance-tegels naast elkaar (VERKOPEN | INKOPEN)."""
    sell_big = f"{balance['sell_moments']:,} momenten".replace(",", ".")
    sell_sub = (
        f"{balance['sell_kwh']:,.0f} kWh teruggeleverd "
        f"<font color='#5B6580'>(~{_fmt_eur_short(balance['sell_value_eur'])} waarde)</font>"
    ).replace(",", ".")
    buy_big = f"{balance['buy_moments']:,} momenten".replace(",", ".")
    buy_sub = (
        f"{balance['buy_kwh']:,.0f} kWh ingekocht "
        f"<font color='#5B6580'>(~{_fmt_eur_short(balance['buy_value_eur'])} waarde)</font>"
    ).replace(",", ".")

    # Bereken de tegelbreedte eerst zodat beide tiles expliciet even breed zijn
    tile_w = (content_width - 4 * mm) / 2.0
    inner_w = tile_w - 12 * mm  # binnen LEFT/RIGHT padding van de tile

    sell_tile = _make_balance_tile(
        "VERKOPEN", sell_big, sell_sub,
        COLOR_GREEN_SOFT, COLOR_GREEN_BORDER, HexColor("#15803D"), styles,
        tile_width=inner_w,
    )
    buy_tile = _make_balance_tile(
        "INKOPEN", buy_big, buy_sub,
        COLOR_SOFT, COLOR_CYAN_BORDER, COLOR_SECONDARY, styles,
        tile_width=inner_w,
    )

    row = Table([[sell_tile, buy_tile]], colWidths=[tile_w, tile_w])
    row.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (0, 0), 2 * mm),
        ("LEFTPADDING", (1, 0), (1, 0), 2 * mm),
        ("RIGHTPADDING", (1, 0), (1, 0), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    return row


def _make_monthly_chart(meter_data: pd.DataFrame, content_width_mm: float = 170) -> Optional[Image]:
    """Maandgrafiek (gegroepeerde staven verbruik vs opwek) als reportlab Image."""
    if meter_data is None or meter_data.empty:
        return None

    # Lazy import matplotlib (alleen nodig voor deze grafiek)
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        logger.warning("matplotlib niet geinstalleerd — maandgrafiek wordt overgeslagen")
        return None

    df = meter_data.copy()
    ts = pd.to_datetime(df["timestamp_from"], errors="coerce", utc=True)
    df["_month"] = ts.dt.month
    df["_year"] = ts.dt.year
    cons = pd.to_numeric(df.get("consumption_kwh", 0), errors="coerce").fillna(0)
    feed = pd.to_numeric(df.get("feed_in_kwh", 0), errors="coerce").fillna(0)
    df["_cons"] = cons
    df["_feed"] = feed
    # Aggregeer per maand-naam (gemiddeld over jaren als er meerdere zijn)
    monthly = df.groupby("_month").agg(
        verbruik=("_cons", "sum"),
        opwek=("_feed", "sum"),
        kwartieren=("_cons", "size"),
    )
    # Normaliseer per maand naar 1 representatieve maand (gemiddelde, geen totale som over jaren)
    expected_q_per_month = 30.4375 * 24 * 4  # 2922 kwartieren
    monthly["scale"] = expected_q_per_month / monthly["kwartieren"].clip(lower=1)
    monthly["verbruik"] = monthly["verbruik"] * monthly["scale"]
    monthly["opwek"] = monthly["opwek"] * monthly["scale"]
    monthly = monthly.reindex(range(1, 13))  # alle 12 maanden

    fig, ax = plt.subplots(figsize=(content_width_mm / 25.4, 2.6))
    x = np.arange(12)
    width = 0.38
    months_nl = ["jan", "feb", "mrt", "apr", "mei", "jun",
                 "jul", "aug", "sep", "okt", "nov", "dec"]
    verbruik_vals = monthly["verbruik"].fillna(0).values
    opwek_vals = monthly["opwek"].fillna(0).values

    ax.bar(x - width / 2, verbruik_vals, width, color="#0B1220", label="Verbruik (kWh van net)")
    ax.bar(x + width / 2, opwek_vals, width, color="#10B981", label="Teruglevering (kWh naar net)")
    ax.set_xticks(x)
    ax.set_xticklabels(months_nl, fontsize=8)
    ax.tick_params(axis="y", labelsize=8)
    ax.set_ylabel("kWh", fontsize=8, color="#5B6580")
    # Legenda boven de plot, horizontaal in 2 kolommen — voorkomt overlap met staven
    ax.legend(
        loc="lower left",
        bbox_to_anchor=(0, 1.02),
        ncol=2,
        frameon=False,
        fontsize=8,
        handlelength=1.2,
        handletextpad=0.5,
        columnspacing=2.0,
    )
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#E6EAF2")
    ax.spines["bottom"].set_color("#E6EAF2")
    ax.grid(axis="y", linestyle=":", color="#E6EAF2", linewidth=0.5)
    ax.set_axisbelow(True)
    # Top margin voor de legenda
    plt.subplots_adjust(top=0.85)
    plt.tight_layout(pad=0.5, rect=[0, 0, 1, 0.92])

    buf = BytesIO()
    plt.savefig(buf, format="png", dpi=160, bbox_inches="tight", transparent=True)
    plt.close(fig)
    buf.seek(0)

    img_width = content_width_mm * mm
    return Image(buf, width=img_width, height=img_width * 0.32)


def _build_energy_year_v2(meter_data: pd.DataFrame, results: pd.DataFrame,
                          config: SimulationConfig, styles) -> list:
    """Pagina 2: "Jouw jaar in stroom" — handelsbalans + maandgrafiek + insight."""
    elements = []
    content_width = 210 * mm - 40 * mm

    # Brand row (zelfde stijl als cover, korter)
    brand = Table(
        [
            [Paragraph(
                '<font color="#06B6D4"><b>⚡</b></font> <b>Energy-Truth</b>',
                styles["BrandName"],
            )],
            [Paragraph("Pagina 2 &middot; Jouw jaar in stroom", styles["BrandSub"])],
        ],
        colWidths=[content_width],
    )
    brand.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (0, 0), 1 * mm),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 8 * mm),
    ]))
    elements.append(brand)

    # Headline + sub
    elements.append(Paragraph("Jouw jaar in stroom", styles["CoverTitle"]))
    elements.append(Paragraph(
        "Zonder dat je het zelf doorhad, ben je een mini-energiehandelaar. "
        "Hieronder hoe vaak je dit jaar stroom verkocht aan het net en hoe vaak je inkocht.",
        styles["CoverSub"],
    ))

    # Balance-tegels
    balance = _compute_energy_balance(meter_data)
    if balance:
        elements.append(Spacer(1, 2 * mm))
        elements.append(_make_balance_row(balance, styles, content_width))
        # Korte voetnoot onder de tegels: wat is een "moment"
        moment_note_style = ParagraphStyle(
            "moment_note", parent=styles["KpiTileFoot"],
            fontSize=8.5, leading=11, textColor=COLOR_MUTED, alignment=TA_LEFT,
        )
        elements.append(Spacer(1, 2 * mm))
        elements.append(Paragraph(
            "Een <b>moment</b> is een meting van 15 minuten — een jaar telt 35.040 momenten.",
            moment_note_style,
        ))

    # Maandgrafiek
    elements.append(Spacer(1, 10 * mm))
    elements.append(Paragraph(
        "VERBRUIK EN TERUGLEVERING PER MAAND",
        styles["SectionEyebrow"],
    ))
    elements.append(Spacer(1, 3 * mm))
    chart = _make_monthly_chart(meter_data, content_width_mm=170)
    if chart is not None:
        elements.append(chart)

    # Insight onder grafiek
    elements.append(Spacer(1, 6 * mm))
    insight_style = ParagraphStyle(
        "p2_insight", parent=styles["BodyText"],
        fontSize=11, leading=15, textColor=COLOR_INK,
    )
    insight_table = Table(
        [[Paragraph(
            "<b>Wat zie je hier?</b> In de zomer wek je veel meer op dan je gebruikt, in de winter "
            "is het andersom. Bij saldering trek je deze stromen tegen elkaar weg, maar dat "
            "verandert in 2027. Een batterij vangt elke zonnige dag de middag-overschot op en "
            "gebruikt die 's avonds in jouw eigen huis. Het effect speelt zich binnen één dag af, "
            "maar telt vooral op in de zonnige maanden.",
            insight_style,
        )]],
        colWidths=[content_width],
    )
    insight_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), COLOR_SOFT),
        ("BOX", (0, 0), (-1, -1), 0.5, COLOR_CYAN_BORDER),
        ("LEFTPADDING", (0, 0), (-1, -1), 6 * mm),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6 * mm),
        ("TOPPADDING", (0, 0), (-1, -1), 4 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4 * mm),
        ("ROUNDEDCORNERS", [10, 10, 10, 10]),
    ]))
    elements.append(insight_table)

    return elements


# ---------------------------------------------------------------------------
# V2 — Pagina 3: "Wat de batterij voor jou doet" (helpers + sectie)
# ---------------------------------------------------------------------------

_NL_MONTHS_TO_SEASON = {
    12: "winter", 1: "winter", 2: "winter",
    3: "lente", 4: "lente", 5: "lente",
    6: "zomer", 7: "zomer", 8: "zomer",
    9: "herfst", 10: "herfst", 11: "herfst",
}
_SEASON_ORDER = ["lente", "zomer", "herfst", "winter"]


def _run_battery_sim_for_report(meter_data: pd.DataFrame, config: SimulationConfig) -> Optional[pd.DataFrame]:
    """Run een batterij-simulatie met strategie A (zelfverbruik) voor pagina 3."""
    try:
        from battery_simulator import simulate_battery
        sim = simulate_battery(meter_data, config.battery, strategy="A")
        if sim.empty:
            return None
        return sim
    except Exception as e:
        logger.warning(f"Batterij-simulatie voor pagina 3 mislukt: {e}")
        return None


def _compute_seasonal_avg_day(sim_df: pd.DataFrame) -> dict:
    """
    Geef per seizoen een DataFrame met 96 rijen (één per kwartier van de dag),
    met gemiddelde feed_in (zon-proxy), consumption (verbruik van net zonder
    batterij) en soc (batterij-vulling met batterij).
    """
    if sim_df is None or sim_df.empty:
        return {}

    df = sim_df.copy()
    ts = pd.to_datetime(df["timestamp_from"], errors="coerce", utc=True)
    df["_month"] = ts.dt.month
    df["_qod"] = ts.dt.hour * 4 + (ts.dt.minute // 15)
    df["_season"] = df["_month"].map(_NL_MONTHS_TO_SEASON)

    out = {}
    for season in _SEASON_ORDER:
        sub = df[df["_season"] == season]
        if sub.empty:
            continue
        agg = sub.groupby("_qod").agg(
            feed_in=("feed_in_kwh", "mean"),
            consumption=("consumption_kwh", "mean"),
            soc=("soc", "mean"),
        )
        # Vul alle 96 kwartieren in, ook ontbrekende
        agg = agg.reindex(range(96)).fillna(0)
        out[season] = agg
    return out


def _compute_battery_kpis(sim_df: pd.DataFrame, sizing_results: Optional[pd.DataFrame],
                          meter_data: pd.DataFrame, config: SimulationConfig) -> dict:
    """
    Bereken 4 KPI's voor pagina 3:
      - kwh_extra_eigen_per_jaar: hoeveel kWh extra zelf gebruikt dankzij batterij
        (= feed_in zonder batterij - grid_feed_in met batterij), geannualiseerd
      - kwh_per_dag_opgeslagen: gemiddeld per dag in de batterij
      - cycli_per_jaar: EFC uit sizing-data
      - uren_onafhankelijk_per_dag: gemiddeld uren/dag dat grid_consumption=0
    """
    if sim_df is None or sim_df.empty:
        return {}

    n_q = len(sim_df)
    quarters_per_year = 365.25 * 24 * 4
    scale = quarters_per_year / n_q if n_q > 0 else 1.0
    days_in_data = n_q / 96.0 if n_q > 0 else 1.0

    feed_zonder = float(pd.to_numeric(meter_data.get("feed_in_kwh", 0), errors="coerce").fillna(0).sum())
    feed_met = float(pd.to_numeric(sim_df.get("grid_feed_in", 0), errors="coerce").fillna(0).sum())
    kwh_extra_jr = max(0.0, (feed_zonder - feed_met) * scale)

    # Opslag per dag: schat uit veranderingen in SOC waar SOC stijgt
    soc = pd.to_numeric(sim_df.get("soc", 0), errors="coerce").fillna(0).to_numpy()
    soc_diff = np.diff(soc, prepend=soc[0] if len(soc) > 0 else 0)
    charge_kwh = float(np.clip(soc_diff, 0, None).sum())
    kwh_dag_opslag = charge_kwh / max(days_in_data, 1.0)

    # Uren onafhankelijk: aandeel kwartieren met grid_consumption == 0
    grid_cons = pd.to_numeric(sim_df.get("grid_consumption", 0), errors="coerce").fillna(0)
    onafh_kwart = int((grid_cons <= 0.001).sum())
    uren_onafh_per_dag = (onafh_kwart / max(days_in_data, 1.0)) / 4.0

    # Cycli per jaar uit sizing
    cycli_jr = None
    if sizing_results is not None and not sizing_results.empty:
        eigen = sizing_results[sizing_results.get("battery_id", 0) == -1]
        if not eigen.empty:
            cycli_jr = float(eigen.iloc[0].get("efc_per_jaar", 0))
        else:
            cycli_jr = float(sizing_results.iloc[0].get("efc_per_jaar", 0))

    return {
        "kwh_extra_eigen_per_jaar": kwh_extra_jr,
        "kwh_per_dag_opgeslagen": kwh_dag_opslag,
        "cycli_per_jaar": cycli_jr,
        "uren_onafhankelijk_per_dag": uren_onafh_per_dag,
    }


def _make_battery_kpi_tile(label, big, foot, color, bg, border, styles):
    """KPI-tegel inhoud (Paragraph-stack). Returns (content_table, bg, border)
    zodat de outer grid de styling per cel kan zetten — gelijke hoogtes
    automatisch via auto-row-height."""
    label_style = ParagraphStyle(
        "p3_kpi_label", parent=styles["KpiTileLabel"],
        fontSize=8, leading=10, textColor=color, alignment=TA_LEFT,
    )
    big_style = ParagraphStyle(
        "p3_kpi_big", parent=styles["KpiTileValue"],
        fontSize=18, leading=22, textColor=COLOR_INK, alignment=TA_LEFT,
    )
    foot_style = ParagraphStyle(
        "p3_kpi_foot", parent=styles["KpiTileFoot"],
        fontSize=8.5, leading=11, textColor=COLOR_MUTED, alignment=TA_LEFT,
    )
    content = Table(
        [
            [Paragraph(label, label_style)],
            [Spacer(1, 2 * mm)],
            [Paragraph(big, big_style)],
            [Spacer(1, 2 * mm)],
            [Paragraph(foot, foot_style)],
        ],
        colWidths=[None],
    )
    content.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    return content, bg, border


def _make_battery_kpi_row(kpis: dict, styles, content_width: float) -> Table:
    """Rij met 4 batterij-KPI tegels. Outer-cell-styling zorgt voor gelijke hoogtes."""
    def _fmt_int(v):
        return f"{v:,.0f}".replace(",", ".") if pd.notna(v) else "—"

    t1, bg1, br1 = _make_battery_kpi_tile(
        "EXTRA EIGEN GEBRUIK",
        f"{_fmt_int(kpis.get('kwh_extra_eigen_per_jaar'))} kWh",
        "per jaar dankzij de batterij",
        COLOR_SECONDARY, COLOR_SOFT, COLOR_CYAN_BORDER, styles,
    )
    t2, bg2, br2 = _make_battery_kpi_tile(
        "OPSLAG PER DAG",
        f"{kpis.get('kwh_per_dag_opgeslagen', 0):.1f} kWh",
        "gemiddeld in de batterij per dag",
        COLOR_SECONDARY, COLOR_SOFT, COLOR_CYAN_BORDER, styles,
    )
    cycli_val = kpis.get("cycli_per_jaar")
    t3, bg3, br3 = _make_battery_kpi_tile(
        "VOLLE CYCLI",
        f"{cycli_val:.0f}/jaar" if pd.notna(cycli_val) else "—",
        "keer volledig vullen en legen",
        COLOR_SECONDARY, COLOR_SOFT, COLOR_CYAN_BORDER, styles,
    )
    t4, bg4, br4 = _make_battery_kpi_tile(
        "ONAFHANKELIJK",
        f"{kpis.get('uren_onafhankelijk_per_dag', 0):.1f} uur",
        "per dag geen stroom van het net",
        HexColor("#15803D"), COLOR_GREEN_SOFT, COLOR_GREEN_BORDER, styles,
    )

    col_w = (content_width - 9 * mm) / 4.0
    row = Table([[t1, t2, t3, t4]], colWidths=[col_w] * 4)
    style_cmds = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4 * mm),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4 * mm),
        ("TOPPADDING", (0, 0), (-1, -1), 4 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4 * mm),
    ]
    for col_idx, (bg, br) in enumerate([(bg1, br1), (bg2, br2), (bg3, br3), (bg4, br4)]):
        style_cmds.append(("BACKGROUND", (col_idx, 0), (col_idx, 0), bg))
        style_cmds.append(("BOX", (col_idx, 0), (col_idx, 0), 0.5, br))
    row.setStyle(TableStyle(style_cmds))
    return row


def _make_season_chart(agg: pd.DataFrame, season_name: str, capacity_kwh: float,
                       width_mm: float = 80) -> Optional[Image]:
    """Mini 24-uurs grafiek voor één seizoen met 3 lijnen."""
    if agg is None or agg.empty:
        return None

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return None

    # X-as: uur (0-24) → 96 kwartieren → 0, 0.25, 0.5 ... 23.75
    x = np.arange(96) / 4.0

    fig, ax1 = plt.subplots(figsize=(width_mm / 25.4, 1.55))
    # Lijnen op linker as (kWh per kwartier)
    line_zon, = ax1.plot(x, agg["feed_in"], color="#10B981", linewidth=1.6, label="Naar net (zon)")
    line_ver, = ax1.plot(x, agg["consumption"], color="#0B1220", linewidth=1.6, label="Van net (verbruik)")
    ax1.fill_between(x, agg["feed_in"], color="#10B981", alpha=0.10)

    ax1.set_xticks([0, 6, 12, 18, 24])
    ax1.set_xticklabels(["00", "06", "12", "18", "24"], fontsize=7, color="#5B6580")
    ax1.tick_params(axis="y", labelsize=7, colors="#5B6580")
    ax1.spines["top"].set_visible(False)
    ax1.spines["right"].set_visible(False)
    ax1.spines["left"].set_color("#E6EAF2")
    ax1.spines["bottom"].set_color("#E6EAF2")
    ax1.grid(axis="y", linestyle=":", color="#E6EAF2", linewidth=0.4)
    ax1.set_axisbelow(True)
    ax1.set_ylim(bottom=0)
    ax1.set_xlim(0, 24)

    # Tweede as voor SoC als % van capaciteit
    ax2 = ax1.twinx()
    soc_pct = (agg["soc"] / capacity_kwh) * 100.0 if capacity_kwh > 0 else agg["soc"] * 0
    line_soc, = ax2.plot(x, soc_pct, color="#06B6D4", linewidth=1.4, linestyle="--",
                         label="Batterij %")
    ax2.set_ylim(0, 100)
    ax2.tick_params(axis="y", labelsize=7, colors="#0891B2")
    ax2.spines["top"].set_visible(False)
    ax2.spines["left"].set_visible(False)
    ax2.spines["bottom"].set_visible(False)
    ax2.spines["right"].set_color("#E6EAF2")

    # Seizoenstitel binnen de plot
    ax1.set_title(season_name.upper(), fontsize=8, color="#0B1220", loc="left", fontweight="bold", pad=4)

    plt.tight_layout(pad=0.4)

    buf = BytesIO()
    plt.savefig(buf, format="png", dpi=160, bbox_inches="tight", transparent=True)
    plt.close(fig)
    buf.seek(0)
    return Image(buf, width=width_mm * mm, height=width_mm * mm * 0.45)


def _make_seasons_grid(seasonal_data: dict, capacity_kwh: float, content_width: float) -> Table:
    """2x2 grid met 4 seizoen-mini-grafieken."""
    if not seasonal_data:
        return Paragraph("Geen data om seizoens-grafieken te tekenen.", getSampleStyleSheet()["BodyText"])

    chart_w = (content_width - 6 * mm) / 2.0
    charts = []
    for season in _SEASON_ORDER:
        if season in seasonal_data:
            img = _make_season_chart(seasonal_data[season], season, capacity_kwh,
                                     width_mm=chart_w / mm)
            charts.append(img if img is not None else Paragraph(season, getSampleStyleSheet()["BodyText"]))
        else:
            charts.append(Paragraph(f"Geen {season}-data", getSampleStyleSheet()["BodyText"]))

    # 2x2 grid
    grid = Table(
        [
            [charts[0], charts[1]],
            [charts[2], charts[3]],
        ],
        colWidths=[chart_w, chart_w],
    )
    grid.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (0, -1), 3 * mm),
        ("RIGHTPADDING", (1, 0), (1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, 0), 0),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 3 * mm),
        ("TOPPADDING", (0, 1), (-1, 1), 0),
        ("BOTTOMPADDING", (0, 1), (-1, 1), 0),
    ]))
    return grid


def _make_legend_swatch(color, dashed: bool = False) -> Table:
    """Klein gekleurd blokje voor in een legenda-rij. Bij dashed=True wordt
    de cel een dunne dashed lijn-representatie (gerealiseerd via overlay)."""
    if dashed:
        # Gestreepte lijn-suggestie: twee korte streepjes naast elkaar in kleur
        cell_content = Paragraph(
            "<b>- -</b>",
            ParagraphStyle("swatch_dashed", fontName="Helvetica-Bold",
                           fontSize=12, leading=13, alignment=TA_CENTER, textColor=color),
        )
        t = Table([[cell_content]], colWidths=[8 * mm], rowHeights=[4 * mm])
        t.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]))
        return t
    # Vol gekleurd blokje
    t = Table([[""]], colWidths=[6 * mm], rowHeights=[3 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), color),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("ROUNDEDCORNERS", [2, 2, 2, 2]),
    ]))
    return t


def _make_battery_day_legend(styles, content_width: float) -> Table:
    """Legenda-rij boven het 4-seizoen grid: drie items met swatch + label."""
    label_style = ParagraphStyle(
        "legend_label", parent=styles["KpiTileFoot"],
        fontSize=9, leading=11, textColor=COLOR_INK, alignment=TA_LEFT,
    )

    items = [
        (_make_legend_swatch(COLOR_INK), "Van net (verbruik)"),
        (_make_legend_swatch(COLOR_ACCENT), "Naar net (teruglevering)"),
        (_make_legend_swatch(COLOR_PRIMARY, dashed=True), "Batterij-vulling (%)"),
    ]

    # Items met een vaste, smalle breedte (swatch 8mm + label 40mm = 48mm).
    # De outer kolom is content_width/3 ≈ 56mm; via hAlign="CENTER" plus
    # ALIGN center op de outer cellen komen items in het midden van hun kolom.
    item_w_swatch = 8 * mm
    item_w_label = 40 * mm
    cells = []
    for swatch, label in items:
        item_t = Table(
            [[swatch, Paragraph(label, label_style)]],
            colWidths=[item_w_swatch, item_w_label],
        )
        item_t.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]))
        item_t.hAlign = "CENTER"
        cells.append(item_t)

    col_w = content_width / 3.0
    row = Table([cells], colWidths=[col_w] * 3)
    row.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    row.hAlign = "CENTER"
    return row


def _build_battery_day_v2(meter_data: pd.DataFrame, sizing_results: Optional[pd.DataFrame],
                          config: SimulationConfig, styles) -> list:
    """Pagina 3: "Wat de batterij voor jou doet" — 4 KPI's + 4 seizoens-mini-grafieken."""
    elements = []
    content_width = 210 * mm - 40 * mm

    # Brand row
    brand = Table(
        [
            [Paragraph(
                '<font color="#06B6D4"><b>⚡</b></font> <b>Energy-Truth</b>',
                styles["BrandName"],
            )],
            [Paragraph("Pagina 3 &middot; Wat de batterij voor jou doet", styles["BrandSub"])],
        ],
        colWidths=[content_width],
    )
    brand.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (0, 0), 1 * mm),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 8 * mm),
    ]))
    elements.append(brand)

    # Headline + sub
    elements.append(Paragraph("Wat de batterij voor jou doet", styles["CoverTitle"]))
    elements.append(Paragraph(
        "Een gemiddelde dag in elk seizoen. Zo zie je wanneer de batterij voor jou werkt en wanneer "
        "hij het lastiger heeft.",
        styles["CoverSub"],
    ))

    # Run simulatie
    sim_df = _run_battery_sim_for_report(meter_data, config)
    if sim_df is None:
        elements.append(Paragraph(
            "Batterij-simulatie kon niet draaien — pagina 3 is leeg.",
            styles["BodyText"],
        ))
        return elements

    # KPI rij
    kpis = _compute_battery_kpis(sim_df, sizing_results, meter_data, config)
    elements.append(Spacer(1, 2 * mm))
    elements.append(_make_battery_kpi_row(kpis, styles, content_width))

    # Seizoens-grid met legenda eronder
    elements.append(Spacer(1, 10 * mm))
    elements.append(Paragraph(
        "EEN GEMIDDELDE DAG PER SEIZOEN",
        styles["SectionEyebrow"],
    ))
    elements.append(Spacer(1, 3 * mm))
    seasonal = _compute_seasonal_avg_day(sim_df)
    capacity = float(getattr(config.battery, "capacity_kwh", 0) or 0)
    elements.append(_make_seasons_grid(seasonal, capacity, content_width))
    elements.append(Spacer(1, 4 * mm))
    elements.append(_make_battery_day_legend(styles, content_width))

    # Insight onder grafieken
    elements.append(Spacer(1, 6 * mm))
    insight_style = ParagraphStyle(
        "p3_insight", parent=styles["BodyText"],
        fontSize=11, leading=15, textColor=COLOR_INK,
    )
    insight_table = Table(
        [[Paragraph(
            "<b>Wat zie je hier?</b> In zomer en lente vult de batterij zich vroeg op de dag uit "
            "jouw zon-overschot en is 's avonds nog hoog gevuld. In herfst en winter blijft de "
            "vulling laag omdat er nauwelijks teruglevering is. De batterij betaalt zichzelf "
            "vooral terug in de zonnige maanden.",
            insight_style,
        )]],
        colWidths=[content_width],
    )
    insight_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), COLOR_SOFT),
        ("BOX", (0, 0), (-1, -1), 0.5, COLOR_CYAN_BORDER),
        ("LEFTPADDING", (0, 0), (-1, -1), 6 * mm),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6 * mm),
        ("TOPPADDING", (0, 0), (-1, -1), 4 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4 * mm),
        ("ROUNDEDCORNERS", [10, 10, 10, 10]),
    ]))
    elements.append(insight_table)

    return elements


# ---------------------------------------------------------------------------
# V2 — Pagina 4: "Bij welke leverancier ben je goedkoopst?" (helpers + sectie)
# ---------------------------------------------------------------------------

def _get_provider_comparison(results: pd.DataFrame, top_n: int = 3) -> dict:
    """Top N goedkoopste + 1 duurste leverancier binnen de aanbevolen strategie."""
    if results is None or results.empty:
        return {}

    # Bepaal aanbevolen strategie uit de top-1 rij van de ranking
    strategy = results.iloc[0].get("strategy", "A")
    filtered = results[results["strategy"] == strategy].sort_values(
        "cost_with_battery"
    ).reset_index(drop=True)
    if filtered.empty:
        filtered = results.sort_values("cost_with_battery").reset_index(drop=True)
        strategy = filtered.iloc[0].get("strategy", strategy)

    cheapest = filtered.head(top_n)
    expensive = filtered.iloc[-1]
    min_cost = float(filtered.iloc[0].get("cost_with_battery", 0))
    max_cost = float(expensive.get("cost_with_battery", 0))

    return {
        "cheapest": cheapest,
        "expensive": expensive,
        "strategy": strategy,
        "savings_diff": max_cost - min_cost,
        "min_cost": min_cost,
        "max_cost": max_cost,
    }


def _make_provider_card_content(row, position: str, styles, card_width: float) -> Table:
    """Inhoud (Paragraph-stack) van een leverancier-kaart, ZONDER bg/border.
    De bg/border wordt op de outer cel gezet zodat alle cellen automatisch
    dezelfde hoogte krijgen (auto-grow van Table row)."""
    naam = row.get("provider_name", row.get("provider_code", "—"))
    jaarkosten = row.get("cost_with_battery", 0)
    marge = row.get("avg_margin_eur_per_kwh") or row.get("avg_margin")

    # Pill-styling op basis van positie
    if position == "winner":
        pill_text = "GOEDKOOPST"
        pill_bg = HexColor("#DCFCE7")
        pill_fg = HexColor("#15803D")
    elif position == "expensive":
        pill_text = "DUURST (REF)"
        pill_bg = HexColor("#FEE2E2")
        pill_fg = HexColor("#B91C1C")
    else:
        pill_text = "ALTERNATIEF"
        pill_bg = HexColor("#ECFEFF")
        pill_fg = COLOR_SECONDARY

    pill_style = ParagraphStyle(
        "prov_pill", fontName="Helvetica-Bold", fontSize=7.5,
        leading=9, textColor=pill_fg, alignment=TA_CENTER,
    )
    pill = Table([[Paragraph(pill_text, pill_style)]], colWidths=[25 * mm])
    pill.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), pill_bg),
        ("LEFTPADDING", (0, 0), (-1, -1), 1 * mm),
        ("RIGHTPADDING", (0, 0), (-1, -1), 1 * mm),
        ("TOPPADDING", (0, 0), (-1, -1), 1 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1 * mm),
        ("ROUNDEDCORNERS", [6, 6, 6, 6]),
    ]))

    name_style = ParagraphStyle(
        "prov_name", fontName="Helvetica-Bold", fontSize=14, leading=17,
        textColor=COLOR_INK,
    )
    label_small_style = ParagraphStyle(
        "prov_lbl", fontName="Helvetica-Bold", fontSize=7,
        leading=9, textColor=COLOR_MUTED, alignment=TA_LEFT,
    )
    big_style = ParagraphStyle(
        "prov_big", fontName="Helvetica-Bold", fontSize=22, leading=26,
        textColor=COLOR_INK, alignment=TA_LEFT,
    )
    sub_style = ParagraphStyle(
        "prov_sub", parent=styles["KpiTileFoot"],
        fontSize=8, leading=11, textColor=COLOR_MUTED, alignment=TA_LEFT,
    )

    rows = [
        [pill],
        [Spacer(1, 4 * mm)],
        [Paragraph(str(naam), name_style)],
        [Spacer(1, 5 * mm)],
        [Paragraph("JAARKOSTEN", label_small_style)],
        [Paragraph(_fmt_eur_short(jaarkosten), big_style)],
    ]
    if marge and float(marge) > 0:
        rows.append([Spacer(1, 3 * mm)])
        rows.append([Paragraph(
            f"Marge {float(marge):.3f} €/kWh boven beurs",
            sub_style,
        )])

    content = Table(rows, colWidths=[card_width])
    content.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    return content


def _make_provider_card(row, position: str, styles, card_width: float) -> Table:
    """LEGACY helper — wordt vervangen door _make_provider_card_content + outer styling."""
    naam = row.get("provider_name", row.get("provider_code", "—"))
    jaarkosten = row.get("cost_with_battery", 0)
    marge = row.get("avg_margin_eur_per_kwh") or row.get("avg_margin")
    if marge is None:
        # Probeer uit jaarkosten ratio te halen, anders weglaten
        marge = 0

    # Position-specifieke styling
    if position == "winner":
        pill_text = "GOEDKOOPST"
        pill_bg = HexColor("#DCFCE7")
        pill_fg = HexColor("#15803D")
        card_bg = COLOR_GREEN_SOFT
        card_border = COLOR_ACCENT
        border_w = 1.5
    elif position == "expensive":
        pill_text = "DUURST (REF)"
        pill_bg = HexColor("#FEE2E2")
        pill_fg = HexColor("#B91C1C")
        card_bg = white
        card_border = COLOR_BORDER
        border_w = 0.6
    else:
        pill_text = "ALTERNATIEF"
        pill_bg = HexColor("#ECFEFF")
        pill_fg = COLOR_SECONDARY
        card_bg = white
        card_border = COLOR_BORDER
        border_w = 0.6

    # Pill
    pill_style = ParagraphStyle(
        "prov_pill", fontName="Helvetica-Bold", fontSize=7,
        leading=9, textColor=pill_fg, alignment=TA_CENTER,
    )
    pill = Table([[Paragraph(pill_text, pill_style)]], colWidths=[22 * mm])
    pill.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), pill_bg),
        ("LEFTPADDING", (0, 0), (-1, -1), 1 * mm),
        ("RIGHTPADDING", (0, 0), (-1, -1), 1 * mm),
        ("TOPPADDING", (0, 0), (-1, -1), 0.8 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0.8 * mm),
        ("ROUNDEDCORNERS", [6, 6, 6, 6]),
    ]))

    # Styles
    name_style = ParagraphStyle(
        "prov_name", parent=styles["BatteryName"],
        fontSize=12, leading=14, textColor=COLOR_INK,
    )
    label_small_style = ParagraphStyle(
        "prov_lbl", parent=styles["KpiTileLabel"],
        fontSize=7.5, leading=10, textColor=COLOR_MUTED, alignment=TA_LEFT,
    )
    big_style = ParagraphStyle(
        "prov_big", parent=styles["KpiTileValue"],
        fontSize=18, leading=22, textColor=COLOR_INK, alignment=TA_LEFT,
    )
    sub_style = ParagraphStyle(
        "prov_sub", parent=styles["KpiTileFoot"],
        fontSize=8.5, leading=11, textColor=COLOR_MUTED, alignment=TA_LEFT,
    )

    # Vaste rowHeights zodat elke kaart precies dezelfde structuur heeft,
    # ongeacht of de leveranciersnaam 1 of 2 regels nodig heeft of of er
    # een marge-regel beschikbaar is.
    rows = [
        [pill],
        [Paragraph(str(naam), name_style)],
        [Paragraph("JAARKOSTEN MET BATTERIJ", label_small_style)],
        [Paragraph(_fmt_eur_short(jaarkosten), big_style)],
        [Paragraph(
            f"Gem. marge {marge:.3f} €/kWh boven beurs" if (marge and marge > 0) else "",
            sub_style,
        )],
    ]
    row_heights = [6 * mm, 14 * mm, 5 * mm, 10 * mm, 8 * mm]

    card = Table(rows, colWidths=[card_width - 6 * mm], rowHeights=row_heights)
    card.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), card_bg),
        ("BOX", (0, 0), (-1, -1), border_w, card_border),
        ("LEFTPADDING", (0, 0), (-1, -1), 3 * mm),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3 * mm),
        ("TOPPADDING", (0, 0), (0, 0), 3 * mm),
        ("BOTTOMPADDING", (0, -1), (-1, -1), 3 * mm),
        ("TOPPADDING", (0, 1), (-1, -1), 1 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, -2), 1 * mm),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROUNDEDCORNERS", [10, 10, 10, 10]),
    ]))
    return card


def _make_providers_grid(comparison: dict, styles, content_width: float) -> Table:
    """
    4 leverancier-kaarten naast elkaar. Achtergrond/border zit op de OUTER cel
    zodat reportlab automatisch alle cellen even hoog maakt op basis van de
    hoogste cel-inhoud — geen vaste rowHeights nodig.
    """
    cheapest_df = comparison.get("cheapest")
    expensive = comparison.get("expensive")
    if cheapest_df is None or cheapest_df.empty:
        return Paragraph("Geen leverancier-data.", styles["BodyText"])

    positions = ["winner", "second", "third"]
    # 4 cellen + 3 gaps; gap = 3mm; effectieve celbreedte: (170-9)/4 ≈ 40mm.
    # Padding binnen cel: 5mm L/R, dus content-breedte per cel: 30mm.
    card_w = (content_width - 9 * mm) / 4.0
    inner_w = card_w - 10 * mm

    contents = []
    rows_data = []
    for i, (_, r) in enumerate(cheapest_df.head(3).iterrows()):
        pos = positions[i] if i < len(positions) else "third"
        contents.append(_make_provider_card_content(r, pos, styles, inner_w))
    if expensive is not None:
        contents.append(_make_provider_card_content(expensive, "expensive", styles, inner_w))

    rows_data.append(contents)

    # Outer Table: één row met N cellen. Auto-row-height geeft elke cel
    # automatisch dezelfde hoogte (= hoogste inhoud). Cel-styling rendert
    # over de volle hoogte.
    grid = Table(rows_data, colWidths=[card_w] * len(contents))
    style_cmds = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5 * mm),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5 * mm),
        ("TOPPADDING", (0, 0), (-1, -1), 5 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6 * mm),
    ]
    # Per cel achtergrond + border zetten op basis van positie
    n = len(contents)
    for col in range(n):
        if col == 0:  # winnaar
            style_cmds.append(("BACKGROUND", (col, 0), (col, 0), COLOR_GREEN_SOFT))
            style_cmds.append(("BOX", (col, 0), (col, 0), 1.5, COLOR_ACCENT))
        elif col == n - 1 and expensive is not None:  # duurst
            style_cmds.append(("BACKGROUND", (col, 0), (col, 0), white))
            style_cmds.append(("BOX", (col, 0), (col, 0), 0.6, COLOR_BORDER))
        else:  # alternatief
            style_cmds.append(("BACKGROUND", (col, 0), (col, 0), white))
            style_cmds.append(("BOX", (col, 0), (col, 0), 0.6, COLOR_BORDER))
    grid.setStyle(TableStyle(style_cmds))
    return grid


def _make_provider_callout(comparison: dict, battery_savings: float, styles,
                           content_width: float) -> Table:
    """
    Hero call-out: vergelijking tussen 'batterij bespaart' en 'overstappen scheelt'.
    """
    cheap_naam = "de goedkoopste leverancier"
    if comparison.get("cheapest") is not None and not comparison["cheapest"].empty:
        cheap_naam = comparison["cheapest"].iloc[0].get(
            "provider_name", comparison["cheapest"].iloc[0].get("provider_code", cheap_naam)
        )
    savings_diff = comparison.get("savings_diff", 0)
    min_cost = comparison.get("min_cost", 0)

    eyebrow_style = ParagraphStyle(
        "cta_eyebrow", parent=styles["KpiTileLabel"],
        fontSize=8.5, leading=11, textColor=HexColor("#67E8F9"), alignment=TA_LEFT,
    )
    big_style = ParagraphStyle(
        "cta_big", parent=styles["KpiTileValue"],
        fontSize=22, leading=26, textColor=white, alignment=TA_LEFT,
    )
    body_style = ParagraphStyle(
        "cta_body", parent=styles["BodyText"],
        fontSize=11, leading=15, textColor=HexColor("#CBD5E1"),
    )

    # Twee scenario's naast elkaar
    inner_w = content_width - 12 * mm
    col_w = (inner_w - 8 * mm) / 2.0

    left = Table(
        [
            [Paragraph("EEN BATTERIJ BESPAART", eyebrow_style)],
            [Paragraph(f"{_fmt_eur_short(battery_savings)}/jaar", big_style)],
            [Paragraph("door minder teruglevering aan het net", body_style)],
        ],
        colWidths=[col_w],
    )
    left.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (0, 0), 1.5 * mm),
        ("BOTTOMPADDING", (0, 1), (0, 1), 1 * mm),
        ("BOTTOMPADDING", (0, 2), (-1, -1), 0),
    ]))

    right_text = (
        f"door over te stappen naar <b>{cheap_naam}</b> "
        f"(jaarrekening {_fmt_eur_short(min_cost)})"
    )
    right = Table(
        [
            [Paragraph("OVERSTAPPEN SCHEELT", eyebrow_style)],
            [Paragraph(f"{_fmt_eur_short(savings_diff)}/jaar", big_style)],
            [Paragraph(right_text, body_style)],
        ],
        colWidths=[col_w],
    )
    right.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (0, 0), 1.5 * mm),
        ("BOTTOMPADDING", (0, 1), (0, 1), 1 * mm),
        ("BOTTOMPADDING", (0, 2), (-1, -1), 0),
    ]))

    cols = Table([[left, right]], colWidths=[col_w, col_w])
    cols.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (0, 0), 0),
        ("RIGHTPADDING", (0, 0), (0, 0), 4 * mm),
        ("LEFTPADDING", (1, 0), (1, 0), 4 * mm),
        ("RIGHTPADDING", (1, 0), (1, 0), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("LINEAFTER", (0, 0), (0, 0), 0.5, HexColor("#475569")),
    ]))

    callout_outer = Table(
        [
            [Paragraph("WIST JE DAT?", ParagraphStyle(
                "cta_eyebrow_top", fontName="Helvetica-Bold", fontSize=9,
                textColor=HexColor("#67E8F9"), alignment=TA_LEFT, leading=11,
            ))],
            [cols],
            [Paragraph(
                "Twee onafhankelijke besparingen die optellen. Overstappen kost geen geld en duurt "
                "10 minuten online.",
                ParagraphStyle("cta_foot", fontName="Helvetica", fontSize=9.5,
                               leading=13, textColor=HexColor("#94A3B8")),
            )],
        ],
        colWidths=[content_width],
    )
    callout_outer.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1),
         HexColor("#0B1220")),  # donkere band
        ("LEFTPADDING", (0, 0), (-1, -1), 6 * mm),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6 * mm),
        ("TOPPADDING", (0, 0), (0, 0), 5 * mm),
        ("BOTTOMPADDING", (0, 0), (0, 0), 2 * mm),
        ("TOPPADDING", (0, 1), (0, 1), 0),
        ("BOTTOMPADDING", (0, 1), (0, 1), 4 * mm),
        ("TOPPADDING", (0, 2), (0, 2), 0),
        ("BOTTOMPADDING", (0, 2), (0, 2), 5 * mm),
        ("ROUNDEDCORNERS", [12, 12, 12, 12]),
    ]))
    return callout_outer


def _build_providers_v2(results: pd.DataFrame, sizing_results: Optional[pd.DataFrame],
                        config: SimulationConfig, styles) -> list:
    """Pagina 4: "Bij welke leverancier ben je goedkoopst?" — top 3 + 1 duurste + hero."""
    elements = []
    content_width = 210 * mm - 40 * mm

    # Brand row
    brand = Table(
        [
            [Paragraph(
                '<font color="#06B6D4"><b>⚡</b></font> <b>Energy-Truth</b>',
                styles["BrandName"],
            )],
            [Paragraph("Pagina 4 &middot; Welke leverancier", styles["BrandSub"])],
        ],
        colWidths=[content_width],
    )
    brand.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (0, 0), 1 * mm),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 8 * mm),
    ]))
    elements.append(brand)

    # Headline + sub
    elements.append(Paragraph("Bij welke leverancier ben je goedkoopst?", styles["CoverTitle"]))
    elements.append(Paragraph(
        "We vergeleken de jaarkosten bij elke leverancier mét de aanbevolen batterij en de aanbevolen "
        "laadstrategie. Hieronder de drie goedkoopste en, ter referentie, de duurste die we testten.",
        styles["CoverSub"],
    ))

    # Vergelijking ophalen
    comparison = _get_provider_comparison(results, top_n=3)
    if not comparison:
        elements.append(Paragraph(
            "Geen leverancier-vergelijking beschikbaar.",
            styles["BodyText"],
        ))
        return elements

    # Grid met 4 leverancier-kaarten
    elements.append(Spacer(1, 2 * mm))
    elements.append(_make_providers_grid(comparison, styles, content_width))

    # Hero call-out onderaan
    elements.append(Spacer(1, 10 * mm))
    # Pak batterij-jaarbesparing uit sizing top row (aanbevolen)
    battery_savings = 0
    if sizing_results is not None and not sizing_results.empty:
        top3 = _select_top3_batteries(sizing_results)
        if not top3.empty:
            battery_savings = float(top3.iloc[0].get("jaarlijkse_besparing_eur", 0) or 0)
    elements.append(_make_provider_callout(comparison, battery_savings, styles, content_width))

    # Footer-tekst over scenario
    elements.append(Spacer(1, 4 * mm))
    foot_style = ParagraphStyle(
        "p4_foot", parent=styles["KpiTileFoot"],
        fontSize=8.5, leading=11, textColor=COLOR_MUTED,
    )
    elements.append(Paragraph(
        f"Vergelijking bij dezelfde aanbevolen instelling "
        f"(<b>{_strategy_name(comparison['strategy'])}</b>). Op pagina 5 leggen we uit waarom we "
        f"deze instelling voor jou aanraden. Jaarkosten zijn berekend op jouw eigen meterdata.",
        foot_style,
    ))

    return elements


# ---------------------------------------------------------------------------
# V2 — Pagina 5: "Waarom deze laadinstelling" (helpers + sectie)
# ---------------------------------------------------------------------------

# Korte mensentaal uitleg per strategie (geen jargon)
_STRATEGY_DESCRIPTIONS = {
    "A": "Eigen zonneoverschot opslaan en 's avonds zelf opmaken. Simpel en altijd winstgevend.",
    "B": "Inkopen wanneer stroom goedkoop is en verkopen wanneer duur. Klinkt slim maar verliest geld door het belastingverschil tussen kopen en verkopen.",
    "C": "Mix van A en B: eigen zon eerst, dan ook nog wat handelen op prijzen.",
    "D": "Alleen eigen zonnestroom opslaan, maar slimmer getimed op basis van prijzen.",
}


def _get_strategy_comparison(results: pd.DataFrame) -> dict:
    """
    Voor elke strategie (A/B/C/D) pak de beste jaarbesparing over alle leveranciers.
    Returns een dict per strategie met cost_with_battery, savings, provider_name.
    """
    if results is None or results.empty:
        return {}

    out = {}
    for strat in ("A", "B", "C", "D"):
        sub = results[results["strategy"] == strat]
        if sub.empty:
            continue
        best = sub.sort_values("cost_with_battery").iloc[0]
        out[strat] = {
            "cost_with_battery": float(best.get("cost_with_battery", 0)),
            "cost_no_battery": float(best.get("cost_no_battery", 0)),
            "savings": float(best.get("savings_eur", 0)),
            "provider": best.get("provider_name", best.get("provider_code", "—")),
        }
    return out


def _make_strategy_tile(strat: str, data: dict, is_recommended: bool,
                        styles, card_width: float) -> Table:
    """Eén strategie-kaart."""
    name = _strategy_name(strat)  # "Zelfverbruik" / "Prijsarbitrage" / etc.
    desc = _STRATEGY_DESCRIPTIONS.get(strat, "")
    savings = data.get("savings", 0)

    # Kleur op basis van besparing
    if savings > 0:
        savings_color = COLOR_ACCENT
        prefix = "+"
    elif savings < 0:
        savings_color = COLOR_NEGATIVE
        prefix = ""
    else:
        savings_color = COLOR_MUTED
        prefix = ""

    # Pill (alleen voor aanbevolen)
    pill_table = None
    if is_recommended:
        pill_style = ParagraphStyle(
            "strat_pill", fontName="Helvetica-Bold", fontSize=7,
            leading=9, textColor=white, alignment=TA_CENTER,
        )
        pill_table = Table([[Paragraph("AANBEVOLEN", pill_style)]], colWidths=[26 * mm])
        pill_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), COLOR_ACCENT),
            ("LEFTPADDING", (0, 0), (-1, -1), 1 * mm),
            ("RIGHTPADDING", (0, 0), (-1, -1), 1 * mm),
            ("TOPPADDING", (0, 0), (-1, -1), 0.8 * mm),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0.8 * mm),
            ("ROUNDEDCORNERS", [6, 6, 6, 6]),
        ]))

    # Styles — naam-font wat kleiner zodat lange namen als "Prijsarbitrage"
    # en "Slim zelfverbruik" niet midden in een woord wrappen.
    name_style = ParagraphStyle(
        "strat_name", parent=styles["BatteryName"],
        fontSize=11, leading=14, textColor=COLOR_INK,
    )
    letter_style = ParagraphStyle(
        "strat_letter", parent=styles["KpiTileLabel"],
        fontSize=8, leading=10, textColor=COLOR_MUTED, alignment=TA_LEFT,
    )
    label_style = ParagraphStyle(
        "strat_lbl", parent=styles["KpiTileLabel"],
        fontSize=7.5, leading=10, textColor=COLOR_MUTED, alignment=TA_LEFT,
    )
    sav_style = ParagraphStyle(
        "strat_sav", parent=styles["KpiTileValue"],
        fontSize=18, leading=22, textColor=savings_color, alignment=TA_LEFT,
    )
    desc_style = ParagraphStyle(
        "strat_desc", parent=styles["KpiTileFoot"],
        fontSize=8.5, leading=11.5, textColor=COLOR_INK,
    )

    rows = []
    if pill_table is not None:
        rows.append([pill_table])
    rows.append([Paragraph(f"Strategie {strat}", letter_style)])
    rows.append([Paragraph(name, name_style)])
    rows.append([Paragraph("BESPARING PER JAAR", label_style)])
    rows.append([Paragraph(f"{prefix}{_fmt_eur_short(abs(savings))}", sav_style)])
    rows.append([Paragraph(desc, desc_style)])

    card = Table(rows, colWidths=[card_width - 6 * mm])
    card_bg = COLOR_GREEN_SOFT if is_recommended else white
    card_border = COLOR_ACCENT if is_recommended else COLOR_BORDER
    border_w = 1.5 if is_recommended else 0.6

    card.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), card_bg),
        ("BOX", (0, 0), (-1, -1), border_w, card_border),
        ("LEFTPADDING", (0, 0), (-1, -1), 3 * mm),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3 * mm),
        ("TOPPADDING", (0, 0), (0, 0), 3 * mm),
        ("BOTTOMPADDING", (0, -1), (-1, -1), 3 * mm),
        ("TOPPADDING", (0, 1), (-1, -1), 1.2 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, -2), 1.2 * mm),
        ("ROUNDEDCORNERS", [10, 10, 10, 10]),
    ]))
    return card


def _make_winner_strategy_card(strat: str, data: dict, styles,
                               content_width: float) -> Table:
    """Hero-card voor de aanbevolen strategie."""
    savings = data.get("savings", 0)
    prefix = "+" if savings >= 0 else ""

    # Bovenste rij: AANBEVOLEN pill links + rank "★" rechts
    eyebrow_style = ParagraphStyle(
        "win_eyebrow", fontName="Helvetica-Bold", fontSize=8.5, leading=10,
        textColor=white, alignment=TA_CENTER,
    )
    pill = Table([[Paragraph("★ AANBEVOLEN VOOR JOU", eyebrow_style)]],
                 colWidths=[42 * mm])
    pill.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), COLOR_ACCENT),
        ("LEFTPADDING", (0, 0), (-1, -1), 2 * mm),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2 * mm),
        ("TOPPADDING", (0, 0), (-1, -1), 1.5 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5 * mm),
        ("ROUNDEDCORNERS", [8, 8, 8, 8]),
    ]))

    name_style = ParagraphStyle(
        "win_name", fontName="Helvetica-Bold", fontSize=24, leading=28,
        textColor=COLOR_INK,
    )
    desc_style = ParagraphStyle(
        "win_desc", parent=styles["BodyText"],
        fontSize=11, leading=15, textColor=COLOR_INK,
    )
    savings_style = ParagraphStyle(
        "win_savings", fontName="Helvetica-Bold", fontSize=28, leading=32,
        textColor=COLOR_ACCENT, alignment=TA_RIGHT,
    )
    savings_label_style = ParagraphStyle(
        "win_sav_lbl", parent=styles["KpiTileLabel"],
        fontSize=8.5, leading=10, textColor=COLOR_MUTED, alignment=TA_RIGHT,
    )

    # Linker kolom: pill + naam + uitleg
    left_w = content_width * 0.62
    right_w = content_width * 0.38 - 12 * mm  # rekening houdend met padding

    left_block = Table(
        [
            [pill],
            [Paragraph(_strategy_name(strat), name_style)],
            [Paragraph(_STRATEGY_DESCRIPTIONS.get(strat, ""), desc_style)],
        ],
        colWidths=[left_w - 6 * mm],
    )
    left_block.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (0, 0), 4 * mm),
        ("BOTTOMPADDING", (0, 1), (0, 1), 3 * mm),
        ("BOTTOMPADDING", (0, 2), (-1, -1), 0),
    ]))

    # Rechter kolom: groot besparing-getal
    right_block = Table(
        [
            [Paragraph("BESPARING PER JAAR", savings_label_style)],
            [Paragraph(f"{prefix}{_fmt_eur_short(abs(savings))}", savings_style)],
        ],
        colWidths=[right_w],
    )
    right_block.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (0, 0), 1.5 * mm),
        ("BOTTOMPADDING", (0, 0), (0, 0), 1 * mm),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 0),
    ]))

    # Outer 2-kolom card
    card = Table([[left_block, right_block]], colWidths=[left_w, content_width - left_w])
    card.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), COLOR_GREEN_SOFT),
        ("BOX", (0, 0), (-1, -1), 1.5, COLOR_ACCENT),
        ("VALIGN", (0, 0), (0, 0), "TOP"),
        ("VALIGN", (1, 0), (1, 0), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6 * mm),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6 * mm),
        ("TOPPADDING", (0, 0), (-1, -1), 5 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5 * mm),
        ("ROUNDEDCORNERS", [12, 12, 12, 12]),
    ]))
    return card


def _make_other_strategies_list(strategies_data: dict, recommended: str,
                                styles, content_width: float) -> Table:
    """Compacte lijst van de 3 niet-aanbevolen strategieën, gesorteerd op besparing."""
    others = [(s, d) for s, d in strategies_data.items() if s != recommended]
    others_sorted = sorted(others, key=lambda x: -float(x[1].get("savings", 0)))

    if not others_sorted:
        return Paragraph("Geen alternatieven beschikbaar.", styles["BodyText"])

    rank_style = ParagraphStyle(
        "oth_rank", fontName="Helvetica-Bold", fontSize=14, leading=16,
        textColor=COLOR_MUTED, alignment=TA_CENTER,
    )
    name_style = ParagraphStyle(
        "oth_name", parent=styles["BatteryName"],
        fontSize=12, leading=15, textColor=COLOR_INK,
    )
    desc_style = ParagraphStyle(
        "oth_desc", parent=styles["KpiTileFoot"],
        fontSize=9, leading=12, textColor=COLOR_MUTED,
    )

    col_rank = 12 * mm
    col_savings = 40 * mm
    col_name = content_width - col_rank - col_savings

    rows = []
    style_cmds = [
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3 * mm),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3 * mm),
        ("TOPPADDING", (0, 0), (-1, -1), 3 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3 * mm),
    ]
    for i, (strat, data) in enumerate(others_sorted):
        savings = data.get("savings", 0)
        if savings > 0:
            sav_color = COLOR_ACCENT
            sav_prefix = "+"
        elif savings < 0:
            sav_color = COLOR_NEGATIVE
            sav_prefix = ""
        else:
            sav_color = COLOR_MUTED
            sav_prefix = ""
        sav_style = ParagraphStyle(
            f"oth_sav_{strat}", fontName="Helvetica-Bold", fontSize=14, leading=16,
            textColor=sav_color, alignment=TA_RIGHT,
        )

        name_block = Table(
            [
                [Paragraph(_strategy_name(strat), name_style)],
                [Paragraph(_STRATEGY_DESCRIPTIONS.get(strat, ""), desc_style)],
            ],
            colWidths=[col_name - 4 * mm],
        )
        name_block.setStyle(TableStyle([
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (0, 0), 1 * mm),
            ("BOTTOMPADDING", (0, 1), (-1, -1), 0),
        ]))

        rows.append([
            Paragraph(str(i + 2), rank_style),  # +2 omdat #1 is de winnaar
            name_block,
            Paragraph(f"{sav_prefix}{_fmt_eur_short(abs(savings))}/jaar", sav_style),
        ])
        if i < len(others_sorted) - 1:
            style_cmds.append(("LINEBELOW", (0, i), (-1, i), 0.4, COLOR_BORDER))

    table = Table(rows, colWidths=[col_rank, col_name, col_savings])
    table.setStyle(TableStyle(style_cmds + [
        ("BOX", (0, 0), (-1, -1), 0.5, COLOR_BORDER),
        ("ROUNDEDCORNERS", [10, 10, 10, 10]),
    ]))
    return table


def _make_strategy_ranking(strategies_data: dict, recommended: str,
                           styles, content_width: float) -> Table:
    """
    Vier strategieën onder elkaar, gesorteerd van meest- naar minst-winstgevend.
    Elke rij: ranking-nummer, strategie-naam, besparing, uitleg.
    """
    if not strategies_data:
        return Paragraph("Geen strategie-data.", styles["BodyText"])

    # Sorteer op savings descending
    sorted_strats = sorted(
        strategies_data.items(),
        key=lambda x: -float(x[1].get("savings", 0)),
    )

    # Kolomverdeling: rank | naam + uitleg | besparing.
    # De AANBEVOLEN-pill wordt buiten de tabel boven de eerste rij geplaatst
    # (zie _make_strategy_ranking_with_badge wrapper).
    inner_w = content_width
    col_rank = 12 * mm
    col_savings = 40 * mm
    col_name = inner_w - col_rank - col_savings

    rank_style = ParagraphStyle(
        "rank_style", fontName="Helvetica-Bold", fontSize=18, leading=20,
        textColor=COLOR_MUTED, alignment=TA_CENTER,
    )
    name_style = ParagraphStyle(
        "rank_name", parent=styles["BatteryName"],
        fontSize=13, leading=15, textColor=COLOR_INK,
    )
    desc_style = ParagraphStyle(
        "rank_desc", parent=styles["KpiTileFoot"],
        fontSize=9, leading=12, textColor=COLOR_MUTED,
    )

    rows_data = []
    style_cmds = [
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3 * mm),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3 * mm),
        ("TOPPADDING", (0, 0), (-1, -1), 4 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4 * mm),
    ]

    for i, (strat, data) in enumerate(sorted_strats):
        savings = data.get("savings", 0)
        # Kleur-coderen besparing
        if savings > 0:
            savings_color = COLOR_ACCENT
            prefix = "+"
        elif savings < 0:
            savings_color = COLOR_NEGATIVE
            prefix = ""
        else:
            savings_color = COLOR_MUTED
            prefix = ""

        savings_style = ParagraphStyle(
            f"rank_sav_{strat}", fontName="Helvetica-Bold",
            fontSize=17, leading=20, textColor=savings_color, alignment=TA_RIGHT,
        )

        # Naam + uitleg gestackt
        name_block = Table(
            [
                [Paragraph(_strategy_name(strat), name_style)],
                [Paragraph(_STRATEGY_DESCRIPTIONS.get(strat, ""), desc_style)],
            ],
            colWidths=[col_name - 4 * mm],
        )
        name_block.setStyle(TableStyle([
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (0, 0), 1.5 * mm),
            ("BOTTOMPADDING", (0, 1), (-1, -1), 0),
        ]))

        rows_data.append([
            Paragraph(str(i + 1), rank_style),
            name_block,
            Paragraph(f"{prefix}{_fmt_eur_short(abs(savings))}/jaar", savings_style),
        ])

        # Highlight aanbevolen rij met zachtgroene achtergrond
        if strat == recommended:
            style_cmds.append(("BACKGROUND", (0, i), (-1, i), COLOR_GREEN_SOFT))

        # Scheidslijn tussen rijen (niet onder de laatste)
        if i < len(sorted_strats) - 1:
            style_cmds.append(("LINEBELOW", (0, i), (-1, i), 0.4, COLOR_BORDER))

    ranking_table = Table(rows_data, colWidths=[col_rank, col_name, col_savings])
    ranking_table.setStyle(TableStyle(style_cmds + [
        ("BOX", (0, 0), (-1, -1), 0.6, COLOR_BORDER),
        ("ROUNDEDCORNERS", [10, 10, 10, 10]),
    ]))
    return ranking_table


def _make_strategy_grid_OLD(strategies_data: dict, recommended: str,
                       styles, content_width: float) -> Table:
    """Vier strategie-kaarten naast elkaar, aanbevolen met groene rand."""
    if not strategies_data:
        return Paragraph("Geen strategie-data.", styles["BodyText"])

    card_w = (content_width - 9 * mm) / 4.0
    cards = []
    for strat in ("A", "B", "C", "D"):
        if strat not in strategies_data:
            # Lege placeholder
            cards.append(Paragraph(f"Strategie {strat} niet gesimuleerd.", styles["BodyText"]))
            continue
        is_rec = (strat == recommended)
        cards.append(_make_strategy_tile(strat, strategies_data[strat], is_rec, styles, card_w))

    # rowHeights forceren zodat alle 4 strategie-tegels precies even hoog zijn.
    grid = Table([cards], colWidths=[card_w] * 4, rowHeights=[80 * mm])
    grid.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3 * mm),
        ("RIGHTPADDING", (-1, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    return grid


def _make_saldering_block(current_savings: float, recommended_strat: str,
                          styles, content_width: float) -> Table:
    """Voor/na-blok over saldering 2027."""
    label_style = ParagraphStyle(
        "sal_label", parent=styles["KpiTileLabel"],
        fontSize=8.5, leading=11, textColor=COLOR_MUTED, alignment=TA_LEFT,
    )
    big_style = ParagraphStyle(
        "sal_big", parent=styles["KpiTileValue"],
        fontSize=20, leading=24, textColor=COLOR_INK, alignment=TA_LEFT,
    )
    sub_style = ParagraphStyle(
        "sal_sub", parent=styles["KpiTileFoot"],
        fontSize=10, leading=13.5, textColor=COLOR_INK,
    )

    inner_w = content_width - 12 * mm
    col_w = (inner_w - 8 * mm) / 2.0

    left = Table(
        [
            [Paragraph("NU (MET SALDERING)", label_style)],
            [Paragraph(f"+{_fmt_eur_short(current_savings)}/jaar", big_style)],
            [Paragraph(
                "Teruglevering wordt gesaldeerd met afname. Een batterij levert <b>extra eigen "
                "verbruik</b> bovenop deze regeling.",
                sub_style,
            )],
        ],
        colWidths=[col_w],
    )
    left.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (0, 0), 1 * mm),
        ("BOTTOMPADDING", (0, 1), (0, 1), 2 * mm),
        ("BOTTOMPADDING", (0, 2), (-1, -1), 0),
    ]))

    right = Table(
        [
            [Paragraph("VANAF 2027 (ZONDER SALDERING)", label_style)],
            [Paragraph("Aanzienlijk hoger", big_style)],
            [Paragraph(
                "Teruglevering levert dan veel minder op. <b>Zelfconsumptie wordt waardevoller</b> "
                f"en daarmee wordt {_strategy_name(recommended_strat).lower()} extra interessant.",
                sub_style,
            )],
        ],
        colWidths=[col_w],
    )
    right.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (0, 0), 1 * mm),
        ("BOTTOMPADDING", (0, 1), (0, 1), 2 * mm),
        ("BOTTOMPADDING", (0, 2), (-1, -1), 0),
    ]))

    cols = Table([[left, right]], colWidths=[col_w, col_w])
    cols.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (0, 0), 0),
        ("RIGHTPADDING", (0, 0), (0, 0), 4 * mm),
        ("LEFTPADDING", (1, 0), (1, 0), 4 * mm),
        ("RIGHTPADDING", (1, 0), (1, 0), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("LINEAFTER", (0, 0), (0, 0), 0.5, COLOR_BORDER),
    ]))

    outer = Table(
        [
            [Paragraph(
                "WAT GEBEURT ER NA 2027?",
                ParagraphStyle("sal_top", fontName="Helvetica-Bold",
                               fontSize=9, leading=11, textColor=COLOR_SECONDARY),
            )],
            [cols],
        ],
        colWidths=[content_width],
    )
    outer.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), COLOR_SOFT),
        ("BOX", (0, 0), (-1, -1), 0.5, COLOR_CYAN_BORDER),
        ("LEFTPADDING", (0, 0), (-1, -1), 6 * mm),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6 * mm),
        ("TOPPADDING", (0, 0), (0, 0), 4 * mm),
        ("BOTTOMPADDING", (0, 0), (0, 0), 2 * mm),
        ("TOPPADDING", (0, 1), (0, 1), 0),
        ("BOTTOMPADDING", (0, 1), (0, 1), 4 * mm),
        ("ROUNDEDCORNERS", [10, 10, 10, 10]),
    ]))
    return outer


def _build_strategies_v2(results: pd.DataFrame, sizing_results: Optional[pd.DataFrame],
                         config: SimulationConfig, styles) -> list:
    """Pagina 5: "Waarom deze laadinstelling" — 4 tegels + saldering 2027 blok."""
    elements = []
    content_width = 210 * mm - 40 * mm

    # Brand row
    brand = Table(
        [
            [Paragraph(
                '<font color="#06B6D4"><b>⚡</b></font> <b>Energy-Truth</b>',
                styles["BrandName"],
            )],
            [Paragraph("Pagina 5 &middot; Waarom deze laadinstelling", styles["BrandSub"])],
        ],
        colWidths=[content_width],
    )
    brand.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (0, 0), 1 * mm),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 8 * mm),
    ]))
    elements.append(brand)

    # Headline + sub
    strat_comp = _get_strategy_comparison(results)
    recommended = "A"
    if results is not None and not results.empty:
        recommended = results.iloc[0].get("strategy", "A")

    elements.append(Paragraph(
        "Waarom we deze instelling voor jou aanraden",
        styles["CoverTitle"],
    ))
    elements.append(Paragraph(
        f"Er zijn vier manieren om een thuisbatterij te gebruiken. Voor jouw verbruikspatroon werkt "
        f"<b>{_strategy_name(recommended).lower()}</b> het beste. Hieronder zie je waarom, plus wat "
        f"er gebeurt als de saldering in 2027 wegvalt.",
        styles["CoverSub"],
    ))

    # Bepaal de echte winnaar (hoogste besparing). Vaak gelijk aan results.iloc[0].strategy,
    # maar als die door een edge case anders is, vertrouwen we de cijfers.
    if strat_comp:
        recommended = max(strat_comp.items(), key=lambda x: float(x[1].get("savings", 0)))[0]

    # Hero-card voor de aanbevolen strategie
    elements.append(_make_winner_strategy_card(recommended, strat_comp[recommended],
                                                styles, content_width))

    # Eyebrow voor de andere 3
    elements.append(Spacer(1, 8 * mm))
    elements.append(Paragraph(
        "DE ANDERE OPTIES, VAN HOOG NAAR LAAG",
        styles["SectionEyebrow"],
    ))
    elements.append(Spacer(1, 4 * mm))
    elements.append(_make_other_strategies_list(strat_comp, recommended, styles, content_width))

    # Footer
    elements.append(Spacer(1, 6 * mm))
    foot_style = ParagraphStyle(
        "p5_foot", parent=styles["KpiTileFoot"],
        fontSize=8.5, leading=11, textColor=COLOR_MUTED,
    )
    elements.append(Paragraph(
        "Besparing per strategie is berekend bij de goedkoopste leverancier in onze test.",
        foot_style,
    ))

    return elements


# ---------------------------------------------------------------------------
# V2 — Pagina 6: "Hoe wij voor jou hebben gerekend" (methodologie)
# ---------------------------------------------------------------------------

_BETROUWBAARHEID_COMPONENTEN = [
    {
        "key": "dekkingsgraad",
        "naam": "Dekkingsgraad",
        "gewicht": 30,
        "uitleg": (
            "Hoeveel meet-momenten we van jou hebben. We rekenen 15-minuten metingen "
            "als 100%, uurdata als 60% en dagdata als 20% — fijnmaziger is beter."
        ),
    },
    {
        "key": "seizoensspreiding",
        "naam": "Seizoensspreiding",
        "gewicht": 30,
        "uitleg": (
            "Of alle vier de seizoenen in jouw data zitten. Zonder een heel jaar moeten "
            "we ontbrekende seizoenen schatten, en de score wordt extra gecapt."
        ),
    },
    {
        "key": "consistentie",
        "naam": "Consistentie",
        "gewicht": 20,
        "uitleg": (
            "Hoeveel gaten er in de meetreeks zitten. Een paar gaten is geen probleem, "
            "maar grote ontbrekende stukken maken de berekening onnauwkeurig."
        ),
    },
    {
        "key": "input_type",
        "naam": "Input-type",
        "gewicht": 20,
        "uitleg": (
            "Origineel 15-minuten meterdata scoort 100%. Heb je alleen uur- of dagdata "
            "aangeleverd, dan moeten we patronen schatten en daalt de score."
        ),
    },
]


def _make_methodology_block(styles, content_width: float) -> Table:
    """Block 'Zo rekenen wij': bronnen + aanpak in mensentaal."""
    head_style = ParagraphStyle(
        "meth_head", fontName="Helvetica-Bold", fontSize=11, leading=14,
        textColor=COLOR_INK,
    )
    body_style = ParagraphStyle(
        "meth_body", parent=styles["BodyText"],
        fontSize=10, leading=14, textColor=COLOR_INK,
    )
    bullet_style = ParagraphStyle(
        "meth_bullet", parent=styles["BodyText"],
        fontSize=10, leading=14, textColor=COLOR_INK, leftIndent=10,
    )

    rows = [
        [Paragraph("Zo rekenen wij voor jou", head_style)],
        [Spacer(1, 1 * mm)],
        [Paragraph(
            "<b>1. Jouw meterdata.</b> Per 15 minuten wat je inkoopt en teruglevert.",
            bullet_style,
        )],
        [Paragraph(
            "<b>2. EPEX-stroomprijzen.</b> Per uur de actuele beursprijs plus leveranciersmarge en belastingen.",
            bullet_style,
        )],
        [Paragraph(
            "<b>3. Batterij-fysica.</b> Laad- en ontlaadrendement, bruikbare capaciteit en realistische cycli-degradatie.",
            bullet_style,
        )],
        [Paragraph(
            "<b>4. Belastingstructuur.</b> Inclusief saldering nu en de verwachte afschaffing in 2027.",
            bullet_style,
        )],
    ]

    inner = Table(rows, colWidths=[content_width - 12 * mm])
    inner.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 1 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1 * mm),
    ]))

    outer = Table([[inner]], colWidths=[content_width])
    outer.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), COLOR_LIGHT_BG),
        ("BOX", (0, 0), (-1, -1), 0.5, COLOR_BORDER),
        ("LEFTPADDING", (0, 0), (-1, -1), 6 * mm),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6 * mm),
        ("TOPPADDING", (0, 0), (-1, -1), 5 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5 * mm),
        ("ROUNDEDCORNERS", [10, 10, 10, 10]),
    ]))
    return outer


def _make_quality_detail_table(quality_score: Optional[dict], styles,
                               content_width: float) -> Table:
    """
    Tabel met de 4 betrouwbaarheid-componenten in detail: naam, gewicht, jouw score,
    uitleg waar de score op gebaseerd is.
    """
    if not quality_score:
        quality_score = {}
    comp = quality_score.get("componenten", {})

    def _score(key):
        if key in comp:
            return float(comp[key].get("score", 0))
        flat_keys = {
            "dekkingsgraad": "coverage_score",
            "seizoensspreiding": "seasonal_score",
            "consistentie": "consistency_score",
            "input_type": "input_type_score",
        }
        return float(quality_score.get(flat_keys.get(key, key), 0))

    # Headerrij
    head_style = ParagraphStyle(
        "qd_head", fontName="Helvetica-Bold", fontSize=8, leading=10,
        textColor=white, alignment=TA_LEFT,
    )
    name_style = ParagraphStyle(
        "qd_name", parent=styles["BatteryName"],
        fontSize=11, leading=13, textColor=COLOR_INK,
    )
    gewicht_style = ParagraphStyle(
        "qd_gew", fontName="Helvetica", fontSize=10, leading=12,
        textColor=COLOR_MUTED, alignment=TA_LEFT,
    )
    body_style = ParagraphStyle(
        "qd_body", parent=styles["BodyText"],
        fontSize=9.5, leading=13, textColor=COLOR_INK,
    )

    rows = [[
        Paragraph("COMPONENT", head_style),
        Paragraph("GEWICHT", head_style),
        Paragraph("JOUW SCORE", head_style),
        Paragraph("WAT WE METEN", head_style),
    ]]

    style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), COLOR_INK),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4 * mm),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4 * mm),
        ("TOPPADDING", (0, 0), (-1, 0), 3 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 3 * mm),
        ("TOPPADDING", (0, 1), (-1, -1), 3.5 * mm),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 3.5 * mm),
        ("BOX", (0, 0), (-1, -1), 0.5, COLOR_BORDER),
        ("ROUNDEDCORNERS", [10, 10, 10, 10]),
    ]

    for i, comp_def in enumerate(_BETROUWBAARHEID_COMPONENTEN, start=1):
        score_val = _score(comp_def["key"])
        if score_val >= 80:
            score_color = HexColor("#15803D")
        elif score_val >= 50:
            score_color = HexColor("#B45309")
        else:
            score_color = HexColor("#B91C1C")
        score_style = ParagraphStyle(
            f"qd_score_{i}", fontName="Helvetica-Bold", fontSize=12, leading=14,
            textColor=score_color, alignment=TA_LEFT,
        )
        rows.append([
            Paragraph(comp_def["naam"], name_style),
            Paragraph(f"{comp_def['gewicht']}%", gewicht_style),
            Paragraph(f"{score_val:.0f}/100", score_style),
            Paragraph(comp_def["uitleg"], body_style),
        ])
        # Scheidslijn tussen rijen
        if i < len(_BETROUWBAARHEID_COMPONENTEN):
            style_cmds.append(("LINEBELOW", (0, i), (-1, i), 0.3, COLOR_BORDER))

    # Naam-kolom breder zodat "Seizoensspreiding" niet midden in een woord wrapt
    col_w = [
        content_width * 0.27,
        content_width * 0.10,
        content_width * 0.14,
        content_width * 0.49,
    ]
    table = Table(rows, colWidths=col_w)
    table.setStyle(TableStyle(style_cmds))
    return table


def _build_methodology_v2(quality_score: Optional[dict], config: SimulationConfig,
                          styles) -> list:
    """Pagina 6: methodologie + betrouwbaarheid-detail."""
    elements = []
    content_width = 210 * mm - 40 * mm

    # Brand row
    brand = Table(
        [
            [Paragraph(
                '<font color="#06B6D4"><b>⚡</b></font> <b>Energy-Truth</b>',
                styles["BrandName"],
            )],
            [Paragraph("Pagina 6 &middot; Hoe wij rekenen", styles["BrandSub"])],
        ],
        colWidths=[content_width],
    )
    brand.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (0, 0), 1 * mm),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 8 * mm),
    ]))
    elements.append(brand)

    # Headline + sub
    elements.append(Paragraph("Hoe wij voor jou hebben gerekend", styles["CoverTitle"]))
    elements.append(Paragraph(
        "Voor wie de details wil weten: zo komen we tot het advies op pagina 1, en wat "
        "betekent de betrouwbaarheidsscore precies?",
        styles["CoverSub"],
    ))

    # Methodologie-blok
    elements.append(Spacer(1, 2 * mm))
    elements.append(_make_methodology_block(styles, content_width))

    # Betrouwbaarheid in detail
    elements.append(Spacer(1, 10 * mm))
    elements.append(Paragraph(
        "WAT ZIT ER IN DE BETROUWBAARHEIDSSCORE?",
        styles["SectionEyebrow"],
    ))
    elements.append(Spacer(1, 4 * mm))
    elements.append(_make_quality_detail_table(quality_score, styles, content_width))

    # Altijd-zichtbare uitleg over hoe de seizoens-cap werkt
    elements.append(Spacer(1, 4 * mm))
    cap_text_style = ParagraphStyle(
        "p6_cap", parent=styles["KpiTileFoot"],
        fontSize=9.5, leading=13, textColor=COLOR_INK,
    )

    # Standaard uitleg over de cap (altijd zichtbaar)
    base_text = (
        "<b>Hoe werkt de seizoens-cap?</b> Een batterij gedraagt zich heel anders per seizoen — "
        "in de zomer vult hij uit zon-overschot, in de winter blijft hij grotendeels leeg. Om die "
        "reden begrenzen we de totaalscore op <b>(aantal aanwezige seizoenen ÷ 4) × 100</b>. Met "
        "alleen winter-data bijvoorbeeld is de maximum-score 25/100, hoeveel kwartieren je ook "
        "hebt aangeleverd. Hebben we alle vier de seizoenen, dan telt de gewogen som van de "
        "componenten gewoon mee."
    )

    cap_actief = False
    if quality_score:
        cap_actief = bool(quality_score.get("cap_actief", False))

    if cap_actief:
        cap_grens = (quality_score or {}).get("cap_grens", "")
        seizoenen = (quality_score or {}).get("seizoenen_aanwezig", 0)
        specific = (
            f" <b>Bij jou is de cap actief op {cap_grens}/100</b> omdat je "
            f"{seizoenen} van de 4 seizoenen hebt aangeleverd."
        )
        elements.append(Paragraph(base_text + specific, cap_text_style))
    else:
        elements.append(Paragraph(base_text, cap_text_style))

    return elements


# ---------------------------------------------------------------------------
# V2 — Pagina 7: "Bijlage" — alle batterijen + alle leveranciers
# ---------------------------------------------------------------------------

def _make_battery_appendix_table(sizing_results: Optional[pd.DataFrame], styles,
                                  content_width: float) -> Table:
    """Tabel met alle geteste batterijen en hun KPIs."""
    if sizing_results is None or sizing_results.empty:
        return Paragraph("Geen batterij-data beschikbaar.", styles["BodyText"])

    df = sizing_results.copy()
    # 1 rij per uniek product (beste strategie per product)
    df["_payback_sort"] = df["payback_jaren"].fillna(9999.0)
    df["_go_sort"] = df["go_nogo"].map({"GO": 0, "ONZEKER": 1, "NOGO": 2}).fillna(3)
    df = df.sort_values(["_go_sort", "_payback_sort"])
    df_unique = df.drop_duplicates(subset=["productnaam"], keep="first").reset_index(drop=True)

    head_style = ParagraphStyle(
        "app_bat_head", fontName="Helvetica-Bold", fontSize=7.5, leading=9,
        textColor=white, alignment=TA_LEFT,
    )
    cell_style = ParagraphStyle(
        "app_bat_cell", fontName="Helvetica", fontSize=8.5, leading=11,
        textColor=COLOR_INK,
    )
    advies_styles = {
        "GO": ParagraphStyle("app_go", fontName="Helvetica-Bold", fontSize=8.5,
                             leading=11, textColor=HexColor("#15803D")),
        "ONZEKER": ParagraphStyle("app_onz", fontName="Helvetica-Bold", fontSize=8.5,
                                  leading=11, textColor=HexColor("#B45309")),
        "NOGO": ParagraphStyle("app_no", fontName="Helvetica-Bold", fontSize=8.5,
                               leading=11, textColor=HexColor("#B91C1C")),
    }
    advies_labels = {"GO": "Go", "ONZEKER": "Twijfel", "NOGO": "No-go"}

    rows = [[
        Paragraph("PRODUCT", head_style),
        Paragraph("kWh", head_style),
        Paragraph("PRIJS", head_style),
        Paragraph("BESPAART/JR", head_style),
        Paragraph("PAYBACK", head_style),
        Paragraph("GARANTIE", head_style),
        Paragraph("ADVIES", head_style),
    ]]

    style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), COLOR_INK),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3 * mm),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3 * mm),
        ("TOPPADDING", (0, 0), (-1, 0), 2.5 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 2.5 * mm),
        ("TOPPADDING", (0, 1), (-1, -1), 2 * mm),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 2 * mm),
        ("BOX", (0, 0), (-1, -1), 0.5, COLOR_BORDER),
    ]

    for i, row in df_unique.iterrows():
        adv_key = row.get("go_nogo", "NOGO")
        adv_style = advies_styles.get(adv_key, cell_style)
        payback = row.get("payback_jaren")
        payback_str = f"{payback:.1f} j" if pd.notna(payback) else "—"
        gar = row.get("garantiejaren")
        gar_str = f"{int(gar)} j" if pd.notna(gar) else "—"

        rows.append([
            Paragraph(str(row.get("productnaam", "—"))[:32], cell_style),
            Paragraph(f"{row.get('capaciteit_kwh', 0):.1f}", cell_style),
            Paragraph(_fmt_eur_short(row.get("totale_capex_eur") or row.get("aanschafprijs_eur", 0)), cell_style),
            Paragraph(_fmt_eur_short(row.get("jaarlijkse_besparing_eur", 0)), cell_style),
            Paragraph(payback_str, cell_style),
            Paragraph(gar_str, cell_style),
            Paragraph(advies_labels.get(adv_key, adv_key), adv_style),
        ])
        # Alternerende rijen
        if (i + 1) % 2 == 0:
            style_cmds.append(("BACKGROUND", (0, i + 1), (-1, i + 1), COLOR_LIGHT_BG))

    col_w = [
        content_width * 0.30,
        content_width * 0.08,
        content_width * 0.13,
        content_width * 0.15,
        content_width * 0.11,
        content_width * 0.11,
        content_width * 0.12,
    ]
    table = Table(rows, colWidths=col_w)
    table.setStyle(TableStyle(style_cmds))
    return table


def _make_providers_appendix_table(selection_info: Optional[dict], results: pd.DataFrame,
                                    styles, content_width: float) -> Table:
    """Tabel met alle leveranciers + gemiddelde marge."""
    if selection_info is None or not selection_info.get("margins"):
        return Paragraph("Geen leverancier-data beschikbaar.", styles["BodyText"])

    margins = selection_info.get("margins", {})
    # Naam-mapping uit results
    name_map = {}
    if results is not None and not results.empty:
        for _, r in results.iterrows():
            code = r.get("provider_code")
            if code not in name_map:
                name_map[code] = r.get("provider_name", code)

    # Sorteren op marge oplopend (goedkoopst eerst)
    sorted_margins = sorted(margins.items(), key=lambda x: float(x[1]))

    head_style = ParagraphStyle(
        "app_prov_head", fontName="Helvetica-Bold", fontSize=7.5, leading=9,
        textColor=white, alignment=TA_LEFT,
    )
    cell_style = ParagraphStyle(
        "app_prov_cell", fontName="Helvetica", fontSize=8.5, leading=11,
        textColor=COLOR_INK,
    )

    rows = [[
        Paragraph("#", head_style),
        Paragraph("LEVERANCIER", head_style),
        Paragraph("CODE", head_style),
        Paragraph("GEM. MARGE (€/kWh)", head_style),
    ]]

    style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), COLOR_INK),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3 * mm),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3 * mm),
        ("TOPPADDING", (0, 0), (-1, 0), 2.5 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 2.5 * mm),
        ("TOPPADDING", (0, 1), (-1, -1), 2 * mm),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 2 * mm),
        ("BOX", (0, 0), (-1, -1), 0.5, COLOR_BORDER),
    ]

    for i, (code, marge) in enumerate(sorted_margins, start=1):
        naam = name_map.get(code, code)
        rows.append([
            Paragraph(str(i), cell_style),
            Paragraph(str(naam), cell_style),
            Paragraph(str(code), cell_style),
            Paragraph(f"€ {float(marge):.4f}", cell_style),
        ])
        if i % 2 == 0:
            style_cmds.append(("BACKGROUND", (0, i), (-1, i), COLOR_LIGHT_BG))

    col_w = [
        content_width * 0.08,
        content_width * 0.52,
        content_width * 0.15,
        content_width * 0.25,
    ]
    table = Table(rows, colWidths=col_w)
    table.setStyle(TableStyle(style_cmds))
    return table


def _build_appendix_v2(results: pd.DataFrame, sizing_results: Optional[pd.DataFrame],
                       selection_info: Optional[dict], config: SimulationConfig,
                       styles) -> list:
    """Pagina 7: bijlage met alle batterijen en alle leveranciers."""
    elements = []
    content_width = 210 * mm - 40 * mm

    # Brand row
    brand = Table(
        [
            [Paragraph(
                '<font color="#06B6D4"><b>⚡</b></font> <b>Energy-Truth</b>',
                styles["BrandName"],
            )],
            [Paragraph("Pagina 7 &middot; Bijlage met alle ruwe data", styles["BrandSub"])],
        ],
        colWidths=[content_width],
    )
    brand.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (0, 0), 1 * mm),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 8 * mm),
    ]))
    elements.append(brand)

    # Headline + sub
    elements.append(Paragraph("Voor wie alle cijfers wil zien", styles["CoverTitle"]))
    elements.append(Paragraph(
        "Alle geteste batterijen en alle Nederlandse leveranciers in twee tabellen. "
        "Handig als je de aanbeveling op pagina 1 wilt nalopen of zelf wilt vergelijken.",
        styles["CoverSub"],
    ))

    # Batterij-tabel
    elements.append(Paragraph(
        "ALLE GETESTE BATTERIJEN",
        styles["SectionEyebrow"],
    ))
    elements.append(Spacer(1, 3 * mm))
    elements.append(_make_battery_appendix_table(sizing_results, styles, content_width))

    # Footer
    elements.append(Spacer(1, 4 * mm))
    foot_style = ParagraphStyle(
        "p7_foot", parent=styles["KpiTileFoot"],
        fontSize=8.5, leading=11, textColor=COLOR_MUTED,
    )
    elements.append(Paragraph(
        "Cijfers zijn berekend over jouw eigen meterperiode en geannualiseerd waar nodig. "
        "De aanbeveling op pagina 1 is gebaseerd op deze data.",
        foot_style,
    ))

    return elements


# ============================================================
# HOOFD-FUNCTIE: generate_report
# ============================================================

def generate_report(
    results,
    config: SimulationConfig,
    output_path: str = "Energy-Truth_Rapport.pdf",
    top_n: int = 30,
    quality_score=None,
    price_cache=None,
    selection_info=None,
    sizing_results=None,
) -> str:
    """
    Genereer een PDF-rapport van de simulatieresultaten (v2 stijl).

    Pagina 1: cover met verdict, KPIs en top-3 batterijen (_build_cover_v2)
    Pagina 2: jaaroverzicht handelsbalans + maandgrafiek (_build_energy_year_v2)

    Sizing-resultaten worden direct in de cover-pagina opgenomen via
    _get_cover_verdict en _make_top3_grid; er is geen aparte sizing-sectie.
    """
    styles = _get_styles()

    # Betrouwbaarheidsscore ophalen als niet meegegeven
    if quality_score is None:
        try:
            from data_quality import calculate_quality_score
            quality_score = calculate_quality_score(
                config.import_batch_id,
                start_date=config.simulation.start_date,
                end_date=config.simulation.end_date,
            )
            logger.info(f"Betrouwbaarheidsscore: {quality_score.get('totaalscore', '?')}")
        except Exception as e:
            logger.warning(f"Betrouwbaarheidsscore kon niet worden berekend: {e}")
            quality_score = None

    user_name = _get_user_name(config.klant_id)
    if user_name:
        logger.info(f"Rapport voor: {user_name}")

    # Meterdata voor pagina 2
    try:
        from scenario_engine import _load_meter_data
        meter_data = _load_meter_data(config)
    except Exception as e:
        logger.warning(f"Meterdata laden mislukt: {e}")
        meter_data = pd.DataFrame()

    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
        title="Energy-Truth Simulatierapport",
        author="Energy-Truth",
    )
    doc.user_name = user_name

    elements = []

    # Pagina 1: cover v2 met sizing-verdict + top 3
    elements.extend(_build_cover_v2(
        results, config, styles,
        quality_score=quality_score,
        sizing_results=sizing_results,
        user_name=user_name,
    ))

    # Pagina 2: jaaroverzicht (alleen als meterdata beschikbaar)
    if not meter_data.empty:
        elements.append(PageBreak())
        elements.extend(_build_energy_year_v2(meter_data, results, config, styles))

    # Pagina 3: wat de batterij voor jou doet (vereist meterdata + simulatie)
    if not meter_data.empty:
        elements.append(PageBreak())
        elements.extend(_build_battery_day_v2(meter_data, sizing_results, config, styles))

    # Pagina 4: welke leverancier
    if results is not None and not results.empty:
        elements.append(PageBreak())
        elements.extend(_build_providers_v2(results, sizing_results, config, styles))

    # Pagina 5: waarom deze laadinstelling
    if results is not None and not results.empty:
        elements.append(PageBreak())
        elements.extend(_build_strategies_v2(results, sizing_results, config, styles))

    # Pagina 6: methodologie + betrouwbaarheid-detail
    elements.append(PageBreak())
    elements.extend(_build_methodology_v2(quality_score, config, styles))

    # Pagina 7: bijlage (alle batterijen + alle leveranciers)
    elements.append(PageBreak())
    elements.extend(_build_appendix_v2(results, sizing_results, selection_info, config, styles))

    doc.build(elements, onFirstPage=_footer, onLaterPages=_footer)
    logger.info(f"Rapport gegenereerd: {output_path}")
    return output_path


# ============================================================
# CLI entry point
# ============================================================

if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    for _lib in ("httpx", "httpcore", "hpack", "urllib3"):
        logging.getLogger(_lib).setLevel(logging.WARNING)

    parser = argparse.ArgumentParser(description="Energy-Truth Rapport Generator")
    parser.add_argument("config", nargs="?", default="config.json",
                        help="Pad naar config.json")
    parser.add_argument("--output", "-o", default="Energy-Truth_Rapport.pdf",
                        help="Output PDF-pad")
    parser.add_argument("--top", type=int, default=30,
                        help="Aantal scenarios in ranking")
    parser.add_argument("--no-sizing", action="store_true",
                        help="Sla batterij-sizing sectie over (sneller)")
    parser.add_argument("--sizing-strategies", default="A,C,D",
                        help="Strategieen voor sizing-advies (default: A,C,D). "
                             "Strategie B optioneel: --sizing-strategies A,B,C,D")
    parser.add_argument("--sizing-provider", default=None,
                        help="Provider voor sizing (default: top-1 uit ranking)")
    parser.add_argument("--sizing-horizon", type=int, default=10,
                        help="NPV-horizon in jaren voor sizing (default: 10)")

    args = parser.parse_args()

    from scenario_engine import run_all_scenarios

    print("Simulatie starten...")
    config = SimulationConfig.from_json(args.config)
    results, price_cache, selection_info = run_all_scenarios(args.config)

    if results.empty:
        print("Geen resultaten - rapport kan niet worden gegenereerd.")
        sys.exit(1)

    sizing_results = None
    if not args.no_sizing:
        try:
            from battery_sizing import find_optimal_battery
            from scenario_engine import _load_meter_data

            sizing_provider = args.sizing_provider
            if sizing_provider is None and not results.empty:
                sizing_provider = results.iloc[0].get("provider_code", "BE")

            sizing_strategies = [s.strip().upper() for s in args.sizing_strategies.split(",")]
            print(f"\nSizing-advies starten ({sizing_provider}, strategieen {sizing_strategies})...")

            meter_data = _load_meter_data(config)
            if meter_data.empty:
                print("Geen meterdata - sizing-sectie overgeslagen.")
            else:
                sizing_results = find_optimal_battery(
                    meter_data,
                    provider_code=sizing_provider,
                    strategies=sizing_strategies,
                    start_date=config.simulation.start_date,
                    end_date=config.simulation.end_date,
                    horizon_years=args.sizing_horizon,
                    own_battery=config.battery,
                )
        except Exception as e:
            logger.warning(f"Sizing-advies mislukt: {e}")
            print(f"Sizing-advies mislukt ({e}) - rapport gaat door zonder sizing-sectie.")

    output = generate_report(
        results, config, output_path=args.output,
        price_cache=price_cache, selection_info=selection_info,
        sizing_results=sizing_results,
    )
    print(f"\nRapport gegenereerd: {output}")
