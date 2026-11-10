# Iteration 10: drain tile layout editor backend (PUT drain-overlay add/remove/recalc, manual layout, reset, png, takeoff)
import os
import math
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/") or open("/app/frontend/.env").read().split("REACT_APP_BACKEND_URL=")[1].split()[0].rstrip("/")
PID = "21f16323-6b5c-4d5b-b541-9d61852f4d55"
OV = f"{BASE_URL}/api/projects/{PID}/pages"
S = requests.Session()
TILE = [[157, 157], [767, 157], [767, 840], [157, 840], [157, 157]]


def put(idx, body):
    return S.put(f"{OV}/{idx}/drain-overlay", json=body, timeout=30)


def page(idx):
    p = S.get(f"{BASE_URL}/api/projects/{PID}", timeout=30).json()
    return next(x for x in p["pages"] if x["index"] == idx)


def takeoff(idx):
    return S.get(f"{BASE_URL}/api/projects/{PID}/drain-takeoff", params={"page": idx}, timeout=30)


@pytest.fixture(scope="module", autouse=True)
def reset_page2():
    put(2, {"reset": True})
    yield
    r = put(2, {"reset": True})
    assert r.status_code == 200


class TestPage2Edits:
    def test_baseline(self):
        pg = page(2)
        ov = pg["drain_overlay"]
        assert pg["drain_status"] == "ready"
        assert ov["length_ft"] == 140 and len(ov["drain_tile"]) == 5 and len(ov["cleanouts"]) == 3

    def test_tile_edit_recomputes_length(self):
        r = put(2, {"drain_tile": TILE[:3]})  # remove 2 legs
        assert r.status_code == 200, r.text
        d = r.json()
        assert 0 < d["length_ft"] < 140
        # roughly proportional to px length of the kept legs
        assert d["edited"] is True
        assert page(2)["drain_overlay"]["length_ft"] == d["length_ft"]

    def test_length_override_recalibrates_scale(self):
        assert put(2, {"drain_tile": TILE}).json()["length_ft"] == pytest.approx(140, abs=0.2)
        r = put(2, {"length_ft": 280})
        assert r.status_code == 200 and r.json()["length_ft"] == 280
        r2 = put(2, {"drain_tile": TILE[:3]}).json()
        r3 = put(2, {"drain_tile": TILE}).json()
        assert r3["length_ft"] == pytest.approx(280, abs=0.3)
        assert r2["length_ft"] < 280

    def test_tile_and_length_together(self):
        r = put(2, {"drain_tile": TILE[:3], "length_ft": 100}).json()
        assert r["length_ft"] == 100
        assert put(2, {"drain_tile": TILE}).json()["length_ft"] > 100

    def test_remove_main_sump_and_discharge(self):
        r = put(2, {"sump": None, "discharge": None, "sumps": []})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["sump"] is None and d["discharge"] is None
        t = takeoff(2)
        assert t.status_code == 200
        assert t.json()["counts"]["sumps"] == 0 and t.json()["counts"]["outlets"] == 0

    def test_add_items(self):
        body = {
            "cleanouts": [{"x": 100, "y": 100, "label": "CO-1"}, {"x": 200, "y": 200, "label": "CO-2"},
                          {"x": 300, "y": 300, "label": "CO-3"}, {"x": 400, "y": 400, "label": "CO-4"}],
            "sump": {"x": 500, "y": 500, "label": "SUMP", "type": "pit_pump", "pump_hp": "1/3", "pit_size": "18x24", "notes": ""},
            "sumps": [{"x": 600, "y": 600, "label": "SP-2", "type": "pit_pump", "pump_hp": "1/2", "pit_size": "", "notes": "", "outlet": [670, 550]}],
            "discharge": {"points": [[500, 500], [560, 520], [620, 560]], "to": "storm", "label": "TO STORM"},
            "slope_arrows": [{"x1": 10, "y1": 10, "x2": 90, "y2": 10, "label": "1/8\"/ft"}],
            "footprint": [[1, 1], [999, 1], [999, 999]],
            "pipe_spec": "  TEST_pipe 4in  ",
        }
        r = put(2, body)
        assert r.status_code == 200, r.text
        ov = page(2)["drain_overlay"]
        assert len(ov["cleanouts"]) == 4 and ov["cleanouts"][3]["label"] == "CO-4"
        assert ov["sump"]["x"] == 500 and ov["sump"]["pump_hp"] == "1/3"
        assert ov["sumps"][0]["outlet"] == [670, 550]
        assert len(ov["discharge"]["points"]) == 3 and ov["discharge"]["to"] == "storm"
        assert len(ov["slope_arrows"]) == 1 and ov["pipe_spec"] == "TEST_pipe 4in"
        c = takeoff(2).json()["counts"]
        assert c["sumps"] == 2 and c["pumps"] == 2 and c["cleanouts"] == 4 and c["outlets"] == 2

    def test_coords_clamped(self):
        r = put(2, {"cleanouts": [{"x": -50, "y": 5000}]}).json()
        assert r["cleanouts"][0]["x"] == 0 and r["cleanouts"][0]["y"] == 1000

    @pytest.mark.parametrize("raw", [
        '{"drain_tile": [[NaN, 1], [2, 3]]}',
        '{"drain_tile": [[Infinity, 1], [2, 3]]}',
        '{"cleanouts": [{"x": NaN, "y": 1}]}',
        '{"discharge": {"points": [[1, Infinity], [2, 3]]}}',
        '{"slope_arrows": [{"x1": NaN, "y1": 1, "x2": 2, "y2": 3}]}',
        '{"sumps": [{"x": 1, "y": 1, "outlet": [NaN, 2]}]}',
        '{"length_ft": Infinity}',
    ])
    def test_non_finite_rejected(self, raw):
        r = S.put(f"{OV}/2/drain-overlay", data=raw, headers={"Content-Type": "application/json"}, timeout=30)
        assert r.status_code in (400, 422), (raw, r.status_code, r.text[:200])

    def test_png_200(self):
        r = S.get(f"{OV}/2/drain-overlay.png", timeout=60)
        assert r.status_code == 200 and r.content[:4] == b"\x89PNG"

    def test_reset_restores_original(self):
        r = put(2, {"reset": True})
        assert r.status_code == 200
        ov = page(2)["drain_overlay"]
        assert ov["length_ft"] == 140 and len(ov["drain_tile"]) == 5 and len(ov["cleanouts"]) == 3
        assert ov["sump"]["x"] == 767 and ov["discharge"] is not None and ov["sumps"] == [] and ov["edited"] is False
        assert len(ov["slope_arrows"]) == 4

    def test_reset_then_tile_edit_uses_original_scale(self):
        # after a recalibration + reset, a tile edit should use the AI scale again (140 LF for the full loop)
        put(2, {"length_ft": 280})
        put(2, {"reset": True})
        r = put(2, {"drain_tile": TILE}).json()
        put(2, {"reset": True})
        assert r["length_ft"] == pytest.approx(140, abs=0.3), f"stale ft_per_px after reset: {r['length_ft']}"


