# Iteration 7: Drag-to-adjust drain layout (PUT drain-overlay edit/reset, validation, PNG + crew PDF render moved positions)
import io
import pytest
import requests
import fitz
from PIL import Image
from test_iter4_tools_photos import API, TEST_PID, SMITH

IDX = 2
URL = f"{API}/projects/{TEST_PID}/pages/{IDX}/drain-overlay"
SUMP = (220, 38, 38)
CLEANOUT = (234, 88, 12)


def page(pid, idx):
    return next(p for p in requests.get(f"{API}/projects/{pid}").json()["pages"] if p["index"] == idx)


def near(img, x, y, color, tol=45):
    w, h = img.size
    px, py = int(x * w / 1000), int(y * h / 1000)
    hits = 0
    for dx in (-2, 0, 2):
        for dy in (-2, 0, 2):
            c = img.getpixel((min(max(px + dx, 0), w - 1), min(max(py + dy, 0), h - 1)))[:3]
            hits += all(abs(a - b) <= tol for a, b in zip(c, color))
    return hits >= 5


@pytest.fixture(scope="module", autouse=True)
def restore():
    orig = page(TEST_PID, IDX)["drain_overlay"]
    yield orig
    requests.put(URL, json={"reset": True})


class TestDrainEdit:
    def test_edit_saves_clamped_and_flags(self, restore):
        ai = page(TEST_PID, IDX)["drain_overlay"]
        ai_pos = ai.get("ai_original") or {k: ai[k] for k in ("sump", "cleanouts", "discharge")}
        body = {"sump": {"x": 450, "y": 500, "label": "SUMP / OUTLET"},
                "cleanouts": [{"x": 300, "y": 300, "label": "CO-1"}, {"x": -50, "y": 1500, "label": "CO-2"}],
                "discharge": {**ai["discharge"], "points": [[450, 500], [1200, -10]]}}
        r = requests.put(URL, json=body)
        assert r.status_code == 200, r.text
        ov = r.json()
        assert ov["edited"] is True and ov.get("edited_at")
        assert ov["sump"]["x"] == 450 and ov["sump"]["y"] == 500
        assert ov["cleanouts"][1]["x"] == 0 and ov["cleanouts"][1]["y"] == 1000
        assert ov["discharge"]["points"] == [[450, 500], [1000, 0]]
        assert ov["ai_original"]["sump"] == ai_pos["sump"]
        # persisted
        g = page(TEST_PID, IDX)["drain_overlay"]
        assert g["edited"] is True and g["sump"]["x"] == 450 and len(g["cleanouts"]) == 2
        assert "_id" not in g

    def test_second_edit_keeps_first_ai_original(self):
        first = page(TEST_PID, IDX)["drain_overlay"]["ai_original"]
        r = requests.put(URL, json={"sump": {"x": 470, "y": 520, "label": "S"}, "cleanouts": [{"x": 300, "y": 300, "label": "CO-1"}],
                                    "discharge": {"points": [[470, 520], [900, 900]]}})
        assert r.status_code == 200
        assert r.json()["ai_original"] == first
        assert r.json()["ai_original"]["sump"]["x"] != 470

    def test_png_renders_moved_positions(self):
        r = requests.get(f"{URL}.png", timeout=60)
        assert r.status_code == 200 and r.headers["content-type"] == "image/png"
        img = Image.open(io.BytesIO(r.content)).convert("RGB")
        assert near(img, 470, 520, SUMP), "sump not drawn at moved position"
        assert near(img, 300, 300, CLEANOUT), "cleanout not drawn at moved position"

    def test_foundation_pdf_renders_moved_positions(self):
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
                if near(img, 470, 520, SUMP) and near(img, 300, 300, CLEANOUT):
                    found = True
        assert found, "no PDF image shows moved sump/cleanout"

    @pytest.mark.parametrize("body", [
        {"sump": {"x": "abc", "y": 1}},
        {"sump": {"y": 1}},
        {"cleanouts": [{"x": 1}]},
        {"discharge": {"points": [[1]]}},
        {"discharge": {"points": [5, 6]}},
        {"cleanouts": [{"x": None, "y": 3}]},
    ])
    def test_bad_coordinates_400(self, body):
        before = page(TEST_PID, IDX)["drain_overlay"]
        r = requests.put(URL, json=body)
        assert r.status_code in (400, 422), (body, r.status_code, r.text)
        assert page(TEST_PID, IDX)["drain_overlay"] == before

    def test_not_ready_sheet_400(self):
        assert page(SMITH, 0).get("drain_status") != "ready"
        r = requests.put(f"{API}/projects/{SMITH}/pages/0/drain-overlay", json={"reset": True})
        assert r.status_code == 400
        assert "draw" in r.json()["detail"].lower()

    def test_missing_page_404(self):
        assert requests.put(f"{API}/projects/{TEST_PID}/pages/99/drain-overlay", json={"reset": True}).status_code == 404
        assert requests.put(f"{API}/projects/nope/pages/0/drain-overlay", json={"reset": True}).status_code == 404

    def test_reset_restores_ai(self, restore):
        ai = page(TEST_PID, IDX)["drain_overlay"]["ai_original"]
        r = requests.put(URL, json={"reset": True})
        assert r.status_code == 200
        ov = r.json()
        assert ov["edited"] is False
        assert ov["sump"] == ai["sump"] and ov["cleanouts"] == ai["cleanouts"] and ov["discharge"] == ai["discharge"]
        g = page(TEST_PID, IDX)["drain_overlay"]
        assert g["edited"] is False and g["sump"] == ai["sump"]
        img = Image.open(io.BytesIO(requests.get(f"{URL}.png", timeout=60).content)).convert("RGB")
        assert near(img, ai["sump"]["x"], ai["sump"]["y"], SUMP)
        assert not near(img, 470, 520, SUMP)
