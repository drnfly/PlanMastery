from fastapi import FastAPI, APIRouter, HTTPException, BackgroundTasks, Request, UploadFile, File, Form
from fastapi.responses import Response, StreamingResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel
from pathlib import Path
from datetime import datetime, timezone, timedelta
import os
import json
import uuid
import logging
import asyncio

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

import io  # noqa: E402
import re  # noqa: E402
import shutil  # noqa: E402
import tempfile  # noqa: E402
from PIL import Image, ImageOps  # noqa: E402
from storage import init_storage, get_object, put_object, APP_NAME  # noqa: E402
from processing import open_pdf, process_pdf_page, process_image  # noqa: E402
from ai_engine import index_sheets, analyze_sheet, model_sheet, stream_chat, temp_file, pick_sheets  # noqa: E402
from overlay import render_overlay  # noqa: E402
from set_tools import drain_overlay  # noqa: E402
from report import build_report  # noqa: E402
from icf_calc import compute as icf_compute  # noqa: E402
from set_tools import ICF_PROMPT, WP_PROMPT, DRAIN_PROMPT, CREWS, set_json, crew_prompt, analyze_photo, photo_followup  # noqa: E402
from contextlib import ExitStack  # noqa: E402

client = AsyncIOMotorClient(os.environ['MONGO_URL'])
db = client[os.environ['DB_NAME']]

app = FastAPI()
api = APIRouter(prefix="/api")
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

MIME = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "webp": "image/webp", "pdf": "application/pdf"}
MAX_BYTES = 150 * 1024 * 1024
MAX_AI_PDF = 18 * 1024 * 1024
UPLOAD_DIR = Path(tempfile.gettempdir()) / "bp_uploads"
UPLOAD_DIR.mkdir(exist_ok=True)
NO_ID = {"_id": 0}
PAGE_LIST = {"_id": 0, "text": 0}


def now():
    return datetime.now(timezone.utc).isoformat()


class ChatIn(BaseModel):
    message: str
    page_index: int = 0
    scope: str = "set"


class Brand(BaseModel):
    company_name: str = ""
    prepared_by: str = ""
    phone: str = ""
    email: str = ""
    client: str = ""


class ReportIn(BaseModel):
    brand: Brand = Brand()
    include_images: bool = True
    include_qa: bool = True
    pages: list[int] | None = None
    crew: str = "full"


class IcfEdit(BaseModel):
    walls: list[dict]
    footings: list[dict]
    params: dict = {}


class WpPatch(BaseModel):
    verified: bool


class PhotoAsk(BaseModel):
    question: str


TOOLS = {"icf", "waterproofing", "drainage", "crew_foundation", "crew_icf", "crew_waterproofing"}
CHECKLISTS = {"waterproofing", "drainage"}
TOOL_QUERY = {
    "icf": "ICF foundation walls, wall sections, foundation plan, footings, rebar schedule, structural notes",
    "waterproofing": "waterproofing, foundation details, wall sections, drain tile, flashing, roof, envelope details",
    "drainage": "site plan, grading, drain tile, foundation plan, sump, downspouts, roof plan, civil drainage details",
    "crew_foundation": "foundation plan, footings, slab, drain tile, structural notes",
    "crew_icf": "ICF walls, wall sections, rebar, openings, foundation plan, structural notes",
    "crew_waterproofing": "waterproofing, drainage, flashing, foundation details, wall sections",
}


SCAN_SEM = asyncio.Semaphore(3)


class UploadInit(BaseModel):
    filename: str
    size: int


class UploadComplete(BaseModel):
    name: str = ""
    scale_hint: str = ""


async def get_project(pid: str) -> dict:
    p = await db.projects.find_one({"id": pid, "is_deleted": False}, NO_ID)
    if not p:
        raise HTTPException(404, "Project not found")
    return p


async def get_page(pid: str, idx: int, fields=NO_ID) -> dict:
    pg = await db.pages.find_one({"project_id": pid, "index": idx}, fields)
    if not pg:
        raise HTTPException(404, "Sheet not found")
    return pg


async def fetch(path: str) -> bytes:
    data, _ = await asyncio.to_thread(get_object, path)
    return data


def sheet_label(pg: dict) -> str:
    return " ".join(x for x in [pg.get("sheet_number"), pg.get("title")] if x) or f"Page {pg['index'] + 1}"


async def ai_source(pg: dict):
    """Vector single-page PDF when small enough, else rendered image."""
    if pg.get("pdf_path") and pg.get("pdf_size", 0) <= MAX_AI_PDF:
        return await fetch(pg["pdf_path"]), "pdf", "application/pdf"
    ext = pg["image_path"].rsplit(".", 1)[-1]
    return await fetch(pg["image_path"]), ext, MIME[ext]


async def set_page(pid: str, idx: int, fields: dict):
    await db.pages.update_one({"project_id": pid, "index": idx}, {"$set": fields})


