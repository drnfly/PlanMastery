import { useEffect, useState } from "react";
import { Loader2, Send, Trash2, RefreshCw, AlertTriangle, ShieldAlert } from "lucide-react";
import { toast } from "sonner";
import { fetchPhoto, askPhoto, reanalyzePhoto, deletePhoto } from "@/lib/api";
import { Markdown } from "@/components/app/Markdown";

const SEV = { high: "border-red-500/40 text-red-300", medium: "border-amber-500/40 text-amber-300", low: "border-slate-600 text-slate-300" };

const List = ({ title, items, id, mark = "•" }) => items?.length ? (
  <div data-testid={id}>
    <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-slate-500 mt-3 mb-1">{title}</p>
    <ul className="space-y-1">{items.map((x, i) => <li key={i} className="text-xs text-slate-300 flex gap-2"><span className="text-cyan-400">{mark === "#" ? `${i + 1}.` : mark}</span>{x}</li>)}</ul>
  </div>
) : null;

const Analysis = ({ a }) => (
  <div data-testid="photo-analysis">
    <p className="font-display font-semibold text-slate-100">{a.title}</p>
    {a.stage && <p className="font-mono text-[10px] text-amber-400 mt-0.5">{a.stage}</p>}
    <p className="text-xs text-slate-300 mt-2 leading-relaxed">{a.what_i_see}</p>
    {a.plan_check && <p className="text-xs text-slate-400 mt-2"><span className="text-cyan-400">Plans check: </span>{a.plan_check}</p>}
    {a.issues?.length > 0 && (
      <div className="mt-3 space-y-2" data-testid="photo-issues">
        <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-slate-500">Issues & how to fix</p>
        {a.issues.map((it, i) => (
          <div key={i} className={`border rounded-lg p-3 ${SEV[it.severity] || SEV.low}`}>
            <p className="text-sm font-medium flex items-center gap-2"><AlertTriangle className="h-3.5 w-3.5" />{it.issue}<span className="font-mono text-[9px] uppercase opacity-80">{it.severity}</span></p>
            {it.why && <p className="text-xs text-slate-400 mt-1">{it.why}</p>}
            <ol className="mt-2 space-y-1">{(it.fix || []).map((f, j) => <li key={j} className="text-xs text-slate-200 flex gap-2"><span className="font-mono text-amber-400">{j + 1}.</span>{f}</li>)}</ol>
            {it.sheets?.length > 0 && <p className="font-mono text-[9px] text-cyan-300 mt-1">{it.sheets.join(" · ")}</p>}
          </div>
        ))}
      </div>
    )}
    <List title="Next steps" items={a.next_steps} id="photo-next-steps" mark="#" />
    <List title="Hold points & inspections" items={a.inspections} id="photo-inspections" mark="✓" />
    {a.safety?.length > 0 && (
      <div className="mt-3 border border-red-500/30 rounded-lg p-3" data-testid="photo-safety">
        <p className="text-xs font-semibold text-red-300 flex items-center gap-1.5"><ShieldAlert className="h-3.5 w-3.5" />Safety</p>
        <ul className="mt-1 text-xs text-slate-300 list-disc pl-5">{a.safety.map((s, i) => <li key={i}>{s}</li>)}</ul>
      </div>
    )}
    <List title="Verify / ask the engineer" items={a.questions} id="photo-questions" mark="?" />
  </div>
);

export const PhotoCard = ({ photo, onChange }) => {
  const [url, setUrl] = useState(null);
  const [q, setQ] = useState("");
  useEffect(() => {
    let u;
    fetchPhoto(photo.id).then((b) => { u = URL.createObjectURL(b); setUrl(u); }).catch(() => {});
    return () => u && URL.revokeObjectURL(u);
  }, [photo.id]);
  const busy = photo.status === "analyzing" || photo.status === "answering";

  const ask = async () => {
    if (!q.trim()) return;
    try { await askPhoto(photo.id, q); setQ(""); onChange(); } catch (e) { toast.error(e.response?.data?.detail || "Could not ask"); }
  };
  const act = async (fn, msg) => { try { await fn(photo.id); toast.info(msg); onChange(); } catch { toast.error("Action failed"); } };

  return (
    <div className="bg-[#111827] border border-slate-800 rounded-xl overflow-hidden grid md:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]" data-testid={`photo-card-${photo.id}`}>
      <div className="relative bg-black/40 min-h-[220px]">
        {url ? <img src={url} alt={photo.note || "job photo"} className="absolute inset-0 w-full h-full object-contain" data-testid="photo-image" /> : <Loader2 className="absolute inset-0 m-auto h-5 w-5 animate-spin text-cyan-400" />}
        {photo.status === "analyzing" && <div className="scan-line" />}
        <div className="absolute top-2 right-2 flex gap-1">
          <button data-testid="photo-reanalyze-button" onClick={() => act(reanalyzePhoto, "Re-checking photo")} disabled={busy} className="h-7 w-7 flex items-center justify-center rounded-md bg-[#0B0F17]/80 border border-slate-700 hover:bg-slate-800 disabled:opacity-40"><RefreshCw className="h-3.5 w-3.5" /></button>
          <button data-testid="photo-delete-button" onClick={() => act(deletePhoto, "Photo removed")} className="h-7 w-7 flex items-center justify-center rounded-md bg-[#0B0F17]/80 border border-slate-700 hover:text-red-400"><Trash2 className="h-3.5 w-3.5" /></button>
        </div>
      </div>
      <div className="p-4 max-h-[640px] overflow-y-auto">
        <p className="font-mono text-[10px] text-slate-500">{new Date(photo.created_at).toLocaleString()}</p>
        {photo.note && <p className="text-sm text-slate-200 mt-1 italic" data-testid="photo-note">"{photo.note}"</p>}
        {photo.status === "analyzing" && <p className="text-xs text-cyan-400 mt-3 flex items-center gap-2" data-testid="photo-analyzing"><Loader2 className="h-4 w-4 animate-spin" />Comparing photo with the plans…</p>}
        {photo.status === "failed" && <p className="text-xs text-red-400 mt-3" data-testid="photo-error">Analysis failed: {photo.error}</p>}
        {photo.analysis && <div className="mt-3"><Analysis a={photo.analysis} /></div>}
        {(photo.thread || []).map((t, i) => (
          <div key={i} className="mt-4 border-t border-slate-800 pt-3" data-testid={`photo-thread-${i}`}>
            <p className="text-xs text-amber-300 font-medium">Q: {t.q}</p>
            <div className="mt-1 text-slate-200"><Markdown text={t.a} /></div>
          </div>
        ))}
        {photo.status === "answering" && <p className="text-xs text-cyan-400 mt-3 flex items-center gap-2"><Loader2 className="h-4 w-4 animate-spin" />Thinking…</p>}
        {photo.analysis && (
          <div className="mt-4 flex gap-2">
            <input data-testid="photo-followup-input" value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => e.key === "Enter" && ask()} disabled={busy}
              placeholder="Ask a follow-up about this photo…" className="flex-1 bg-[#0B0F17] border border-slate-800 rounded-md px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-cyan-500" />
            <button data-testid="photo-followup-send" onClick={ask} disabled={busy || !q.trim()} className="h-9 w-9 flex items-center justify-center rounded-md bg-cyan-500 text-[#0B0F17] hover:bg-cyan-400 disabled:opacity-40"><Send className="h-4 w-4" /></button>
          </div>
        )}
      </div>
    </div>
  );
};
