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
    "walls": [("id", "ID", 0.6), ("location", "Location", 1.5), ("length", "Length", 0.75), ("thickness", "Thick", 0.7),
              ("type", "Type", 0.9), ("source", "Src", 0.6), ("notes", "Notes", 2.05)],
    "openings": [("id", "ID", 0.6), ("type", "Type", 0.7), ("location", "Location", 1.5), ("width", "Width", 0.75),
                 ("height", "Height", 0.75), ("source", "Src", 0.6), ("notes", "Notes", 2.2)],
}


def P(text, style="body"):
    return Paragraph(escape("" if text is None else str(text)), S[style])


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


def bullets(items: list, mark: str = "•") -> list:
    return [Paragraph(escape(str(n)), S["bullet"], bulletText=mark) for n in items or []]


def simple_table(headers: list, rows: list, widths: list, bg=INK) -> Table:
    t = grid([[P(h, "head") for h in headers]] + [[P(c, "cell") for c in r] for r in rows], bg)
    t._argW = [w * inch for w in widths]
    return t


CREW_TITLES = {"foundation": "FOUNDATION CREW PACKET", "icf": "ICF WALL CREW PACKET", "waterproofing": "WATERPROOFING CREW PACKET"}


def crew_section(packet: dict) -> list:
    flow = [P("Crew briefing", "h2"), P(packet.get("scope"))]
    for key, title, mark in [("sequence", "Work sequence", "•"), ("notes", "Expert notes for crews", "•"),
                             ("materials", "Materials & specs from plans", "•"), ("inspections", "Hold points & inspections", "✓"),
                             ("rfis", "Open questions / RFIs", "?")]:
        if packet.get(key):
            flow += [P(title, "h3")] + bullets(packet[key], mark)
    return flow + [PageBreak()]


def icf_section(icf: dict) -> list:
    ex, calc = icf.get("extract") or {}, icf.get("calc") or {}
    t, pr = calc.get("totals") or {}, calc.get("params") or {}
    flow = [P("ICF material estimate", "h2"),
            P(f"System: {ex.get('system') or 'not specified'} · Block {pr.get('block_length_in')}\"x{pr.get('block_height_in')}\" · "
              f"waste {pr.get('waste_pct')}% · concrete overage {pr.get('concrete_overage_pct')}% · "
              f"{pr.get('stock_length_ft')}' bar stock · lap {pr.get('lap_bar_diameters')} bar dia.", "meta"), Spacer(1, 6),
            simple_table(["Straight blocks", "Corner blocks", "Wall concrete", "Footing concrete", "Total concrete", "Rebar weight"],
                         [[t.get("straight_blocks"), t.get("corner_blocks"), f"{t.get('wall_cy')} yd³", f"{t.get('footing_cy')} yd³",
                           f"{t.get('total_cy')} yd³", f"{t.get('rebar_lb')} lb"]], [1.2] * 6, AMBER)]
    calc_by_id = {r["id"]: r for r in calc.get("walls", [])}
    if ex.get("walls"):
        rows = [[w.get("id"), w.get("location"), w.get("length_ft"), w.get("height_ft"), w.get("core_in"),
                 calc_by_id.get(w.get("id"), {}).get("straight_blocks"), calc_by_id.get(w.get("id"), {}).get("concrete_cy"),
                 f"{w.get('vertical_bar') or '—'} @ {w.get('vertical_spacing_in') or '—'}\"",
                 f"({w.get('horizontal_bars_per_row') or '—'}) {w.get('horizontal_bar') or '—'} / {w.get('horizontal_every_courses') or '—'} crs"]
                for w in ex["walls"]]
        flow += [P("ICF wall runs", "h3"), simple_table(["ID", "Location", "L ft", "H ft", "Core in", "Blocks", "yd³", "Vertical", "Horizontal"],
                                                        rows, [0.45, 1.75, 0.5, 0.5, 0.55, 0.6, 0.55, 1.0, 1.4])]
    if ex.get("footings"):
        fc = {r["id"]: r for r in calc.get("footings", [])}
        rows = [[f.get("id"), f.get("location"), f.get("length_ft"), f"{f.get('width_in')}\" x {f.get('depth_in')}\"",
                 f"({f.get('bar_count')}) {f.get('bars')}", fc.get(f.get("id"), {}).get("concrete_cy")] for f in ex["footings"]]
        flow += [P("Footings", "h3"), simple_table(["ID", "Location", "L ft", "W x D", "Bars", "yd³"], rows, [0.5, 2.6, 0.7, 1.2, 1.2, 1.1])]
    if calc.get("rebar"):
        flow += [P("Rebar order", "h3"), simple_table(["Size", "Linear ft", "Sticks", "Stock", "Weight lb"],
                                                      [[r["size"], r["lf"], r["sticks"], f"{r['stock_ft']}'", r["weight_lb"]] for r in calc["rebar"]],
                                                      [1.2, 1.5, 1.2, 1.2, 1.5])]
    if ex.get("assumptions"):
        flow += [P("Assumptions", "h3")] + bullets(ex["assumptions"])
    if ex.get("missing"):
        flow += [P("Missing from plans — confirm before ordering", "h3")] + bullets(ex["missing"], "!")
    return flow + [PageBreak()]