async def process_project(pid: str, tmp: Path):
    p = await db.projects.find_one({"id": pid}, NO_ID)
    try:
        if p["ext"] == "pdf":
            doc = await asyncio.to_thread(open_pdf, str(tmp))
            await db.projects.update_one({"id": pid}, {"$set": {"page_count": doc.page_count}})
            for i in range(doc.page_count):
                pg = await asyncio.to_thread(process_pdf_page, doc, i, pid)
                await db.pages.insert_one({**pg, "project_id": pid, "sheet_number": "", "title": f"Page {i + 1}",
                                           "discipline": "", "status": "pending", "analysis": None, "error": None,
                                           "model3d_status": "none", "model3d": None})
                await db.projects.update_one({"id": pid}, {"$set": {"processed_pages": i + 1}})
            doc.close()
            await index_project(pid)
        else:
            pg = await asyncio.to_thread(process_image, tmp.read_bytes(), pid, p["ext"], p["content_type"])
            await db.pages.insert_one({**pg, "project_id": pid, "sheet_number": "", "title": p["name"], "discipline": "",
                                       "status": "pending", "analysis": None, "error": None,
                                       "model3d_status": "none", "model3d": None})
            await db.projects.update_one({"id": pid}, {"$set": {"page_count": 1, "processed_pages": 1}})
        await db.projects.update_one({"id": pid}, {"$set": {"status": "ready", "updated_at": now()}})
    except Exception as e:
        logger.exception("processing failed")
        msg = "Could not read this file — it may be corrupt or password-protected." if "open" in str(e).lower() else "Processing failed — please re-upload."
        await db.projects.update_one({"id": pid}, {"$set": {"status": "failed", "error": msg}})
    finally:
        tmp.unlink(missing_ok=True)


async def index_project(pid: str):
    pages = await db.pages.find({"project_id": pid}, {"_id": 0, "index": 1, "text": 1}).sort("index", 1).to_list(2000)
    texted = [{"page": pg["index"] + 1, "text": pg["text"]} for pg in pages if pg["text"].strip()]
    if not texted:
        return
    try:
        for s in await index_sheets(texted):
            await set_page(pid, int(s["page"]) - 1, {"sheet_number": s.get("sheet_number", ""),
                                                      "title": s.get("title") or f"Page {s['page']}",
                                                      "discipline": s.get("discipline", "")})
    except Exception:
        logger.exception("sheet indexing failed")


async def run_analysis(pid: str, idx: int):
    p = await db.projects.find_one({"id": pid}, NO_ID)
    pg = await get_page(pid, idx)
    try:
        data, ext, mime = await ai_source(pg)
        async with SCAN_SEM:
            with temp_file(data, ext) as path:
                result = await analyze_sheet(path, mime, sheet_label(pg), p.get("scale_hint", ""))
        await set_page(pid, idx, {"status": "ready", "analysis": result, "error": None})
    except Exception as e:
        logger.exception("analysis failed")
        await set_page(pid, idx, {"status": "failed", "error": str(e)[:300]})


async def run_drain(pid: str, idx: int):
    pg = await get_page(pid, idx)
    try:
        p = await db.projects.find_one({"id": pid}, NO_ID)
        dr = ((p.get("tools") or {}).get("drainage") or {}).get("data") or {}
        ctx = json.dumps({"strategy": dr.get("strategy"), "items": [{k: i.get(k) for k in ("item", "status", "spec", "quantity", "recommendation")}
                                                                     for i in dr.get("items", [])]})[:12000] if dr else "(no drainage plan yet)"
        data = await fetch(pg["image_path"])
        with temp_file(data, pg["image_path"].rsplit(".", 1)[-1]) as path:
            result = await drain_overlay(path, sheet_label(pg), ctx)
        await set_page(pid, idx, {"drain_status": "ready", "drain_overlay": result, "drain_error": None})
    except Exception as e:
        logger.exception("drain overlay failed")
        await set_page(pid, idx, {"drain_status": "failed", "drain_error": str(e)[:300]})


async def run_model3d(pid: str, idx: int):
    pg = await get_page(pid, idx)
    try:
        data = await fetch(pg["image_path"])
        if not pg["image_path"].endswith(".png"):
            buf = io.BytesIO()
            Image.open(io.BytesIO(data)).convert("RGB").save(buf, "PNG")
            data = buf.getvalue()
        with temp_file(data, "png") as path:
            result = await model_sheet(path, sheet_label(pg))
        await set_page(pid, idx, {"model3d_status": "ready", "model3d": result, "model3d_error": None})
    except Exception as e:
        logger.exception("3d failed")
        await set_page(pid, idx, {"model3d_status": "failed", "model3d_error": str(e)[:300]})


@api.get("/")
async def root():
    return {"message": "Blueprint AI"}


