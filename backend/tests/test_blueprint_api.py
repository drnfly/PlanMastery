"""Backend API tests for Blueprint AI: chunked upload, large PDF plan-set processing, per-page analysis/3D, chat."""
import os
import time
import json
import subprocess
import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL').rstrip('/')
API = f"{BASE_URL}/api"
CH = 4 * 1024 * 1024
LARGE_PDF = "/tmp/TEST_large_planset.pdf"
SAMPLE_PNG = "/app/tests/sample_floorplan.png"


def chunked_upload(path, name, scale_hint=""):
    size = os.path.getsize(path)
    r = requests.post(f"{API}/uploads/init", json={"filename": os.path.basename(path), "size": size}, timeout=30)
    assert r.status_code == 200, r.text
    uid = r.json()["upload_id"]
    with open(path, "rb") as f:
        n = 0
        while chunk := f.read(CH):
            rr = requests.put(f"{API}/uploads/{uid}/chunk/{n}", data=chunk,
                              headers={"Content-Type": "application/octet-stream"}, timeout=120)
            assert rr.status_code == 200, f"chunk {n}: {rr.status_code} {rr.text[:200]}"
            n += 1
    r = requests.post(f"{API}/uploads/{uid}/complete", json={"name": name, "scale_hint": scale_hint}, timeout=60)
    assert r.status_code == 200, r.text
    return r.json()


def wait_project(pid, timeout=400):
    deadline = time.time() + timeout
    seen_progress = set()
    while time.time() < deadline:
        p = requests.get(f"{API}/projects/{pid}", timeout=30).json()
        seen_progress.add(p.get("processed_pages"))
        if p["status"] in ("ready", "failed"):
            return p, seen_progress
        time.sleep(4)
    return p, seen_progress


@pytest.fixture(scope="session")
def large_project():
    if not os.path.exists(LARGE_PDF):
        subprocess.run(["python", "/app/tests/make_large_planset.py", LARGE_PDF], check=True)
    assert os.path.getsize(LARGE_PDF) > 20 * 1024 * 1024
    p = chunked_upload(LARGE_PDF, "TEST_Large_Planset")
    yield p
    requests.delete(f"{API}/projects/{p['id']}", timeout=15)


@pytest.fixture(scope="session")
def ready_large(large_project):
    p, prog = wait_project(large_project["id"])
    assert p["status"] == "ready", f"status={p['status']} err={p.get('error')}"
    return p


# ---------- health ----------
def test_root():
    r = requests.get(f"{API}/", timeout=15)
    assert r.status_code == 200 and "message" in r.json()


# ---------- upload init validation ----------
def test_init_rejects_bad_ext():
    r = requests.post(f"{API}/uploads/init", json={"filename": "bad.txt", "size": 100}, timeout=15)
    assert r.status_code == 400 and "Unsupported" in r.json()["detail"]


def test_init_rejects_oversize():
    r = requests.post(f"{API}/uploads/init", json={"filename": "big.pdf", "size": 150 * 1024 * 1024 + 1}, timeout=15)
    assert r.status_code == 400


def test_init_rejects_zero_size():
    r = requests.post(f"{API}/uploads/init", json={"filename": "z.pdf", "size": 0}, timeout=15)
    assert r.status_code == 400


def test_init_accepts_150mb():
    r = requests.post(f"{API}/uploads/init", json={"filename": "ok.pdf", "size": 150 * 1024 * 1024}, timeout=15)
    assert r.status_code == 200 and isinstance(r.json()["upload_id"], str)


# ---------- chunk ordering / completion ----------
def test_out_of_order_chunk_409_and_incomplete():
    uid = requests.post(f"{API}/uploads/init", json={"filename": "TEST_x.png", "size": 10}, timeout=15).json()["upload_id"]
    r = requests.put(f"{API}/uploads/{uid}/chunk/1", data=b"abc", timeout=15)
    assert r.status_code == 409
    r = requests.put(f"{API}/uploads/{uid}/chunk/0", data=b"abcde", timeout=15)
    assert r.status_code == 200 and r.json()["received"] == 5
    r = requests.put(f"{API}/uploads/{uid}/chunk/1", data=b"0123456789", timeout=15)
    assert r.status_code == 400  # exceeds declared size
    r = requests.post(f"{API}/uploads/{uid}/complete", json={"name": "TEST_x"}, timeout=15)
    assert r.status_code == 400  # incomplete


def test_chunk_unknown_upload_404():
    r = requests.put(f"{API}/uploads/does-not-exist/chunk/0", data=b"abc", timeout=15)
    assert r.status_code == 404


# ---------- large PDF processing ----------
def test_large_complete_returns_processing(large_project):
    assert large_project["status"] == "processing"
    assert large_project["name"] == "TEST_Large_Planset"
    assert large_project["ext"] == "pdf"
    assert large_project["size"] > 20 * 1024 * 1024
    assert "_id" not in large_project


