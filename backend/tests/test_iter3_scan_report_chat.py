# Iteration 3: scan-set, brand settings/logo, PDF report, set-scope chat
import io
import os
import json
import time
import pytest
import requests
import fitz
from PIL import Image


def _base():
    url = os.environ.get("REACT_APP_BACKEND_URL")
    if not url:
        for line in open("/app/frontend/.env"):
            if line.startswith("REACT_APP_BACKEND_URL="):
                url = line.split("=", 1)[1].strip()
    return url.rstrip("/")


BASE_URL = _base()
API = f"{BASE_URL}/api"
SMITH = "31e1ec93-0b9d-455d-8286-13ab4945c57f"
TEST_PID = os.environ.get("TEST_SCAN_PID")  # TEST_ project uploaded for scan-from-scratch


def png_bytes(color=(245, 158, 11), size=(200, 80)):
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, "PNG")
    return buf.getvalue()


@pytest.fixture(scope="module", autouse=True)
def brand_backup():
    orig = requests.get(f"{API}/settings/brand").json()
    yield orig
    restore = {k: orig.get(k, "") for k in ["company_name", "prepared_by", "phone", "email", "client"]}
    requests.put(f"{API}/settings/brand", json=restore)
    if not orig.get("logo_path"):
        requests.delete(f"{API}/settings/brand/logo")


# --- Branding settings ---
class TestBrand:
    def test_put_get_brand(self):
        body = {"company_name": "TEST_Co", "prepared_by": "TEST_PM", "phone": "555-0100", "email": "t@x.io", "client": "TEST_GC"}
        r = requests.put(f"{API}/settings/brand", json=body)
        assert r.status_code == 200
        for k, v in body.items():
            assert r.json()[k] == v
        g = requests.get(f"{API}/settings/brand").json()
        for k, v in body.items():
            assert g[k] == v
        assert "_id" not in g

    def test_logo_rejects_other_types(self):
        r = requests.post(f"{API}/settings/brand/logo", files={"file": ("x.gif", b"GIF89a", "image/gif")})
        assert r.status_code == 400
        r = requests.post(f"{API}/settings/brand/logo", files={"file": ("x.pdf", b"%PDF", "application/pdf")})
        assert r.status_code == 400

    def test_logo_rejects_over_5mb(self):
        r = requests.post(f"{API}/settings/brand/logo", files={"file": ("big.png", b"0" * (5 * 1024 * 1024 + 10), "image/png")})
        assert r.status_code == 400

    def test_logo_upload_get_delete(self):
        data = png_bytes()
        r = requests.post(f"{API}/settings/brand/logo", files={"file": ("logo.png", data, "image/png")})
        assert r.status_code == 200 and r.json()["logo_path"].endswith(".png")
        g = requests.get(f"{API}/settings/brand/logo")
        assert g.status_code == 200 and g.headers["content-type"].startswith("image/png")
        assert g.content == data
        assert requests.delete(f"{API}/settings/brand/logo").status_code == 200
        assert requests.get(f"{API}/settings/brand/logo").status_code == 404


# --- PDF report ---
class TestReport:
    def _check_pdf(self, r):
        assert r.status_code == 200, r.text[:300]
        assert r.headers["content-type"] == "application/pdf"
        assert "attachment" in r.headers.get("content-disposition", "")
        doc = fitz.open(stream=r.content, filetype="pdf")
        return doc, "\n".join(p.get_text() for p in doc)

    def test_report_full(self):
        r = requests.post(f"{API}/projects/{SMITH}/report", json={
            "brand": {"company_name": "TEST_Co", "prepared_by": "TEST_PM", "client": "TEST_GC"},
            "include_images": True, "include_qa": True})
        doc, text = self._check_pdf(r)
        assert "TEST_Co" in text and "TEST_GC" in text
        for t in ["Cover Sheet", "First Floor Plan", "Foundation Plan", "S-201"]:
            assert t in text, t
        assert "Expert notes for crews" in text
        assert "DIMENSION TAKEOFF REPORT" in text
        print("pages", doc.page_count, "images", sum(len(p.get_images()) for p in doc), "QA", "Expert Q&A" in text)
        assert sum(len(p.get_images()) for p in doc) >= 3

    def test_report_no_images_no_qa_subset(self):
        r = requests.post(f"{API}/projects/{SMITH}/report", json={
            "brand": {"company_name": "TEST_Co"}, "include_images": False, "include_qa": False, "pages": [2]})
        doc, text = self._check_pdf(r)
        assert "Foundation Plan" in text and "Cover Sheet" not in text.split("Sheets in this report")[1]
        assert "Expert Q&A" not in text
        assert sum(len(p.get_images()) for p in doc) == 0

    def test_report_with_logo(self):
        requests.post(f"{API}/settings/brand/logo", files={"file": ("logo.png", png_bytes((10, 120, 200)), "image/png")})
        r = requests.post(f"{API}/projects/{SMITH}/report", json={"brand": {"company_name": "TEST_Co"}, "include_images": False, "include_qa": False})
        doc, text = self._check_pdf(r)
        assert "TEST_Co" in text
        assert all(len(p.get_images()) >= 1 for p in doc), "logo should be on every page header"
        requests.delete(f"{API}/settings/brand/logo")

    def test_report_jpg_logo(self):
        buf = io.BytesIO(); Image.new("RGB", (120, 60), (0, 200, 0)).save(buf, "JPEG")
        assert requests.post(f"{API}/settings/brand/logo", files={"file": ("logo.jpg", buf.getvalue(), "image/jpeg")}).status_code == 200
        r = requests.post(f"{API}/projects/{SMITH}/report", json={"brand": {"company_name": "TEST_Co"}, "include_images": False, "include_qa": False})
        self._check_pdf(r)
        requests.delete(f"{API}/settings/brand/logo")

    def test_report_corrupt_logo_does_not_500(self):
        # logo with png extension but not a real image
        requests.post(f"{API}/settings/brand/logo", files={"file": ("logo.png", b"not an image", "image/png")})
        r = requests.post(f"{API}/projects/{SMITH}/report", json={"brand": {"company_name": "TEST_Co"}, "include_images": False, "include_qa": False})
        requests.delete(f"{API}/settings/brand/logo")
        assert r.status_code != 500, "Corrupt logo accepted at upload and breaks report with 500"

    def test_report_400_when_nothing_scanned(self):
        r = requests.post(f"{API}/projects/{SMITH}/report", json={"pages": [99]})
        assert r.status_code == 400
        assert "scan" in r.json()["detail"].lower()

    def test_report_404_unknown_project(self):
        assert requests.post(f"{API}/projects/nope/report", json={}).status_code == 404

    def test_report_brand_persisted(self):
        requests.post(f"{API}/projects/{SMITH}/report", json={"brand": {"company_name": "TEST_Persist", "phone": "1"}, "include_images": False, "include_qa": False})
        g = requests.get(f"{API}/settings/brand").json()
        assert g["company_name"] == "TEST_Persist"


