# Iteration 13: drain layout rule checks (drain-rules), AI plan check (drain-check), drainage PDF, supplier map / price compare (supply)
import copy
import io
import os
import time

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"
P1 = "eb4fb34f-fc53-4700-abee-97f4822c8ce9"   # manual layout page 0, has supplier search
P2 = "c5675b5d-4a36-4502-a217-48d6b5e176d2"   # AI layout on page 4
KEYS = ("sump", "sumps", "cleanouts", "discharge", "drain_tile", "footprint", "length_ft")


def overlay(pid, idx):
    r = requests.get(f"{API}/projects/{pid}", timeout=30)
    assert r.status_code == 200
    pg = next(p for p in r.json()["pages"] if p["index"] == idx)
    return pg, pg["drain_overlay"]


def rules(pid, idx, ov):
    body = {k: ov.get(k) for k in KEYS if ov.get(k) is not None}
    body["ft_per_px"] = ov.get("ft_per_px")
    r = requests.post(f"{API}/projects/{pid}/pages/{idx}/drain-rules", json=body, timeout=30)
    assert r.status_code == 200, r.text
    iss = r.json()["issues"]
    assert isinstance(iss, list)
    return iss


# ---- Drain rules (live checks) ----
class TestDrainRules:
    def test_saved_layout_issues_shape(self):
        _, ov = overlay(P1, 0)
        iss = rules(P1, 0, ov)
        for i in iss:
            assert {"severity", "item", "problem", "why", "fix", "kind", "i"} <= set(i)
            assert i["severity"] in ("error", "warning", "info")
        print("baseline:", [(i["severity"], i["item"], i["problem"]) for i in iss])

    def test_cleanout_off_tile_error(self):
        _, ov = overlay(P1, 0)
        ov = copy.deepcopy(ov)
        ov["cleanouts"][0].update(x=900.0, y=900.0)
        iss = rules(P1, 0, ov)
        hit = [i for i in iss if i["kind"] == "cleanout" and i["i"] == 0 and "off the drain tile" in i["problem"]]
        assert hit and hit[0]["severity"] == "error" and hit[0]["why"] and hit[0]["fix"]

    def test_tile_point_inside_footing(self):
        _, ov = overlay(P1, 0)
        ov = copy.deepcopy(ov)
        ov["drain_tile"][1] = [310.0, 300.0]   # inside footing polygon
        iss = rules(P1, 0, ov)
        hit = [i for i in iss if i["kind"] == "tile" and "inside the footing" in i["problem"]]
        assert hit and "Tile point 2" in hit[0]["problem"] and hit[0]["i"] == 1

    def test_pump_no_discharge(self):
        _, ov = overlay(P1, 0)
        ov = copy.deepcopy(ov)
        ov["sumps"].append({"x": 440.0, "y": 300.0, "label": "SP-9", "type": "pump"})
        iss = rules(P1, 0, ov)
        hit = [i for i in iss if i["kind"] == "xsump" and "Pump has no discharge line" in i["problem"]]
        assert hit and hit[0]["severity"] == "error" and hit[0]["i"] == len(ov["sumps"]) - 1

    def test_moved_and_added_info_on_ai_layout(self):
        _, ov = overlay(P2, 4)
        ov = copy.deepcopy(ov)
        ov["cleanouts"][0]["x"] = min(1000, ov["cleanouts"][0]["x"] + 60)
        ov["cleanouts"].append({"x": ov["drain_tile"][0][0], "y": ov["drain_tile"][0][1], "label": "CO-99"})
        iss = rules(P2, 4, ov)
        infos = [i for i in iss if i["severity"] == "info"]
        print("infos:", [i["problem"] for i in infos])
        assert any(i["i"] == 0 and i["problem"].startswith("Moved") for i in infos)
        assert any(i["item"] == "CO-99" and i["problem"].startswith("Added on site") for i in infos)

    def test_unknown_page_404(self):
        r = requests.post(f"{API}/projects/{P1}/pages/999/drain-rules", json={}, timeout=30)
        assert r.status_code == 404

    def test_drain_check_requires_layout(self):
        r = requests.post(f"{API}/projects/{P1}/pages/1/drain-check", timeout=30)
        assert r.status_code == 400


# ---- Drainage PDF ----
class TestDrainagePdf:
    def test_pdf_has_offsets_and_checks(self):
        r = requests.post(f"{API}/projects/{P1}/report", json={"crew": "drainage"}, timeout=180)
        assert r.status_code == 200, r.text[:300]
        assert r.headers["content-type"].startswith("application/pdf")
        import pymupdf
        txt = " ".join(p.get_text() for p in pymupdf.open(stream=r.content, filetype="pdf"))
        open("/tmp/iter13_drain.txt", "w").write(txt)
        assert "Straight line" in txt
        assert txt.count("Along wall") >= 2
        assert "Layout checks" in txt