@api.post("/uploads/init")
async def upload_init(body: UploadInit):
    ext = body.filename.rsplit(".", 1)[-1].lower() if "." in body.filename else ""
    if ext not in MIME:
        raise HTTPException(400, "Unsupported file type. Use PNG, JPG, WEBP or PDF.")
    if body.size <= 0 or body.size > MAX_BYTES:
        raise HTTPException(400, "File must be between 1 byte and 150 MB.")
    uid = str(uuid.uuid4())
    (UPLOAD_DIR / uid).write_bytes(b"")
    await db.uploads.insert_one({"id": uid, "filename": body.filename, "ext": ext, "size": body.size,
                                 "next_chunk": 0, "created_at": now()})
    return {"upload_id": uid}


@api.put("/uploads/{uid}/chunk/{n}")
async def upload_chunk(uid: str, n: int, request: Request):
    up = await db.uploads.find_one({"id": uid}, NO_ID)
    if not up:
        raise HTTPException(404, "Upload not found")
    data = await request.body()
    if n == up["next_chunk"] - 1 and len(data) == up.get("last_len"):
        return {"received": (UPLOAD_DIR / uid).stat().st_size}
    if n != up["next_chunk"]:
        raise HTTPException(409, f"Expected chunk {up['next_chunk']}")
    tmp = UPLOAD_DIR / uid
    if tmp.stat().st_size + len(data) > up["size"]:
        raise HTTPException(400, "Chunk exceeds declared size")
    with open(tmp, "ab") as f:
        f.write(data)
    await db.uploads.update_one({"id": uid}, {"$inc": {"next_chunk": 1}, "$set": {"last_len": len(data)}})
    return {"received": tmp.stat().st_size}


@api.post("/uploads/{uid}/complete")
async def upload_complete(uid: str, body: UploadComplete, background: BackgroundTasks):
    up = await db.uploads.find_one({"id": uid}, NO_ID)
    tmp = UPLOAD_DIR / uid
    if not up or not tmp.exists() or tmp.stat().st_size != up["size"]:
        raise HTTPException(400, "Upload incomplete")
    pid = str(uuid.uuid4())
    final = UPLOAD_DIR / f"{pid}.{up['ext']}"
    shutil.move(str(tmp), final)
    await db.uploads.delete_one({"id": uid})
    doc = {"id": pid, "name": body.name.strip() or up["filename"].rsplit(".", 1)[0], "original_filename": up["filename"],
           "content_type": MIME[up["ext"]], "ext": up["ext"], "size": up["size"], "scale_hint": body.scale_hint.strip(),
           "status": "processing", "page_count": 0, "processed_pages": 0, "error": None,
           "is_deleted": False, "created_at": now(), "updated_at": now()}
    await db.projects.insert_one(doc.copy())
    background.add_task(process_project, pid, final)
    return doc


@api.get("/projects")
async def list_projects():
    return await db.projects.find({"is_deleted": False}, NO_ID).sort("created_at", -1).to_list(500)


@api.get("/projects/{pid}")
async def project_detail(pid: str):
    p = await get_project(pid)
    p["pages"] = await db.pages.find({"project_id": pid}, PAGE_LIST).sort("index", 1).to_list(2000)
    return p


@api.delete("/projects/{pid}")
async def delete_project(pid: str):
    await get_project(pid)
    await db.projects.update_one({"id": pid}, {"$set": {"is_deleted": True}})
    return {"ok": True}


@api.get("/projects/{pid}/pages/{idx}/image")
async def page_image(pid: str, idx: int):
    pg = await get_page(pid, idx, PAGE_LIST)
    ext = pg["image_path"].rsplit(".", 1)[-1]
    return Response(content=await fetch(pg["image_path"]), media_type=MIME[ext],
                    headers={"Cache-Control": "private, max-age=86400"})


@api.post("/projects/{pid}/pages/{idx}/analyze")
async def analyze_page(pid: str, idx: int, background: BackgroundTasks):
    await get_page(pid, idx, PAGE_LIST)
    await set_page(pid, idx, {"status": "analyzing", "error": None})
    background.add_task(run_analysis, pid, idx)
    return {"status": "analyzing"}


@api.post("/projects/{pid}/scan")
async def scan_set(pid: str, background: BackgroundTasks):
    await get_project(pid)
    todo = await db.pages.find({"project_id": pid, "status": {"$ne": "analyzing"}, "$or": [
        {"status": {"$in": ["pending", "failed"]}}, {"analysis.digest": {"$exists": False}}]}, {"_id": 0, "index": 1}).to_list(2000)
    idxs = [t["index"] for t in todo]
    if idxs:
        await db.pages.update_many({"project_id": pid, "index": {"$in": idxs}}, {"$set": {"status": "analyzing", "error": None}})
        background.add_task(scan_all, pid, idxs)
    return {"queued": len(idxs)}


async def scan_all(pid: str, idxs: list):
    await asyncio.gather(*[run_analysis(pid, i) for i in idxs])


@api.get("/settings/brand")
async def get_brand():
    return await db.settings.find_one({"id": "brand"}, {"_id": 0, "id": 0}) or {}


