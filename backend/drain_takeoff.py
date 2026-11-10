import math
import re

DEFAULTS = {
    "tile_lf": 0.0, "pipe_dia_in": 4.0, "pipe_stick_ft": 10.0, "waste_pct": 10.0,
    "trench_width_in": 12.0, "stone_depth_in": 12.0, "stone_tons_per_cy": 1.4,
    "fabric_overlap_pct": 15.0, "fabric_roll_sf": 1800.0,
    "board_height_ft": 8.0, "board_roll_sf": 200.0, "wall_perimeter_lf": 0.0,
    "cleanout_depth_ft": 4.0, "discharge_lf": 0.0, "pump_discharge_lf": 0.0, "pump_pipe_dia_in": 1.5,
    "downspouts": 4.0, "downspout_leader_lf": 10.0,
}
PUMP_TYPES = {"pump", "pit_pump", "ejector"}


def _len(points, w, h):
    pts = [(p[0] * w / 1000, p[1] * h / 1000) for p in points or [] if isinstance(p, (list, tuple)) and len(p) >= 2]
    return sum(math.dist(a, b) for a, b in zip(pts, pts[1:]))


def derive(ov: dict, page: dict, drainage: dict | None) -> dict:
    """Prefill takeoff inputs from the drain tile layout geometry and drainage plan."""
    w, h = page.get("img_w") or 1000, page.get("img_h") or 1000
    tile_lf = float(ov.get("length_ft") or 0)
    tile_px = _len(ov.get("drain_tile"), w, h)
    ft_per_px = tile_lf / tile_px if tile_lf and tile_px else 0
    foot = [f for f in ov.get("footprint") or [] if isinstance(f, (list, tuple)) and len(f) >= 2]
    if len(foot) > 1 and list(foot[0]) == list(foot[-1]):
        foot = foot[:-1]
    wall_lf = _len(foot + foot[:1], w, h) * ft_per_px if len(foot) > 2 and ft_per_px else tile_lf
    dis_lf = _len((ov.get("discharge") or {}).get("points"), w, h) * ft_per_px
    pump_lf = sum(_len([[s["x"], s["y"]], s["outlet"]], w, h) for s in ov.get("sumps") or [] if s.get("outlet")) * ft_per_px
    m = re.search(r'(\d+(?:\.\d+)?)\s*(?:"|in|inch)', ov.get("pipe_spec") or "")
    stone = re.search(r'(?<![/\d])(\d+)\s*(?:"|in)\s*(?:of\s*|min\.?\s*|deep\s*)?(?:washed\s*|clean\s*)?(?:stone|gravel|aggregate)', (ov.get("pipe_spec") or "").lower())
    p = {**DEFAULTS, "tile_lf": round(tile_lf, 1), "wall_perimeter_lf": round(wall_lf, 1),
         "discharge_lf": max(round(dis_lf, 1), 10.0), "pump_discharge_lf": round(pump_lf, 1)}
    if m and 2 <= float(m.group(1)) <= 8:
        p["pipe_dia_in"] = float(m.group(1))
    if stone:
        p["stone_depth_in"] = float(stone.group(1))
    ds = next((i for i in (drainage or {}).get("items", []) if "downspout" in (i.get("item", "") + i.get("category", "")).lower()), None)
    n = re.search(r"(\d+)", (ds or {}).get("quantity") or "")
    if n:
        p["downspouts"] = float(n.group(1))
    return p


