import { useEffect, useRef, useState } from "react";
import { ZoomIn, ZoomOut, Maximize2, Loader2, Box, RotateCcw } from "lucide-react";
import { toast } from "sonner";
import { fetchPageImage, generate3d } from "@/lib/api";
import { Plan3D } from "@/components/app/Plan3D";

const Ctrl = ({ id, onClick, children }) => (
  <button data-testid={id} onClick={onClick} className="h-8 w-8 flex items-center justify-center rounded-md border border-slate-700 bg-[#0B0F17]/80 hover:bg-slate-800 transition-colors">{children}</button>
);

const ModeBtn = ({ id, on, onClick, children }) => (
  <button data-testid={id} onClick={onClick} className={`px-3 py-1.5 rounded-md text-xs font-medium flex items-center gap-1.5 transition-colors ${on ? "bg-cyan-500 text-[#0B0F17]" : "text-slate-400 hover:text-slate-100"}`}>{children}</button>
);

const ThreeDPane = ({ project, page, url, onChange }) => {
  const [replay, setReplay] = useState(0);
  const start = async () => { await generate3d(project.id, page.index); toast.info("Tracing walls for 3D"); onChange(); };
  if (page.model3d_status === "generating") return (
    <div className="absolute inset-0 flex flex-col items-center justify-center gap-2" data-testid="model3d-generating">
      <div className="scan-line" /><Loader2 className="h-6 w-6 animate-spin text-cyan-400" /><p className="text-xs text-slate-400">Tracing wall lines and heights…</p>
    </div>
  );
  if (page.model3d_status !== "ready" || !page.model3d?.walls?.length) return (
    <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 text-center px-6" data-testid="model3d-empty">
      <Box className="h-8 w-8 text-amber-500" />
      <p className="text-sm text-slate-300 max-w-sm">{page.model3d_status === "ready" ? "No floor plan walls found on this sheet." : page.model3d_status === "failed" ? `3D failed: ${page.model3d_error}` : "Raise the walls of this floor plan out of the sheet."}</p>
      <button data-testid="generate-3d-button" onClick={start} className="rounded-md bg-amber-500 text-[#0B0F17] font-semibold text-sm px-4 py-2 hover:bg-amber-400 active:scale-95 transition-[background-color,transform]">
        {page.model3d_status === "none" ? "Raise walls in 3D" : "Try again"}
      </button>
    </div>
  );
  return (
    <>
      <Plan3D url={url} model={page.model3d} replayKey={replay} />
      <div className="absolute bottom-3 right-3 flex gap-1.5">
        <Ctrl id="replay-3d-button" onClick={() => setReplay((r) => r + 1)}><RotateCcw className="h-4 w-4" /></Ctrl>
        <button data-testid="regenerate-3d-button" onClick={start} className="h-8 px-3 text-xs rounded-md border border-slate-700 bg-[#0B0F17]/80 hover:bg-slate-800 transition-colors">Re-trace</button>
      </div>
      <div className="absolute top-3 left-3 font-mono text-[10px] text-slate-400 bg-[#0B0F17]/80 border border-slate-800 rounded px-2 py-1" data-testid="model3d-legend">
        <span className="text-amber-400">■</span> exterior <span className="text-cyan-400 ml-2">■</span> interior · {page.model3d.walls.length} walls · {page.model3d.wall_height_ft || 9}' high · drag to orbit
      </div>
    </>
  );
};

export const BlueprintViewer = ({ project, page, onChange }) => {
  const [url, setUrl] = useState(null);
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [mode, setMode] = useState("2d");
  const drag = useRef(null);

  useEffect(() => {
    let u;
    setUrl(null); setZoom(1); setPan({ x: 0, y: 0 });
    fetchPageImage(project.id, page.index).then((b) => { u = URL.createObjectURL(b); setUrl(u); });
    return () => u && URL.revokeObjectURL(u);
  }, [project.id, page.index]);

  const onDown = (e) => { drag.current = { x: e.clientX - pan.x, y: e.clientY - pan.y }; };
  const onMove = (e) => { if (drag.current) setPan({ x: e.clientX - drag.current.x, y: e.clientY - drag.current.y }); };

  return (
    <div data-testid="blueprint-canvas-viewer" className="relative bg-[#111827] border border-slate-800 rounded-xl overflow-hidden fade-up">
      <div className="flex items-center justify-between px-4 py-3 border-b border-slate-800">
        <div className="min-w-0">
          <p className="font-display font-semibold truncate" data-testid="viewer-project-name">{page.sheet_number ? `${page.sheet_number} · ` : ""}{page.title}</p>
          <p className="font-mono text-[10px] text-slate-500 truncate">{project.name} · sheet {page.index + 1} of {project.page_count}</p>
        </div>
        <div className="flex items-center gap-3">
          {mode === "2d" && <span className="font-mono text-xs text-amber-400" data-testid="zoom-level">{Math.round(zoom * 100)}%</span>}
          <div className="flex gap-1 bg-[#0B0F17] border border-slate-800 rounded-lg p-1">
            <ModeBtn id="view-2d-button" on={mode === "2d"} onClick={() => setMode("2d")}>2D</ModeBtn>
            <ModeBtn id="view-3d-button" on={mode === "3d"} onClick={() => setMode("3d")}><Box className="h-3.5 w-3.5" />3D</ModeBtn>
          </div>
        </div>
      </div>
      <div className="relative h-[460px] blueprint-grid overflow-hidden select-none"
        onMouseDown={mode === "2d" ? onDown : undefined} onMouseMove={onMove} onMouseUp={() => (drag.current = null)} onMouseLeave={() => (drag.current = null)}>
        {!url && <div className="absolute inset-0 flex items-center justify-center"><Loader2 className="h-6 w-6 animate-spin text-cyan-400" /></div>}
        {url && mode === "3d" && <ThreeDPane project={project} page={page} url={url} onChange={onChange} />}
        {url && mode === "2d" && (
          <img src={url} alt="blueprint" draggable={false} data-testid="blueprint-image"
            className="absolute inset-0 m-auto max-h-full max-w-full object-contain cursor-grab active:cursor-grabbing"
            style={{ transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`, transition: drag.current ? "none" : "transform .15s" }} />
        )}
        {mode === "2d" && page.status === "analyzing" && <div className="scan-line" data-testid="scan-indicator" />}
        {mode === "2d" && (
          <div className="absolute bottom-3 right-3 flex gap-1.5">
            <Ctrl id="zoom-in-button" onClick={() => setZoom((z) => Math.min(z + 0.25, 5))}><ZoomIn className="h-4 w-4" /></Ctrl>
            <Ctrl id="zoom-out-button" onClick={() => setZoom((z) => Math.max(z - 0.25, 0.25))}><ZoomOut className="h-4 w-4" /></Ctrl>
            <Ctrl id="zoom-reset-button" onClick={() => { setZoom(1); setPan({ x: 0, y: 0 }); }}><Maximize2 className="h-4 w-4" /></Ctrl>
          </div>
        )}
      </div>
    </div>
  );
};
