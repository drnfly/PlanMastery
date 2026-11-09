# Iteration 5: Drainage plan tool (real Gemini), drainage PATCH, crew packets with drainage sections, full report, photos
import pytest
import requests
from test_iter4_tools_photos import API, TEST_PID, SMITH, PHOTO, EX_WALL, EX_FOOT, pdf_text, poll

pytestmark = pytest.mark.slow


def tool(pid, name):
    return (requests.get(f"{API}/projects/{pid}").json().get("tools") or {}).get(name) or {}


# ---- fast checks (Smith, read-only + restore) ----
class TestDrainageFast:
    def test_unknown_tool_404(self):
        assert requests.post(f"{API}/projects/{SMITH}/tools/foo").status_code == 404

    def test_patch_other_tool_404(self):
        assert requests.patch(f"{API}/projects/{SMITH}/tools/icf/items/0", json={"verified": True}).status_code == 404
        assert requests.patch(f"{API}/projects/{SMITH}/tools/crew_icf/items/0", json={"verified": True}).status_code == 404

    def test_patch_bad_index_404(self):
        assert requests.patch(f"{API}/projects/{SMITH}/tools/drainage/items/999", json={"verified": True}).status_code == 404
        assert requests.patch(f"{API}/projects/{SMITH}/tools/drainage/items/-1", json={"verified": True}).status_code == 404

    def test_patch_invalid_body_422(self):
        r = requests.patch(f"{API}/projects/{SMITH}/tools/drainage/items/0", json={})
        assert r.status_code == 422

    def test_smith_drainage_schema(self):
        d = tool(SMITH, "drainage")["data"]
        assert isinstance(d["summary"], str) and isinstance(d["strategy"], str) and d["strategy"]
        for k in ("sequence", "inspections", "rfis"):
            assert isinstance(d[k], list)
        for it in d["items"]:
            assert it["status"] in ("specified", "missing", "unclear")
            assert {"category", "item", "status", "sheets", "spec", "recommendation", "severity", "verified", "quantity"} <= set(it)

    def test_smith_drainage_patch_persist_restore(self):
        items = tool(SMITH, "drainage")["data"]["items"]
        i = len(items) - 1
        orig = bool(items[i].get("verified"))
        assert requests.patch(f"{API}/projects/{SMITH}/tools/drainage/items/{i}", json={"verified": not orig}).status_code == 200
        assert tool(SMITH, "drainage")["data"]["items"][i]["verified"] is (not orig)
        # waterproofing list unaffected
        requests.patch(f"{API}/projects/{SMITH}/tools/drainage/items/{i}", json={"verified": orig})
        assert tool(SMITH, "drainage")["data"]["items"][i]["verified"] is orig

    def test_full_report_has_drainage(self):
        r = requests.post(f"{API}/projects/{SMITH}/report", json={"include_images": False}, timeout=120)
        assert r.status_code == 200 and r.content[:4] == b"%PDF"
        txt, _ = pdf_text(r.content)
        assert "ICF material estimate" in txt and "Waterproofing checklist" in txt and "Drainage plan" in txt

    def test_wp_crew_report_has_drainage(self):
        r = requests.post(f"{API}/projects/{SMITH}/report", json={"crew": "waterproofing", "include_images": False}, timeout=120)
        assert r.status_code == 200
        txt, _ = pdf_text(r.content)
        assert "WATERPROOFING CREW PACKET" in txt.upper() and "Crew briefing" in txt
        assert "Drainage plan" in txt and "ICF material estimate" not in txt

    def test_icf_crew_report_no_drainage(self):
        r = requests.post(f"{API}/projects/{SMITH}/report", json={"crew": "icf", "include_images": False}, timeout=120)
        txt, _ = pdf_text(r.content)
        assert "Drainage plan" not in txt and "ICF material estimate" in txt


