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

DRAIN_PROMPT = """Review the ENTIRE plan set below as a civil / geotechnical drainage specialist with ICF foundation experience,
and build a complete DRAINAGE PLAN for this building and site. Cover at least: Footing drain tile (perforated pipe, size,
location inside/outside footing), Gravel / aggregate envelope & filter fabric, Drain tile discharge (daylight, sump, storm),
Sump pit & pump, Cleanouts, Drainage board / foundation wall drainage, Under-slab drainage & capillary break, Backfill
material & compaction, Finish grading slope away from foundation (min 6" in 10 ft), Swales, Downspouts & leaders,
Splash blocks / underground roof drain lines, Area drains / window wells, Driveway / hardscape drainage, Retaining wall
drainage, Erosion & sediment control. Compute quantities where possible from the plans (e.g. drain tile LF from the
footing perimeter, number of downspouts, cleanouts at each corner / every 100 ft).
Return ONLY valid JSON (no markdown fences):
{
  "summary": "2-3 sentence overall assessment of the drainage design",
  "strategy": "recommended overall drainage approach for this building in plain words (route of water from roof and soil to discharge)",
  "items": [{"category": "", "item": "specific drainage component/requirement", "status": "specified | missing | unclear",
             "sheets": ["S-201"], "spec": "what the plans say, '' if missing", "quantity": "e.g. 140 LF 4\\" perf PVC, or ''",
             "recommendation": "what the crew/GC should install or ask", "severity": "high | medium | low"}],
  "sequence": ["ordered installation steps for the drainage work"],
  "inspections": ["hold points / inspections (e.g. drain tile before backfill)"],
  "rfis": ["questions for the engineer / GC"]
}
Flag as "missing" anything a competent drainage plan requires that the plans do not show. Cite sheets."""

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


DRAIN_OVERLAY_PROMPT = """The attached image is construction sheet {sheet}. Lay out the FOUNDATION DRAIN TILE system on top of it so a crew
can see the route. Coordinates are normalized 0-1000 relative to the FULL image: x from the left edge, y from the top edge.
Project drainage plan context (from the whole plan set):
{context}

Rules: trace the outer edge of the foundation/footing; route the perforated drain tile just OUTSIDE the footing (offset ~1-2% of
the image) around the full perimeter as a continuous path that starts at the HIGH point and runs both ways to the LOW point /
outlet; put the sump (or outlet) at the low point — use the location shown on the plans if any, else the corner nearest the lowest
grade or street/daylight side; draw the solid discharge line from the sump/outlet away from the building (>= 10 ft) to daylight,
storm or dry well; place cleanouts at the upstream (high) end, at corners where needed and at least every 100 ft; add 2-4 slope
arrows along the tile pointing toward the outlet (downhill, in the direction water flows) labeled with the slope (min 1/8" per ft unless
plans say otherwise); each arrow should be at least 80 units long. The discharge line should be at least 120 units long.
Return ONLY valid JSON (no markdown fences):
{{
  "is_foundation": true,
  "footprint": [[x, y], ...],
  "drain_tile": [[x, y], ...],
  "sump": {{"x": 0, "y": 0, "label": "SUMP / OUTLET"}},
  "discharge": {{"points": [[x, y], ...], "to": "daylight | storm | dry well", "label": "TO DAYLIGHT"}},
  "cleanouts": [{{"x": 0, "y": 0, "label": "CO-1"}}],
  "slope_arrows": [{{"x1": 0, "y1": 0, "x2": 0, "y2": 0, "label": "1/8\\"/ft"}}],
  "pipe_spec": "e.g. 4\\" perforated PVC in 12\\" washed stone wrapped in filter fabric",
  "length_ft": 0,
  "notes": ["short crew notes about this layout, incl. what was assumed because the plans don't show it"]
}}
If the sheet shows no foundation or floor plan outline, set "is_foundation": false and leave the arrays empty."""


async def drain_overlay(image_path: str, sheet: str, context: str) -> dict:
    mime = "image/jpeg" if image_path.lower().endswith((".jpg", ".jpeg")) else "image/webp" if image_path.lower().endswith(".webp") else "image/png"
    return _parse(await _collect(EXPERT, DRAIN_OVERLAY_PROMPT.format(sheet=sheet, context=context), [(image_path, mime)]))
