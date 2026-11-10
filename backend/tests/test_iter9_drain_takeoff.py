# Iteration 9: Drainage material takeoff — GET/PUT /api/projects/{id}/drain-takeoff, math, validation, sump integration, PDF
import io
import math
import pytest
import requests
import fitz
from test_iter4_tools_photos import API, TEST_PID

IDX = 2
URL = f"{API}/projects/{TEST_PID}/drain-takeoff"
OV_URL = f"{API}/projects/{TEST_PID}/pages/{IDX}/drain-overlay"
POST_OAK = "c5675b5d-4a36-4502-a217-48d6b5e176d2"  # read-only: page 0 non-foundation, page 3 foundation
SMITH = "31e1ec93-0b9d-455d-8286-13ab4945c57f"


def line(d, item):
    return next((ln for ln in d["lines"] if ln["item"] == item), None)


@pytest.fixture(scope="module", autouse=True)
def restore():
    requests.put(URL, json={"page_index": IDX, "params": {}})
    yield
    requests.put(OV_URL, json={"reset": True})
    requests.put(URL, json={"page_index": IDX, "params": {}})


class TestGet:
    def test_shape_and_defaults_math(self):
        r = requests.get(f"{URL}?page={IDX}")
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ("params", "derived", "lines", "counts", "page_index", "sheet", "edited"):
            assert k in d
        assert d["page_index"] == IDX and d["edited"] is False
        p = d["params"]
        assert p["tile_lf"] == 140 and p["waste_pct"] == 10 and p["discharge_lf"] >= 10
        perf = line(d, "Perforated drain tile")
        assert perf["qty"] == 154.0 and perf["unit"] == "LF" and perf["notes"].startswith("16 sticks")
        stone = line(d, "Washed drain stone")
        assert stone["qty"] == 5.7 and "8.0 tons" in stone["notes"]
        assert line(d, "Non-woven filter fabric")["qty"] == 644
        assert line(d, "Couplings")["qty"] == 15
        assert d["counts"]["corners"] == 4 and line(d, "Corner sweeps / 90° elbows")["qty"] == 4
        assert d["counts"]["cleanouts"] == 3 == line(d, "Cleanout wye / tee + cap")["qty"]
        assert line(d, "Sump / ejector pumps") is None and line(d, "Check valves + unions") is None
        for ln in d["lines"]:
            assert set(ln) == {"group", "item", "spec", "qty", "unit", "notes"} and ln["qty"]

    def test_non_foundation_page_404(self):
        assert requests.get(f"{URL}?page=0").status_code == 404

    def test_default_skips_non_foundation_first_page(self):
        # project whose first ready page is non-foundation must fall through to the foundation sheet
        r = requests.get(f"{API}/projects/{POST_OAK}/drain-takeoff")
        assert r.status_code == 200, r.text
        assert r.json()["page_index"] != 0

    def test_smith_read(self):
        assert requests.get(f"{API}/projects/{SMITH}/drain-takeoff").status_code in (200, 404)

    def test_unknown_project_404(self):
        assert requests.get(f"{API}/projects/nope-xyz/drain-takeoff").status_code == 404


class TestPut:
    def test_override_and_reset(self):
        r = requests.put(URL, json={"page_index": IDX, "params": {"waste_pct": 20, "bogus": 5}})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["edited"] is True and d["params"]["waste_pct"] == 20 and "bogus" not in d["params"]
        assert line(d, "Perforated drain tile")["qty"] == 168.0
        assert d["derived"]["waste_pct"] == 10
        g = requests.get(URL).json()
        assert g["edited"] is True and line(g, "Perforated drain tile")["qty"] == 168.0
        r = requests.put(URL, json={"page_index": IDX, "params": {}})
        assert r.json()["edited"] is False and line(r.json(), "Perforated drain tile")["qty"] == 154.0
        assert requests.get(URL).json()["edited"] is False

    @pytest.mark.parametrize("val", [-1, 1e7])
    def test_bad_values_400(self, val):
        r = requests.put(URL, json={"page_index": IDX, "params": {"waste_pct": val}})
        assert r.status_code == 400
        assert requests.get(URL).json()["params"]["waste_pct"] == 10

    def test_nan_rejected(self):
        r = requests.put(URL, data='{"page_index": 2, "params": {"waste_pct": NaN}}', headers={"Content-Type": "application/json"})
        assert r.status_code in (400, 422)

    def test_non_foundation_sheet_400(self):
        assert requests.put(URL, json={"page_index": 0, "params": {}}).status_code == 400
        assert requests.put(URL, json={"page_index": 99, "params": {}}).status_code == 400


class TestSumpIntegration:
    def test_pump_sump_adds_lines(self):
        ov = requests.get(f"{API}/projects/{TEST_PID}/pages/{IDX}").json()["drain_overlay"] if requests.get(f"{API}/projects/{TEST_PID}/pages/{IDX}").ok else None
        body = {"sumps": [
            {"x": 400, "y": 500, "label": "TEST_SP-2", "type": "pump", "pump_hp": "1/2", "outlet": [400, 600]},
            {"x": 300, "y": 500, "label": "TEST_SP-3", "type": "ejector", "pump_hp": "1"},
            {"x": 200, "y": 500, "label": "TEST_OUT", "type": "outlet"},
        ]}
        r = requests.put(OV_URL, json=body)
        assert r.status_code == 200, r.text
        d = requests.get(URL).json()
        assert d["counts"]["pumps"] == 2
        assert line(d, "Sump / ejector pumps")["qty"] == 2
        assert line(d, "Check valves + unions")["qty"] == 2
        # basins: main sump (if typed non-outlet) + pump + ejector, excluding 'outlet'
        assert "TEST_OUT" not in line(d, "Sump basins")["notes"]
        assert d["params"]["pump_discharge_lf"] > 0
        pd = line(d, "Pump discharge pipe")
        assert pd and math.isclose(pd["qty"], round(d["params"]["pump_discharge_lf"] * 1.1, 1), abs_tol=0.11)
        requests.put(OV_URL, json={"reset": True})
        d = requests.get(URL).json()
        assert d["counts"]["pumps"] == 0 and line(d, "Pump discharge pipe") is None


class TestPdf:
    @pytest.mark.parametrize("crew", ["full", "foundation", "waterproofing"])
    def test_pdf_has_takeoff(self, crew):
        r = requests.post(f"{API}/projects/{TEST_PID}/report", json={"crew": crew, "include_images": False}, timeout=120)
        assert r.status_code == 200, r.text[:300]
        doc = fitz.open(stream=io.BytesIO(r.content).read(), filetype="pdf")
        assert "Drainage material takeoff" in "".join(p.get_text() for p in doc)