def wp_section(wp: dict, title: str = "Waterproofing checklist") -> list:
    items = wp.get("items") or []
    counts = {s: sum(1 for i in items if i.get("status") == s) for s in ("specified", "missing", "unclear")}
    flow = [P(title, "h2"),
            P(f"{counts['specified']} specified · {counts['missing']} missing · {counts['unclear']} unclear · "
              f"{sum(1 for i in items if i.get('verified'))} verified on site", "meta"), Spacer(1, 4), P(wp.get("summary"))]
    if wp.get("strategy"):
        flow += [Spacer(1, 4), P("Strategy", "h3"), P(wp["strategy"])]
    order = {"missing": 0, "unclear": 1, "specified": 2}
    rows = [["✓" if i.get("verified") else "☐", (i.get("status") or "").upper(), (i.get("severity") or "").upper(),
             f"{i.get('category')}: {i.get('item')}" + (f" — {i['quantity']}" if i.get("quantity") else ""),
             i.get("spec") or "—", i.get("recommendation"), ", ".join(i.get("sheets") or [])]
            for i in sorted(items, key=lambda i: order.get(i.get("status"), 3))]
    flow += [Spacer(1, 6), simple_table(["", "Status", "Sev", "Item", "Plans say", "Recommendation", "Sheets"], rows,
                                        [0.25, 0.75, 0.55, 1.6, 1.5, 1.95, 0.7])]
    for key, label, mark in [("sequence", "Installation sequence", "•"), ("inspections", "Hold points & inspections", "✓"), ("rfis", "Open questions / RFIs", "?")]:
        if wp.get(key):
            flow += [P(label, "h3")] + bullets(wp[key], mark)
    return flow + [PageBreak()]


def build_report(project: dict, pages: list, images: dict, brand: dict, logo: bytes | None, qa: list, extras: dict | None = None) -> bytes:
    extras = extras or {}
    crew = extras.get("crew", "full")
    buf = io.BytesIO()
    company = brand.get("company_name") or "BuildSpec.ai"
    date = datetime.now(timezone.utc).strftime("%b %d, %Y")
    try:
        logo_reader = ImageReader(io.BytesIO(logo)) if logo else None
    except Exception:
        logo_reader = None

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
        c.drawRightString(w - 0.6 * inch, h - 0.5 * inch, f"{project['name']} · {CREW_TITLES.get(crew, 'Takeoff report').title()}")
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
    flow = [Spacer(1, 0.6 * inch), P(CREW_TITLES.get(crew, "DIMENSION TAKEOFF REPORT"), "h3"), P(project["name"], "h1"), Spacer(1, 8),
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
    t._argW = [w * inch for w in (0.8, 2.2, 1.0, 1.2, 0.6, 0.6, 0.9)]
    flow += [t, PageBreak()]

    if extras.get("packet"):
        flow += crew_section(extras["packet"])
    if extras.get("icf"):
        flow += icf_section(extras["icf"])
    if extras.get("wp"):
        flow += wp_section(extras["wp"])
    if extras.get("drain"):
        flow += wp_section(extras["drain"], "Drainage plan")

    for pg in pages:
        flow += sheet_section(pg, images.get(pg["index"]))

    if qa:
        flow.append(P("Expert Q&A", "h2"))
        for q, a in qa:
            flow.append(KeepTogether([P(f"Q: {q}", "h3")] + md_to_paras(a)[:1]))
            flow += md_to_paras(a)[1:] + [Spacer(1, 6)]

    doc.build(flow)
    return buf.getvalue()
