# Generates a ~30MB multi-page plan set PDF (noisy high-res images + title blocks) for large-upload testing
import io
import sys
import numpy as np
import pymupdf
from PIL import Image

out = sys.argv[1] if len(sys.argv) > 1 else "/tmp/TEST_large_planset.pdf"
sheets = [("A-000", "COVER SHEET"), ("A-101", "FIRST FLOOR PLAN"), ("A-102", "SECOND FLOOR PLAN"),
          ("S-201", "FOUNDATION PLAN"), ("S-301", "ICF WALL SECTIONS"), ("A-501", "WATERPROOFING DETAILS")]
rng = np.random.default_rng(1)
doc = pymupdf.open()
for i, (num, title) in enumerate(sheets):
    p = doc.new_page(width=1728, height=1152)
    if i in (0, 4, 5):
        arr = rng.integers(0, 255, (1700, 2000, 3), dtype=np.uint8)
        buf = io.BytesIO()
        Image.fromarray(arr).save(buf, "PNG", compress_level=1)
        p.insert_image(pymupdf.Rect(60, 60, 900, 640), stream=buf.getvalue())
    if num == "A-101":
        p.insert_image(pymupdf.Rect(100, 80, 1500, 1080), filename="/app/tests/sample_floorplan.png")
    if num == "S-201":
        p.draw_rect(pymupdf.Rect(300, 200, 1300, 950), width=6)
        p.insert_text((650, 180), "40'-0\"", fontsize=22)
        p.insert_text((180, 580), "30'-0\"", fontsize=22)
        p.insert_text((400, 400), "ICF FOUNDATION WALL 8\" CORE, FOOTING 24\" x 12\"", fontsize=18)
    p.insert_text((1100, 1060), "TEST LARGE RESIDENCE - CONSTRUCTION DOCUMENTS", fontsize=16)
    p.insert_text((1300, 1100), f"{num} {title}", fontsize=24)
doc.save(out, deflate=False)
print(out)
