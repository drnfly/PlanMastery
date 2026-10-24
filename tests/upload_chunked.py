import os
import sys
import json
import requests

API = sys.argv[1] + "/api"
path = sys.argv[2]
size = os.path.getsize(path)
uid = requests.post(f"{API}/uploads/init", json={"filename": os.path.basename(path), "size": size}).json()["upload_id"]
CH = 4 * 1024 * 1024
with open(path, "rb") as f:
    n = 0
    while chunk := f.read(CH):
        r = requests.put(f"{API}/uploads/{uid}/chunk/{n}", data=chunk)
        r.raise_for_status()
        n += 1
print(json.dumps(requests.post(f"{API}/uploads/{uid}/complete", json={"name": "Smith Residence Set"}).json()))
