"""Generate fictional German SME profile PDFs for lead-parsing tests.

All companies and people are invented. Intended mix:
  good leads, poor leads, incomplete docs, duplicates, messy formatting.
"""

from __future__ import annotations

from pathlib import Path

from reportlab.lib.colors import Color, HexColor, black, gray, white
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

OUT = Path(__file__).resolve().parent
FONTS = Path(r"C:\Windows\Fonts")

pdfmetrics.registerFont(TTFont("Arial", str(FONTS / "arial.ttf")))
pdfmetrics.registerFont(TTFont("Arial-Bold", str(FONTS / "arialbd.ttf")))
pdfmetrics.registerFont(TTFont("Arial-Italic", str(FONTS / "ariali.ttf")))
pdfmetrics.registerFont(TTFont("Calibri", str(FONTS / "calibri.ttf")))
pdfmetrics.registerFont(TTFont("Calibri-Bold", str(FONTS / "calibrib.ttf")))
pdfmetrics.registerFont(TTFont("Georgia", str(FONTS / "georgia.ttf")))
pdfmetrics.registerFont(TTFont("Georgia-Bold", str(FONTS / "georgiab.ttf")))
pdfmetrics.registerFont(TTFont("CourierNew", str(FONTS / "cour.ttf")))
pdfmetrics.registerFont(TTFont("CourierNew-Bold", str(FONTS / "courbd.ttf")))
pdfmetrics.registerFont(TTFont("Comic", str(FONTS / "comic.ttf")))
pdfmetrics.registerFont(TTFont("Consolas", str(FONTS / "consola.ttf")))

PAGE_W, PAGE_H = A4
LEFT = 22 * mm
RIGHT = PAGE_W - 22 * mm


def new_pdf(name: str) -> canvas.Canvas:
    path = OUT / name
    c = canvas.Canvas(str(path), pagesize=A4)
    c.setTitle(name.replace(".pdf", "").replace("_", " "))
    c.setAuthor("Fictional sample — not a real company")
    return c


def draw_footer(c: canvas.Canvas, note: str) -> None:
    c.setFillColor(gray)
    c.setFont("Arial", 7)
    c.drawString(LEFT, 12 * mm, "FICTIONAL SAMPLE DATA — for software testing only")
    c.drawRightString(RIGHT, 12 * mm, note)


def kv_block(
    c: canvas.Canvas,
    pairs: list[tuple[str, str]],
    *,
    y: float,
    label_font: str = "Arial-Bold",
    value_font: str = "Arial",
    size: float = 11,
    gap: float = 9 * mm,
    label_color: Color = HexColor("#333333"),
    value_color: Color = black,
    wrap_width: float = 120 * mm,
) -> float:
    for label, value in pairs:
        c.setFillColor(label_color)
        c.setFont(label_font, size)
        c.drawString(LEFT, y, f"{label}:")
        c.setFillColor(value_color)
        c.setFont(value_font, size)
        text = c.beginText(LEFT + 48 * mm, y)
        text.setFont(value_font, size)
        text.setFillColor(value_color)
        text.textLines(_wrap(value, 78))
        c.drawText(text)
        lines = max(1, len(_wrap(value, 78)))
        y -= gap + (lines - 1) * (size + 2)
    return y


def _wrap(text: str, width: int) -> list[str]:
    words = text.split()
    if not words:
        return [""]
    lines: list[str] = []
    cur = words[0]
    for w in words[1:]:
        if len(cur) + 1 + len(w) <= width:
            cur += " " + w
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    return lines


def header_bar(c: canvas.Canvas, title: str, subtitle: str, color: str) -> None:
    c.setFillColor(HexColor(color))
    c.rect(0, PAGE_H - 32 * mm, PAGE_W, 32 * mm, fill=1, stroke=0)
    c.setFillColor(white)
    c.setFont("Calibri-Bold", 20)
    c.drawString(LEFT, PAGE_H - 16 * mm, title)
    c.setFont("Calibri", 11)
    c.drawString(LEFT, PAGE_H - 24 * mm, subtitle)