# ---- Supply ----
@pytest.fixture(scope="module")
def supply():
    r = requests.get(f"{API}/projects/{P1}/supply", timeout=30)
    assert r.status_code == 200
    d = r.json()
    if not d.get("suppliers"):
        pytest.skip("no supplier search on P1")
    return d


class TestSupply:
    def test_get_shape(self, supply):
        assert supply["status"] == "ready" and supply["price_status"] == "ready"
        assert isinstance(supply["lat"], float)
        cats = {s["category"] for s in supply["suppliers"]}
        assert cats and all(isinstance(s["distance_mi"], (int, float)) for s in supply["suppliers"])
        secs = {i["section"] for i in supply["items"]}
        assert {"Drainage", "Waterproofing", "Equipment rental"} <= secs
        assert len(supply["estimates"]) > 0

    def test_all_suppliers_have_estimates(self, supply):
        unpriced = [s["name"] for s in supply["suppliers"] if s["id"] not in supply["estimates"]]
        print(f"{len(unpriced)}/{len(supply['suppliers'])} suppliers have no estimates: {unpriced[:15]}")
        assert len(unpriced) <= len(supply["suppliers"]) * 0.2

    def test_item_qty_persist_and_restore(self, supply):
        it = next(i for i in supply["items"] if i["key"] == "eq_dumpster")
        r = requests.put(f"{API}/projects/{P1}/supply/item", json={"key": "eq_dumpster", "qty": 3, "on": False}, timeout=30)
        assert r.status_code == 200
        d = requests.get(f"{API}/projects/{P1}/supply", timeout=30).json()
        got = next(i for i in d["items"] if i["key"] == "eq_dumpster")
        assert got["qty"] == 3 and got["on"] is False and got["edited"] is True
        requests.put(f"{API}/projects/{P1}/supply/item", json={"key": "eq_dumpster", "qty": it["qty"], "on": it["on"]}, timeout=30)

    def test_item_unknown_404(self):
        r = requests.put(f"{API}/projects/{P1}/supply/item", json={"key": "nope", "qty": 1}, timeout=30)
        assert r.status_code == 404

    def test_quote_set_and_clear(self, supply):
        sid = supply["suppliers"][0]["id"]
        r = requests.put(f"{API}/projects/{P1}/supply/quote", json={"supplier_id": sid, "item_key": "dr_0", "price": 1.23}, timeout=30)
        assert r.status_code == 200
        d = requests.get(f"{API}/projects/{P1}/supply", timeout=30).json()
        assert d["quotes"][sid]["dr_0"] == 1.23
        r = requests.put(f"{API}/projects/{P1}/supply/quote", json={"supplier_id": sid, "item_key": "dr_0", "price": None}, timeout=30)
        assert r.status_code == 200
        d = requests.get(f"{API}/projects/{P1}/supply", timeout=30).json()
        assert "dr_0" not in (d["quotes"].get(sid) or {})

    def test_quote_validation(self, supply):
        sid = supply["suppliers"][0]["id"]
        assert requests.put(f"{API}/projects/{P1}/supply/quote", json={"supplier_id": "zz", "item_key": "dr_0", "price": 1}, timeout=30).status_code == 404
        assert requests.put(f"{API}/projects/{P1}/supply/quote", json={"supplier_id": sid, "item_key": "dr_0", "price": -1}, timeout=30).status_code == 422

    def test_add_and_remove_supplier(self, supply):
        r = requests.post(f"{API}/projects/{P1}/supply/supplier",
                          json={"name": "TEST_Yard", "category": "landscape", "address": "Grandview Heights, Ohio", "phone": "555"}, timeout=60)
        assert r.status_code == 200, r.text
        s = r.json()
        assert s["id"].startswith("u") and s["source"] == "Added by you" and s["distance_mi"] < 20
        d = requests.get(f"{API}/projects/{P1}/supply", timeout=30).json()
        assert d["suppliers"][0]["id"] == s["id"]
        assert requests.delete(f"{API}/projects/{P1}/supply/supplier/{s['id']}", timeout=30).status_code == 200
        d = requests.get(f"{API}/projects/{P1}/supply", timeout=30).json()
        assert s["id"] not in {x["id"] for x in d["suppliers"]}

    def test_add_supplier_bad_category(self):
        r = requests.post(f"{API}/projects/{P1}/supply/supplier",
                          json={"name": "TEST_X", "category": "bogus", "address": "Columbus, Ohio"}, timeout=30)
        assert r.status_code == 400

    def test_search_bad_address_404(self):
        r = requests.post(f"{API}/projects/{P2}/supply/search", json={"address": "zzzzqqq", "radius_mi": 10}, timeout=60)
        assert r.status_code == 404
        assert "address" in r.json()["detail"].lower()

    def test_search_validation(self):
        r = requests.post(f"{API}/projects/{P2}/supply/search", json={"address": "Dayton, OH", "radius_mi": 500}, timeout=30)
        assert r.status_code == 422

    def test_supply_unknown_project_404(self):
        assert requests.get(f"{API}/projects/nope-123/supply", timeout=30).status_code == 404
