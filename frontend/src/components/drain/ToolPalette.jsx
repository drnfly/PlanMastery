import { MousePointer2, Spline, CircleDot, Square, ArrowUpRight, MoveUpRight, Pentagon, Trash2, Undo2, Eraser } from "lucide-react";
import { TOOLS } from "@/components/drain/geometry";

const ICONS = { select: MousePointer2, tile: Spline, cleanout: CircleDot, sump: Square, discharge: MoveUpRight, slope: ArrowUpRight, footprint: Pentagon };
const HINT = {
  select: "Drag any item or point to move it. Tap + on a line to add a bend. Select an item, then Delete. Hide a layer to reach points underneath.",
  tile: "Tap the sheet to add drain tile points in order around the footing.",
  cleanout: "Tap the sheet to drop a cleanout.",
  sump: "Tap the sheet to place a sump / pump. The first one becomes the main sump.",
  discharge: "Tap to extend the main discharge line from the sump toward daylight / storm.",
  slope: "Tap the sheet to add a slope arrow, then drag its ends.",
  footprint: "Tap to add footing outline corners.",
};

export const ToolPalette = ({ tool, setTool, canDelete, onDelete, canUndo, onUndo, onClear }) => (
  <div className="space-y-2" data-testid="layout-tool-palette">
    <div className="flex flex-wrap gap-1.5">
      {TOOLS.map(([k, l]) => {
        const Icon = ICONS[k];
        return (
          <button key={k} data-testid={`layout-tool-${k}`} onClick={() => setTool(k)} title={l}
            className={`flex items-center gap-1.5 rounded-md border px-2.5 sm:px-3 py-2 text-xs font-medium transition-colors ${tool === k ? "border-cyan-400 bg-cyan-500 text-[#0B0F17]" : "border-slate-700 text-slate-300 hover:bg-slate-800"}`}>
            <Icon className="h-3.5 w-3.5" /><span className={tool === k ? "" : "hidden sm:inline"}>{k === "select" ? l : `+ ${l}`}</span>
          </button>
        );
      })}
      <span className="w-px bg-slate-700 mx-1" />
      <button data-testid="layout-delete-button" onClick={onDelete} disabled={!canDelete} className="flex items-center gap-1.5 rounded-md border border-red-500/50 text-red-300 px-3 py-2 text-xs hover:bg-red-500/10 disabled:opacity-40"><Trash2 className="h-3.5 w-3.5" />Delete</button>
      <button data-testid="layout-undo-button" onClick={onUndo} disabled={!canUndo} className="flex items-center gap-1.5 rounded-md border border-slate-700 text-slate-300 px-3 py-2 text-xs hover:bg-slate-800 disabled:opacity-40"><Undo2 className="h-3.5 w-3.5" />Undo</button>
      <button data-testid="layout-clear-button" onClick={onClear} className="flex items-center gap-1.5 rounded-md border border-slate-700 text-slate-400 px-3 py-2 text-xs hover:bg-slate-800"><Eraser className="h-3.5 w-3.5" />Clear all</button>
    </div>
    <p className="text-[11px] text-slate-400" data-testid="layout-tool-hint">{HINT[tool]}</p>
  </div>
);