# ---------------------------------------------------------------------------
# 1. Obvious good lead — clean, complete (user example)
# ---------------------------------------------------------------------------
def pdf_mueller() -> None:
    c = new_pdf("mueller_maschinenbau.pdf")
    header_bar(
        c,
        "Müller Maschinenbau GmbH",
        "Company profile  ·  confidential internal use",
        "#1F4E79",
    )
    y = PAGE_H - 48 * mm
    kv_block(
        c,
        [
            ("Location", "Villingen-Schwenningen, Germany"),
            ("Industry", "Industrial Manufacturing"),
            ("Employees", "85"),
            ("Annual Revenue", "€12.4 million"),
            ("Contact", "Max Müller"),
            ("Position", "Managing Director"),
            (
                "Current Situation",
                "The company currently manages several administrative processes using spreadsheets and manually maintained documents.",
            ),
            (
                "Digitalization",
                "The company is interested in improving internal workflows and reducing repetitive administrative work.",
            ),
            (
                "Potential Need",
                "Process automation and digital workflow optimization.",
            ),
        ],
        y=y,
    )
    draw_footer(c, "profile / 2026-03")
    c.save()


# ---------------------------------------------------------------------------
# 2. Obvious good lead — logistics, explicit budget and timeline
# ---------------------------------------------------------------------------
def pdf_nordlogistik() -> None:
    c = new_pdf("nordlogistik_hamburg.pdf")
    header_bar(
        c,
        "NordLogistik Hamburg GmbH",
        "Account brief  ·  sales opportunity",
        "#0B6E4F",
    )
    y = PAGE_H - 48 * mm
    kv_block(
        c,
        [
            ("Location", "Hamburg-Harburg, Germany"),
            ("Industry", "Freight forwarding and contract logistics"),
            ("Employees", "210"),
            ("Annual Revenue", "€41.8 million (FY 2025)"),
            ("Contact", "Lena Hoffmann"),
            ("Position", "Head of Operations"),
            ("Email", "l.hoffmann@nordlogistik-hamburg.example"),
            ("Phone", "+49 40 555 120-0"),
            (
                "Current Situation",
                "Order intake, dock scheduling and invoice matching are still handled in Excel workbooks emailed between shifts. Warehouse pick lists are printed daily. Three failed attempts to replace the old TMS left parallel systems in place.",
            ),
            (
                "Digitalization",
                "Management approved a digitalization budget of €180,000 for 2026. They want to go live before peak season (October). Explicitly asked vendors for workflow automation, EDI, and exception handling dashboards.",
            ),
            (
                "Potential Need",
                "TMS/WMS integration, invoice automation, and digital dock-to-office workflows. Decision expected Q3 2026. Hoffmann is the economic buyer.",
            ),
        ],
        y=y,
        gap=8.2 * mm,
    )
    draw_footer(c, "opportunity brief / 2026-06")
    c.save()


# ---------------------------------------------------------------------------
# 3. Obvious good lead — professional services, paper-heavy
# ---------------------------------------------------------------------------
def pdf_bergmann() -> None:
    c = new_pdf("bergmann_steuerberatung.pdf")
    header_bar(
        c,
        "Bergmann & Partner Steuerberatungsgesellschaft mbH",
        "Kanzleiprofil",
        "#5C2D91",
    )
    y = PAGE_H - 48 * mm
    kv_block(
        c,
        [
            ("Location", "Saarbrücken, Saarland, Germany"),
            ("Industry", "Tax advisory / accounting"),
            ("Employees", "22 (4 Steuerberater, 18 staff)"),
            ("Annual Revenue", "€3.1 million"),
            ("Contact", "Dr. Klaus Bergmann"),
            ("Position", "Managing Partner"),
            (
                "Current Situation",
                "DATEV is used for filings, but incoming client documents arrive by post, email and WhatsApp. Two clerks spend most mornings renaming PDFs and typing data into Excel before anything reaches DATEV. Client status is tracked on a whiteboard.",
            ),
            (
                "Digitalization",
                "Partners voted in May 2026 to introduce a client portal and automatic document intake. They are looking for a solution that works with DATEV and reduces manual capture. German-language support is required.",
            ),
            (
                "Potential Need",
                "Document capture, client workflow automation, and a simple portal. Budget indicated: mid five-figure annual. Go-live target: January 2027.",
            ),
        ],
        y=y,
        gap=8.4 * mm,
    )
    draw_footer(c, "kanzlei / intern")
    c.save()


