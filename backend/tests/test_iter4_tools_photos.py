# Iteration 4: ICF estimator, Waterproofing checklist, Crew packets/reports, Job-site photos
import io
import os
import sys
import time
import pytest
import requests
import fitz

sys.path.insert(0, "/app/backend")
from icf_calc import compute  # noqa: E402

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    for line in open("/app/frontend/.env"):
        if line.startswith("REACT_APP_BACKEND_URL="):
            BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
API = f"{BASE_URL}/api"
SMITH = "31e1ec93-0b9d-455d-8286-13ab4945c57f"
TEST_PID = os.environ.get("TEST_PID", "21f16323-6b5c-4d5b-b541-9d61852f4d55")
PHOTO = "/app/tests/site_photo.jpg"


def pdf_text(b):
    doc = fitz.open(stream=b, filetype="pdf")
    return "\n".join(pg.get_text() for pg in doc), doc.page_count


def poll(fn, ok, timeout=300, every=6):
    end = time.time() + timeout
    last = None
    while time.time() < end:
        last = fn()
        if ok(last):
            return last
        time.sleep(every)
    return last


EX_WALL = {"id": "W1", "length_ft": 140, "height_ft": 8, "core_in": 8, "corners_90": 4, "corners_45": 0, "openings_sqft": 0,
           "vertical_bar": "#5", "vertical_spacing_in": 16, "horizontal_bar": "#4", "horizontal_bars_per_row": 2,
           "horizontal_every_courses": 2}
EX_FOOT = {"id": "F1", "length_ft": 140, "width_in": 24, "depth_in": 12, "bars": "#4", "bar_count": 3}


# ---- ICF calc unit tests ----
class TestIcfCalcUnit:
    def test_example(self):
        c = compute([EX_WALL], [EX_FOOT], {})
        t = c["totals"]
        assert t["straight_blocks"] == 196 and t["corner_blocks"] == 24
        assert t["wall_cy"] == 29.87 and t["footing_cy"] == 11.2
        assert t["total_cy"] == round(29.87 + 11.2, 2)
        sizes = {r["size"]: r for r in c["rebar"]}
        assert set(sizes) == {"#4", "#5"}
        assert all(r["sticks"] == -(-r["lf"] // 20) for r in c["rebar"])

    def test_zero_height_and_strings(self):
        c = compute([{**EX_WALL, "height_ft": 0}], [], {"waste_pct": "10", "bogus": 1})
        assert c["totals"]["straight_blocks"] == 0 and c["totals"]["wall_cy"] == 0
        assert c["params"]["waste_pct"] == 10.0 and "bogus" not in c["params"]
        c2 = compute([{**EX_WALL, "length_ft": "abc", "vertical_bar": "5"}], [], {"waste_pct": ""})
        assert c2["params"]["waste_pct"] == 5
        assert c2["totals"]["net_sqft"] == 0

    def test_bar_normalization(self):
        c = compute([{**EX_WALL, "vertical_bar": "5", "horizontal_bar": "# 4"}], [], {})
        assert {r["size"] for r in c["rebar"]} == {"#4", "#5"}


# ---- Tools API basics ----
class TestToolsApi:
    def test_unknown_tool_404(self):
        r = requests.post(f"{API}/projects/{SMITH}/tools/bogus")
        assert r.status_code == 404

    def test_unknown_project_404(self):
        r = requests.post(f"{API}/projects/nope/tools/icf")
        assert r.status_code == 404

    def test_wp_patch_out_of_range(self):
        assert requests.patch(f"{API}/projects/{SMITH}/tools/waterproofing/items/999", json={"verified": True}).status_code == 404
        assert requests.patch(f"{API}/projects/{SMITH}/tools/waterproofing/items/-1", json={"verified": True}).status_code == 404

    def test_wp_patch_persists_and_restore(self):
        p = requests.get(f"{API}/projects/{SMITH}").json()
        items = p["tools"]["waterproofing"]["data"]["items"]
        i = len(items) - 1
        orig = bool(items[i].get("verified"))
        assert requests.patch(f"{API}/projects/{SMITH}/tools/waterproofing/items/{i}", json={"verified": not orig}).status_code == 200
        p2 = requests.get(f"{API}/projects/{SMITH}").json()
        assert p2["tools"]["waterproofing"]["data"]["items"][i]["verified"] is (not orig)
        requests.patch(f"{API}/projects/{SMITH}/tools/waterproofing/items/{i}", json={"verified": orig})

    def test_wp_schema(self):
        d = requests.get(f"{API}/projects/{SMITH}").json()["tools"]["waterproofing"]["data"]
        assert isinstance(d["summary"], str) and d["items"]
        for it in d["items"]:
            assert it["status"] in ("specified", "missing", "unclear")
            assert {"category", "item", "sheets", "spec", "recommendation", "severity", "verified"} <= set(it)


# ---- Reports ----
class TestReports:
    def test_unknown_crew(self):
        r = requests.post(f"{API}/projects/{SMITH}/report", json={"crew": "plumbing"})
        assert r.status_code == 400

    def test_crew_not_prepared(self):
        p = requests.get(f"{API}/projects/{SMITH}").json()
        if (p.get("tools", {}).get("crew_waterproofing") or {}).get("status") == "ready":
            pytest.skip("already prepared")
        r = requests.post(f"{API}/projects/{SMITH}/report", json={"crew": "waterproofing"})
        assert r.status_code == 400 and "Prepare the crew packet first" in r.json()["detail"]

    def test_icf_crew_pdf(self):
        r = requests.post(f"{API}/projects/{SMITH}/report", json={"crew": "icf", "include_images": False}, timeout=120)
        assert r.status_code == 200 and r.content[:4] == b"%PDF"
        txt, _ = pdf_text(r.content)
        assert "ICF WALL CREW PACKET" in txt and "Crew briefing" in txt
        assert "ICF material estimate" in txt
        assert "Waterproofing checklist" not in txt
        assert "icf_crew_packet.pdf" in r.headers.get("content-disposition", "")

    def test_full_pdf_sections(self):
        r = requests.post(f"{API}/projects/{SMITH}/report", json={"include_images": False}, timeout=120)
        assert r.status_code == 200
        txt, _ = pdf_text(r.content)
        assert "ICF material estimate" in txt and "Waterproofing checklist" in txt


# ---- Photos validation ----
class TestPhotoValidation:
    def test_bad_ext(self):
        r = requests.post(f"{API}/projects/{TEST_PID}/photos", files={"file": ("x.gif", b"GIF89a", "image/gif")})
        assert r.status_code == 400

    def test_bad_image(self):
        r = requests.post(f"{API}/projects/{TEST_PID}/photos", files={"file": ("x.jpg", b"notanimage", "image/jpeg")})
        assert r.status_code == 400

    def test_unknown_photo(self):
        assert requests.get(f"{API}/photos/nope/image").status_code == 404
        assert requests.post(f"{API}/photos/nope/ask", json={"question": "x"}).status_code == 404
