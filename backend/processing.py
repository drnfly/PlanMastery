import io
import pymupdf
from PIL import Image
from storage import put_object, APP_NAME

MAX_SIDE = 3000


def open_pdf(path: str):
    return pymupdf.open(path)


def process_pdf_page(doc, i: int, pid: str) -> dict:
    page = doc[i]
    zoom = min(MAX_SIDE / max(page.rect.width, page.rect.height), 4)
    pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False)
    single = pymupdf.open()
    single.insert_pdf(doc, from_page=i, to_page=i)
    pdf_bytes = single.tobytes(garbage=3, deflate=True)
    single.close()
    img_path = put_object(f"{APP_NAME}/pages/{pid}/{i}.png", pix.tobytes("png"), "image/png")["path"]
    pdf_path = put_object(f"{APP_NAME}/pages/{pid}/{i}.pdf", pdf_bytes, "application/pdf")["path"]
    return {"index": i, "image_path": img_path, "pdf_path": pdf_path, "pdf_size": len(pdf_bytes),
            "img_w": pix.width, "img_h": pix.height, "text": page.get_text()[:6000]}


def process_image(data: bytes, pid: str, ext: str, mime: str) -> dict:
    w, h = Image.open(io.BytesIO(data)).size
    img_path = put_object(f"{APP_NAME}/pages/{pid}/0.{ext}", data, mime)["path"]
    return {"index": 0, "image_path": img_path, "pdf_path": None, "pdf_size": 0, "img_w": w, "img_h": h, "text": ""}
