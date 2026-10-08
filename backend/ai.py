import os
import json
import re
import tempfile
import uuid
from emergentintegrations.llm.chat import LlmChat, UserMessage, FileContentWithMimeType, TextDelta, StreamDone

MODEL = ("gemini", "gemini-3.1-pro-preview")

ANALYSIS_SYSTEM = """You are a senior construction estimator and architectural drafter who reads blueprints with extreme precision.
Rules:
- Read every dimension string, dimension line, room label, door/window tag, schedule and scale note on the drawing.
- Prefer dimensions written on the drawing. Only derive a value (from scale or by summing chains) when it is not labeled, and mark it as derived.
- Never invent values. If something is unreadable, say so in warnings.
- Keep the drawing's native units and notation (e.g. 12'-6" or 3810 mm)."""

ANALYSIS_PROMPT = """Analyze this construction blueprint and return ONLY valid JSON (no markdown fences) with this exact shape:
{
  "title": "short drawing title",
  "drawing_type": "floor plan | site plan | elevation | section | other",
  "units": "imperial | metric",
  "scale": "scale as noted on drawing or 'not noted'",
  "overall": {"width": "", "length": "", "total_area": ""},
  "rooms": [{"name": "", "width": "", "length": "", "area": "", "ceiling_height": "", "source": "labeled | derived", "notes": ""}],
  "walls": [{"id": "W1", "location": "", "length": "", "thickness": "", "type": "exterior | interior | load-bearing | partition", "source": "labeled | derived", "notes": ""}],
  "openings": [{"id": "D1", "type": "door | window | opening", "location": "", "width": "", "height": "", "source": "labeled | derived", "notes": ""}],
  "summary": "2-4 sentence plain-English summary of the layout",
  "warnings": ["any ambiguities, unreadable dimensions, or assumptions"]
}
Use empty string for unknown fields. Area should include units (e.g. "187.5 sq ft")."""

CHAT_SYSTEM = """You are a precise construction blueprint assistant. You have the blueprint attached and a prior structured extraction.
Answer questions about layout dimensions, areas, clearances, and quantities. Show your math for any calculation.
Cite whether each number is labeled on the drawing or derived. Be concise and use markdown tables/lists when helpful.
If the drawing doesn't contain the answer, say so plainly."""


def _write_temp(data: bytes, ext: str) -> str:
    path = os.path.join(tempfile.gettempdir(), f"{uuid.uuid4()}.{ext}")
    with open(path, "wb") as f:
        f.write(data)
    return path


def _new_chat(system: str) -> LlmChat:
    return LlmChat(api_key=os.environ["EMERGENT_LLM_KEY"], session_id=str(uuid.uuid4()),
                   system_message=system).with_model(*MODEL)


def _parse_json(text: str) -> dict:
    cleaned = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    start, end = cleaned.find("{"), cleaned.rfind("}")
    return json.loads(cleaned[start:end + 1])


async def analyze_blueprint(data: bytes, ext: str, mime: str, scale_hint: str) -> dict:
    path = _write_temp(data, ext)
    try:
        prompt = ANALYSIS_PROMPT + (f"\nUser-provided scale/notes: {scale_hint}" if scale_hint else "")
        msg = UserMessage(text=prompt, file_contents=[FileContentWithMimeType(file_path=path, mime_type=mime)])
        out = ""
        async for ev in _new_chat(ANALYSIS_SYSTEM).stream_message(msg):
            if isinstance(ev, TextDelta):
                out += ev.content
            elif isinstance(ev, StreamDone):
                break
        return _parse_json(out)
    finally:
        os.remove(path)


async def stream_chat(data: bytes, ext: str, mime: str, analysis: dict, history: list, question: str):
    path = _write_temp(data, ext)
    try:
        transcript = "\n".join(f"{m['role'].upper()}: {m['content']}" for m in history[-12:])
        text = (f"Prior structured extraction (JSON):\n{json.dumps(analysis)}\n\n"
                f"Conversation so far:\n{transcript or '(none)'}\n\nUSER QUESTION: {question}")
        msg = UserMessage(text=text, file_contents=[FileContentWithMimeType(file_path=path, mime_type=mime)])
        async for ev in _new_chat(CHAT_SYSTEM).stream_message(msg):
            if isinstance(ev, TextDelta):
                yield ev.content
            elif isinstance(ev, StreamDone):
                break
    finally:
        os.remove(path)