# ---------------------------------------------------------------------------
# 4. Poor lead — they sell software, already fully digital, do-not-contact
# ---------------------------------------------------------------------------
def pdf_kaiser() -> None:
    c = new_pdf("kaiser_digital_ag.pdf")
    header_bar(c, "Kaiser Digital AG", "Vendor / not a prospect", "#8B1E1E")
    y = PAGE_H - 48 * mm
    kv_block(
        c,
        [
            ("Location", "München, Germany (HQ) + Berlin office"),
            ("Industry", "Enterprise software and IT consulting"),
            ("Employees", "420"),
            ("Annual Revenue", "€67 million"),
            ("Contact", "Procurement mailbox"),
            ("Position", "n/a — do not approach individual staff"),
            (
                "Current Situation",
                "Fully digital operating model. Custom internal ERP, in-house RPA team of 14, and a product line that competes directly with workflow automation vendors.",
            ),
            (
                "Digitalization",
                "No external automation or workflow tools will be purchased. IT strategy 2026–2028 is 'build, not buy'. Previous outreach was marked as spam.",
            ),
            (
                "Potential Need",
                "None. Written request: remove from mailing lists. They are a competitor, not a customer.",
            ),
        ],
        y=y,
        gap=8.5 * mm,
        label_color=HexColor("#8B1E1E"),
    )
    c.setFillColor(HexColor("#8B1E1E"))
    c.setFont("Arial-Bold", 12)
    c.drawString(LEFT, 28 * mm, "STATUS: DO NOT CONTACT  ·  competitor / closed-lost")
    draw_footer(c, "suppression list")
    c.save()


# ---------------------------------------------------------------------------
# 5. Poor lead — micro business, no budget, no interest
# ---------------------------------------------------------------------------
def pdf_baeckerei() -> None:
    c = new_pdf("schneider_baeckerei.pdf")
    c.setFillColor(HexColor("#F4E6C3"))
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    c.setFillColor(HexColor("#6B3F1D"))
    c.setFont("Georgia-Bold", 22)
    c.drawCentredString(PAGE_W / 2, PAGE_H - 30 * mm, "Bäckerei Schneider")
    c.setFont("Georgia", 11)
    c.drawCentredString(PAGE_W / 2, PAGE_H - 38 * mm, "Inhabergeführt seit 1987")

    lines = [
        "Ort:  Kirchheim am Neckar  (kleiner Laden, eine Filiale)",
        "Branche:  Bäckerei / Konditorei",
        "Mitarbeiter:  3  (Inhaber + 2 Teilzeit)",
        "Jahresumsatz:  ca. 190.000 Euro",
        "Ansprechpartner:  Hans Schneider  (Inhaber, backt selbst)",
        "",
        "Aktuelle Situation:",
        "Kasse ist ein altes Gerät. Bestellungen vom Dorf kommen telefonisch.",
        "Ein Computer steht im Hinterzimmer für E-Mails und die Steuererklärung.",
        "",
        "Digitalisierung:",
        "Kein Interesse. Kein Budget. 'Wir backen Brot, wir kaufen keine Software.'",
        "",
        "Potenzieller Bedarf:",
        "Keiner. Bitte nicht anrufen. Bitte nicht per Newsletter anschreiben.",
    ]
    c.setFillColor(black)
    y = PAGE_H - 55 * mm
    for line in lines:
        font = "Georgia-Bold" if line.endswith(":") and len(line) < 28 else "Georgia"
        c.setFont(font, 11)
        c.drawString(LEFT, y, line)
        y -= 8 * mm
    draw_footer(c, "micro / no-fit")
    c.save()