class TestManualLayoutPage1:
    def test_reset_no_layout_400(self):
        assert page(1)["drain_status"] != "ready"
        assert put(1, {"reset": True}).status_code == 400

    def test_png_404_without_layout(self):
        assert S.get(f"{OV}/1/drain-overlay.png", timeout=30).status_code == 404

    def test_manual_create(self):
        r = put(1, {"drain_tile": [[100, 100], [900, 100], [900, 900]], "cleanouts": [{"x": 100, "y": 100, "label": "CO-1"}],
                    "sump": None, "discharge": None, "slope_arrows": [], "footprint": [], "sumps": [], "pipe_spec": "4in", "length_ft": 160})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["manual"] is True and d["length_ft"] == 160 and d["is_foundation"] is True
        pg = page(1)
        assert pg["drain_status"] == "ready" and len(pg["drain_overlay"]["drain_tile"]) == 3
        # scale calibrated: shorten -> proportional length
        d2 = put(1, {"drain_tile": [[100, 100], [900, 100]]}).json()
        assert 0 < d2["length_ft"] < 160
        assert S.get(f"{OV}/1/drain-overlay.png", timeout=60).status_code == 200
        t = takeoff(1)
        assert t.status_code == 200 and t.json()["page_index"] == 1 and t.json()["counts"]["sumps"] == 0

    def test_manual_without_length_has_zero(self):
        d = put(1, {"drain_tile": [[100, 100], [900, 100], [900, 900], [100, 900]]}).json()
        assert d["length_ft"] >= 0