def compute(ov: dict, params: dict) -> dict:
    p = {**DEFAULTS, **{k: float(v) for k, v in (params or {}).items() if k in DEFAULTS and v not in (None, "")}}
    waste = 1 + p["waste_pct"] / 100
    foot = [tuple(f) for f in ov.get("footprint") or [] if isinstance(f, (list, tuple)) and len(f) >= 2]
    if len(foot) > 1 and foot[0] == foot[-1]:
        foot = foot[:-1]
    corners = max(len(foot), 4) if foot else 4
    cleanouts = len(ov.get("cleanouts") or [])
    sumps = ([ov["sump"]] if (ov.get("sump") or {}).get("x") is not None else []) + list(ov.get("sumps") or [])
    pumps = [s for s in sumps if s.get("type") in PUMP_TYPES]
    basins = [s for s in sumps if s.get("type") != "outlet"]
    outlets = (1 if len((ov.get("discharge") or {}).get("points") or []) > 1 else 0) + sum(1 for s in ov.get("sumps") or [] if s.get("outlet"))
    dia = f'{p["pipe_dia_in"]:g}"'
    tile_lf = p["tile_lf"] * waste
    sticks = math.ceil(tile_lf / p["pipe_stick_ft"]) if p["pipe_stick_ft"] else 0
    stone_cy = p["tile_lf"] * (p["trench_width_in"] * p["stone_depth_in"] / 144) / 27 * waste
    fabric_sf = p["tile_lf"] * 2 * (p["trench_width_in"] + p["stone_depth_in"]) / 12 * (1 + p["fabric_overlap_pct"] / 100)
    board_sf = p["wall_perimeter_lf"] * p["board_height_ft"] * waste
    riser_lf = cleanouts * p["cleanout_depth_ft"] * waste
    solid_lf = (p["discharge_lf"] + riser_lf + p["downspouts"] * p["downspout_leader_lf"]) * waste
    pump_lf = p["pump_discharge_lf"] * waste
    r = lambda v, d=1: round(v, d)  # noqa: E731
    rolls = lambda sf, per: (lambda n: f"{n} roll{'s' if n != 1 else ''} @ {per:g} SF")(math.ceil(sf / per) if per else 0)  # noqa: E731
    lines = [
        ("Pipe", "Perforated drain tile", f"{dia} perforated PVC/HDPE, sock optional", r(tile_lf), "LF", f"{sticks} sticks @ {p['pipe_stick_ft']:g}'"),
        ("Pipe", "Solid pipe — outlet, cleanout risers, leaders", f"{dia} solid PVC SDR-35", r(solid_lf), "LF", f"{math.ceil(solid_lf / p['pipe_stick_ft']) if p['pipe_stick_ft'] else 0} sticks"),
        ("Fittings", "Corner sweeps / 90° elbows", dia, corners, "EA", "one per footing corner"),
        ("Fittings", "Couplings", dia, max(sticks - 1, 0), "EA", "one per stick joint"),
        ("Fittings", "Cleanout wye / tee + cap", dia, cleanouts, "EA", "per cleanout on layout"),
        ("Fittings", "Outlet rodent guard / end grate", dia, outlets, "EA", "each daylight / discharge end"),
        ("Fittings", "Downspout adapters", f'{dia} x leader', int(p["downspouts"]), "EA", ""),
        ("Aggregate", "Washed drain stone", '3/4" clean, no fines', r(stone_cy, 2), "CY", f"≈ {r(stone_cy * p['stone_tons_per_cy'], 1)} tons"),
        ("Geotextile", "Non-woven filter fabric", "wrap stone envelope", r(fabric_sf, 0), "SF", rolls(fabric_sf, p["fabric_roll_sf"])),
        ("Wall", "Drainage board / dimple mat", "foundation wall face", r(board_sf, 0), "SF", rolls(board_sf, p["board_roll_sf"])),
        ("Sump", "Sump basins", ", ".join(s.get("pit_size") or "per plan" for s in basins) or "—", len(basins), "EA", ", ".join(s.get("label") or "SUMP" for s in basins)),
        ("Sump", "Sump / ejector pumps", ", ".join(f"{s.get('pump_hp') or '?'} HP" for s in pumps) or "—", len(pumps), "EA", ", ".join(s.get("label") or "SUMP" for s in pumps)),
        ("Sump", "Check valves + unions", f'{p["pump_pipe_dia_in"]:g}"', len(pumps), "EA", "one per pump"),
        ("Sump", "Pump discharge pipe", f'{p["pump_pipe_dia_in"]:g}" Sch 40 PVC', r(pump_lf), "LF", "from added sump outlets"),
    ]
    rows = [{"group": g, "item": i, "spec": s, "qty": q, "unit": u, "notes": n} for g, i, s, q, u, n in lines if q]
    return {"params": p, "lines": rows, "counts": {"corners": corners, "cleanouts": cleanouts, "sumps": len(basins), "pumps": len(pumps), "outlets": outlets}}
