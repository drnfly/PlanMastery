import asyncio
import math
import re

import httpx
from datetime import datetime

from ai_engine import _collect, _parse

UA = {"User-Agent": "BuildSpec.ai supplier finder (construction takeoff tool)"}
NOMINATIM = "https://nominatim.openstreetmap.org/search"
OVERPASS = ["https://overpass-api.de/api/interpreter"]

CATS = {
    "rental": "Equipment rental",
    "big_box": "Home center",
    "building": "Building / lumber supply",
    "landscape": "Stone / landscape supply",
    "plumbing": "Plumbing supply",
    "hardware": "Hardware store",
}
CARRIES = {
    "rental": {"Equipment"},
    "big_box": {"Pipe", "Fittings", "Aggregate", "Geotextile", "Wall", "Waterproofing", "Sump", "Equipment"},
    "building": {"Pipe", "Fittings", "Geotextile", "Wall", "Waterproofing", "Sump"},
    "landscape": {"Aggregate", "Geotextile", "Pipe"},
    "plumbing": {"Pipe", "Fittings", "Sump"},
    "hardware": {"Pipe", "Fittings", "Sump", "Waterproofing"},
}

EQUIPMENT = [
    ("eq_excavator", "Mini excavator", "3-5 ton, digging tile trench", 2, "day"),
    ("eq_compactor", "Plate compactor", "backfill compaction", 1, "day"),
    ("eq_laser", "Rotary laser level", "set tile slope", 2, "day"),
    ("eq_trencher", "Walk-behind trencher", "outlet / discharge line", 1, "day"),
    ("eq_pump", "Dewatering pump", "2\" trash pump with hose", 2, "day"),
    ("eq_dumpster", "Roll-off dumpster", "20 yd", 1, "each"),
]


def haversine_mi(a, b) -> float:
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 3958.8 * 2 * math.asin(math.sqrt(h))


async def geocode(address: str) -> dict | None:
    async with httpx.AsyncClient(timeout=20, headers=UA) as c:
        r = await c.get(NOMINATIM, params={"q": address, "format": "jsonv2", "limit": 1, "addressdetails": 1})
        r.raise_for_status()
        hits = r.json()
    if not hits:
        return None
    h, ad = hits[0], hits[0].get("address") or {}
    place = ", ".join(x for x in [ad.get("city") or ad.get("town") or ad.get("village") or ad.get("county"), ad.get("state"), ad.get("country_code", "").upper()] if x)
    return {"lat": float(h["lat"]), "lon": float(h["lon"]), "display": h.get("display_name"), "place": place}


def categorize(tags: dict) -> str | None:
    name = (tags.get("name") or "").lower()
    shop = tags.get("shop")
    if re.search(r"home depot|lowe'?s|menards", name):
        return "big_box"
    if shop == "tool_hire" or re.search(r"rental|rentals|sunbelt|united rentals|herc|equipment", name):
        return "rental"
    if shop == "garden_centre" or tags.get("landuse") == "quarry" or re.search(r"landscap|stone|aggregate|gravel|quarry|sand|topsoil|mulch", name):
        return "landscape"
    if shop == "plumbing" or re.search(r"plumbing|ferguson|winsupply|hd supply", name):
        return "plumbing"
    if shop in ("trade", "building_materials") or tags.get("trade") or re.search(r"lumber|building|supply|concrete|beacon|abc supply", name):
        return "building"
    if shop in ("hardware", "doityourself"):
        return "hardware"
    return None


SKIP = r"apartment|flooring|battery|showroom|walmart|meijer|target|furniture|cabinet|tile & stone|countertop|granite|jewel"


def _addr(t: dict) -> str:
    return " ".join(x for x in [t.get("addr:housenumber"), t.get("addr:street")] if x) + \
        (", " + t["addr:city"] if t.get("addr:city") else "")