# ---------------------------------------------------------------------------
# 6. Incomplete — missing company name, revenue, most fields
# ---------------------------------------------------------------------------
def pdf_incomplete_note() -> None:
    c = new_pdf("intern_notiz_unvollstaendig.pdf")
    c.setFillColor(HexColor("#FFF8DC"))
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    c.setFillColor(HexColor("#444444"))
    c.setFont("Comic", 16)
    c.drawString(LEFT, PAGE_H - 25 * mm, "interne notiz  —  messe stuttgart")
    c.setStrokeColor(HexColor("#CCCCAA"))
    c.setLineWidth(0.4)
    for gy in range(int(20 * mm), int(PAGE_H - 15 * mm), 9):
        c.line(LEFT - 4 * mm, gy, RIGHT + 4 * mm, gy)

    c.setFillColor(HexColor("#1A1A1A"))
    c.setFont("Comic", 12)
    notes = [
        "firma aus stand C14??? gelbes logo",
        "ort: irgendwo BW  —  nicht hamburg",
        "branche:   (hab ich vergessen nachzufragen)",
        "MA:  'so um die 40 oder 50?'  unsicher",
        "umsatz:  —",
        "kontakt:  Thomas  (nachname??)   visitenkarte verloren",
        "position:  ? sagte irgendwas mit einkauf oder lager",
        "",
        "situation:  arbeiten noch viel mit excel, meinte er",
        "digital:  'vielleicht später' / 'mal schauen'",
        "bedarf:  unklar. rückruf vereinbart, nummer nicht notiert.",
        "",
        "TODO:  jemand soll im internet nach gelbem logo + stuttgart messe suchen",
    ]
    y = PAGE_H - 42 * mm
    for line in notes:
        c.drawString(LEFT + 4 * mm, y, line)
        y -= 11 * mm
    draw_footer(c, "incomplete / handwritten note")
    c.save()


# ---------------------------------------------------------------------------
# 7. Duplicate of Müller — stale CRM export, spelling variants
# ---------------------------------------------------------------------------
def pdf_mueller_duplicate() -> None:
    c = new_pdf("mueller_maschinenbau_crm_export.pdf")
    c.setFillColor(HexColor("#1A1A1A"))
    c.rect(0, PAGE_H - 14 * mm, PAGE_W, 14 * mm, fill=1, stroke=0)
    c.setFillColor(HexColor("#B8F27A"))
    c.setFont("Consolas", 9)
    c.drawString(LEFT, PAGE_H - 9 * mm, "CRM_EXPORT  |  accounts.csv -> print  |  pulled 2024-11-02")

    c.setFillColor(black)
    c.setFont("CourierNew-Bold", 13)
    c.drawString(LEFT, PAGE_H - 28 * mm, "ACCOUNT_RECORD")
    c.setFont("CourierNew", 10)
    dump = [
        "account_id ........... A-10482",
        "legal_name ........... Mueller Maschinenbau GmbH",
        "aka .................. Müller Maschinenbau / MM Bau VS",
        "street ............... Industriestr. 14",
        "city ................. Villingen Schwenningen",
        "country .............. DE",
        "industry_code ........ mechanical engineering",
        "headcount ............ 82",
        "rev_eur .............. 12000000",
        "owner_user ........... sales_west",
        "primary_contact ...... Maximilian Mueller",
        "job_title ............ Geschäftsführer",
        "email ................ info@mueller-maschinenbau.example",
        "phone ................ +49 7721 00000",
        "last_touch ........... 2024-09-18 (trade fair)",
        "notes ................ still on Excel for shop-floor admin;",
        "                      asked about workflow tools at Motek.",
        "need_guess ........... process automation",
        "duplicate_of ......... (empty)",
        "source ............... imported from old SATURN crm",
    ]
    y = PAGE_H - 40 * mm
    for line in dump:
        c.drawString(LEFT, y, line)
        y -= 6.2 * mm
    c.setFont("CourierNew", 8)
    c.setFillColor(HexColor("#666666"))
    c.drawString(LEFT, 22 * mm, "WARNING: record not merged. spelling differs from 'Müller Maschinenbau GmbH'.")
    draw_footer(c, "duplicate / stale export")
    c.save()


