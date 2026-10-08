from fastapi import FastAPI, APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import Response, StreamingResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel
from pathlib import Path
from datetime import datetime, timezone
import os
import json
import uuid
import logging
import asyncio

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

from storage import init_storage, put_object, get_object, APP_NAME  # noqa: E402
from ai import analyze_blueprint, stream_chat  # noqa: E402

client = AsyncIOMotorClient(os.environ['MONGO_URL'])
db = client[os.environ['DB_NAME']]

app = FastAPI()
api = APIRouter(prefix="/api")
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

MIME = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "webp": "image/webp", "pdf": "application/pdf"}
MAX_BYTES = 20 * 1024 * 1024
PROJ_FIELDS = {"_id": 0}


def now():
    return datetime.now(timezone.utc).isoformat()


class ChatIn(BaseModel):
    message: str


async def get_project(pid: str) -> dict:
    p = await db.projects.find_one({"id": pid, "is_deleted": False}, PROJ_FIELDS)
    if not p:
        raise HTTPException(404, "Project not found")
    return p


async def load_file(p: dict) -> bytes:
    data, _ = await asyncio.to_thread(get_object, p["storage_path"])
    return data


async def run_analysis(pid: str, data: bytes):
    p = await db.projects.find_one({"id": pid}, PROJ_FIELDS)
    try:
        result = await analyze_blueprint(data, p["ext"], p["content_type"], p.get("scale_hint", ""))
        await db.projects.update_one({"id": pid}, {"$set": {"status": "ready", "analysis": result, "updated_at": now()}})
    except Exception as e:
        logger.exception("analysis failed")
        await db.projects.update_one({"id": pid}, {"$set": {"status": "failed", "error": str(e)[:300], "updated_at": now()}})


@api.get("/")
async def root():
    return {"message": "Blueprint AI"}


@api.post("/projects")
async def create_project(background: BackgroundTasks, file: UploadFile = File(...),
                         name: str = Form(""), scale_hint: str = Form("")):
    ext = (file.filename.rsplit(".", 1)[-1] if "." in file.filename else "").lower()
    if ext not in MIME:
        raise HTTPException(400, "Unsupported file type. Use PNG, JPG, WEBP or PDF.")
    data = await file.read()
    if not data or len(data) > MAX_BYTES:
        raise HTTPException(400, "File must be between 1 byte and 20 MB.")
    pid = str(uuid.uuid4())
    stored = await asyncio.to_thread(put_object, f"{APP_NAME}/uploads/{pid}.{ext}", data, MIME[ext])
    doc = {"id": pid, "name": name.strip() or file.filename.rsplit(".", 1)[0], "original_filename": file.filename,
           "storage_path": stored["path"], "content_type": MIME[ext], "ext": ext, "size": len(data),
           "scale_hint": scale_hint.strip(), "status": "analyzing", "analysis": None, "error": None,
           "is_deleted": False, "created_at": now(), "updated_at": now()}
    await db.projects.insert_one(doc.copy())
    background.add_task(run_analysis, pid, data)
    return doc


@api.get("/projects")
async def list_projects():
    return await db.projects.find({"is_deleted": False}, {"_id": 0, "analysis": 0}).sort("created_at", -1).to_list(500)


@api.get("/projects/{pid}")
async def project_detail(pid: str):
    return await get_project(pid)


@api.post("/projects/{pid}/reanalyze")
async def reanalyze(pid: str, background: BackgroundTasks):
    p = await get_project(pid)
    data = await load_file(p)
    await db.projects.update_one({"id": pid}, {"$set": {"status": "analyzing", "error": None}})
    background.add_task(run_analysis, pid, data)
    return {"status": "analyzing"}


@api.delete("/projects/{pid}")
async def delete_project(pid: str):
    await get_project(pid)
    await db.projects.update_one({"id": pid}, {"$set": {"is_deleted": True}})
    return {"ok": True}


@api.get("/projects/{pid}/file")
async def project_file(pid: str):
    p = await get_project(pid)
    return Response(content=await load_file(p), media_type=p["content_type"])


@api.get("/projects/{pid}/messages")
async def messages(pid: str):
    return await db.messages.find({"project_id": pid}, {"_id": 0}).sort("created_at", 1).to_list(1000)


@api.post("/projects/{pid}/chat")
async def chat(pid: str, body: ChatIn):
    p = await get_project(pid)
    question = body.message.strip()
    if not question:
        raise HTTPException(400, "Message is empty")
    history = await db.messages.find({"project_id": pid}, {"_id": 0}).sort("created_at", 1).to_list(1000)
    data = await load_file(p)
    await db.messages.insert_one({"id": str(uuid.uuid4()), "project_id": pid, "role": "user",
                                  "content": question, "created_at": now()})

    async def events():
        answer = ""
        try:
            async for tok in stream_chat(data, p["ext"], p["content_type"], p.get("analysis") or {}, history, question):
                answer += tok
                yield f"data: {json.dumps({'delta': tok})}\n\n"
        except Exception as e:
            logger.exception("chat failed")
            yield f"data: {json.dumps({'error': str(e)[:200]})}\n\n"
        if answer:
            await db.messages.insert_one({"id": str(uuid.uuid4()), "project_id": pid, "role": "assistant",
                                          "content": answer, "created_at": now()})
        yield f"data: {json.dumps({'done': True})}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


app.include_router(api)
app.add_middleware(CORSMiddleware, allow_credentials=True,
                   allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
                   allow_methods=["*"], allow_headers=["*"])


@app.on_event("startup")
async def startup():
    try:
        init_storage()
        logger.info("Storage initialized")
    except Exception as e:
        logger.error(f"Storage init failed: {e}")


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