@api.put("/settings/brand")
async def put_brand(body: Brand):
    await db.settings.update_one({"id": "brand"}, {"$set": body.model_dump()}, upsert=True)
    return await get_brand()


@api.post("/settings/brand/logo")
async def put_logo(file: UploadFile = File(...)):
    ext = (file.filename or "").rsplit(".", 1)[-1].lower()
    if ext not in ("png", "jpg", "jpeg"):
        raise HTTPException(400, "Logo must be PNG or JPG")
    data = await file.read()
    if len(data) > 5 * 1024 * 1024:
        raise HTTPException(400, "Logo must be under 5 MB")
    try:
        Image.open(io.BytesIO(data)).verify()
    except Exception:
        raise HTTPException(400, "Logo is not a valid image")
    path = (await asyncio.to_thread(put_object, f"{APP_NAME}/brand/{uuid.uuid4()}.{ext}", data, MIME[ext]))["path"]
    await db.settings.update_one({"id": "brand"}, {"$set": {"logo_path": path}}, upsert=True)
    return {"logo_path": path}


@api.get("/settings/brand/logo")
async def get_logo():
    b = await get_brand()
    if not b.get("logo_path"):
        raise HTTPException(404, "No logo")
    return Response(content=await fetch(b["logo_path"]), media_type=MIME[b["logo_path"].rsplit(".", 1)[-1]])


@api.delete("/settings/brand/logo")
async def delete_logo():
    await db.settings.update_one({"id": "brand"}, {"$unset": {"logo_path": ""}})
    return {"ok": True}


@api.post("/projects/{pid}/report")
async def report(pid: str, body: ReportIn):
    p = await get_project(pid)
    tools = p.get("tools") or {}
    q = {"project_id": pid, "status": "ready", "analysis": {"$ne": None}}
    packet = None
    if body.crew != "full":
        if body.crew not in CREWS:
            raise HTTPException(400, "Unknown crew")
        t = tools.get(f"crew_{body.crew}") or {}
        if t.get("status") != "ready":
            raise HTTPException(400, "Prepare the crew packet first")
        packet = t["data"]
        q["index"] = {"$in": [int(n) - 1 for n in packet.get("sheets", []) if str(n).isdigit() and int(n) > 0]}
    elif body.pages is not None:
        q["index"] = {"$in": body.pages}
    pages = await db.pages.find(q, PAGE_LIST).sort("index", 1).to_list(2000)
    if not pages and not packet:
        raise HTTPException(400, "No scanned sheets yet — scan the set first")
    stored = await get_brand()
    given = body.brand.model_dump(exclude_unset=True) if "brand" in body.model_fields_set else {}
    brand = {**stored, **given}
    if given:
        await db.settings.update_one({"id": "brand"}, {"$set": given}, upsert=True)
    logo = await fetch(stored["logo_path"]) if stored.get("logo_path") else None
    images = {pg["index"]: await fetch(pg["image_path"]) for pg in pages} if body.include_images else {}
    qa = []
    if body.include_qa and body.crew == "full":
        msgs = await db.messages.find({"project_id": pid}, NO_ID).sort("created_at", 1).to_list(1000)
        qa = [(m["content"], n["content"]) for m, n in zip(msgs, msgs[1:]) if m["role"] == "user" and n["role"] == "assistant"]
    extras = {"crew": body.crew, "packet": packet}
    if body.crew in ("full", "foundation", "icf") and (tools.get("icf") or {}).get("status") == "ready":
        extras["icf"] = tools["icf"]["data"]
    if body.crew in ("full", "foundation", "waterproofing") and (tools.get("waterproofing") or {}).get("status") == "ready":
        extras["wp"] = tools["waterproofing"]["data"]
    if body.crew in ("full", "foundation", "waterproofing") and (tools.get("drainage") or {}).get("status") == "ready":
        extras["drain"] = tools["drainage"]["data"]
        drawn = await db.pages.find({"project_id": pid, "drain_status": "ready"}, PAGE_LIST).sort("index", 1).to_list(20)
        extras["drain_images"] = [(sheet_label(pg), await asyncio.to_thread(render_overlay, await fetch(pg["image_path"]), pg["drain_overlay"]),
                                   pg["drain_overlay"].get("notes") or []) for pg in drawn if pg["drain_overlay"].get("is_foundation", True)]
    pdf = await asyncio.to_thread(build_report, p, pages, images, brand, logo, qa, extras)
    suffix = "takeoff_report" if body.crew == "full" else f"{body.crew}_crew_packet"
    fname = re.sub(r"[^A-Za-z0-9_-]+", "_", p["name"])[:60] + f"_{suffix}.pdf"
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{fname}"'})


