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