# ---------------------------------------------------------------------------
# 8. Messy formatting — forwarded email printout, mixed languages, typos
# ---------------------------------------------------------------------------
def pdf_messy_email() -> None:
    c = new_pdf("FW_RE_unternehmen_daten.pdf")
    # chaotic header
    c.setFillColor(HexColor("#0033AA"))
    c.setFont("Arial-Bold", 9)
    c.drawString(8 * mm, PAGE_H - 10 * mm, "OUTLOOK  ·  Druckansicht")
    c.setFillColor(HexColor("#CC0000"))
    c.setFont("Arial", 16)
    c.drawString(8 * mm, PAGE_H - 20 * mm, "WG: AW: WG: firma info dringend!!!!")
    c.setFillColor(black)
    c.setFont("Arial-Italic", 8)
    c.drawString(8 * mm, PAGE_H - 26 * mm, "Von:  anna.k@intern.example    An: vertrieb-alle    Datum: Mo 03.08.2026  22:17")

    c.setStrokeColor(HexColor("#DDDDDD"))
    c.line(8 * mm, PAGE_H - 29 * mm, PAGE_W - 8 * mm, PAGE_H - 29 * mm)

    # mixed sizes / cases / languages
    y = PAGE_H - 38 * mm
    blocks = [
        ("Comic", 11, HexColor("#000000"), "hi team  anbei was der praktikant zusammenkopiert hat, sorry fuer format"),
        ("Arial-Bold", 18, HexColor("#003366"), "HOLZWERK   sued   GmbH ??? oder Holzwerk Süd?"),
        ("Arial", 10, black, "LOCATION::   trossingen / tuttligen /  near VS???   Baden  Wuerttemberg"),
        ("Calibri-Bold", 14, HexColor("#AA0000"), "INDUSTRY  wood processing / sägewerk /  packaging pallets"),
        ("Georgia", 9, black, "employees   60ish     maybe 58     Lisa said  'unter 100'"),
        ("CourierNew-Bold", 12, HexColor("#003300"), "REVENUE:  8,2 Mio €   OR  8.2 million   OR  'acht komma zwei'"),
        ("Arial", 11, black, "Contact:  Frau   G.   WEBER      (einkauf? produktion?  'Frau Weber aus dem Büro')"),
        ("Arial-Italic", 10, HexColor("#333333"), "Position................           n/a / unknown / 'sie macht alles'"),
        ("Calibri", 11, black, "current SITUATION---they still  FAX  delivery notes to customers   and  the  office  has  4  different  excel files  named  FINAL_v3_neu_NEU2.xlsx"),
        ("Arial", 13, HexColor("#003399"), "Digitalisierung:   JA!!!   chef will 'endlich papier loswerden'  but  no  timeline  and  they  'haben kein IT-ler'"),
        ("Comic", 12, HexColor("#660066"), "potential need??  maybe  invoice  automation   or  just  a  shared  drive  idk"),
        ("Arial", 8, gray, "ps:  this might be the same as that mueller thing??  wait no  different  company  wood  not  machines"),
        ("Georgia-Bold", 10, black, "PPS they also wrote:  'please send offer  but  only  if  cheap'"),
    ]
    for font, size, color, text in blocks:
        c.setFillColor(color)
        c.setFont(font, size)
        t = c.beginText(8 * mm, y)
        t.setFont(font, size)
        t.setFillColor(color)
        t.setLeading(size + 3)
        for line in _wrap(text, 92):
            t.textLine(line)
            y -= size + 3
        c.drawText(t)
        y -= 4 * mm
        if y < 28 * mm:
            break

    c.setFillColor(HexColor("#FFEE00"))
    c.rect(120 * mm, 18 * mm, 70 * mm, 10 * mm, fill=1, stroke=0)
    c.setFillColor(black)
    c.setFont("Arial-Bold", 8)
    c.drawString(122 * mm, 21 * mm, "!! follow up  this week  ??")
    draw_footer(c, "messy / email printout")
    c.save()