def set_context(pages: list) -> str:
    slim = {sheet_label(pg): {k: v for k, v in pg["analysis"].items() if k != "digest"} for pg in pages if pg.get("analysis")}
    notes = [f"=== {sheet_label(pg)} (page {pg['index'] + 1}) ===\n"
             f"{((pg.get('analysis') or {}).get('digest') or (pg.get('text') or '')[:2500]).strip() or '(no readable text)'}"
             for pg in pages]
    return (f"PRIOR TAKEOFFS (JSON):\n{json.dumps(slim)[:60000]}\n\nSHEET TRANSCRIPTIONS:\n" + "\n\n".join(notes)[:250000])


async def picked_sources(pages: list, query: str, k: int = 4, budget: int = 30 * 1024 * 1024) -> list:
    by_num = {pg["index"] + 1: pg for pg in pages}
    chosen = [by_num[n] for n in await pick_sheets(query, catalog(pages), k) if n in by_num]
    out, size = [], 0
    for pg in chosen:
        data, ext, mime = await ai_source(pg)
        if out and size + len(data) > budget:
            break
        size += len(data)
        out.append((data, ext, mime))
    return out


async def project_pages(pid: str) -> list:
    return await db.pages.find({"project_id": pid}, NO_ID).sort("index", 1).to_list(2000)


async def set_tool(pid: str, tool: str, fields: dict):
    await db.projects.update_one({"id": pid}, {"$set": {f"tools.{tool}.{k}": v for k, v in fields.items()}})


async def run_tool(pid: str, tool: str):
    try:
        pages = await project_pages(pid)
        srcs = await picked_sources(pages, TOOL_QUERY[tool])
        with ExitStack() as st:
            files = [(st.enter_context(temp_file(d, e)), m) for d, e, m in srcs]
            prompt = {"icf": ICF_PROMPT, "waterproofing": WP_PROMPT, "drainage": DRAIN_PROMPT}.get(tool) or crew_prompt(tool[5:])
            data = await set_json(prompt, set_context(pages), files)
        if tool == "icf":
            data = {"extract": data, "calc": icf_compute(data.get("walls", []), data.get("footings", []), {})}
        if tool in CHECKLISTS:
            prev = ((await db.projects.find_one({"id": pid}, {"_id": 0, f"tools.{tool}.data.items": 1})) or {})
            prev_items = (((prev.get("tools") or {}).get(tool) or {}).get("data") or {}).get("items") or []
            done = {(i.get("category", "").lower(), i.get("item", "").lower()) for i in prev_items if i.get("verified")}
            for it in data.get("items", []):
                it["verified"] = (it.get("category", "").lower(), it.get("item", "").lower()) in done
        await set_tool(pid, tool, {"status": "ready", "data": data, "error": None, "updated_at": now()})
    except Exception as e:
        logger.exception(f"tool {tool} failed")
        await set_tool(pid, tool, {"status": "failed", "error": str(e)[:300]})


@api.post("/projects/{pid}/tools/{tool}")
async def start_tool(pid: str, tool: str, background: BackgroundTasks):
    p = await get_project(pid)
    if tool not in TOOLS:
        raise HTTPException(404, "Unknown tool")
    if p["status"] != "ready":
        raise HTTPException(400, "Plans are still processing")
    if ((p.get("tools") or {}).get(tool) or {}).get("status") == "running":
        raise HTTPException(409, "Already running")
    await set_tool(pid, tool, {"status": "running", "error": None})
    background.add_task(run_tool, pid, tool)
    return {"status": "running"}


@api.put("/projects/{pid}/tools/icf")
async def edit_icf(pid: str, body: IcfEdit):
    p = await get_project(pid)
    t = (p.get("tools") or {}).get("icf") or {}
    if t.get("status") != "ready":
        raise HTTPException(400, "Build the ICF estimate first")
    data = t["data"]
    data["extract"]["walls"], data["extract"]["footings"] = body.walls, body.footings
    data["calc"] = icf_compute(body.walls, body.footings, body.params)
    await set_tool(pid, "icf", {"data": data})
    return data


@api.patch("/projects/{pid}/tools/{tool}/items/{i}")
async def patch_wp(pid: str, tool: str, i: int, body: WpPatch):
    if tool not in CHECKLISTS:
        raise HTTPException(404, "Unknown checklist")
    p = await get_project(pid)
    items = (((p.get("tools") or {}).get(tool) or {}).get("data") or {}).get("items") or []
    if not 0 <= i < len(items):
        raise HTTPException(404, "Item not found")
    await db.projects.update_one({"id": pid}, {"$set": {f"tools.{tool}.data.items.{i}.verified": body.verified}})
    return {"ok": True}


PHOTO_EXT = {"png", "jpg", "jpeg", "webp"}


async def photo_inputs(pid: str, photo: dict, query: str):
    pages = await project_pages(pid)
    srcs = await picked_sources(pages, query, k=3, budget=25 * 1024 * 1024) if pages else []
    return pages, [(await fetch(photo["image_path"]), "jpg", "image/jpeg"), *srcs]