def test_large_pdf_split_and_indexed(ready_large):
    p = ready_large
    assert p["page_count"] == 6 and p["processed_pages"] == 6
    assert len(p["pages"]) == 6
    for pg in p["pages"]:
        assert "_id" not in pg and "text" not in pg
        assert pg["status"] in ("pending", "analyzing", "ready")
    nums = [pg["sheet_number"] for pg in p["pages"]]
    print("SHEETS:", [(pg["sheet_number"], pg["title"], pg["discipline"]) for pg in p["pages"]])
    assert "A-101" in nums and "S-201" in nums


def test_page_image_png(ready_large):
    r = requests.get(f"{API}/projects/{ready_large['id']}/pages/1/image", timeout=60)
    assert r.status_code == 200 and r.headers["content-type"] == "image/png"
    assert r.content[:8] == b"\x89PNG\r\n\x1a\n"


def test_page_not_found(ready_large):
    r = requests.get(f"{API}/projects/{ready_large['id']}/pages/99/image", timeout=15)
    assert r.status_code == 404


def test_analyze_page(ready_large):
    pid = ready_large["id"]
    r = requests.post(f"{API}/projects/{pid}/pages/1/analyze", timeout=30)
    assert r.status_code == 200 and r.json()["status"] == "analyzing"
    deadline = time.time() + 240
    pg = None
    while time.time() < deadline:
        pg = requests.get(f"{API}/projects/{pid}", timeout=30).json()["pages"][1]
        if pg["status"] in ("ready", "failed"):
            break
        time.sleep(5)
    assert pg["status"] == "ready", pg.get("error")
    for k in ("rooms", "walls", "openings", "overall", "summary", "warnings"):
        assert k in pg["analysis"]


def test_analyze_noisy_large_page(ready_large):
    """Page 0 has a ~10MB noisy raster -> per-page PDF fed to Gemini."""
    pid = ready_large["id"]
    requests.post(f"{API}/projects/{pid}/pages/0/analyze", timeout=30)
    deadline = time.time() + 240
    while time.time() < deadline:
        pg = requests.get(f"{API}/projects/{pid}", timeout=30).json()["pages"][0]
        if pg["status"] in ("ready", "failed"):
            break
        time.sleep(5)
    assert pg["status"] == "ready", pg.get("error")


def test_model3d_page(ready_large):
    pid = ready_large["id"]
    r = requests.post(f"{API}/projects/{pid}/pages/1/model3d", timeout=30)
    assert r.status_code == 200 and r.json()["model3d_status"] == "generating"
    deadline = time.time() + 240
    while time.time() < deadline:
        pg = requests.get(f"{API}/projects/{pid}", timeout=30).json()["pages"][1]
        if pg["model3d_status"] in ("ready", "failed"):
            break
        time.sleep(5)
    assert pg["model3d_status"] == "ready", pg.get("model3d_error")
    m = pg["model3d"]
    assert isinstance(m["walls"], list) and len(m["walls"]) > 0
    for w in m["walls"]:
        for k in ("x1", "y1", "x2", "y2"):
            assert 0 <= float(w[k]) <= 1000


def read_sse(r):
    deltas, done, err = [], False, None
    for raw in r.iter_lines(decode_unicode=True):
        if not raw or not raw.startswith("data: "):
            continue
        ev = json.loads(raw[6:])
        if "delta" in ev:
            deltas.append(ev["delta"])
        if "error" in ev:
            err = ev["error"]
        if "done" in ev:
            done = True
            break
    return "".join(deltas), done, err


def test_chat_expert_persona(ready_large):
    pid = ready_large["id"]
    r = requests.post(f"{API}/projects/{pid}/chat", json={
        "message": "Briefly: for the ICF foundation wall on the foundation plan, what waterproofing do you recommend? Cite the sheet.",
        "page_index": 3}, stream=True, timeout=240)
    assert r.status_code == 200 and "text/event-stream" in r.headers["content-type"]
    text, done, err = read_sse(r)
    print("CHAT:", text[:600])
    assert err is None, err
    assert done and len(text) > 50
    assert "S-201" in text or "foundation" in text.lower()
    msgs = requests.get(f"{API}/projects/{pid}/messages", timeout=15).json()
    assert [m["role"] for m in msgs][-2:] == ["user", "assistant"]


def test_chat_empty_400(ready_large):
    r = requests.post(f"{API}/projects/{ready_large['id']}/chat", json={"message": "  "}, timeout=15)
    assert r.status_code == 400


def test_image_upload_and_delete():
    p = chunked_upload(SAMPLE_PNG, "TEST_png")
    q, _ = wait_project(p["id"], 60)
    assert q["status"] == "ready" and q["page_count"] == 1 and len(q["pages"]) == 1
    assert requests.delete(f"{API}/projects/{p['id']}", timeout=15).json()["ok"] is True
    assert requests.get(f"{API}/projects/{p['id']}", timeout=15).status_code == 404
