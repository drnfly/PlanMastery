import math
from overlay import corner_pts, fmt_ft

PUMP_TYPES = ("pump", "pit_pump", "ejector")


def _px(p, w, h):
    return (float(p[0]) * w / 1000, float(p[1]) * h / 1000)


def _seg_dist(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    t = max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / ((dx * dx + dy * dy) or 1)))
    return math.dist(p, (a[0] + t * dx, a[1] + t * dy))


def _line_dist(p, line):
    if len(line) == 1:
        return math.dist(p, line[0])
    return min(_seg_dist(p, a, b) for a, b in zip(line, line[1:]))


def _inside(p, poly):
    x, y, hit = p[0], p[1], False
    for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1]):
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / ((y2 - y1) or 1e-9) + x1:
            hit = not hit
    return hit


def scale(ov: dict, w: int, h: int) -> float:
    k = float(ov.get("ft_per_px") or 0)
    if not k and ov.get("length_ft"):
        tile = [_px(p, w, h) for p in ov.get("drain_tile") or []]
        L = sum(math.dist(a, b) for a, b in zip(tile, tile[1:]))
        k = float(ov["length_ft"]) / L if L else 0
    return k


def _issue(sev, item, problem, why, fix, kind=None, i=None):
    return {"severity": sev, "item": item, "problem": problem, "why": why, "fix": fix, "kind": kind, "i": i}


def _moves(ov, k, w, h):
    orig = ov.get("ai_original")
    if not orig or not k:
        return []
    out = []
    pairs = [("cleanout", i, c, "CO", orig.get("cleanouts") or []) for i, c in enumerate(ov.get("cleanouts") or [])]
    pairs += [("xsump", i, s, "SP", orig.get("sumps") or []) for i, s in enumerate(ov.get("sumps") or [])]
    if (ov.get("sump") or {}).get("x") is not None:
        pairs.append(("sump", None, ov["sump"], "SUMP", [orig["sump"]] if (orig.get("sump") or {}).get("x") is not None else []))
    for kind, i, it, default, olds in pairs:
        name = it.get("label") or default
        match = next((o for o in olds if o.get("label") and o.get("label") == it.get("label")), None)
        if match is None and kind == "sump" and olds:
            match = olds[0]
        if match is None:
            out.append(_issue("info", name, "Added on site — not in the AI layout taken from the plans",
                              "The plans were not used to place this item.", "Confirm with the plans or engineer before installing.", kind, i))
            continue
        moved = math.dist(_px((it["x"], it["y"]), w, h), _px((match["x"], match["y"]), w, h)) * k
        if moved > 3:
            out.append(_issue("info", name, f"Moved {fmt_ft(moved)} from where the AI placed it from the plans",
                              "Field moves are fine if they still meet the rules below.", "Run the plan check to compare with the sheet notes.", kind, i))
    return out