# ---------------------------------------------------------------------------
# 9. Incomplete + OCR-messy — truncated company, garbled fields
# ---------------------------------------------------------------------------
def pdf_ocr_fragment() -> None:
    c = new_pdf("lead_sheet_scanlike.pdf")
    c.setFillColor(HexColor("#EFEFEF"))
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    # fake scan shadow
    c.setFillColor(HexColor("#D0D0D0"))
    c.rect(12 * mm, 18 * mm, PAGE_W - 20 * mm, PAGE_H - 32 * mm, fill=1, stroke=0)
    c.setFillColor(white)
    c.rect(10 * mm, 22 * mm, PAGE_W - 22 * mm, PAGE_H - 36 * mm, fill=1, stroke=0)

    c.setFillColor(HexColor("#222222"))
    c.setFont("Georgia-Bold", 15)
    c.drawString(18 * mm, PAGE_H - 32 * mm, "Fischer Präz...")
    c.setFont("Georgia", 8)
    c.setFillColor(HexColor("#888888"))
    c.drawString(18 * mm, PAGE_H - 38 * mm, "[page 1 of ?  ·  fax received  ·  quality: poor]")

    c.setFillColor(HexColor("#222222"))
    y = PAGE_H - 52 * mm
    ocr_lines = [
        ("Locatlon", "Stuttg4rt?  /  Filderstadt  /  l.E.  'bei  S'"),
        ("lndustry", "precisi0n  parts  /  CNC  /  (cut off)"),
        ("Emp1oyees", "4O"),
        ("Revenu", "€  ??.?   million     hand-written:  8,2?"),
        ("C0ntact", "Herr  Fisch—     (rest unreadable)"),
        ("Positlon", ""),
        ("Current  Sit.", "spreadshe ets   and   shop  packets  on  paper"),
        ("DigitaIization", "int  r  sted   in   'weniger  Zettel'"),
        ("Potentlal  Need", "???"),
    ]
    for label, value in ocr_lines:
        c.setFont("CourierNew-Bold", 10)
        c.setFillColor(HexColor("#555555"))
        c.drawString(18 * mm, y, label)
        c.setFont("CourierNew", 11)
        c.setFillColor(black)
        c.drawString(18 * mm + 42 * mm, y, value if value else "________________")
        y -= 14 * mm

    c.setFont("Arial-Italic", 9)
    c.setFillColor(HexColor("#AA0000"))
    c.drawString(18 * mm, 36 * mm, "OCR confidence 41%   ·   fields missing   ·   do not import without review")
    draw_footer(c, "incomplete + messy OCR")
    c.save()


# ---------------------------------------------------------------------------
# 10. Second duplicate — NordLogistik under another legal-name variant
# ---------------------------------------------------------------------------
def pdf_nordlogistik_duplicate() -> None:
    c = new_pdf("nlh_gmbh_account_card.pdf")
    c.setFillColor(HexColor("#F7F7F7"))
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    c.setFillColor(HexColor("#0B6E4F"))
    c.roundRect(18 * mm, PAGE_H - 118 * mm, PAGE_W - 36 * mm, 100 * mm, 6, fill=0, stroke=1)
    c.setFont("Calibri-Bold", 16)
    c.drawString(24 * mm, PAGE_H - 32 * mm, "NLH GmbH")
    c.setFont("Calibri", 10)
    c.setFillColor(HexColor("#444444"))
    c.drawString(24 * mm, PAGE_H - 40 * mm, "also filed as: Nord-Logistik HH  /  NordLogistik Hamburg GmbH")

    c.setFillColor(black)
    rows = [
        ("Seat", "Harburg, Hamburg, DE"),
        ("NACE / industry", "52.29 — other transportation support"),
        ("Staff (2025 filing)", "198"),
        ("Turnover", "EUR 42m (rounded, Bundesanzeiger)"),
        ("Key person", "L. Hoffmann, Operations"),
        ("Systems today", "Excel + legacy TMS + printed pick lists"),
        ("Buyer signal", "budget reserved; wants live before Oct peak"),
        ("Need (coded)", "WMS/TMS, invoice matching, workflow"),
        ("Internal ID", "ACC-7781  (possible match to NordLogistik Hamburg)"),
    ]
    y = PAGE_H - 52 * mm
    for k, v in rows:
        c.setFont("Calibri-Bold", 10)
        c.drawString(24 * mm, y, k)
        c.setFont("Calibri", 10)
        c.drawString(70 * mm, y, v)
        y -= 7.5 * mm
    draw_footer(c, "duplicate / register card")
    c.save()


def main() -> None:
    builders = [
        pdf_mueller,
        pdf_nordlogistik,
        pdf_bergmann,
        pdf_kaiser,
        pdf_baeckerei,
        pdf_incomplete_note,
        pdf_mueller_duplicate,
        pdf_messy_email,
        pdf_ocr_fragment,
        pdf_nordlogistik_duplicate,
    ]
    for fn in builders:
        fn()
        print("wrote", fn.__name__)


if __name__ == "__main__":
    main()
