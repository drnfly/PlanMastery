from ai_engine import EXPERT, _collect, _parse

ICF_PROMPT = """From the ENTIRE plan set below (sheet transcriptions, prior takeoffs and attached sheets), extract every ICF
(insulated concrete form) wall run and every footing so an estimator can calculate blocks, concrete and rebar.
Return ONLY valid JSON (no markdown fences):
{
  "system": "ICF brand/system and block type noted on plans, or ''",
  "walls": [{"id": "IW1", "location": "e.g. North foundation wall, grid A", "sheets": "S-201", "length_ft": 40.0,
             "height_ft": 8.0, "core_in": 6, "corners_90": 2, "corners_45": 0, "openings_sqft": 0,
             "vertical_bar": "#5", "vertical_spacing_in": 16, "horizontal_bar": "#4", "horizontal_bars_per_row": 2,
             "horizontal_every_courses": 2, "source": "labeled | derived", "notes": ""}],
  "footings": [{"id": "F1", "location": "", "sheets": "", "length_ft": 0, "width_in": 0, "depth_in": 0,
                "bars": "#4", "bar_count": 3, "source": "labeled | derived", "notes": ""}],
  "assumptions": ["each assumption you made"],
  "missing": ["information needed for an accurate ICF takeoff that the plans do not show"]
}
Rules: numbers are decimal feet / inches as named. Split walls by straight run so corners are counted once per corner
(assign each outside corner to exactly one wall). openings_sqft = total area of doors/windows/bucks in that run.
If foundation walls are concrete but ICF is not stated, still include them and say so in notes. Never invent rebar —
if not specified, leave bar fields '' and add to "missing"."""

WP_PROMPT = """Review the ENTIRE plan set below as a waterproofing and building-envelope specialist (with ICF experience).
Build a waterproofing checklist covering at least these categories: Below-grade waterproofing membrane, Damp-proofing,
Drainage board / dimple mat, Protection board, Drain tile / footing drain, Sump or drain discharge, Footing-to-wall joint
& waterstop, Under-slab vapor barrier, Capillary break, Window & door flashing, Through-wall / step / kick-out flashing,
Roof flashing & underlayment, Penetration seals, Termination bar & transition to above-grade WRB, ICF-compatible products.
Return ONLY valid JSON (no markdown fences):
{
  "summary": "2-3 sentence overall assessment",
  "items": [{"category": "", "item": "specific requirement", "status": "specified | missing | unclear",
             "sheets": ["S-201"], "spec": "what the plans say (quote or paraphrase), '' if missing",
             "recommendation": "what the crew/GC should do or ask", "severity": "high | medium | low"}]
}
Flag as "missing" anything a competent waterproofing detail would require that the plans do not show. Note that ICF foam
needs solvent-free, ICF-compatible membranes. Cite sheets."""

CREWS = {
    "foundation": "Foundation crew: excavation, footings, footing rebar, dowels, slab-on-grade, under-slab vapor barrier, drain tile, backfill",
    "icf": "ICF wall crew: ICF block layout, corners, bucks/openings, bracing & alignment, wall rebar, embedments/anchor bolts, pour sequencing and lift heights",
    "waterproofing": "Waterproofing crew: below-grade membrane, damp-proofing, drainage board, protection board, drain tile, flashing, penetrations, terminations",
}

CREW_PROMPT = """Prepare a field packet for the {crew}.
Using the ENTIRE plan set below, return ONLY valid JSON (no markdown fences):
{{
  "sheets": [page numbers (integers) of every sheet this crew needs],
  "scope": "2-3 sentence scope of work for this crew on this project",
  "sequence": ["ordered work steps"],
  "notes": ["crew-specific expert notes: tolerances, dimensions, specs, gotchas, cite sheets"],
  "materials": ["key materials/products/sizes called out on the plans for this crew"],
  "inspections": ["hold points and inspections before moving on"],
  "rfis": ["questions to send the GC/engineer because the plans are missing or unclear"]
}}"""


async def set_json(prompt: str, context: str, files: list) -> dict:
    return _parse(await _collect(EXPERT, prompt + "\n\n" + context, files))


PHOTO_PROMPT = """The FIRST attached file is a JOB-SITE PHOTO taken on this project. Any other attached files are plan sheets
from the project's plan set. The crew's note/question about the photo: "{note}"
Act as the project's structural engineer, architect, ICF and waterproofing specialist doing a site visit.
Compare what you see against the plans. Return ONLY valid JSON (no markdown fences):
{{
  "title": "short title of what the photo shows",
  "stage": "construction stage you see (e.g. footings poured, ICF course 3, membrane install)",
  "what_i_see": "2-4 sentence factual description",
  "plan_check": "how the photo compares with the plans (cite sheets); say if the plans don't cover it",
  "issues": [{{"issue": "", "severity": "high | medium | low", "why": "risk if not fixed",
              "fix": ["step-by-step fix the crew can follow"], "sheets": ["S-201"]}}],
  "next_steps": ["ordered next steps for the crew from this point"],
  "inspections": ["hold points / inspections before proceeding"],
  "safety": ["safety concerns visible, if any"],
  "questions": ["things to verify or ask the engineer/GC"]
}}
Be specific and practical. If the photo is unclear, say what additional photo would help. Structural fixes must be
approved by the engineer of record."""


async def analyze_photo(note: str, context: str, files: list) -> dict:
    return await set_json(PHOTO_PROMPT.format(note=note or "(none — assess the work and tell me the next step)"), context, files)


async def photo_followup(analysis: dict, question: str, context: str, files: list) -> str:
    text = (f"Earlier assessment of the FIRST attached job-site photo:\n{analysis}\n\nCrew follow-up question: {question}\n"
            "Answer as the project's structural engineer / architect / ICF and waterproofing specialist. Give concrete steps, "
            "cite sheets, be concise, use markdown.\n\n" + context)
    return await _collect(EXPERT, text, files)


def crew_prompt(crew: str) -> str:
    return CREW_PROMPT.format(crew=CREWS[crew])
