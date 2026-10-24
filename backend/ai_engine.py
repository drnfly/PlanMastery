import os
import json
import re
import tempfile
import uuid
from contextlib import contextmanager
from emergentintegrations.llm.chat import LlmChat, UserMessage, FileContentWithMimeType, TextDelta, StreamDone

MODEL = ("gemini", "gemini-3.1-pro-preview")

EXPERT = """You are a senior licensed Structural Engineer (PE/SE) and registered Architect with 25+ years of field experience,
and a nationally recognized specialist in ICF (Insulated Concrete Form) construction and building waterproofing
(below-grade foundations, ICF wall assemblies, membranes, drainage boards, flashing, envelope transitions, roofing and air/vapor barriers).
You read construction drawings with extreme precision: dimension strings, grid lines, room tags, door/window schedules,
structural notes, rebar callouts, footing/foundation details, wall sections, and general notes.
Never invent values. Distinguish clearly between what is LABELED on the drawings and what you DERIVE or RECOMMEND."""

ANALYSIS_PROMPT = """Analyze this construction drawing sheet ({sheet}) and return ONLY valid JSON (no markdown fences) with this exact shape:
{{
  "title": "short drawing title",
  "drawing_type": "floor plan | foundation plan | framing plan | site plan | elevation | section | detail | schedule | other",
  "units": "imperial | metric",
  "scale": "scale as noted or 'not noted'",
  "overall": {{"width": "", "length": "", "total_area": ""}},
  "rooms": [{{"name": "", "width": "", "length": "", "area": "", "ceiling_height": "", "source": "labeled | derived", "notes": ""}}],
  "walls": [{{"id": "W1", "location": "", "length": "", "thickness": "", "type": "exterior | interior | load-bearing | partition | ICF | foundation", "source": "labeled | derived", "notes": ""}}],
  "openings": [{{"id": "D1", "type": "door | window | opening", "location": "", "width": "", "height": "", "source": "labeled | derived", "notes": ""}}],
  "summary": "2-4 sentence plain-English summary of this sheet, including any structural, ICF or waterproofing items",
  "warnings": ["ambiguities, unreadable dimensions, code or constructability concerns"]
}}
Keep native notation (e.g. 12'-6"). Use empty strings for unknown fields and empty arrays when the sheet has no such items.{hint}"""

MODEL3D_PROMPT = """This is a construction drawing sheet ({sheet}). Trace the WALLS of the main floor plan on this image for a 3D model.
Coordinates are normalized 0-1000 relative to the full image: x from the left edge, y from the top edge.
Return ONLY valid JSON (no markdown fences):
{{
  "is_plan": true,
  "plan_bbox": {{"x1": 0, "y1": 0, "x2": 0, "y2": 0}},
  "plan_width_ft": 0,
  "wall_height_ft": 9,
  "walls": [{{"x1": 0, "y1": 0, "x2": 0, "y2": 0, "type": "exterior | interior", "thickness_in": 6}}],
  "openings": [{{"x": 0, "y": 0, "type": "door | window", "width_ft": 3}}]
}}
plan_bbox is the outer footprint of the building; plan_width_ft is the real-world horizontal width of that footprint read from the dimensions.
Each wall is a straight centerline segment; split walls at corners and intersections. Include every exterior and interior wall.
wall_height_ft: use labeled plate/ceiling height, else 9. If this sheet has no floor plan, set "is_plan": false and empty arrays."""

INDEX_PROMPT = """Below are text excerpts extracted from each page of a construction plan set. Identify every sheet.
Return ONLY a JSON array (no markdown fences): [{"page": 1, "sheet_number": "A-101", "title": "First Floor Plan", "discipline": "Architectural | Structural | Civil | MEP | Landscape | General | Other"}]
Include one entry per page listed. If unclear, use sheet_number "" and a best-guess title.

"""

CHAT_RULES = """Answer anything about these plans as the expert above: dimensions, areas, quantities, load paths, beams/headers,
footings, rebar, ICF wall systems (core size, block courses, bracing, pour heights, embedments), waterproofing and drainage
details, code considerations, constructability and sequencing. Show your math. Cite sheet numbers. State which values are
labeled vs derived. If the drawings do not show something, say so and give a professional recommendation. Be concise; use markdown.
For life-safety structural decisions, note that a licensed engineer of record must verify."""


@contextmanager
def temp_file(data: bytes, ext: str):
    path = os.path.join(tempfile.gettempdir(), f"{uuid.uuid4()}.{ext}")
    with open(path, "wb") as f:
        f.write(data)
    try:
        yield path
    finally:
        os.remove(path)


def _chat(system: str) -> LlmChat:
    return LlmChat(api_key=os.environ["EMERGENT_LLM_KEY"], session_id=str(uuid.uuid4()),
                   system_message=system).with_model(*MODEL)


async def _stream(system: str, text: str, files: list):
    msg = UserMessage(text=text, file_contents=[FileContentWithMimeType(file_path=p, mime_type=m) for p, m in files])
    async for ev in _chat(system).stream_message(msg):
        if isinstance(ev, TextDelta):
            yield ev.content
        elif isinstance(ev, StreamDone):
            break


async def _collect(system: str, text: str, files: list) -> str:
    return "".join([t async for t in _stream(system, text, files)])


def _parse(text: str, opener: str = "{", closer: str = "}"):
    cleaned = re.sub(r"```(?:json)?", "", text).strip()
    return json.loads(cleaned[cleaned.find(opener):cleaned.rfind(closer) + 1])


async def index_sheets(pages: list) -> list:
    out = []
    for i in range(0, len(pages), 40):
        batch = pages[i:i + 40]
        body = "\n\n".join(f"--- PAGE {p['page']} ---\n{p['text'][:400]}\n...\n{p['text'][-400:]}" for p in batch)
        out += _parse(await _collect(EXPERT, INDEX_PROMPT + body, []), "[", "]")
    return out


async def analyze_sheet(file_path: str, mime: str, sheet: str, scale_hint: str) -> dict:
    hint = f"\nUser-provided scale/notes: {scale_hint}" if scale_hint else ""
    return _parse(await _collect(EXPERT, ANALYSIS_PROMPT.format(sheet=sheet, hint=hint), [(file_path, mime)]))


async def model_sheet(image_path: str, sheet: str) -> dict:
    return _parse(await _collect(EXPERT, MODEL3D_PROMPT.format(sheet=sheet), [(image_path, "image/png")]))


def stream_chat(files: list, context: str, history: list, question: str):
    transcript = "\n".join(f"{m['role'].upper()}: {m['content']}" for m in history[-12:])
    text = f"{context}\n\nConversation so far:\n{transcript or '(none)'}\n\nUSER QUESTION: {question}"
    return _stream(EXPERT + "\n\n" + CHAT_RULES, text, files)
