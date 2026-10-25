import io
import re
from datetime import datetime, timezone
from xml.sax.saxutils import escape
from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (BaseDocTemplate, Frame, PageTemplate, Paragraph, Spacer, Table, TableStyle,
                                Image, PageBreak, KeepTogether)

INK = colors.HexColor("#0B0F17")
AMBER = colors.HexColor("#F59E0B")
SLATE = colors.HexColor("#475569")
LINE = colors.HexColor("#CBD5E1")
ZEBRA = colors.HexColor("#F8FAFC")

S = {
    "h1": ParagraphStyle("h1", fontName="Helvetica-Bold", fontSize=26, leading=30, textColor=INK),
    "h2": ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=15, leading=19, textColor=INK, spaceBefore=4, spaceAfter=4),
    "h3": ParagraphStyle("h3", fontName="Helvetica-Bold", fontSize=10.5, leading=14, textColor=AMBER, spaceBefore=10, spaceAfter=4),
    "body": ParagraphStyle("body", fontName="Helvetica", fontSize=9, leading=12.5, textColor=INK),
    "meta": ParagraphStyle("meta", fontName="Helvetica", fontSize=8.5, leading=11, textColor=SLATE),
    "cell": ParagraphStyle("cell", fontName="Helvetica", fontSize=7.8, leading=9.6, textColor=INK),
    "head": ParagraphStyle("head", fontName="Helvetica-Bold", fontSize=7.8, leading=9.6, textColor=colors.white),
    "bullet": ParagraphStyle("bullet", fontName="Helvetica", fontSize=9, leading=12.5, textColor=INK, leftIndent=12, bulletIndent=2),
}

COLS = {
    "rooms": [("name", "Room", 1.5), ("width", "Width", 0.8), ("length", "Length", 0.8), ("area", "Area", 0.8),
              ("ceiling_height", "Clg ht", 0.6), ("source", "Src", 0.6), ("notes", "Notes", 2.0)],
    "walls": [("id", "ID", 0.45), ("location", "Location", 1.5), ("length", "Length", 0.75), ("thickness", "Thick", 0.7),
              ("type", "Type", 0.9), ("source", "Src", 0.6), ("notes", "Notes", 2.2)],
    "openings": [("id", "ID", 0.45), ("type", "Type", 0.7), ("location", "Location", 1.5), ("width", "Width", 0.75),
                 ("height", "Height", 0.75), ("source", "Src", 0.6), ("notes", "Notes", 2.35)],
}


def P(text, style="body"):
    return Paragraph(escape(str(text or "")), S[style])


def md_to_paras(text: str) -> list:
    out = []
    for line in (text or "").splitlines():
        line = line.strip()
        if not line or set(line) <= set("-|: "):
            continue
        line = re.sub(r"[*_`#>]+", "", line)
        if re.match(r"^(\d+\.|-|•)\s", line):
            out.append(Paragraph(escape(re.sub(r"^(\d+\.|-|•)\s", "", line)), S["bullet"], bulletText="•"))
        else:
            out.append(P(line))
    return out


