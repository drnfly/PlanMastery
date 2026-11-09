import io
import math
from PIL import Image, ImageDraw, ImageFont

TILE = (37, 99, 235)
DISCHARGE = (22, 163, 74)
CLEANOUT = (234, 88, 12)
SUMP = (220, 38, 38)
SLOPE = (192, 38, 211)
FOOT = (6, 182, 212)


def _pt(p, w, h):
    return (float(p[0]) * w / 1000, float(p[1]) * h / 1000)


def _pts(seq, w, h):
    return [_pt(p, w, h) for p in seq or [] if isinstance(p, (list, tuple)) and len(p) >= 2]


def _arrow(d, a, b, color, width):
    if math.dist(a, b) < 1:
        return
    d.line([a, b], fill=color, width=width)
    ang = math.atan2(b[1] - a[1], b[0] - a[0])
    s = width * 4
    left = (b[0] - s * math.cos(ang - 0.45), b[1] - s * math.sin(ang - 0.45))
    right = (b[0] - s * math.cos(ang + 0.45), b[1] - s * math.sin(ang + 0.45))
    d.polygon([b, left, right], fill=color)


def _dashed(d, pts, color, width, dash):
    for a, b in zip(pts, pts[1:]):
        length = math.dist(a, b)
        if length < 1:
            continue
        n = max(int(length // (dash * 2)), 1)
        for i in range(n):
            t0, t1 = (2 * i) * dash / length, min((2 * i + 1) * dash / length, 1)
            if t0 >= 1:
                break
            d.line([(a[0] + (b[0] - a[0]) * t0, a[1] + (b[1] - a[1]) * t0), (a[0] + (b[0] - a[0]) * t1, a[1] + (b[1] - a[1]) * t1)], fill=color, width=width)


SUMP_TYPES = {"pit": "SUMP PIT", "pump": "SUMP PUMP", "pit_pump": "PIT + PUMP", "ejector": "EJECTOR PUMP", "outlet": "OUTLET"}


def sump_text(s: dict, default: str) -> str:
    bits = [s.get("label") or default]
    if s.get("type") in SUMP_TYPES and SUMP_TYPES[s["type"]] not in bits[0].upper():
        bits.append(SUMP_TYPES[s["type"]])
    if s.get("pump_hp"):
        bits.append(f"{s['pump_hp']} HP")
    if s.get("pit_size"):
        bits.append(f"pit {s['pit_size']}")
    return " · ".join(bits).replace(" · ", " - ")


def render_overlay(image: bytes, ov: dict) -> bytes:
    img = Image.open(io.BytesIO(image)).convert("RGB")
    w, h = img.size
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    lw = max(int(max(w, h) / 300), 3)
    font = ImageFont.load_default(size=max(int(max(w, h) / 90), 14))

    foot = _pts(ov.get("footprint"), w, h)
    if len(foot) > 2:
        d.polygon(foot, fill=FOOT + (28,), outline=FOOT + (200,), width=max(lw // 2, 2))
    tile = _pts(ov.get("drain_tile"), w, h)
    if len(tile) > 1:
        d.line(tile, fill=TILE + (235,), width=lw * 2, joint="curve")
        for p in tile[::max(len(tile) // 12, 1)]:
            d.ellipse([p[0] - lw * 0.6, p[1] - lw * 0.6, p[0] + lw * 0.6, p[1] + lw * 0.6], fill=(255, 255, 255, 230))
    dis = ov.get("discharge") or {}
    dpts = _pts(dis.get("points"), w, h)
    if len(dpts) > 1:
        _dashed(d, dpts[:-1] + [dpts[-1]], DISCHARGE + (240,), lw * 2, lw * 4)
        _arrow(d, dpts[-2], dpts[-1], DISCHARGE + (240,), lw * 2)
        d.text((dpts[-1][0] + lw * 3, dpts[-1][1]), dis.get("label") or "DISCHARGE", fill=DISCHARGE + (255,), font=font, stroke_width=3, stroke_fill=(255, 255, 255, 255))
    for s in ov.get("slope_arrows") or []:
        try:
            a, b = _pt((s["x1"], s["y1"]), w, h), _pt((s["x2"], s["y2"]), w, h)
        except (KeyError, TypeError, ValueError):
            continue
        _arrow(d, a, b, SLOPE + (230,), max(lw // 2, 2))
        d.text(((a[0] + b[0]) / 2 + lw * 2, (a[1] + b[1]) / 2), s.get("label", ""), fill=SLOPE + (255,), font=font, stroke_width=3, stroke_fill=(255, 255, 255, 255))
    for c in ov.get("cleanouts") or []:
        try:
            x, y = _pt((c["x"], c["y"]), w, h)
        except (KeyError, TypeError, ValueError):
            continue
        r = lw * 3
        d.ellipse([x - r, y - r, x + r, y + r], fill=CLEANOUT + (240,), outline=(255, 255, 255, 255), width=2)
        d.text((x + r + 4, y - r), c.get("label") or "CO", fill=CLEANOUT + (255,), font=font, stroke_width=3, stroke_fill=(255, 255, 255, 255))
    sump = ov.get("sump") or {}
    if sump.get("x") is not None and (sump.get("x") or sump.get("y")):
        x, y = _pt((sump["x"], sump["y"]), w, h)
        r = lw * 4
        d.rectangle([x - r, y - r, x + r, y + r], fill=SUMP + (240,), outline=(255, 255, 255, 255), width=2)
        d.text((x + r + 4, y - r), sump_text(sump, "SUMP"), fill=SUMP + (255,), font=font, stroke_width=3, stroke_fill=(255, 255, 255, 255))
    extra_marks = []
    for s in ov.get("sumps") or []:
        try:
            x, y = _pt((s["x"], s["y"]), w, h)
        except (KeyError, TypeError, ValueError):
            continue
        out = s.get("outlet")
        if out and len(out) == 2:
            o = _pt(out, w, h)
            _dashed(d, [(x, y), o], DISCHARGE + (240,), lw * 2, lw * 4)
            _arrow(d, (x, y), o, DISCHARGE + (240,), lw * 2)
            extra_marks.append(o)
        r = lw * 4
        d.rectangle([x - r, y - r, x + r, y + r], fill=SUMP + (240,), outline=(255, 255, 255, 255), width=2)
        if s.get("type") in ("pump", "pit_pump", "ejector"):
            d.ellipse([x - r * 0.45, y - r * 0.45, x + r * 0.45, y + r * 0.45], fill=(255, 255, 255, 255))
        d.text((x + r + 4, y - r), sump_text(s, "SUMP"), fill=SUMP + (255,), font=font, stroke_width=3, stroke_fill=(255, 255, 255, 255))
        extra_marks.append((x, y))

    items = [(TILE, f"Drain tile - {ov.get('pipe_spec') or 'perforated pipe'}" + (f" ({ov['length_ft']} LF)" if ov.get("length_ft") else "")),
             (DISCHARGE, "Discharge / solid outlet"), (CLEANOUT, "Cleanout"), (SUMP, "Sump / pump (dot = pump)"), (SLOPE, "Slope direction")]
    pad, row = lw * 3, int(font.size * 1.6)
    box_w = int(max(d.textlength(t, font=font) for _, t in items) + pad * 4 + row)
    box_h = row * len(items) + pad * 2
    marks = dpts + extra_marks + ([_pt((sump["x"], sump["y"]), w, h)] if sump.get("x") is not None else [])
    corners = [(pad, h - box_h - pad), (w - box_w - pad, h - box_h - pad), (pad, pad), (w - box_w - pad, pad)]

    def clearance(c):
        cx, cy = c[0] + box_w / 2, c[1] + box_h / 2
        return min((math.dist((cx, cy), m) for m in marks), default=1e9)
    x0, y0 = max(corners, key=clearance) if marks else corners[0]
    x0, y0 = max(x0, 0), max(y0, 0)
    d.rectangle([x0, y0, x0 + box_w, y0 + box_h], fill=(255, 255, 255, 235), outline=(30, 41, 59, 255), width=2)
    for i, (col, t) in enumerate(items):
        yy = y0 + pad + i * row
        d.rectangle([x0 + pad, yy + 3, x0 + pad + row - 8, yy + row - 8], fill=col + (255,))
        d.text((x0 + pad * 2 + row - 8, yy), t, fill=(15, 23, 42, 255), font=font)

    out = Image.alpha_composite(img.convert("RGBA"), layer).convert("RGB")
    buf = io.BytesIO()
    out.save(buf, "PNG", optimize=True)
    return buf.getvalue()