def check_layout(ov: dict, w: int, h: int, k: float | None = None) -> list:
    k = scale(ov, w, h) if k is None else k
    foot = [_px(p, w, h) for p in corner_pts(ov)]
    tile = [_px(p, w, h) for p in ov.get("drain_tile") or [] if isinstance(p, (list, tuple)) and len(p) >= 2]
    sump = ov.get("sump") if (ov.get("sump") or {}).get("x") is not None else None
    dis = [_px(p, w, h) for p in (ov.get("discharge") or {}).get("points") or []]
    out = []
    ft = (lambda px: px * k) if k else None
    if len(foot) < 3:
        out.append(_issue("warning", "Footing outline", "No footing outline traced",
                          "Tile position, stake-out and setbacks can't be checked without the footing.", "Trace the footing with the Footing outline tool."))
    if len(tile) < 2:
        out.append(_issue("error", "Drain tile", "No drain tile drawn", "The foundation has no drainage.", "Draw the tile around the footing."))
    if not k:
        out.append(_issue("warning", "Scale", "Tile length not set — distances can't be checked",
                          "Clearances and spacing are measured in feet.", "Enter the measured tile length in the side panel."))
    if len(foot) >= 3 and len(tile) >= 2:
        perim = foot + foot[:1]
        inside = [n + 1 for n, p in enumerate(tile) if _inside(p, foot) and _line_dist(p, perim) * (k or 0) > 0.5]
        if inside:
            out.append(_issue("error", "Drain tile", f"Tile point{'s' if len(inside) > 1 else ''} {', '.join(map(str, inside[:6]))} {'run' if len(inside) > 1 else 'runs'} inside the footing",
                              "Footing drain tile must sit outside the footing (beside or below it), not under the slab.", "Drag those points outside the footing line.",
                              "tile", inside[0] - 1))
        if ft:
            far = [n + 1 for n, p in enumerate(tile) if n + 1 not in inside and ft(_line_dist(p, perim)) > 4]
            if far:
                out.append(_issue("warning", "Drain tile", f"Tile point{'s' if len(far) > 1 else ''} {', '.join(map(str, far[:6]))} {'sit' if len(far) > 1 else 'sits'} more than 4 ft from the footing",
                                  "Tile away from the footing won't relieve water pressure at the footing/wall joint.", "Keep the tile tight to the footing, inside the stone bed.",
                                  "tile", far[0] - 1))
            perim_len = sum(math.dist(a, b) for a, b in zip(perim, perim[1:]))
            tile_len = sum(math.dist(a, b) for a, b in zip(tile, tile[1:]))
            if perim_len and tile_len < perim_len * 0.85:
                out.append(_issue("warning", "Drain tile", f"Tile covers only {round(tile_len / perim_len * 100)}% of the footing perimeter",
                                  "Plans and code (IRC R405) call for drainage around the full below-grade foundation.", "Extend the tile around the whole footing."))
    sumps = ([("sump", None, sump, "SUMP")] if sump else []) + [("xsump", i, s, "SP") for i, s in enumerate(ov.get("sumps") or [])]
    if not sumps and len(dis) < 2:
        out.append(_issue("error", "Outlet", "No sump or outlet", "Water collected by the tile has nowhere to go.", "Add a sump / pump or a daylight discharge."))
    for kind, i, s, default in sumps:
        name = s.get("label") or default
        p = _px((s["x"], s["y"]), w, h)
        if ft and len(tile) >= 2 and ft(_line_dist(p, tile)) > 6:
            out.append(_issue("warning", name, f"{fmt_ft(ft(_line_dist(p, tile)))} from the drain tile",
                              "The tile must drain into the pit; a long gap needs a solid connector (and a sleeve through the footing).",
                              "Move it onto the tile or note the solid connector pipe.", kind, i))
        has_out = (len(dis) >= 2) if kind == "sump" else bool(s.get("outlet"))
        if s.get("type") in PUMP_TYPES and not has_out:
            out.append(_issue("error", name, "Pump has no discharge line", "A pump with nowhere to discharge floods the pit.",
                              "Add a discharge line to daylight, storm or dry well.", kind, i))
    ends = ([("Discharge", dis[-1], "dpt", len(dis) - 1)] if len(dis) >= 2 else []) + \
           [((s.get("label") or "SP") + " discharge", _px(s["outlet"], w, h), "xoutlet", i) for i, s in enumerate(ov.get("sumps") or []) if s.get("outlet")]
    for name, p, kind, i in ends:
        if len(foot) >= 3 and _inside(p, foot):
            out.append(_issue("error", name, "Discharge ends inside the foundation", "Water would be dumped back against the foundation.",
                              "Run the discharge out past the building.", kind, i))
        elif ft and len(foot) >= 3 and ft(_line_dist(p, foot + foot[:1])) < 10:
            out.append(_issue("warning", name, f"Discharge ends only {fmt_ft(ft(_line_dist(p, foot + foot[:1])))} from the foundation",
                              "Discharge should end at least 10 ft from the foundation so water doesn't cycle back.", "Extend the discharge line to 10 ft or more.", kind, i))
    cos = ov.get("cleanouts") or []
    for i, c in enumerate(cos):
        name = c.get("label") or f"CO-{i + 1}"
        p = _px((c["x"], c["y"]), w, h)
        if ft and len(tile) >= 2 and ft(_line_dist(p, tile)) > 2:
            out.append(_issue("error", name, f"{fmt_ft(ft(_line_dist(p, tile)))} off the drain tile",
                              "A cleanout must tee into the tile to be usable for flushing.", "Drag it onto the tile line.", "cleanout", i))
        if len(foot) >= 3 and _inside(p, foot):
            out.append(_issue("warning", name, "Inside the footing / under the slab", "Crews can't reach a cleanout under the slab after the pour.",
                              "Move it outside the footing and bring the riser to grade.", "cleanout", i))
    if len(tile) >= 2:
        if not cos:
            out.append(_issue("warning", "Cleanouts", "No cleanouts", "The tile can't be flushed or camera-inspected.",
                              "Add a cleanout at the high (upstream) end and at least every 100 ft."))
        elif ft:
            tile_ft = ft(sum(math.dist(a, b) for a, b in zip(tile, tile[1:])))
            if tile_ft / len(cos) > 100:
                out.append(_issue("warning", "Cleanouts", f"{len(cos)} cleanout{'s' if len(cos) > 1 else ''} for {round(tile_ft)} LF of tile",
                                  "Common practice and most specs call for a cleanout at least every 100 ft.", f"Add {math.ceil(tile_ft / 100) - len(cos)} more."))
    if ft:
        pts = [(c.get("label") or f"CO-{i + 1}", _px((c["x"], c["y"]), w, h), "cleanout", i) for i, c in enumerate(cos)] + \
              [(s.get("label") or d, _px((s["x"], s["y"]), w, h), kd, i) for kd, i, s, d in sumps]
        for a in range(len(pts)):
            for b in range(a + 1, len(pts)):
                if ft(math.dist(pts[a][1], pts[b][1])) < 1:
                    out.append(_issue("warning", pts[a][0], f"Overlaps {pts[b][0]}", "Two fittings can't occupy the same spot.",
                                      "Spread them apart or delete the duplicate.", pts[a][2], pts[a][3]))
    return out + _moves(ov, k, w, h)
