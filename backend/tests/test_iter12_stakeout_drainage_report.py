# Iteration 12: stake-out distances + drainage-only PDF report (and crew regression)
import os
import io
import math
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/") or open("/app/frontend/.env").read().split("REACT_APP_BACKEND_URL=")[1].split()[0].rstrip("/")
PID = "eb4fb34f-fc53-4700-abee-97f4822c8ce9"
PID2 = "c5675b5d-4a36-4502-a217-48d6b5e176d2"
NO_LAYOUT = "bbed49f5-464e-438d-8757-bc864ffcd2b6"
S = requests.Session()


def rep(pid, body):
    return S.post(f"{BASE_URL}/api/projects/{pid}/report", json=body, timeout=120)


def pdf_text(b):
    import fitz
    doc = fitz.open(stream=b, filetype="pdf")
    if os.environ.get("SAVE_PDF"):
        open(os.environ["SAVE_PDF"], "wb").write(b)
    return doc.page_count, "\n".join(p.get_text() for p in doc)


# Drainage-only PDF
class TestDrainageReport:
    def test_drainage_pdf(self):
        r = rep(PID, {"crew": "drainage"})
        assert r.status_code == 200, r.text[:300]
        assert r.headers["content-type"] == "application/pdf"
        assert "_drainage_report.pdf" in r.headers.get("content-disposition", "")
        assert r.content[:4] == b"%PDF"
        n, txt = pdf_text(r.content)
        print("pages", n)
        print(txt[:3000])
        assert "Stake-out distances" in txt
        assert "Drain tile layout" in txt
        assert "Drainage material takeoff" in txt
        assert "CO-1" in txt and "SUMP" in txt
        assert "Sheets in this report" not in txt

    def test_drainage_pdf_project2(self):
        r = rep(PID2, {"crew": "drainage"})
        assert r.status_code == 200, r.text[:300]
        n, txt = pdf_text(r.content)
        assert "Stake-out" in txt
        assert "Drainage plan checklist" in txt

    def test_drainage_no_layout_400(self):
        r = rep(NO_LAYOUT, {"crew": "drainage"})
        assert r.status_code == 400
        assert "Draw the drain tile layout" in r.json()["detail"]

    def test_drainage_404_project(self):
        r = rep("does-not-exist", {"crew": "drainage"})
        assert r.status_code == 404


# Regression: other crews
@pytest.mark.parametrize("crew", ["full", "foundation", "waterproofing"])
def test_crew_regression(crew):
    p = S.get(f"{BASE_URL}/api/projects/{PID2}", timeout=30).json()
    if crew != "full" and (p.get("tools") or {}).get(f"crew_{crew}", {}).get("status") != "ready":
        # use TEST_Iter4 which has crew packets
        pid = "21f16323-6b5c-4d5b-b541-9d61852f4d55"
    else:
        pid = PID2
    r = rep(pid, {"crew": crew, "include_images": False})
    assert r.status_code == 200, r.text[:300]
    assert r.content[:4] == b"%PDF"
