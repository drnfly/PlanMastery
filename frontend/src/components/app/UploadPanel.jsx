import { useRef, useState } from "react";
import { UploadCloud, Loader2, ScanLine } from "lucide-react";
import { toast } from "sonner";
import { uploadPlans } from "@/lib/api";

const ACCEPT = ".png,.jpg,.jpeg,.webp,.pdf";

export const UploadPanel = ({ onCreated }) => {
  const inputRef = useRef(null);
  const [file, setFile] = useState(null);
  const [name, setName] = useState("");
  const [scale, setScale] = useState("");
  const [drag, setDrag] = useState(false);
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState(0);

  const pick = (f) => {
    if (!f) return;
    if (f.size > 150 * 1024 * 1024) return toast.error("File is larger than 150 MB");
    setFile(f); if (!name) setName(f.name.replace(/\.[^.]+$/, ""));
  };

  const submit = async () => {
    if (!file) return toast.error("Choose a blueprint file first");
    setBusy(true); setProgress(0);
    try {
      onCreated(await uploadPlans(file, name, scale, setProgress));
      toast.success("Uploaded — splitting and indexing sheets");
    } catch (e) {
      toast.error(e.response?.data?.detail || "Upload failed");
    } finally { setBusy(false); }
  };

  return (
    <div className="bg-[#111827] border border-slate-800 rounded-xl p-8 fade-up" data-testid="upload-panel">
      <p className="font-mono text-[10px] uppercase tracking-[0.25em] text-amber-500 mb-3">Sheet A-101 / New analysis</p>
      <h1 className="font-display text-4xl sm:text-5xl font-bold tracking-tight leading-[1.05]">Drop a blueprint.<br /><span className="text-slate-500">Get every dimension.</span></h1>
      <p className="text-sm text-slate-400 mt-4 max-w-xl">Upload a floor plan, elevation or site plan. The assistant reads labeled dimensions, room tags and schedules, then builds a takeoff of rooms, walls and openings you can question.</p>

      <div data-testid="blueprint-dropzone" onClick={() => inputRef.current.click()}
        onDragOver={(e) => { e.preventDefault(); setDrag(true); }} onDragLeave={() => setDrag(false)}
        onDrop={(e) => { e.preventDefault(); setDrag(false); pick(e.dataTransfer.files[0]); }}
        className={`mt-8 blueprint-grid rounded-xl border-2 border-dashed p-10 cursor-pointer flex flex-col items-center justify-center text-center transition-colors ${drag ? "border-cyan-400" : "border-slate-700 hover:border-slate-500"}`}>
        <UploadCloud className="h-10 w-10 text-cyan-400 mb-3" />
        <p className="text-sm font-medium" data-testid="dropzone-file-name">{file ? file.name : "Drag & drop or click to browse"}</p>
        <p className="font-mono text-[11px] text-slate-500 mt-1">Full PDF plan sets or PNG · JPG · WEBP — max 150 MB</p>
        {file && <p className="font-mono text-[11px] text-cyan-400 mt-1" data-testid="dropzone-file-size">{(file.size / 1048576).toFixed(1)} MB</p>}
        <input ref={inputRef} type="file" accept={ACCEPT} hidden data-testid="file-upload-input" onChange={(e) => pick(e.target.files[0])} />
      </div>

      <div className="grid sm:grid-cols-2 gap-4 mt-6">
        <label className="text-xs text-slate-400">Project name
          <input data-testid="project-name-input" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Lot 14 – Ground Floor"
            className="mt-1.5 w-full bg-[#0B0F17] border border-slate-800 rounded-md px-3 py-2.5 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-cyan-500" />
        </label>
        <label className="text-xs text-slate-400">Scale / notes (optional)
          <input data-testid="scale-hint-input" value={scale} onChange={(e) => setScale(e.target.value)} placeholder={`e.g. 1/4" = 1'-0"`}
            className="mt-1.5 w-full bg-[#0B0F17] border border-slate-800 rounded-md px-3 py-2.5 text-sm font-mono text-slate-100 focus:outline-none focus:ring-2 focus:ring-cyan-500" />
        </label>
      </div>

      <button data-testid="analyze-blueprint-button" onClick={submit} disabled={busy}
        className="mt-6 inline-flex items-center gap-2 rounded-md bg-amber-500 text-[#0B0F17] font-semibold px-6 py-3 hover:bg-amber-400 active:scale-95 disabled:opacity-60 transition-[background-color,transform]">
        {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <ScanLine className="h-4 w-4" />} {busy ? `Uploading ${progress}%` : "Upload plans"}
      </button>
      {busy && (
        <div className="mt-4 h-1.5 w-full max-w-md bg-slate-800 rounded-full overflow-hidden" data-testid="upload-progress">
          <div className="h-full bg-cyan-400 transition-[width] duration-300" style={{ width: `${progress}%` }} />
        </div>
      )}
    </div>
  );
};
