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


STAKE = (180, 83, 9)


def fmt_ft(f: float) -> str:
    ft, inch = int(f), round((f - int(f)) * 12)
    if inch == 12:
        ft, inch = ft + 1, 0
    return f"{ft}'-{inch}\""


def corner_pts(ov: dict) -> list:
    a = [p for p in ov.get("footprint") or [] if isinstance(p, (list, tuple)) and len(p) >= 2]
    return a[:-1] if len(a) > 2 and list(a[0][:2]) == list(a[-1][:2]) else a


def stakeouts(ov: dict, w: int, h: int) -> list:
    corners = corner_pts(ov)
    if not corners:
        return []
    k = float(ov.get("ft_per_px") or 0)
    if not k and ov.get("length_ft"):
        tile = _pts(ov.get("drain_tile"), w, h)
        px = sum(math.dist(a, b) for a, b in zip(tile, tile[1:]))
        k = float(ov["length_ft"]) / px if px else 0
    items = [("Cleanout", c, f"CO-{i + 1}") for i, c in enumerate(ov.get("cleanouts") or [])]
    sump = ov.get("sump") or {}
    if sump.get("x") is not None:
        items.append(("Sump", sump, "SUMP"))
    items += [("Sump", s, f"SP-{i + 2}") for i, s in enumerate(ov.get("sumps") or [])]
    cs = [_pt(c, w, h) for c in corners]
    out = []
    for kind, it, default in items:
        try:
            p = _pt((it["x"], it["y"]), w, h)
        except (KeyError, TypeError, ValueError):
            continue
        j = min(range(len(cs)), key=lambda n: math.dist(p, cs[n]))
        px = math.dist(p, cs[j])
        out.append({"kind": kind, "label": it.get("label") or default, "corner": j + 1, "p": p, "c": cs[j],
                    "ft": round(px * k, 2) if k else None})
    return out


def _draw_stakes(d, ov, w, h, lw, font):
    for i, c in enumerate(corner_pts(ov)):
        x, y = _pt(c, w, h)
        d.ellipse([x - lw * 1.4, y - lw * 1.4, x + lw * 1.4, y + lw * 1.4], fill=STAKE + (255,), outline=(255, 255, 255, 255), width=2)
        d.text((x + lw * 2, y + lw), f"C{i + 1}", fill=STAKE + (255,), font=font, stroke_width=3, stroke_fill=(255, 255, 255, 255))
    for s in stakeouts(ov, w, h):
        _dashed(d, [s["p"], s["c"]], STAKE + (235,), max(lw // 2, 2), lw * 2)
        if s["ft"] is not None:
            mx, my = (s["p"][0] + s["c"][0]) / 2, (s["p"][1] + s["c"][1]) / 2
            d.text((mx, my), fmt_ft(s["ft"]), fill=(255, 255, 255, 255), font=font, anchor="mm", stroke_width=4, stroke_fill=STAKE + (255,))


def _crop(img, ov: dict, margin: float = 0.12):
    w, h = img.size
    xs, ys = [], []
    for key in ("footprint", "drain_tile"):
        for p in ov.get(key) or []:
            xs.append(p[0]); ys.append(p[1])
    for p in (ov.get("discharge") or {}).get("points") or []:
        xs.append(p[0]); ys.append(p[1])
    for it in (ov.get("cleanouts") or []) + (ov.get("sumps") or []) + [ov.get("sump") or {}]:
        if it.get("x") is not None:
            xs.append(it["x"]); ys.append(it["y"])
    if not xs:
        return img, ov
    x0, x1, y0, y1 = min(xs) * w / 1000, max(xs) * w / 1000, min(ys) * h / 1000, max(ys) * h / 1000
    m = max(x1 - x0, y1 - y0) * margin + 40
    box = (int(max(x0 - m, 0)), int(max(y0 - m, 0)), int(min(x1 + m, w)), int(min(y1 + m, h)))
    cw, ch = box[2] - box[0], box[3] - box[1]
    fx = lambda x: (x * w / 1000 - box[0]) * 1000 / cw  # noqa: E731
    fy = lambda y: (y * h / 1000 - box[1]) * 1000 / ch  # noqa: E731
    tp = lambda a: [[fx(p[0]), fy(p[1])] for p in a or [] if isinstance(p, (list, tuple)) and len(p) >= 2]  # noqa: E731
    tx = lambda it: {**it, "x": fx(it["x"]), "y": fy(it["y"])} if it and it.get("x") is not None else it  # noqa: E731
    o = {**ov, "footprint": tp(ov.get("footprint")), "drain_tile": tp(ov.get("drain_tile")),
         "cleanouts": [tx(c) for c in ov.get("cleanouts") or []], "sump": tx(ov.get("sump")),
         "sumps": [{**tx(s), "outlet": [fx(s["outlet"][0]), fy(s["outlet"][1])] if s.get("outlet") else None} for s in ov.get("sumps") or []],
         "slope_arrows": [{**a, "x1": fx(a["x1"]), "y1": fy(a["y1"]), "x2": fx(a["x2"]), "y2": fy(a["y2"])} for a in ov.get("slope_arrows") or []]}
    if ov.get("discharge"):
        o["discharge"] = {**ov["discharge"], "points": tp(ov["discharge"].get("points"))}
    if not ov.get("ft_per_px") and ov.get("length_ft"):
        tile = _pts(ov.get("drain_tile"), w, h)
        px = sum(math.dist(a, b) for a, b in zip(tile, tile[1:]))
        o["ft_per_px"] = float(ov["length_ft"]) / px if px else 0
    return img.crop(box), o


def render_overlay(image: bytes, ov: dict, stake: bool = False, crop: bool = False) -> bytes:
    img = Image.open(io.BytesIO(image)).convert("RGB")
    full = max(img.size)
    if crop:
        img, ov = _crop(img, ov)
    w, h = img.size
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    lw = max(int(full / 300 * (0.55 if crop else 1)), 2)
    font = ImageFont.load_default(size=max(int(full / 90 * (0.6 if crop else 1)), 12))

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

    if stake:
        _draw_stakes(d, ov, w, h, lw, font)

    items = [(TILE, f"Drain tile - {ov.get('pipe_spec') or 'perforated pipe'}" + (f" ({ov['length_ft']} LF)" if ov.get("length_ft") else "")),
             (DISCHARGE, "Discharge / solid outlet"), (CLEANOUT, "Cleanout"), (SUMP, "Sump / pump (dot = pump)"), (SLOPE, "Slope direction")] + ([(STAKE, "Stake-out: distance to nearest footing corner")] if stake else [])
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
    out = Image.alpha_composite(img.convert("RGBA"), layer).convert("RGB")
    if crop:
        ext = Image.new("RGB", (max(w, box_w + pad * 2), h + box_h + pad * 2), (255, 255, 255))
        ext.paste(out, (0, 0))
        out, x0, y0 = ext, pad, h + pad
    d = ImageDraw.Draw(out)
    d.rectangle([x0, y0, x0 + box_w, y0 + box_h], fill=(255, 255, 255), outline=(30, 41, 59), width=2)
    for i, (col, t) in enumerate(items):
        yy = y0 + pad + i * row
        d.rectangle([x0 + pad, yy + 3, x0 + pad + row - 8, yy + row - 8], fill=col)
        d.text((x0 + pad * 2 + row - 8, yy), t, fill=(15, 23, 42), font=font)

    buf = io.BytesIO()
    out.save(buf, "PNG", optimize=True)
    return buf.getvalue()