async def run_photo(photo_id: str, question: str | None = None):
    photo = await db.photos.find_one({"id": photo_id}, NO_ID)
    try:
        pages, srcs = await photo_inputs(photo["project_id"], photo, question or photo.get("note") or "site photo construction progress")
        with ExitStack() as st:
            files = [(st.enter_context(temp_file(d, e)), m) for d, e, m in srcs]
            ctx = set_context(pages) if pages else "(no plan sheets)"
            if question:
                answer = await photo_followup(json.dumps(photo.get("analysis")), question, ctx, files)
                await db.photos.update_one({"id": photo_id}, {"$set": {"status": "ready"},
                                                              "$push": {"thread": {"q": question, "a": answer, "created_at": now()}}})
                return
            analysis = await analyze_photo(photo.get("note", ""), ctx, files)
        await db.photos.update_one({"id": photo_id}, {"$set": {"status": "ready", "analysis": analysis, "error": None}})
    except Exception as e:
        logger.exception("photo analysis failed")
        if question:
            await db.photos.update_one({"id": photo_id}, {"$set": {"status": "ready"}, "$push": {"thread": {
                "q": question, "a": "_Sorry — that answer failed. Please ask again._", "created_at": now()}}})
            return
        await db.photos.update_one({"id": photo_id}, {"$set": {"status": "failed", "error": str(e)[:300]}})


@api.post("/projects/{pid}/photos")
async def upload_photo(pid: str, background: BackgroundTasks, file: UploadFile = File(...), note: str = Form("")):
    await get_project(pid)
    ext = (file.filename or "").rsplit(".", 1)[-1].lower()
    if ext not in PHOTO_EXT:
        raise HTTPException(400, "Photo must be JPG, PNG or WEBP")
    raw = await file.read()
    if len(raw) > 25 * 1024 * 1024:
        raise HTTPException(400, "Photo must be under 25 MB")
    try:
        img = ImageOps.exif_transpose(Image.open(io.BytesIO(raw))).convert("RGB")
    except Exception:
        raise HTTPException(400, "Not a valid image")
    img.thumbnail((2000, 2000))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=85)
    path = (await asyncio.to_thread(put_object, f"{APP_NAME}/photos/{pid}/{uuid.uuid4()}.jpg", buf.getvalue(), "image/jpeg"))["path"]
    doc = {"id": str(uuid.uuid4()), "project_id": pid, "image_path": path, "note": note.strip(), "original_filename": file.filename,
           "status": "analyzing", "analysis": None, "error": None, "thread": [], "is_deleted": False, "created_at": now()}
    await db.photos.insert_one(doc)
    background.add_task(run_photo, doc["id"])
    doc.pop("_id", None)
    return doc


@api.get("/projects/{pid}/photos")
async def list_photos(pid: str):
    return await db.photos.find({"project_id": pid, "is_deleted": False}, NO_ID).sort("created_at", -1).to_list(500)


async def get_photo(photo_id: str) -> dict:
    ph = await db.photos.find_one({"id": photo_id, "is_deleted": False}, NO_ID)
    if not ph:
        raise HTTPException(404, "Photo not found")
    return ph


@api.get("/photos/{photo_id}/image")
async def photo_image(photo_id: str):
    ph = await get_photo(photo_id)
    return Response(content=await fetch(ph["image_path"]), media_type="image/jpeg", headers={"Cache-Control": "private, max-age=86400"})


@api.post("/photos/{photo_id}/ask")
async def ask_photo(photo_id: str, body: PhotoAsk, background: BackgroundTasks):
    ph = await get_photo(photo_id)
    if ph["status"] != "ready" or not body.question.strip():
        raise HTTPException(400, "Photo is not ready or question is empty")
    await db.photos.update_one({"id": photo_id}, {"$set": {"status": "answering"}})
    background.add_task(run_photo, photo_id, body.question.strip())
    return {"status": "answering"}


@api.post("/photos/{photo_id}/reanalyze")
async def reanalyze_photo(photo_id: str, background: BackgroundTasks):
    await get_photo(photo_id)
    await db.photos.update_one({"id": photo_id}, {"$set": {"status": "analyzing", "error": None}})
    background.add_task(run_photo, photo_id)
    return {"status": "analyzing"}


@api.delete("/photos/{photo_id}")
async def delete_photo(photo_id: str):
    await get_photo(photo_id)
    await db.photos.update_one({"id": photo_id}, {"$set": {"is_deleted": True}})
    return {"ok": True}


@api.post("/projects/{pid}/pages/{idx}/drain-overlay")
async def start_drain(pid: str, idx: int, background: BackgroundTasks):
    pg = await get_page(pid, idx)
    if pg.get("drain_status") == "generating":
        raise HTTPException(409, "Already drawing")
    await set_page(pid, idx, {"drain_status": "generating", "drain_error": None})
    background.add_task(run_drain, pid, idx)
    return {"drain_status": "generating"}