def grid(rows: list, header_bg=INK) -> Table:
    t = Table(rows, repeatRows=1, hAlign="LEFT")
    style = [("BACKGROUND", (0, 0), (-1, 0), header_bg), ("GRID", (0, 0), (-1, -1), 0.4, LINE),
             ("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]
    style += [("BACKGROUND", (0, i), (-1, i), ZEBRA) for i in range(2, len(rows), 2)]
    t.setStyle(TableStyle(style))
    return t


def dim_table(kind: str, items: list) -> Table:
    cols = COLS[kind]
    scale = 7.3 / sum(c[2] for c in cols)
    rows = [[P(c[1], "head") for c in cols]] + [[P(it.get(c[0], ""), "cell") for c in cols] for it in items]
    t = grid(rows)
    t._argW = [c[2] * scale * inch for c in cols]
    return t


def sheet_image(data: bytes):
    img = PILImage.open(io.BytesIO(data)).convert("RGB")
    img.thumbnail((1600, 1600))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=72)
    buf.seek(0)
    w, h = img.size
    max_w, max_h = 7.3 * inch, 4.6 * inch
    r = min(max_w / w, max_h / h)
    im = Image(buf, width=w * r, height=h * r)
    im.hAlign = "LEFT"
    return im


def label(pg: dict) -> str:
    return " · ".join(x for x in [pg.get("sheet_number"), pg.get("title")] if x) or f"Page {pg['index'] + 1}"


def sheet_section(pg: dict, image: bytes | None) -> list:
    a = pg["analysis"]
    ov = a.get("overall") or {}
    flow = [P(label(pg), "h2"),
            P(f"{(a.get('drawing_type') or 'drawing').title()} · Scale {a.get('scale') or 'not noted'} · "
              f"Units {a.get('units') or '—'} · Discipline {pg.get('discipline') or '—'}", "meta"), Spacer(1, 6)]
    if any(ov.values()):
        flow.append(grid([[P("Overall width", "head"), P("Overall length", "head"), P("Total area", "head")],
                          [P(ov.get("width"), "cell"), P(ov.get("length"), "cell"), P(ov.get("total_area"), "cell")]], AMBER))
        flow.append(Spacer(1, 6))
    if image:
        flow += [sheet_image(image), Spacer(1, 6)]
    if a.get("summary"):
        flow += [P("Summary", "h3"), P(a["summary"])]
    for kind in ("rooms", "walls", "openings"):
        if a.get(kind):
            flow += [P(f"{kind.title()} ({len(a[kind])})", "h3"), dim_table(kind, a[kind])]
    if a.get("expert_notes"):
        flow.append(P("Expert notes for crews", "h3"))
        flow += [Paragraph(escape(n), S["bullet"], bulletText="•") for n in a["expert_notes"]]
    if a.get("warnings"):
        flow.append(P("Verify on site", "h3"))
        flow += [Paragraph(escape(w), S["bullet"], bulletText="!") for w in a["warnings"]]
    return flow + [PageBreak()]


def build_report(project: dict, pages: list, images: dict, brand: dict, logo: bytes | None, qa: list) -> bytes:
    buf = io.BytesIO()
    company = brand.get("company_name") or "BuildSpec.ai"
    date = datetime.now(timezone.utc).strftime("%b %d, %Y")
    logo_reader = ImageReader(io.BytesIO(logo)) if logo else None

    def chrome(c, doc):
        c.saveState()
        w, h = letter
        c.setFillColor(AMBER)
        c.rect(0, h - 6, w, 6, fill=1, stroke=0)
        x = 0.6 * inch
        if logo_reader:
            iw, ih = logo_reader.getSize()
            lh = 0.32 * inch
            c.drawImage(logo_reader, x, h - 0.62 * inch, width=lh * iw / ih, height=lh, mask="auto")
            x += lh * iw / ih + 8
        c.setFillColor(INK)
        c.setFont("Helvetica-Bold", 10)
        c.drawString(x, h - 0.5 * inch, company)
        c.setFont("Helvetica", 8)
        c.setFillColor(SLATE)
        c.drawRightString(w - 0.6 * inch, h - 0.5 * inch, f"{project['name']} · Takeoff report")
        c.setStrokeColor(LINE)
        c.line(0.6 * inch, h - 0.7 * inch, w - 0.6 * inch, h - 0.7 * inch)
        c.line(0.6 * inch, 0.62 * inch, w - 0.6 * inch, 0.62 * inch)
        c.setFont("Helvetica", 7)
        c.drawString(0.6 * inch, 0.45 * inch, "AI-assisted takeoff. Verify all dimensions in the field. Structural items must be "
                                             "confirmed by the engineer of record.")
        c.drawRightString(w - 0.6 * inch, 0.45 * inch, f"{date} · Page {doc.page}")
        c.restoreState()

    doc = BaseDocTemplate(buf, pagesize=letter, leftMargin=0.6 * inch, rightMargin=0.6 * inch,
                          topMargin=0.9 * inch, bottomMargin=0.8 * inch, title=f"{project['name']} takeoff report")
    doc.addPageTemplates([PageTemplate(frames=[Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height)], onPage=chrome)])

    contact = " · ".join(x for x in [brand.get("prepared_by"), brand.get("phone"), brand.get("email")] if x)
    flow = [Spacer(1, 0.6 * inch), P("DIMENSION TAKEOFF REPORT", "h3"), P(project["name"], "h1"), Spacer(1, 8),
            P(f"Prepared by {company}" + (f" — {contact}" if contact else ""), "meta"),
            P(f"Issued {date} · {len(pages)} of {project.get('page_count', len(pages))} sheets in set", "meta")]
    if brand.get("client"):
        flow.append(P(f"Prepared for {brand['client']}", "meta"))
    flow += [Spacer(1, 18), P("Sheets in this report", "h3")]
    rows = [[P(h, "head") for h in ["Sheet", "Title", "Discipline", "Type", "Rooms", "Walls", "Openings"]]]
    for pg in pages:
        a = pg["analysis"]
        rows.append([P(pg.get("sheet_number") or f"P{pg['index'] + 1}", "cell"), P(pg.get("title"), "cell"),
                     P(pg.get("discipline"), "cell"), P(a.get("drawing_type"), "cell"),
                     P(len(a.get("rooms") or []), "cell"), P(len(a.get("walls") or []), "cell"), P(len(a.get("openings") or []), "cell")])
    t = grid(rows)
    t._argW = [w * inch for w in (0.8, 2.4, 1.0, 1.3, 0.6, 0.6, 0.6)]
    flow += [t, PageBreak()]

    for pg in pages:
        flow += sheet_section(pg, images.get(pg["index"]))

    if qa:
        flow.append(P("Expert Q&A", "h2"))
        for q, a in qa:
            flow.append(KeepTogether([P(f"Q: {q}", "h3")] + md_to_paras(a)[:1]))
            flow += md_to_paras(a)[1:] + [Spacer(1, 6)]

    doc.build(flow)
    return buf.getvalue()
