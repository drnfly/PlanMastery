# Snapshot / restore drain fields of TEST_Iter4 pages (iteration 10 helper, not a test)
import sys, json, asyncio, os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
load_dotenv("/app/backend/.env")
PID = "21f16323-6b5c-4d5b-b541-9d61852f4d55"
F = ["drain_status", "drain_overlay", "drain_error"]
PATH = "/tmp/iter10_snapshot.json"


async def main(mode):
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    if mode == "save":
        out = {}
        async for p in db.pages.find({"project_id": PID}, {"_id": 0, "index": 1, **{f: 1 for f in F}}):
            out[str(p["index"])] = {f: p.get(f, "__missing__") for f in F}
        json.dump(out, open(PATH, "w"), default=str)
        for k, v in out.items():
            ov = v["drain_overlay"] if isinstance(v["drain_overlay"], dict) else {}
            print(k, v["drain_status"], "len", ov.get("length_ft"), "tile", len(ov.get("drain_tile") or []), "ai_original", bool(ov.get("ai_original")), "edited", ov.get("edited"))
        proj = await db.projects.find_one({"id": PID}, {"_id": 0, "name": 1, "tools.drain_takeoff": 1})
        print(proj)
    elif mode.startswith("restore"):
        idx = mode[-1]
        snap = json.load(open(PATH))[idx]
        st, un = {}, {}
        for f in F:
            (un.__setitem__(f, "") if snap[f] == "__missing__" else st.__setitem__(f, snap[f]))
        upd = {}
        if st: upd["$set"] = st
        if un: upd["$unset"] = un
        r = await db.pages.update_one({"project_id": PID, "index": int(idx)}, upd)
        print("restored page", idx, r.modified_count, upd)

asyncio.run(main(sys.argv[1]))
