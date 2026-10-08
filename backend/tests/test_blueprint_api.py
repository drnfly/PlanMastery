"""Backend API tests for Blueprint AI."""
import io
import os
import time
import json
import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://blueprint-measure-6.preview.emergentagent.com').rstrip('/')
API = f"{BASE_URL}/api"
SAMPLE_PNG = "/app/tests/sample_floorplan.png"


@pytest.fixture(scope="session")
def sample_bytes():
    with open(SAMPLE_PNG, "rb") as f:
        return f.read()


@pytest.fixture(scope="session")
def created_project(sample_bytes):
    files = {"file": ("TEST_floorplan.png", sample_bytes, "image/png")}
    data = {"name": "TEST_Backend_Project", "scale_hint": '1/4"=1\'-0"'}
    r = requests.post(f"{API}/projects", files=files, data=data, timeout=60)
    assert r.status_code == 200, r.text
    p = r.json()
    assert p["status"] == "analyzing"
    assert p["name"] == "TEST_Backend_Project"
    assert p["ext"] == "png"
    assert "id" in p
    yield p
    # Cleanup
    try:
        requests.delete(f"{API}/projects/{p['id']}", timeout=10)
    except Exception:
        pass


# ---------- health ----------
def test_root():
    r = requests.get(f"{API}/", timeout=15)
    assert r.status_code == 200
    assert "message" in r.json()


# ---------- upload validation ----------
def test_upload_rejects_unsupported_ext():
    files = {"file": ("bad.txt", b"hello world", "text/plain")}
    r = requests.post(f"{API}/projects", files=files, data={"name": "bad", "scale_hint": ""}, timeout=30)
    assert r.status_code == 400
    assert "Unsupported" in r.json().get("detail", "")


def test_upload_rejects_empty_file():
    files = {"file": ("empty.png", b"", "image/png")}
    r = requests.post(f"{API}/projects", files=files, data={"name": "", "scale_hint": ""}, timeout=30)
    assert r.status_code == 400


# ---------- create + list ----------
def test_create_project_returns_analyzing(created_project):
    assert created_project["status"] == "analyzing"
    assert created_project["analysis"] is None


def test_list_projects_contains_created(created_project):
    r = requests.get(f"{API}/projects", timeout=15)
    assert r.status_code == 200
    ids = [p["id"] for p in r.json()]
    assert created_project["id"] in ids
    # ensure _id is not leaked
    for p in r.json():
        assert "_id" not in p


# ---------- file retrieval ----------
def test_get_project_file(created_project, sample_bytes):
    r = requests.get(f"{API}/projects/{created_project['id']}/file", timeout=30)
    assert r.status_code == 200
    assert r.headers.get("content-type") == "image/png"
    assert len(r.content) == len(sample_bytes)


# ---------- analysis completion ----------
def test_analysis_eventually_ready(created_project):
    pid = created_project["id"]
    deadline = time.time() + 180
    status = None
    data = None
    while time.time() < deadline:
        r = requests.get(f"{API}/projects/{pid}", timeout=20)
        assert r.status_code == 200
        data = r.json()
        status = data["status"]
        if status in ("ready", "failed"):
            break
        time.sleep(5)
    assert status == "ready", f"status={status}, error={data.get('error') if data else None}"
    a = data["analysis"]
    assert isinstance(a, dict)
    for k in ("rooms", "walls", "openings", "overall", "summary", "warnings"):
        assert k in a, f"missing key {k} in analysis"
    assert isinstance(a["rooms"], list)


# ---------- messages & chat ----------
def test_messages_initially_empty(created_project):
    pid = created_project["id"]
    r = requests.get(f"{API}/projects/{pid}/messages", timeout=15)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_chat_streaming_sse(created_project):
    pid = created_project["id"]
    # Wait for ready first (may already be ready from prior test)
    deadline = time.time() + 60
    while time.time() < deadline:
        s = requests.get(f"{API}/projects/{pid}", timeout=15).json()["status"]
        if s == "ready":
            break
        time.sleep(4)
    r = requests.post(f"{API}/projects/{pid}/chat",
                      json={"message": "In one short sentence, what type of drawing is this?"},
                      stream=True, timeout=120)
    assert r.status_code == 200
    assert "text/event-stream" in r.headers.get("content-type", "")
    deltas = []
    done = False
    err = None
    for raw in r.iter_lines(decode_unicode=True):
        if not raw or not raw.startswith("data: "):
            continue
        ev = json.loads(raw[6:])
        if "delta" in ev:
            deltas.append(ev["delta"])
        if "done" in ev:
            done = True
            break
        if "error" in ev:
            err = ev["error"]
            break
    r.close()
    assert err is None, f"stream error: {err}"
    assert done
    assert len("".join(deltas)) > 0

    # verify persisted
    msgs = requests.get(f"{API}/projects/{pid}/messages", timeout=15).json()
    roles = [m["role"] for m in msgs]
    assert "user" in roles and "assistant" in roles


def test_chat_rejects_empty_message(created_project):
    r = requests.post(f"{API}/projects/{created_project['id']}/chat",
                      json={"message": "   "}, timeout=30)
    assert r.status_code == 400


# ---------- reanalyze ----------
def test_reanalyze_sets_status(created_project):
    pid = created_project["id"]
    r = requests.post(f"{API}/projects/{pid}/reanalyze", timeout=30)
    assert r.status_code == 200
    assert r.json()["status"] == "analyzing"
    detail = requests.get(f"{API}/projects/{pid}", timeout=10).json()
    assert detail["status"] == "analyzing"


# ---------- delete (soft) ----------
def test_delete_soft(sample_bytes):
    # Create a disposable project to delete
    files = {"file": ("TEST_del.png", sample_bytes, "image/png")}
    p = requests.post(f"{API}/projects", files=files, data={"name": "TEST_delete_me", "scale_hint": ""}, timeout=60).json()
    pid = p["id"]
    r = requests.delete(f"{API}/projects/{pid}", timeout=15)
    assert r.status_code == 200
    assert r.json().get("ok") is True
    # Should 404 now
    r2 = requests.get(f"{API}/projects/{pid}", timeout=15)
    assert r2.status_code == 404
    # Not in list
    ids = [x["id"] for x in requests.get(f"{API}/projects", timeout=15).json()]
    assert pid not in ids


def test_not_found():
    r = requests.get(f"{API}/projects/nonexistent-id-xyz", timeout=15)
    assert r.status_code == 404
