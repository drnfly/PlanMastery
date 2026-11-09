# Iteration 4 slow E2E flow on a TEST_ project: tools run (real Gemini), ICF PUT recalculation, crew packet report, photo lifecycle
import os
import time
import pytest
import requests
from test_iter4_tools_photos import API, TEST_PID, PHOTO, EX_WALL, EX_FOOT, pdf_text, poll

pytestmark = pytest.mark.slow


def tool(name):
    return (requests.get(f"{API}/projects/{TEST_PID}").json().get("tools") or {}).get(name) or {}


class TestSlowFlow:
    def test_01_start_tools(self):
        for t in ("icf", "waterproofing", "crew_foundation"):
            r = requests.post(f"{API}/projects/{TEST_PID}/tools/{t}")
            assert r.status_code == 200 and r.json()["status"] == "running"
            assert tool(t)["status"] == "running"

    def test_02_crew_report_blocked_while_running(self):
        r = requests.post(f"{API}/projects/{TEST_PID}/report", json={"crew": "foundation"})
        assert r.status_code == 400 and "Prepare the crew packet first" in r.json()["detail"]

    def test_03_put_icf_blocked_until_ready(self):
        if tool("icf").get("status") == "ready":
            pytest.skip("already ready")
        r = requests.put(f"{API}/projects/{TEST_PID}/tools/icf", json={"walls": [], "footings": []})
        assert r.status_code == 400

    def test_04_icf_ready_schema(self):
        t = poll(lambda: tool("icf"), lambda x: x.get("status") in ("ready", "failed"), 300)
        assert t.get("status") == "ready", t.get("error")
        ex, calc = t["data"]["extract"], t["data"]["calc"]
        assert {"system", "walls", "footings", "assumptions", "missing"} <= set(ex)
        assert {"params", "walls", "footings", "rebar", "totals"} <= set(calc)
        for r in calc["rebar"]:
            assert {"size", "lf", "sticks", "stock_ft", "weight_lb"} <= set(r)

    def test_05_icf_put_example(self):
        r = requests.put(f"{API}/projects/{TEST_PID}/tools/icf", json={"walls": [EX_WALL], "footings": [EX_FOOT], "params": {}})
        assert r.status_code == 200
        t = r.json()["calc"]["totals"]
        assert (t["straight_blocks"], t["corner_blocks"], t["wall_cy"], t["footing_cy"]) == (196, 24, 29.87, 11.2)
        got = tool("icf")["data"]
        assert got["calc"]["totals"]["straight_blocks"] == 196
        assert got["extract"]["walls"][0]["id"] == "W1"
        r2 = requests.put(f"{API}/projects/{TEST_PID}/tools/icf", json={"walls": [EX_WALL], "footings": [EX_FOOT], "params": {"waste_pct": 0}})
        assert r2.json()["calc"]["totals"]["straight_blocks"] == 186

    def test_06_wp_ready_and_patch(self):
        t = poll(lambda: tool("waterproofing"), lambda x: x.get("status") in ("ready", "failed"), 300)
        assert t.get("status") == "ready", t.get("error")
        items = t["data"]["items"]
        assert items and all(i["verified"] is False for i in items)
        assert {"missing", "specified", "unclear"} & {i["status"] for i in items}
        assert requests.patch(f"{API}/projects/{TEST_PID}/tools/waterproofing/items/0", json={"verified": True}).status_code == 200
        assert tool("waterproofing")["data"]["items"][0]["verified"] is True
        assert requests.patch(f"{API}/projects/{TEST_PID}/tools/waterproofing/items/{len(items)}", json={"verified": True}).status_code == 404

    def test_07_foundation_crew_report(self):
        t = poll(lambda: tool("crew_foundation"), lambda x: x.get("status") in ("ready", "failed"), 300)
        assert t.get("status") == "ready", t.get("error")
        d = t["data"]
        assert isinstance(d.get("sheets"), list) and d.get("scope")
        print("foundation packet sheets:", d["sheets"])
        r = requests.post(f"{API}/projects/{TEST_PID}/report", json={"crew": "foundation", "include_images": False}, timeout=120)
        assert r.status_code == 200 and r.content[:4] == b"%PDF"
        txt, _ = pdf_text(r.content)
        assert "FOUNDATION CREW PACKET" in txt and "Crew briefing" in txt
        assert "ICF material estimate" in txt and "Waterproofing checklist" in txt
        assert f"{len(set(d['sheets']))} of 3 sheets" in txt or "of 3 sheets" in txt
        rw = requests.post(f"{API}/projects/{TEST_PID}/report", json={"crew": "waterproofing"})
        assert rw.status_code == 400

    def test_08_photo_lifecycle(self):
        with open(PHOTO, "rb") as f:
            r = requests.post(f"{API}/projects/{TEST_PID}/photos", files={"file": ("site.jpg", f, "image/jpeg")},
                              data={"note": "TEST_ North wall footing — ready to pour?"})
        assert r.status_code == 200
        ph = r.json()
        assert ph["status"] == "analyzing" and "_id" not in ph and ph["note"].startswith("TEST_")
        pid = ph["id"]
        img = requests.get(f"{API}/photos/{pid}/image")
        assert img.status_code == 200 and img.headers["content-type"] == "image/jpeg" and img.content[:2] == b"\xff\xd8"

        def get():
            return next((p for p in requests.get(f"{API}/projects/{TEST_PID}/photos").json() if p["id"] == pid), {})
        p = poll(get, lambda x: x.get("status") in ("ready", "failed"), 240)
        assert p.get("status") == "ready", p.get("error")
        a = p["analysis"]
        assert {"title", "stage", "what_i_see", "plan_check", "issues", "next_steps", "inspections", "safety", "questions"} <= set(a)
        # ask while ready
        r = requests.post(f"{API}/photos/{pid}/ask", json={"question": "What should we check before pouring?"})
        assert r.status_code == 200 and r.json()["status"] == "answering"
        assert requests.post(f"{API}/photos/{pid}/ask", json={"question": "again"}).status_code == 400
        p = poll(get, lambda x: x.get("status") in ("ready", "failed"), 240)
        assert p.get("status") == "ready" and len(p["thread"]) == 1 and p["thread"][0]["a"]
        assert requests.post(f"{API}/photos/{pid}/ask", json={"question": "   "}).status_code == 400
        # reanalyze
        r = requests.post(f"{API}/photos/{pid}/reanalyze")
        assert r.status_code == 200 and get()["status"] == "analyzing"
        p = poll(get, lambda x: x.get("status") in ("ready", "failed"), 240)
        assert p.get("status") == "ready" and p["analysis"] and len(p["thread"]) == 1
        # delete
        assert requests.delete(f"{API}/photos/{pid}").status_code == 200
        assert get() == {}
        assert requests.get(f"{API}/photos/{pid}/image").status_code == 404