@api.get("/projects/{pid}/pages/{idx}/drain-overlay.png")
async def drain_png(pid: str, idx: int):
    pg = await get_page(pid, idx)
    if pg.get("drain_status") != "ready":
        raise HTTPException(404, "No drain tile layout for this sheet")
    png = await asyncio.to_thread(render_overlay, await fetch(pg["image_path"]), pg["drain_overlay"])
    return Response(content=png, media_type="image/png",
                    headers={"Content-Disposition": f'attachment; filename="drain_tile_{re.sub(r"[^A-Za-z0-9_-]+", "_", sheet_label(pg))}.png"'})


@api.post("/projects/{pid}/pages/{idx}/model3d")
async def model_page(pid: str, idx: int, background: BackgroundTasks):
    await get_page(pid, idx, PAGE_LIST)
    await set_page(pid, idx, {"model3d_status": "generating", "model3d_error": None})
    background.add_task(run_model3d, pid, idx)
    return {"model3d_status": "generating"}


@api.get("/projects/{pid}/messages")
async def messages(pid: str):
    return await db.messages.find({"project_id": pid}, NO_ID).sort("created_at", 1).to_list(1000)


def relevant_pages(pages: list, question: str, exclude: int, k: int = 2) -> list:
    words = {w for w in re.findall(r"[a-z0-9]{4,}", question.lower())}
    scored = []
    for pg in pages:
        if pg["index"] == exclude or not words:
            continue
        hay = f"{pg.get('title', '')} {pg.get('discipline', '')} {pg.get('text', '')}".lower()
        score = sum(hay.count(w) for w in words) + 5 * sum(w in pg.get("title", "").lower() for w in words)
        if score:
            scored.append((score, pg))
    return [pg for _, pg in sorted(scored, key=lambda x: -x[0])[:k]]


def build_context(pages: list, current: dict, extra: list, scope: str = "sheet") -> str:
    index = "\n".join(f"- Page {pg['index'] + 1}: {sheet_label(pg)} [{pg.get('discipline', '')}]" for pg in pages)
    slim = {sheet_label(pg): {k: v for k, v in pg["analysis"].items() if k != "digest"} for pg in pages if pg.get("analysis")}
    takeoffs = json.dumps(slim)[:60000]
    attached = ", ".join(sheet_label(pg) for pg in [current, *extra])
    ctx = (f"PLAN SET SHEET INDEX:\n{index}\n\nATTACHED SHEET IMAGES/PDFs (in order): {attached}\n"
           f"The user is currently viewing: {sheet_label(current)}\n\nPRIOR TAKEOFFS (JSON):\n{takeoffs or '(none yet)'}")
    if scope == "set":
        notes = []
        for pg in pages:
            body = (pg.get("analysis") or {}).get("digest") or (pg.get("text") or "")[:2500]
            notes.append(f"=== {sheet_label(pg)} (page {pg['index'] + 1}) ===\n{body.strip() or '(no readable text; not scanned yet)'}")
        ctx += ("\n\nFULL-SET SEARCH: the question applies to the ENTIRE plan set. Below is the transcribed content of every sheet. "
                "Search all of it, combine information across sheets, and cite every sheet you used.\n\n" + "\n\n".join(notes)[:250000])
    return ctx


def catalog(pages: list) -> str:
    lines = []
    for pg in pages:
        body = ((pg.get("analysis") or {}).get("digest") or pg.get("text") or "").replace("\n", " ")
        lines.append(f"Page {pg['index'] + 1}: {sheet_label(pg)} [{pg.get('discipline', '')}] — {body[:350]}")
    return "\n".join(lines)