# ---- slow: real Gemini drainage + crew_waterproofing on TEST project ----
class TestDrainageSlow:
    def test_01_start(self):
        for t in ("drainage", "crew_waterproofing"):
            r = requests.post(f"{API}/projects/{TEST_PID}/tools/{t}")
            assert r.status_code == 200 and r.json()["status"] == "running"
        assert tool(TEST_PID, "drainage")["status"] == "running"

    def test_02_crew_blocked(self):
        r = requests.post(f"{API}/projects/{TEST_PID}/report", json={"crew": "waterproofing"})
        assert r.status_code == 400 and "Prepare the crew packet first" in r.json()["detail"]

    def test_03_drainage_ready(self):
        t = poll(lambda: tool(TEST_PID, "drainage"), lambda x: x.get("status") in ("ready", "failed"), 300)
        assert t.get("status") == "ready", t.get("error")
        d = t["data"]
        assert {"summary", "strategy", "items", "sequence", "inspections", "rfis"} <= set(d)
        assert d["items"] and all(it["verified"] is False for it in d["items"])
        assert any(it.get("quantity") for it in d["items"])
        print("DRAINAGE items", len(d["items"]), "seq", len(d["sequence"]))

    def test_04_patch_drainage(self):
        assert requests.patch(f"{API}/projects/{TEST_PID}/tools/drainage/items/0", json={"verified": True}).status_code == 200
        d = tool(TEST_PID, "drainage")["data"]
        assert d["items"][0]["verified"] is True

    def test_05_crew_wp_ready_and_pdf(self):
        t = poll(lambda: tool(TEST_PID, "crew_waterproofing"), lambda x: x.get("status") in ("ready", "failed"), 300)
        assert t.get("status") == "ready", t.get("error")
        assert {"sheets", "scope", "sequence"} <= set(t["data"])
        r = requests.post(f"{API}/projects/{TEST_PID}/report", json={"crew": "waterproofing", "include_images": False}, timeout=120)
        assert r.status_code == 200
        txt, _ = pdf_text(r.content)
        assert "Crew briefing" in txt and "Drainage plan" in txt and "Waterproofing checklist" in txt

    def test_06_icf_put_example(self):
        r = requests.put(f"{API}/projects/{TEST_PID}/tools/icf", json={"walls": [EX_WALL], "footings": [EX_FOOT], "params": {}})
        assert r.status_code == 200
        t = r.json()["calc"]["totals"]
        assert (t["straight_blocks"], t["corner_blocks"], t["wall_cy"], t["footing_cy"]) == (196, 24, 29.87, 11.2)
        assert tool(TEST_PID, "icf")["data"]["calc"]["totals"]["straight_blocks"] == 196


class TestPhotos:
    def test_photo_lifecycle(self):
        with open(PHOTO, "rb") as f:
            r = requests.post(f"{API}/projects/{TEST_PID}/photos", files={"file": ("TEST_site.jpg", f, "image/jpeg")},
                              data={"note": "TEST_ footing drain tile — next step?"})
        assert r.status_code == 200 and r.json()["status"] == "analyzing"
        pid = r.json()["id"]
        try:
            assert requests.get(f"{API}/photos/{pid}/image").headers["content-type"] == "image/jpeg"
            get = lambda: next((p for p in requests.get(f"{API}/projects/{TEST_PID}/photos").json() if p["id"] == pid), {})
            ph = poll(get, lambda x: x.get("status") in ("ready", "failed"), 240)
            assert ph["status"] == "ready", ph.get("error")
            a = ph["analysis"]
            assert {"title", "stage", "what_i_see", "plan_check", "issues", "next_steps", "inspections", "safety", "questions"} <= set(a)
            assert all(isinstance(i.get("fix"), list) for i in a["issues"])
            assert requests.post(f"{API}/photos/{pid}/ask", json={"question": "  "}).status_code == 400
            assert requests.post(f"{API}/photos/{pid}/ask", json={"question": "What gravel size?"}).json()["status"] == "answering"
            ph = poll(get, lambda x: x.get("status") in ("ready", "failed"), 240)
            assert ph["status"] == "ready" and len(ph["thread"]) == 1 and ph["thread"][0]["a"]
        finally:
            assert requests.delete(f"{API}/photos/{pid}").status_code == 200
            assert requests.get(f"{API}/photos/{pid}/image").status_code == 404