def read_sse(resp):
    events = []
    for line in resp.iter_lines(decode_unicode=True):
        if line and line.startswith("data: "):
            events.append(json.loads(line[6:]))
    return events


# --- Set-scope chat ---
class TestChatScope:
    def test_set_scope_finds_other_sheet(self):
        r = requests.post(f"{API}/projects/{SMITH}/chat", json={
            "message": "What size are the footings and what rebar is specified?", "page_index": 0, "scope": "set"},
            stream=True, timeout=240)
        assert r.status_code == 200
        ev = read_sse(r)
        kinds = [next(iter(e)) for e in ev]
        assert kinds[0] == "status", kinds[:3]
        si = kinds.index("sources")
        assert "delta" in kinds[si:]
        assert not any("error" in e for e in ev), [e for e in ev if "error" in e]
        sources = ev[si]["sources"]
        print("sources", sources)
        assert any("S-201" in s for s in sources)
        answer = "".join(e.get("delta", "") for e in ev)
        assert len(answer) > 50
        msgs = requests.get(f"{API}/projects/{SMITH}/messages").json()
        last = msgs[-1]
        assert last["role"] == "assistant" and last["sources"] == sources
        assert msgs[-2]["scope"] == "set"

    def test_sheet_scope_no_status_event(self):
        r = requests.post(f"{API}/projects/{SMITH}/chat", json={
            "message": "What is the drawing title of this sheet?", "page_index": 1, "scope": "sheet"}, stream=True, timeout=240)
        ev = read_sse(r)
        kinds = [next(iter(e)) for e in ev]
        assert "status" not in kinds
        assert kinds[0] == "sources"
        assert "A-101" in ev[0]["sources"][0]
        assert "delta" in kinds

    def test_chat_empty_message(self):
        assert requests.post(f"{API}/projects/{SMITH}/chat", json={"message": "  ", "scope": "set"}).status_code == 400


# --- Scan entire set (TEST_ project) ---
@pytest.mark.skipif(not TEST_PID, reason="TEST_SCAN_PID not set")
class TestScanSet:
    def test_scan_from_scratch(self):
        r = requests.post(f"{API}/projects/{TEST_PID}/scan")
        assert r.status_code == 200
        n = requests.get(f"{API}/projects/{TEST_PID}").json()["page_count"]
        q = r.json()["queued"]
        assert q == n, (q, n)
        statuses = [p["status"] for p in requests.get(f"{API}/projects/{TEST_PID}").json()["pages"]]
        assert all(s == "analyzing" for s in statuses)
        # second call while analyzing queues nothing
        assert requests.post(f"{API}/projects/{TEST_PID}/scan").json()["queued"] == 0
        t0 = time.time(); done_times = {}
        while time.time() - t0 < 600:
            pages = requests.get(f"{API}/projects/{TEST_PID}").json()["pages"]
            for p in pages:
                if p["status"] != "analyzing" and p["index"] not in done_times:
                    done_times[p["index"]] = round(time.time() - t0)
            if len(done_times) == n:
                break
            time.sleep(5)
        print("completion times (s):", done_times)
        pages = requests.get(f"{API}/projects/{TEST_PID}").json()["pages"]
        for p in pages:
            assert p["status"] == "ready", (p["index"], p.get("error"))
            assert isinstance(p["analysis"].get("expert_notes"), list) and p["analysis"]["expert_notes"]
            assert isinstance(p["analysis"].get("digest"), str) and len(p["analysis"]["digest"]) > 20
        assert requests.post(f"{API}/projects/{TEST_PID}/scan").json()["queued"] == 0

    def test_scan_404(self):
        assert requests.post(f"{API}/projects/nope/scan").status_code == 404
