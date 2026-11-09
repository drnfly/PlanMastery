# Iteration 6: Drain tile overlay (POST drain-overlay, GET drain-overlay.png, report drain layout page, render_overlay unit)
import io
import sys
import time
import pytest
import requests
from PIL import Image
from test_iter4_tools_photos import API, TEST_PID, SMITH, pdf_text, poll

sys.path.insert(0, "/app/backend")
from overlay import render_overlay  # noqa: E402


def page(pid, idx):
    return next(p for p in requests.get(f"{API}/projects/{pid}").json()["pages"] if p["index"] == idx)


def check_schema(ov):
    for k in ("is_foundation", "footprint", "drain_tile", "sump", "discharge", "cleanouts", "slope_arrows", "pipe_spec", "length_ft", "notes"):
        assert k in ov, k
    for p in ov["footprint"] + ov["drain_tile"]:
        assert 0 <= p[0] <= 1000 and 0 <= p[1] <= 1000


# ---- fast: Smith S-201 already ready ----
class TestDrainFast:
    def test_smith_s201_ready_schema(self):
        pg = page(SMITH, 2)
        assert pg["drain_status"] == "ready"
        ov = pg["drain_overlay"]
        check_schema(ov)
        assert ov["is_foundation"] is True
        assert len(ov["drain_tile"]) > 2 and len(ov["cleanouts"]) >= 1
        assert {"x", "y"} <= set(ov["sump"]) and len(ov["discharge"]["points"]) >= 2

    def test_png_ready(self):
        r = requests.get(f"{API}/projects/{SMITH}/pages/2/drain-overlay.png", timeout=60)
        assert r.status_code == 200
        assert r.headers["content-type"] == "image/png"
        assert "attachment" in r.headers.get("content-disposition", "") and "drain_tile_" in r.headers["content-disposition"]
        im = Image.open(io.BytesIO(r.content))
        assert im.size[0] > 200

    def test_png_404_no_layout(self):
        if page(SMITH, 1).get("drain_status") == "ready":
            pytest.skip("page 1 has a layout")
        assert requests.get(f"{API}/projects/{SMITH}/pages/1/drain-overlay.png").status_code == 404

    def test_png_404_bad_page(self):
        assert requests.get(f"{API}/projects/{SMITH}/pages/99/drain-overlay.png").status_code == 404
        assert requests.post(f"{API}/projects/{SMITH}/pages/99/drain-overlay").status_code == 404
        assert requests.post(f"{API}/projects/nope/pages/0/drain-overlay").status_code == 404

    def test_full_report_has_drain_page(self):
        r = requests.post(f"{API}/projects/{SMITH}/report", json={"include_images": False}, timeout=180)
        assert r.status_code == 200
        txt, _ = pdf_text(r.content)
        assert "Drain tile layout" in txt and "S-201" in txt

    def test_foundation_crew_has_drain_page(self):
        r = requests.post(f"{API}/projects/{SMITH}/report", json={"crew": "foundation", "include_images": False}, timeout=180)
        assert r.status_code == 200
        assert "Drain tile layout" in pdf_text(r.content)[0]

    def test_icf_crew_no_drain_page(self):
        r = requests.post(f"{API}/projects/{SMITH}/report", json={"crew": "icf", "include_images": False}, timeout=180)
        assert r.status_code == 200
        assert "Drain tile layout" not in pdf_text(r.content)[0]


# ---- unit: render_overlay robustness ----
class TestRenderUnit:
    def _img(self):
        b = io.BytesIO()
        Image.new("RGB", (800, 600), "white").save(b, "PNG")
        return b.getvalue()

    def test_render_empty(self):
        out = render_overlay(self._img(), {"is_foundation": False, "footprint": [], "drain_tile": []})
        assert Image.open(io.BytesIO(out)).size == (800, 600)

    def test_render_zero_length_discharge_segment(self):
        out = render_overlay(self._img(), {"drain_tile": [[100, 100], [900, 100]], "discharge": {"points": [[500, 500], [500, 500], [600, 600]]}})
        assert out[:4] == b"\x89PNG"


# ---- slow: real Gemini draws on TEST project ----
@pytest.mark.slow
class TestDrainSlow:
    def test_draw_foundation_409_then_ready(self):
        r = requests.post(f"{API}/projects/{TEST_PID}/pages/2/drain-overlay")
        assert r.status_code == 200 and r.json()["drain_status"] == "generating"
        assert page(TEST_PID, 2)["drain_status"] == "generating"
        assert requests.post(f"{API}/projects/{TEST_PID}/pages/2/drain-overlay").status_code == 409
        t = time.time()
        pg = poll(lambda: page(TEST_PID, 2), lambda p: p.get("drain_status") != "generating", timeout=240, every=6)
        print("draw took", round(time.time() - t), "s")
        assert pg["drain_status"] == "ready", pg.get("drain_error")
        check_schema(pg["drain_overlay"])
        assert pg["drain_overlay"]["is_foundation"] is True
        r = requests.get(f"{API}/projects/{TEST_PID}/pages/2/drain-overlay.png", timeout=60)
        assert r.status_code == 200 and r.content[:4] == b"\x89PNG"

    def test_draw_cover_not_foundation(self):
        assert requests.post(f"{API}/projects/{TEST_PID}/pages/0/drain-overlay").status_code == 200
        pg = poll(lambda: page(TEST_PID, 0), lambda p: p.get("drain_status") != "generating", timeout=240, every=6)
        assert pg["drain_status"] == "ready", pg.get("drain_error")
        assert pg["drain_overlay"]["is_foundation"] is False

    def test_wp_crew_report_skips_non_foundation(self):
        r = requests.post(f"{API}/projects/{TEST_PID}/report", json={"crew": "waterproofing", "include_images": False}, timeout=180)
        assert r.status_code == 200
        txt = pdf_text(r.content)[0]
        assert "Drain tile layout" in txt
        assert txt.count("Drain tile layout —") == 1