async def find_suppliers(lat: float, lon: float, radius_mi: float) -> list:
    r = int(radius_mi * 1609.34)
    a = f"(around:{r},{lat},{lon})"
    q = f"""[out:json][timeout:40];
(
 nwr{a}["shop"~"^(hardware|doityourself|trade|building_materials|garden_centre|tool_hire|plumbing)$"];
 nwr{a}["trade"]["name"];
 nwr{a}["name"~"rental|equipment|supply|lumber|landscap|aggregate|stone|quarry|gravel|plumbing",i]["shop"];
 nwr{a}["name"~"rental|equipment rent|supply|lumber|aggregate|quarry|gravel",i]["office"];
 nwr{a}["landuse"="quarry"]["name"];
);
out center tags 400;"""
    data = None
    async with httpx.AsyncClient(timeout=httpx.Timeout(45, connect=6), headers=UA) as c:
        for url in OVERPASS:
            try:
                res = await c.post(url, data={"data": q})
                res.raise_for_status()
                data = res.json()
                break
            except (httpx.HTTPError, ValueError):
                continue
    elements = data.get("elements", []) if data else await _nominatim_places(lat, lon, radius_mi)
    out, seen = [], set()
    for el in elements:
        t = el.get("tags") or {}
        cat = categorize(t)
        plat = el.get("lat") or (el.get("center") or {}).get("lat")
        plon = el.get("lon") or (el.get("center") or {}).get("lon")
        if not cat or not t.get("name") or plat is None or re.search(SKIP, t["name"], re.I):
            continue
        key = (t["name"].lower(), round(plat, 3), round(plon, 3))
        if key in seen:
            continue
        seen.add(key)
        out.append({"id": f"{el['type'][0]}{el['id']}", "name": t["name"][:120], "category": cat, "lat": plat, "lon": plon,
                    "address": _addr(t)[:200], "phone": (t.get("phone") or t.get("contact:phone") or "")[:40],
                    "website": (t.get("website") or t.get("contact:website") or "")[:300],
                    "distance_mi": round(haversine_mi((lat, lon), (plat, plon)), 1), "source": "OpenStreetMap"})
    out.sort(key=lambda s: s["distance_mi"])
    per = {}
    kept = []
    for s in out:
        n = re.sub(r"^the\s+", "", s["name"].lower()).strip()
        per[n] = per.get(n, 0) + 1
        if per[n] <= 2:
            kept.append(s)
    return kept[:50]


NOM_QUERIES = ["hardware store", "building materials", "lumber", "building supply", "home depot", "lowe's", "menards",
               "equipment rental", "tool rental", "rentals", "landscape supply", "stone", "aggregate", "garden centre", "plumbing supply"]


async def _nominatim_places(lat: float, lon: float, radius_mi: float) -> list:
    dlat = radius_mi / 69.0
    dlon = radius_mi / max(69.0 * math.cos(math.radians(lat)), 1)
    box = f"{lon - dlon},{lat + dlat},{lon + dlon},{lat - dlat}"
    out = []
    async with httpx.AsyncClient(timeout=20, headers=UA) as c:
        for q in NOM_QUERIES:
            try:
                r = await c.get(NOMINATIM, params={"q": q, "format": "jsonv2", "limit": 40, "viewbox": box, "bounded": 1,
                                                   "extratags": 1, "addressdetails": 1})
                r.raise_for_status()
                hits = r.json()
            except (httpx.HTTPError, ValueError):
                hits = []
            for h in hits:
                ad, ex = h.get("address") or {}, h.get("extratags") or {}
                tags = {**ex, "name": h.get("name") or "", h.get("category") or "x": h.get("type"),
                        "addr:housenumber": ad.get("house_number"), "addr:street": ad.get("road"),
                        "addr:city": ad.get("city") or ad.get("town") or ad.get("village")}
                if h.get("category") not in ("shop", "craft", "office", "landuse", "amenity", "building") or not h.get("name"):
                    continue
                if h.get("category") == "building" and not categorize(tags):
                    continue
                out.append({"type": h.get("osm_type") or "n", "id": h.get("osm_id"), "lat": float(h["lat"]), "lon": float(h["lon"]), "tags": tags})
            await asyncio.sleep(1.05)
    return out