@api.post("/projects/{pid}/chat")
async def chat(pid: str, body: ChatIn):
    p = await get_project(pid)
    question = body.message.strip()
    if not question:
        raise HTTPException(400, "Message is empty")
    if p["status"] != "ready":
        raise HTTPException(400, "Plans are still processing")
    pages = await db.pages.find({"project_id": pid}, NO_ID).sort("index", 1).to_list(2000)
    if not pages:
        raise HTTPException(400, "No sheets in this project")
    current = next((pg for pg in pages if pg["index"] == body.page_index), pages[0])
    scope = "set" if body.scope == "set" and len(pages) > 1 else "sheet"
    history = await db.messages.find({"project_id": pid}, NO_ID).sort("created_at", 1).to_list(1000)
    user_msg_id = str(uuid.uuid4())
    await db.messages.insert_one({"id": user_msg_id, "project_id": pid, "role": "user", "content": question,
                                  "page_index": current["index"], "scope": scope, "created_at": now()})

    async def events():
        answer = ""
        paths = []
        used = []
        try:
            if scope == "set":
                scanned = sum(1 for pg in pages if (pg.get("analysis") or {}).get("digest"))
                yield f"data: {json.dumps({'status': f'Searching all {len(pages)} sheets ({scanned} fully scanned)…'})}\n\n"
                picks = await pick_sheets(question, catalog(pages))
                by_num = {pg["index"] + 1: pg for pg in pages}
                chosen = [by_num[n] for n in picks if n in by_num] or [current]
            else:
                chosen = [current, *relevant_pages(pages, question, current["index"])]
            sources = []
            for pg in chosen:
                src = await ai_source(pg)
                if sources and sum(len(s[0]) for s in sources) + len(src[0]) > 30 * 1024 * 1024:
                    break
                sources.append(src)
                used.append(pg)
            yield f"data: {json.dumps({'sources': [sheet_label(pg) for pg in used]})}\n\n"
            for data, ext, _ in sources:
                path = Path(tempfile.gettempdir()) / f"{uuid.uuid4()}.{ext}"
                path.write_bytes(data)
                paths.append(str(path))
            files = [(path, mime) for path, (_, _, mime) in zip(paths, sources)]
            context = build_context(pages, used[0], used[1:], scope)
            async for tok in stream_chat(files, context, history, question):
                answer += tok
                yield f"data: {json.dumps({'delta': tok})}\n\n"
        except Exception as e:
            logger.exception("chat failed")
            yield f"data: {json.dumps({'error': str(e)[:200]})}\n\n"
        finally:
            for path in paths:
                Path(path).unlink(missing_ok=True)
        if answer:
            await db.messages.insert_one({"id": str(uuid.uuid4()), "project_id": pid, "role": "assistant", "content": answer,
                                          "sources": [sheet_label(pg) for pg in used], "created_at": now()})
        else:
            await db.messages.delete_one({"id": user_msg_id})
        yield f"data: {json.dumps({'done': True})}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


async def cleanup_uploads():
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=6)).isoformat()
    async for up in db.uploads.find({"created_at": {"$lt": cutoff}}, NO_ID):
        (UPLOAD_DIR / up["id"]).unlink(missing_ok=True)
        await db.uploads.delete_one({"id": up["id"]})
    await db.projects.update_many({"status": "processing", "updated_at": {"$lt": cutoff}},
                                  {"$set": {"status": "failed", "error": "Processing was interrupted — please re-upload."}})


async def migrate_legacy():
    await cleanup_uploads()
    await db.pages.update_many({"status": "analyzing"}, {"$set": {"status": "pending"}})
    await db.pages.update_many({"model3d_status": "generating"}, {"$set": {"model3d_status": "none"}})
    await db.pages.update_many({"drain_status": "generating"}, {"$set": {"drain_status": "failed", "drain_error": "Interrupted — draw again"}})
    for tool in TOOLS:
        await db.projects.update_many({f"tools.{tool}.status": "running"},
                                      {"$set": {f"tools.{tool}.status": "failed", f"tools.{tool}.error": "Interrupted — run again"}})
    await db.photos.update_many({"status": {"$in": ["analyzing", "answering"]}}, {"$set": {"status": "failed", "error": "Interrupted — re-run"}})
    async for p in db.projects.find({"page_count": {"$exists": False}, "storage_path": {"$exists": True}}, NO_ID):
        try:
            data = await fetch(p["storage_path"])
            w, h = Image.open(io.BytesIO(data)).size if p["ext"] != "pdf" else (0, 0)
        except Exception:
            w, h = 0, 0
        await db.pages.insert_one({"project_id": p["id"], "index": 0, "image_path": p["storage_path"], "pdf_path": None,
                                   "pdf_size": 0, "img_w": w, "img_h": h, "text": "", "sheet_number": "",
                                   "title": p["name"], "discipline": "",
                                   "status": "ready" if p.get("analysis") else "pending", "analysis": p.get("analysis"),
                                   "error": None, "model3d_status": "none", "model3d": None})
        await db.projects.update_one({"id": p["id"]}, {"$set": {"page_count": 1, "processed_pages": 1, "status": "ready"},
                                                       "$unset": {"analysis": ""}})
    async for pg in db.pages.find({"pdf_path": None, "image_path": {"$regex": r"\.pdf$"}}, NO_ID):
        pid = pg["project_id"]
        try:
            tmp = UPLOAD_DIR / f"{pid}.pdf"
            tmp.write_bytes(await fetch(pg["image_path"]))
            await db.pages.delete_many({"project_id": pid})
            await db.projects.update_one({"id": pid}, {"$set": {"status": "processing", "processed_pages": 0}})
            await process_project(pid, tmp)
            if pg.get("analysis") and await db.pages.count_documents({"project_id": pid}) == 1:
                await set_page(pid, 0, {"analysis": pg["analysis"], "status": "ready"})
        except Exception:
            logger.exception(f"legacy pdf repair failed for {pid}")



app.include_router(api)
app.add_middleware(CORSMiddleware, allow_credentials=True,
                   allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
                   allow_methods=["*"], allow_headers=["*"])


@app.on_event("startup")
async def startup():
    try:
        init_storage()
        logger.info("Storage initialized")
        asyncio.create_task(migrate_legacy())
    except Exception as e:
        logger.error(f"Storage init failed: {e}")


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
