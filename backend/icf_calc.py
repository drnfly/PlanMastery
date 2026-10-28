import math

BAR_LB_FT = {"#3": 0.376, "#4": 0.668, "#5": 1.043, "#6": 1.502, "#7": 2.044, "#8": 2.670}
BAR_DIA_IN = {"#3": 0.375, "#4": 0.5, "#5": 0.625, "#6": 0.75, "#7": 0.875, "#8": 1.0}

DEFAULT_PARAMS = {"block_length_in": 48, "block_height_in": 16, "waste_pct": 5, "concrete_overage_pct": 8,
                  "stock_length_ft": 20, "lap_bar_diameters": 48}


def num(v, default=0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def bar(v: str) -> str:
    v = (v or "").strip().replace(" ", "")
    if v and not v.startswith("#"):
        v = "#" + v
    return v if v in BAR_LB_FT else ""


def run_length(length_ft: float, lap_ft: float, stock: float) -> float:
    """Total bar LF for one continuous line including lap splices."""
    if length_ft <= 0:
        return 0.0
    pieces = math.ceil(length_ft / max(stock - lap_ft, 1))
    return length_ft + max(pieces - 1, 0) * lap_ft


def compute(walls: list, footings: list, params: dict) -> dict:
    p = {**DEFAULT_PARAMS, **{k: num(v, DEFAULT_PARAMS[k]) for k, v in (params or {}).items() if k in DEFAULT_PARAMS}}
    face_sqft = p["block_length_in"] * p["block_height_in"] / 144
    waste = 1 + p["waste_pct"] / 100
    over = 1 + p["concrete_overage_pct"] / 100
    stock = p["stock_length_ft"]
    rebar = {}

    def add(size, lf):
        if size and lf > 0:
            rebar[size] = rebar.get(size, 0) + lf

    def lap_ft(size):
        return BAR_DIA_IN.get(size, 0.625) * p["lap_bar_diameters"] / 12

    rows = []
    tot = {"gross_sqft": 0, "net_sqft": 0, "straight_blocks": 0, "corner_blocks": 0, "wall_cy": 0.0}
    for w in walls:
        L, H, core = num(w.get("length_ft")), num(w.get("height_ft")), num(w.get("core_in"), 6)
        courses = math.ceil(H * 12 / p["block_height_in"]) if H else 0
        gross = L * H
        net = max(gross - num(w.get("openings_sqft")), 0)
        corners = int(num(w.get("corners_90"))) + int(num(w.get("corners_45")))
        corner_blocks = corners * courses
        straight = math.ceil(max(net / face_sqft - corner_blocks, 0) * waste) if net else 0
        cy = net * core / 12 / 27 * over
        vb, hb = bar(w.get("vertical_bar")), bar(w.get("horizontal_bar"))
        v_spacing = num(w.get("vertical_spacing_in"))
        v_count = math.ceil(L * 12 / v_spacing) + 1 if vb and v_spacing and L else 0
        v_lf = v_count * run_length(H, lap_ft(vb), stock)
        dowel_lf = v_count * (lap_ft(vb) + 1)
        h_rows = math.ceil(courses / max(num(w.get("horizontal_every_courses"), 1), 1)) if hb else 0
        h_lf = h_rows * int(num(w.get("horizontal_bars_per_row"), 1)) * run_length(L, lap_ft(hb), stock)
        add(vb, v_lf + dowel_lf)
        add(hb, h_lf)
        rows.append({"id": w.get("id"), "courses": courses, "net_sqft": round(net, 1), "straight_blocks": straight,
                     "corner_blocks": corner_blocks, "concrete_cy": round(cy, 2), "vertical_bars": v_count,
                     "vertical_lf": round(v_lf, 1), "dowel_lf": round(dowel_lf, 1), "horizontal_lf": round(h_lf, 1)})
        tot["gross_sqft"] += gross
        tot["net_sqft"] += net
        tot["straight_blocks"] += straight
        tot["corner_blocks"] += corner_blocks
        tot["wall_cy"] += cy

    frows = []
    footing_cy = 0.0
    for f in footings:
        L = num(f.get("length_ft"))
        cy = L * num(f.get("width_in")) / 12 * num(f.get("depth_in")) / 12 / 27 * over
        fb = bar(f.get("bars"))
        lf = int(num(f.get("bar_count"))) * run_length(L, lap_ft(fb), stock) if fb else 0
        add(fb, lf)
        footing_cy += cy
        frows.append({"id": f.get("id"), "concrete_cy": round(cy, 2), "rebar_lf": round(lf, 1)})

    rebar_rows = [{"size": s, "lf": round(lf, 1), "sticks": math.ceil(lf / stock), "stock_ft": stock,
                   "weight_lb": round(lf * BAR_LB_FT[s])} for s, lf in sorted(rebar.items())]
    return {
        "params": p,
        "walls": rows,
        "footings": frows,
        "rebar": rebar_rows,
        "totals": {"gross_sqft": round(tot["gross_sqft"], 1), "net_sqft": round(tot["net_sqft"], 1),
                   "straight_blocks": tot["straight_blocks"], "corner_blocks": tot["corner_blocks"],
                   "wall_cy": round(tot["wall_cy"], 2), "footing_cy": round(footing_cy, 2),
                   "total_cy": round(tot["wall_cy"] + footing_cy, 2),
                   "rebar_lb": sum(r["weight_lb"] for r in rebar_rows)},
    }