def build_items(takeoff: dict | None, wp: dict | None) -> list:
    items = []
    lines = (takeoff or {}).get("lines") or []
    wall_sf = perim = 0.0
    for n, ln in enumerate(lines):
        if ln["group"] == "Wall":
            wall_sf = float(ln["qty"] or 0)
        items.append({"key": f"dr_{n}", "group": ln["group"], "name": ln["item"], "spec": ln.get("spec") or "",
                      "qty": float(ln["qty"] or 0), "unit": ln["unit"], "section": "Drainage", "on": True})
    perim = float(((takeoff or {}).get("params") or {}).get("tile_lf") or 0)
    spec = next((i.get("spec") for i in (wp or {}).get("items", []) if re.search(r"membrane|damp|waterproof", (i.get("item") or "").lower()) and i.get("spec")), None)
    if wall_sf or perim:
        items += [
            {"key": "wp_membrane", "group": "Waterproofing", "name": "Waterproofing membrane", "spec": (spec or "below-grade sheet / fluid-applied")[:120],
             "qty": round(wall_sf * 1.1), "unit": "SF", "section": "Waterproofing", "on": True},
            {"key": "wp_primer", "group": "Waterproofing", "name": "Membrane primer", "spec": "per membrane maker", "qty": max(round(wall_sf / 300), 1),
             "unit": "GAL", "section": "Waterproofing", "on": True},
            {"key": "wp_term", "group": "Waterproofing", "name": "Termination bar", "spec": "aluminum, 10' lengths", "qty": round(perim * 1.05),
             "unit": "LF", "section": "Waterproofing", "on": True},
            {"key": "wp_mastic", "group": "Waterproofing", "name": "Mastic / sealant", "spec": "10 oz tubes", "qty": max(round(perim / 20), 1),
             "unit": "EA", "section": "Waterproofing", "on": True},
        ]
    for i in items:
        if i["group"] == "Wall":
            i.update(group="Waterproofing", section="Waterproofing")
    items += [{"key": k, "group": "Equipment", "name": n, "spec": s, "qty": q, "unit": u, "section": "Equipment rental", "on": True}
              for k, n, s, q, u in EQUIPMENT]
    return items


PRICE_PROMPT = """Estimate CURRENT ({year}) local prices for a foundation drainage / waterproofing job near {place}; adjust older price knowledge for inflation.
For each supplier below, give a realistic unit price (USD, before tax) for every item that kind of supplier normally stocks or rents.
Account for supplier type (home centers retail pricing, trade/lumber yards contractor pricing, landscape yards bulk stone by the CY
or ton, rental shops daily rates) and regional cost level. Skip items the supplier would not carry. Unit prices must match each item's unit.

Suppliers (id | name | type):
{suppliers}

Items (key | group | name | spec | unit):
{items}

Return ONLY JSON (no fences): {{"prices": [{{"s": "supplier id", "i": "item key", "p": 12.5}}], "notes": "1-2 sentences on assumptions"}}"""


async def estimate_prices(place: str, suppliers: list, items: list) -> dict:
    sup = "\n".join(f"{s['id']} | {s['name']} | {CATS[s['category']]}" for s in suppliers[:30])
    its = "\n".join(f"{i['key']} | {i['group']} | {i['name']} | {i['spec']} | {i['unit']}" for i in items)
    res = _parse(await _collect("You are a construction estimator who knows current US/Canadian material and equipment rental prices by region. "
                                "Give realistic, conservative estimates; never claim they are quotes.",
                                PRICE_PROMPT.format(year=datetime.now().year, place=place or "the job site", suppliers=sup, items=its), []))
    ids, keys = {s["id"]: s for s in suppliers}, {i["key"]: i for i in items}
    est = {}
    for row in res.get("prices") or []:
        s, i, p = row.get("s"), row.get("i"), row.get("p")
        if s in ids and i in keys and isinstance(p, (int, float)) and 0 < p < 1e6 and keys[i]["group"] in CARRIES[ids[s]["category"]]:
            est.setdefault(s, {})[i] = round(float(p), 2)
    return {"estimates": est, "notes": str(res.get("notes") or "")[:600]}
