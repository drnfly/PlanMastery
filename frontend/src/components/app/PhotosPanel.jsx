import { useCallback, useEffect, useRef, useState } from "react";
import { Camera, ImagePlus, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { listPhotos, uploadPhoto } from "@/lib/api";
import { PhotoCard } from "@/components/app/PhotoCard";

export const PhotosPanel = ({ project }) => {
  const [photos, setPhotos] = useState([]);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [tick, setTick] = useState(0);
  const camRef = useRef(null);
  const fileRef = useRef(null);
  const poke = useCallback(() => setTick((t) => t + 1), []);

  useEffect(() => {
    let timer;
    let stop = false;
    const load = async () => {
      const list = await listPhotos(project.id).catch(() => null);
      if (!list || stop) return;
      setPhotos(list);
      if (list.some((p) => p.status === "analyzing" || p.status === "answering")) timer = setTimeout(load, 4000);
    };
    load();
    return () => { stop = true; clearTimeout(timer); };
  }, [project.id, tick]);

  const upload = async (files) => {
    if (!files?.length) return;
    setBusy(true);
    try {
      for (const f of files) await uploadPhoto(project.id, f, note);
      toast.success(`${files.length} photo${files.length > 1 ? "s" : ""} uploaded — AI is reviewing`);
      setNote("");
      poke();
    } catch (e) { toast.error(e.response?.data?.detail || "Upload failed"); }
    finally { setBusy(false); camRef.current.value = ""; fileRef.current.value = ""; }
  };

  return (
    <div className="space-y-4" data-testid="photos-panel">
      <div className="bg-[#111827] border border-slate-800 rounded-xl p-5">
        <p className="font-display font-semibold text-lg">Job-site photos</p>
        <p className="text-sm text-slate-400 mt-1">Snap the work in progress. The AI compares it with these plans and tells you what's wrong, how to fix it, and the next step.</p>
        <textarea data-testid="photo-note-input" value={note} onChange={(e) => setNote(e.target.value)} rows={2}
          placeholder="Optional: what are we looking at / what do you want to know? (e.g. 'North wall course 4 — ready to pour?')"
          className="mt-3 w-full bg-[#0B0F17] border border-slate-800 rounded-md px-3 py-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-cyan-500" />
        <div className="flex flex-wrap gap-2 mt-3">
          <button data-testid="photo-camera-button" onClick={() => camRef.current?.click()} disabled={busy}
            className="flex items-center gap-2 rounded-md bg-amber-500 text-[#0B0F17] font-semibold px-4 py-2 text-sm hover:bg-amber-400 disabled:opacity-50 active:scale-95 transition-[background-color,transform]">
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Camera className="h-4 w-4" />} Take photo
          </button>
          <button data-testid="photo-upload-button" onClick={() => fileRef.current?.click()} disabled={busy}
            className="flex items-center gap-2 rounded-md border border-slate-700 px-4 py-2 text-sm hover:bg-slate-800 disabled:opacity-50 transition-colors">
            <ImagePlus className="h-4 w-4" /> Upload photos
          </button>
          <input ref={camRef} type="file" accept="image/*" capture="environment" hidden data-testid="photo-camera-input" onChange={(e) => upload([...e.target.files])} />
          <input ref={fileRef} type="file" accept="image/png,image/jpeg,image/webp" multiple hidden data-testid="photo-file-input" onChange={(e) => upload([...e.target.files])} />
        </div>
      </div>
      {photos.length === 0 && <p className="text-xs text-slate-500" data-testid="photos-empty">No photos yet for this job.</p>}
      {photos.map((p) => <PhotoCard key={p.id} photo={p} onChange={poke} />)}
    </div>
  );
};
