# BuildSpec.ai — PRD
## Problem
"Need an ai assistant that can read construction blue prints and give precise layout dimensions"
## Choices
Gemini 3.1 Pro vision (Emergent LLM key) · Images + PDF upload (Emergent Object Storage) · Chat Q&A + structured table (rooms/walls/openings) · No auth, saved project history
## Architecture
FastAPI (server.py, ai.py, storage.py) + MongoDB (projects, messages) + React (Workspace page, Sidebar, UploadPanel, BlueprintViewer, AnalysisSummary, DimensionTable, ChatPanel)
## Implemented (2026-06)
- Upload → background Gemini analysis → JSON takeoff (overall, rooms, walls, openings, labeled/derived source, warnings)
- Viewer with zoom/pan (images) and PDF iframe; re-run analysis; soft delete; search history
- Dimension table tabs, filter, CSV export
- Streaming SSE chat with blueprint attached + persisted history
## Backlog
- P1: Multi-sheet PDFs per page selection; overlay bounding boxes on drawing
- P1: Material/quantity estimates (drywall, flooring, framing)
- P2: Manual scale calibration tool; PDF report export; auth

## Iteration 2 (2026-06)
- Chunked uploads (4MB chunks, retry, idempotent) up to 150 MB; full PDF plan sets split per sheet (PNG + single-page vector PDF) and AI sheet index (number/title/discipline)
- Takeoff runs automatically when a sheet is opened; per-sheet re-run
- Chat persona: Structural Engineer + Architect + ICF & waterproofing specialist; attaches current sheet + 2 keyword-relevant sheets + sheet index + takeoffs
- 3D view: AI traces wall centerlines -> walls rise out of the plan sheet (three.js / react-three-fiber, orbit, replay)
- Legacy single-file PDFs auto-split on startup; stale uploads cleaned
## Backlog next
- Door/window cut-outs in 3D walls, ICF block/concrete quantity estimator, waterproofing detail checklist, PDF report export

## Iteration 3 (2026-06)
- "Scan entire set": all sheets analyzed in parallel (3 at a time); each sheet gets takeoff + expert_notes (crew notes) + digest (full text transcription)
- Whole-set Q&A: chat scope "Entire set" (default) — AI routes the question across all sheet digests, attaches the best sheets, cites sources (chips)
- Branded PDF takeoff report (reportlab): logo, company/prepared by/phone/email/client, cover + sheet table, per-sheet dims/image/tables/expert notes/verify list, optional Expert Q&A appendix; branding saved globally
## Backlog
- Door/window cut-outs in 3D, ICF block/concrete estimator, waterproofing checklist, per-crew report filters (e.g., foundation crew only)

## Iteration 4-5 (2026-06)
- ICF material estimator (AI extracts wall runs/footings from whole set → deterministic blocks/corners/concrete yd³/rebar sticks; all inputs editable)
- Waterproofing checklist + Drainage plan tabs (set-wide, specified/missing/unclear, quantities, sequence, hold points, RFIs, on-site verify checkboxes kept across re-runs)
- Crew-specific PDF packets (foundation / ICF / waterproofing): AI-picked sheets + briefing, sequence, hold points, RFIs + relevant estimate/checklists
- Job-site photos: upload/take photo + note → AI compares with plans: issues, step-by-step fixes, next steps, inspections, safety; follow-up Q&A per photo
## Backlog
- Door/window cutouts in 3D, split server.py into routers, photo timeline in reports

## Iteration 6 (2026-06)
- Drain tile overlay (Drainage tab): AI traces foundation outline on chosen sheet and lays out drain tile route, cleanouts, sump/outlet, discharge and slope arrows (normalized coords); interactive SVG layers + animated flow; server-rendered PNG for crews (legend placed away from sump); included in full/foundation/waterproofing PDFs

## Iteration 7 (2026-06)
- Drag To Adjust: "Adjust on site" edit mode on drain tile layout — drag sump (discharge follows), outlet, cleanouts; add/remove cleanouts; save (FIELD-ADJUSTED badge), cancel, restore AI layout; PNG + PDFs use saved field positions; touch-friendly handles
- Sump / pump tab (Iteration 8): "Add sump / pump" on drain tile layout — multiple sumps/pumps, each with type (pit, pump, pit+pump, ejector, daylight outlet), pump HP, pit size, notes and optional own discharge line; draggable; rendered in PNG/PDF
- Drainage material takeoff (Iteration 9): deterministic from drain tile layout geometry (perf/solid pipe LF+sticks, sweeps, couplings, cleanout fittings, rodent guards, downspout adapters, stone CY/tons, filter fabric SF/rolls, drainage board SF/rolls, sump basins, pumps, check valves, pump discharge pipe); editable assumptions (only overrides saved), CSV export, included in full/foundation/waterproofing PDFs; visible even before AI drainage plan is run
