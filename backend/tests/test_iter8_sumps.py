# Iteration 8: Add sump/pump — PUT drain-overlay `sumps` + main sump fields, validation, reset, PNG + crew PDF rendering
import io
import json
import pytest
import requests
import fitz
from PIL import Image
from test_iter4_tools_photos import API, TEST_PID
from test_iter7_drain_edit import near, page, SUMP

IDX = 2
URL = f"{API}/projects/{TEST_PID}/pages/{IDX}/drain-overlay"
GREEN = (22, 163, 74)


def cur():
    return page(TEST_PID, IDX)["drain_overlay"]


@pytest.fixture(scope="module", autouse=True)
def restore():
    yield
    requests.put(URL, json={"reset": True})


def base_body(ov):
    return {"sump": ov["sump"], "cleanouts": ov["cleanouts"], "discharge": ov["discharge"]}


class TestSumps:
    def test_save_sumps_clamped_rounded(self):
        ov = cur()
        body = {**base_body(ov),
                "sump": {**ov["sump"], "type": "pit_pump", "pump_hp": " 1/2 ", "pit_size": "18x24", "notes": "main"},
                "sumps": [
                    {"x": 300.456, "y": 600.04, "label": "TEST_SP-2", "type": "pump", "pump_hp": "3/4", "pit_size": "24\" x 30\"",
                     "notes": "check valve", "outlet": [1200, -40]},
                    {"x": -10, "y": 2000, "label": "TEST_SP-3", "type": "pit", "outlet": None},
                ]}
        r = requests.put(URL, json=body)
        assert r.status_code == 200, r.text
        d = r.json()
        s0, s1 = d["sumps"]
        assert (s0["x"], s0["y"]) == (300.5, 600.0)
        assert s0["outlet"] == [1000.0, 0.0]
        assert s0["type"] == "pump" and s0["pump_hp"] == "3/4" and s0["notes"] == "check valve"
        assert (s1["x"], s1["y"]) == (0.0, 1000.0) and s1["outlet"] is None and s1["type"] == "pit"
        assert d["sump"]["type"] == "pit_pump" and d["sump"]["pump_hp"] == "1/2" and d["sump"]["pit_size"] == "18x24"
        assert d["edited"] is True
        g = cur()
        assert [s["label"] for s in g["sumps"]] == ["TEST_SP-2", "TEST_SP-3"]
        assert g["sump"]["type"] == "pit_pump"

    def test_body_without_sumps_keeps_them(self):
        ov = cur()
        r = requests.put(URL, json={"cleanouts": ov["cleanouts"]})
        assert r.status_code == 200
        assert [s["label"] for s in r.json()["sumps"]] == ["TEST_SP-2", "TEST_SP-3"]
        assert [s["label"] for s in cur()["sumps"]] == ["TEST_SP-2", "TEST_SP-3"]

    def test_png_shows_extra_sumps_and_discharge(self):
        # place a sump with an outlet in a known spot
        ov = cur()
        body = {"sumps": [{"x": 450, "y": 450, "label": "TEST_SP-2", "type": "pump", "pump_hp": "1/3", "outlet": [450, 650]},
                          {"x": 650, "y": 300, "label": "TEST_SP-3", "type": "pit"}]}
        assert requests.put(URL, json=body).status_code == 200
        r = requests.get(f"{URL}.png", timeout=60)
        assert r.status_code == 200 and r.headers["content-type"] == "image/png"
        img = Image.open(io.BytesIO(r.content)).convert("RGB")
        w, h = img.size
        # pump has a white center dot; check red at an offset from center
        r_px = max(int(max(w, h) / 300), 3) * 4  # square half-size; white dot is 0.45*r
        off = 0.75 * r_px * 1000 / w
        assert near(img, 450 + off, 450, SUMP) or near(img, 450 - off, 450, SUMP), "pump sump square missing"
        assert img.getpixel((int(450 * w / 1000), int(450 * h / 1000)))[:3] >= (230, 230, 230), "white dot for pump missing"
        assert near(img, 650, 300, SUMP), "pit sump missing"
        # discharge green somewhere along line 450,500..620
        hits = sum(near(img, 450, y, GREEN, tol=60) for y in range(500, 640, 4))
        assert hits >= 3, f"green discharge line not found ({hits})"
        self.__class__.png_ok = True

    def test_crew_pdf_shows_extra_sump(self):
        r = requests.post(f"{API}/projects/{TEST_PID}/report", json={"crew": "foundation", "include_images": False}, timeout=180)
        assert r.status_code == 200
        doc = fitz.open(stream=r.content, filetype="pdf")
        found = False
        for pg in doc:
            for im in pg.get_images(full=True):
                pix = fitz.Pixmap(doc, im[0])
                if pix.width < 800:
                    continue
                img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
                if near(img, 650, 300, SUMP):
                    found = True
        assert found

    @pytest.mark.parametrize("body", [
        {"sumps": [{"x": 1, "y": 1, "type": "bogus"}]},
        {"sumps": [{"x": "abc", "y": 1}]},
        {"sumps": [{"y": 1}]},
        {"sumps": [{"x": 1, "y": 1, "pump_hp": "x" * 21}]},
        {"sumps": [{"x": 1, "y": 1, "pit_size": "x" * 41}]},
        {"sumps": [{"x": 1, "y": 1, "notes": "x" * 301}]},
        {"sumps": [{"x": 1, "y": 1, "outlet": [1]}]},
        {"sump": {"x": 1, "y": 1, "type": "nope"}},
    ])
    def test_invalid_422(self, body):
        before = cur()
        r = requests.put(URL, json=body)
        assert r.status_code in (400, 422), (body, r.status_code, r.text)
        assert cur() == before

    @pytest.mark.parametrize("raw", [
        '{"sumps": [{"x": NaN, "y": 1}]}',
        '{"sumps": [{"x": 1, "y": Infinity}]}',
        '{"sumps": [{"x": 1, "y": 1, "outlet": [NaN, 1]}]}',
        '{"sump": {"x": Infinity, "y": 1}}',
    ])
    def test_non_finite(self, raw):
        before = cur()
        r = requests.put(URL, data=raw, headers={"Content-Type": "application/json"})
        assert r.status_code in (400, 422), (raw, r.status_code, r.text)
        assert cur() == before

    def test_empty_sumps_clears(self):
        r = requests.put(URL, json={"sumps": [{"x": 10, "y": 10, "label": "TEST_tmp"}]})
        assert r.status_code == 200 and len(r.json()["sumps"]) == 1
        r = requests.put(URL, json={"sumps": []})
        assert r.status_code == 200 and r.json()["sumps"] == []

    def test_reset_removes_sumps(self):
        requests.put(URL, json={"sumps": [{"x": 650, "y": 300, "label": "TEST_SP-3", "type": "pit"}]})
        r = requests.put(URL, json={"reset": True})
        assert r.status_code == 200
        d = r.json()
        assert d["sumps"] == [] and d["edited"] is False
        g = cur()
        assert g["sumps"] == [] and g["sump"] == g["ai_original"]["sump"]
        img = Image.open(io.BytesIO(requests.get(f"{URL}.png", timeout=60).content)).convert("RGB")
        assert not near(img, 650, 300, SUMP)
