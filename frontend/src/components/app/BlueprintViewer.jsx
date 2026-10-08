import { useEffect, useRef, useState } from "react";
import { ZoomIn, ZoomOut, Maximize2, Loader2 } from "lucide-react";
import { fetchFileBlob } from "@/lib/api";

const Ctrl = ({ id, onClick, children }) => (
  <button data-testid={id} onClick={onClick} className="h-8 w-8 flex items-center justify-center rounded-md border border-slate-700 bg-[#0B0F17]/80 hover:bg-slate-800 transition-colors">{children}</button>
);

export const BlueprintViewer = ({ project }) => {
  const [url, setUrl] = useState(null);
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const drag = useRef(null);
  const isPdf = project.ext === "pdf";

  useEffect(() => {
    let u;
    setUrl(null); setZoom(1); setPan({ x: 0, y: 0 });
    fetchFileBlob(project.id).then((b) => { u = URL.createObjectURL(b); setUrl(u); });
    return () => u && URL.revokeObjectURL(u);
  }, [project.id]);

  const onDown = (e) => { drag.current = { x: e.clientX - pan.x, y: e.clientY - pan.y }; };
  const onMove = (e) => { if (drag.current) setPan({ x: e.clientX - drag.current.x, y: e.clientY - drag.current.y }); };

  return (
    <div data-testid="blueprint-canvas-viewer" className="relative bg-[#111827] border border-slate-800 rounded-xl overflow-hidden fade-up">
      <div className="flex items-center justify-between px-4 py-3 border-b border-slate-800">
        <div className="min-w-0">
          <p className="font-display font-semibold truncate" data-testid="viewer-project-name">{project.name}</p>
          <p className="font-mono text-[10px] text-slate-500 truncate">{project.original_filename} · {(project.size / 1024).toFixed(0)} KB</p>
        </div>
        {!isPdf && <span className="font-mono text-xs text-amber-400" data-testid="zoom-level">{Math.round(zoom * 100)}%</span>}
      </div>
      <div className="relative h-[420px] blueprint-grid overflow-hidden select-none"
        onMouseDown={isPdf ? undefined : onDown} onMouseMove={onMove} onMouseUp={() => (drag.current = null)} onMouseLeave={() => (drag.current = null)}>
        {!url && <div className="absolute inset-0 flex items-center justify-center"><Loader2 className="h-6 w-6 animate-spin text-cyan-400" /></div>}
        {url && isPdf && <iframe title="blueprint" src={url} className="w-full h-full bg-white" data-testid="blueprint-pdf-frame" />}
        {url && !isPdf && (
          <img src={url} alt="blueprint" draggable={false} data-testid="blueprint-image"
            className="absolute inset-0 m-auto max-h-full max-w-full object-contain cursor-grab active:cursor-grabbing"
            style={{ transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`, transition: drag.current ? "none" : "transform .15s" }} />
        )}
        {project.status === "analyzing" && <div className="scan-line" data-testid="scan-indicator" />}
        {!isPdf && (
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
