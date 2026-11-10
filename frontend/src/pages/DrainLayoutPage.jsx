import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import { ArrowLeft, Download, Loader2, PenLine, Save, Undo2, Ruler, Wand2, Trash2 } from "lucide-react";
import { getProject, fetchPageImage, startDrainOverlay, editDrainOverlay, fetchDrainPng, deleteDrainOverlay } from "@/lib/api";
import { LayoutCanvas } from "@/components/drain/LayoutCanvas";
import { ToolPalette } from "@/components/drain/ToolPalette";
import { Inspector } from "@/components/drain/Inspector";
import { DrainTakeoff } from "@/components/app/DrainTakeoff";
import { addAt, moveSel, removeSel, clone, toBody } from "@/components/drain/geometry";

const LAYERS = [["tile", "Drain tile"], ["foot", "Footing outline"], ["cleanouts", "Cleanouts"], ["sump", "Sumps & discharge"], ["slope", "Slope arrows"]];
const BLANK = { is_foundation: true, footprint: [], drain_tile: [], sump: null, sumps: [], cleanouts: [], discharge: null, slope_arrows: [], pipe_spec: "4\" perforated pipe in washed stone", length_ft: 0 };
const pickFoundation = (pages) => (pages.find((p) => p.drain_status === "ready" && p.drain_overlay?.is_foundation !== false)
  || pages.find((p) => /foundation/i.test(`${p.title} ${p.sheet_number}`)) || pages[0]).index;

export default function DrainLayoutPage() {
  const { pid } = useParams();
  const nav = useNavigate();
  const [project, setProject] = useState(null);
  const [idx, setIdx] = useState(null);
  const [url, setUrl] = useState(null);
  const [aspect, setAspect] = useState(0.66);
  const [draft, setDraft] = useState(null);
  const [hist, setHist] = useState([]);
  const [sel, setSel] = useState(null);
  const [tool, setTool] = useState("select");
  const [on, setOn] = useState({ tile: true, foot: true, cleanouts: true, sump: true, slope: true });
  const [saving, setSaving] = useState(false);

  const load = useCallback(() => getProject(pid).then((p) => { setProject(p); setIdx((i) => (i ?? pickFoundation(p.pages))); return p; }), [pid]);
  useEffect(() => { load().catch(() => toast.error("Project not found")); }, [load]);

  const page = project?.pages.find((p) => p.index === idx);
  const status = page?.drain_status || "none";
  const saved = page?.drain_status === "ready" && page.drain_overlay?.is_foundation !== false ? page.drain_overlay : null;
  const dirty = !!draft && JSON.stringify(toBody(draft)) !== JSON.stringify(toBody(saved || BLANK)) || !!draft?._length_set;

  useEffect(() => { setDraft(saved ? clone(saved) : null); setHist([]); setSel(null); }, [idx, saved?.edited_at, saved?.edited, status]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (idx == null) return undefined;
    let u;
    setUrl(null);
    fetchPageImage(pid, idx).then((b) => { u = URL.createObjectURL(b); const im = new Image(); im.onload = () => setAspect(im.naturalHeight / im.naturalWidth); im.src = u; setUrl(u); });
    return () => u && URL.revokeObjectURL(u);
  }, [pid, idx]);
  useEffect(() => {
    if (status !== "generating") return undefined;
    const t = setInterval(load, 3000);
    return () => clearInterval(t);
  }, [status, load]);

  const begin = useCallback(() => setHist((h) => [...h.slice(-40), draft]), [draft]);
  const apply = (next) => { begin(); setDraft(next); };
  const patch = (fn) => { const o = clone(draft); fn(o); o._length_set = draft._length_set || o._length_set; apply(o); };
  const del = useCallback(() => { if (sel && draft) { setHist((h) => [...h.slice(-40), draft]); setDraft(removeSel(draft, sel)); setSel(null); } }, [sel, draft]);
  const undo = () => { if (hist.length) { setDraft(hist.at(-1)); setHist(hist.slice(0, -1)); setSel(null); } };
  useEffect(() => {
    const k = (e) => { if ((e.key === "Delete" || e.key === "Backspace") && !/INPUT|TEXTAREA|SELECT/.test(e.target.tagName)) { e.preventDefault(); del(); } };
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  }, [del]);

  const aiDraw = async () => { try { await startDrainOverlay(pid, idx); toast.info("AI is laying out the drain tile…"); load(); } catch (e) { toast.error(e.response?.data?.detail || "Could not start"); } };
  const manual = () => { setDraft(clone(BLANK)); setTool("tile"); };
  const save = async () => {
    setSaving(true);
    try {
      const body = toBody(draft);
      if (draft._length_set) body.length_ft = Number(draft.length_ft) || 0;
      await editDrainOverlay(pid, idx, body);
      toast.success("Drain tile layout saved", { position: "top-center" });
      await load();
    } catch (e) { const dd = e.response?.data?.detail; toast.error(typeof dd === "string" ? dd : "Could not save — check the values"); }
    finally { setSaving(false); }
  };
  const resetAi = async () => {
    setSaving(true);
    try { await editDrainOverlay(pid, idx, { reset: true }); toast.success("Restored the original layout"); await load(); }
    catch (e) { toast.error(e.response?.data?.detail || "Could not restore"); }
    finally { setSaving(false); }
  };
  const removeLayout = async () => {
    if (!window.confirm("Delete the drain tile layout on this sheet?")) return;
    try { await deleteDrainOverlay(pid, idx); toast.success("Layout deleted"); setDraft(null); await load(); }
    catch { toast.error("Could not delete"); }
  };
  const download = async () => {
    try {
      const href = URL.createObjectURL(await fetchDrainPng(pid, idx));
      Object.assign(document.createElement("a"), { href, download: `drain_tile_${page.sheet_number || idx + 1}.png` }).click();
      setTimeout(() => URL.revokeObjectURL(href), 2000);
    } catch { toast.error("Save the layout first"); }
  };
  const refreshKey = useMemo(() => (project?.pages || []).map((p) => `${p.drain_status}:${p.drain_overlay?.edited_at || ""}`).join("|"), [project]);

  if (!project || idx == null) return <div className="min-h-screen bg-[#0B0F17] flex items-center justify-center"><Loader2 className="h-6 w-6 animate-spin text-cyan-400" /></div>;

  return (
    <div className="min-h-screen bg-[#0B0F17] text-slate-100" data-testid="drain-layout-page">
      <header className="sticky top-0 z-30 h-14 px-4 md:px-6 flex items-center gap-3 border-b border-slate-800 bg-[#0B0F17]/90 backdrop-blur-xl">
        <button data-testid="layout-back-button" onClick={() => nav(`/?project=${pid}&tab=drainage`)} className="flex items-center gap-1.5 text-xs border border-slate-700 rounded-md px-3 py-1.5 hover:bg-slate-800"><ArrowLeft className="h-3.5 w-3.5" />Back</button>
        <div className="min-w-0">
          <p className="font-display font-semibold truncate">Drain tile layout</p>
          <p className="font-mono text-[10px] text-slate-500 truncate">{project.name}</p>
        </div>
        <select data-testid="layout-sheet-select" value={idx} disabled={dirty} onChange={(e) => setIdx(Number(e.target.value))}
          className="ml-auto bg-[#111827] border border-slate-700 rounded-md px-2 py-1.5 text-xs max-w-[150px] sm:max-w-[260px] disabled:opacity-50">
          {project.pages.map((p) => <option key={p.index} value={p.index}>{p.sheet_number ? `${p.sheet_number} · ` : ""}{p.title}{p.drain_status === "ready" && p.drain_overlay?.is_foundation !== false ? " ✓" : ""}</option>)}
        </select>
        {saved?.edited && <span className="hidden md:inline font-mono text-[10px] text-amber-300 border border-amber-500/40 rounded px-1.5 py-0.5" data-testid="layout-edited-badge">FIELD-ADJUSTED</span>}
      </header>

      <main className="max-w-[1600px] mx-auto p-4 md:p-6 space-y-4">
        {!draft && status !== "generating" && (
          <div className="bg-[#111827] border border-slate-800 rounded-xl p-6 flex flex-wrap items-center gap-3" data-testid="layout-start-panel">
            <p className="text-sm text-slate-300 mr-auto">{page.drain_overlay?.is_foundation === false ? "The AI found no foundation outline on this sheet. Draw it yourself or pick the foundation plan." : "No drain tile layout on this sheet yet."}</p>
            <button data-testid="layout-ai-draw" onClick={aiDraw} className="flex items-center gap-2 rounded-md bg-amber-500 text-[#0B0F17] font-semibold px-4 py-2 text-sm hover:bg-amber-400"><Wand2 className="h-4 w-4" />Draw with AI</button>
            <button data-testid="layout-manual-start" onClick={manual} className="flex items-center gap-2 rounded-md border border-cyan-500/60 text-cyan-300 px-4 py-2 text-sm hover:bg-cyan-500/10"><PenLine className="h-4 w-4" />Draw it myself</button>
          </div>
        )}
        {status === "generating" && <div className="bg-[#111827] border border-slate-800 rounded-xl p-6 flex items-center gap-3" data-testid="layout-generating"><Loader2 className="h-5 w-5 animate-spin text-cyan-400" /><p className="text-sm">AI is tracing the footing and laying out the drain tile…</p></div>}

        {draft && (
          <div className="bg-[#111827] border border-slate-800 rounded-xl p-4 space-y-3 md:sticky md:top-14 z-20" data-testid="layout-toolbar">
            <ToolPalette tool={tool} setTool={setTool} canDelete={!!sel} onDelete={del} canUndo={hist.length > 0} onUndo={undo}
              onClear={() => { if (window.confirm("Remove every item from this layout?")) { apply({ ...clone(BLANK), pipe_spec: draft.pipe_spec, length_ft: draft.length_ft }); setSel(null); } }} />
            <div className="flex flex-wrap items-center gap-3 border-t border-slate-800 pt-3">
              {LAYERS.map(([k, l]) => (
                <label key={k} className="flex items-center gap-1.5 text-xs text-slate-300 cursor-pointer">
                  <input type="checkbox" data-testid={`layout-layer-${k}`} checked={on[k]} onChange={() => setOn({ ...on, [k]: !on[k] })} className="accent-cyan-500" />{l}
                </label>
              ))}
              <div className="ml-auto flex flex-wrap gap-2">
                {saved?.ai_original && <button data-testid="layout-reset-ai" onClick={resetAi} disabled={saving} className="flex items-center gap-1.5 text-xs border border-slate-700 rounded-md px-3 py-1.5 hover:bg-slate-800"><Undo2 className="h-3.5 w-3.5" />Original layout</button>}
                {saved && <button data-testid="layout-delete-layout" onClick={removeLayout} className="flex items-center gap-1.5 text-xs border border-red-500/40 text-red-300 rounded-md px-3 py-1.5 hover:bg-red-500/10"><Trash2 className="h-3.5 w-3.5" />Delete layout</button>}
                {saved && <button data-testid="layout-ai-redraw" onClick={() => window.confirm("Replace this layout with a fresh AI layout?") && aiDraw()} className="flex items-center gap-1.5 text-xs border border-slate-700 rounded-md px-3 py-1.5 hover:bg-slate-800"><Wand2 className="h-3.5 w-3.5" />Redraw with AI</button>}
                <button data-testid="layout-download" onClick={download} disabled={!saved || dirty} title={dirty ? "Save first" : ""} className="flex items-center gap-1.5 text-xs border border-cyan-500/60 text-cyan-300 rounded-md px-3 py-1.5 hover:bg-cyan-500/10 disabled:opacity-40"><Download className="h-3.5 w-3.5" />PNG for crew</button>
                <button data-testid="layout-cancel" onClick={() => { setDraft(saved ? clone(saved) : null); setHist([]); setSel(null); }} disabled={!dirty || saving} className="text-xs border border-slate-700 rounded-md px-3 py-1.5 hover:bg-slate-800 disabled:opacity-40">Discard</button>
                <button data-testid="layout-save" onClick={save} disabled={!dirty || saving} className="flex items-center gap-1.5 text-xs rounded-md bg-amber-500 text-[#0B0F17] font-semibold px-4 py-1.5 hover:bg-amber-400 disabled:opacity-40">
                  {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Save className="h-3.5 w-3.5" />}Save layout
                </button>
              </div>
            </div>
          </div>
        )}

        <div className="grid xl:grid-cols-[1fr_380px] gap-4 items-start">
          <div className="bg-white rounded-xl overflow-x-auto border border-slate-800" data-testid="layout-scroll">
            {!url && <div className="h-96 bg-[#111827] flex items-center justify-center"><Loader2 className="h-6 w-6 animate-spin text-cyan-400" /></div>}
            {url && draft && (
              <LayoutCanvas d={draft} aspect={aspect} on={on} tool={tool} sel={sel} setSel={setSel} url={url} onBegin={begin} setDraft={setDraft}
                onAdd={(t, x, y) => { const [o, s] = addAt(draft, t, x, y); apply(o); setSel(s); }}
                onMove={(s, x, y, start) => setDraft((d) => moveSel(d, s, x, y, start))} />
            )}
            {url && !draft && <img src={url} alt="sheet" className="w-full h-auto block min-w-[860px]" data-testid="layout-sheet-preview" />}
          </div>
          {draft && (
            <div className="space-y-4 xl:sticky xl:top-[220px]">
              <Inspector d={draft} sel={sel} patch={patch} onDelete={del} />
              <div className="bg-[#111827] border border-slate-800 rounded-xl p-4 text-xs text-slate-400 space-y-1" data-testid="layout-counts">
                <p className="flex items-center gap-1.5 text-slate-200 font-semibold"><Ruler className="h-3.5 w-3.5 text-cyan-400" />On this layout</p>
                <p>{(draft.drain_tile || []).length} tile points · {(draft.cleanouts || []).length} cleanouts · {(draft.sump?.x != null ? 1 : 0) + (draft.sumps || []).length} sumps/pumps · {(draft.slope_arrows || []).length} slope arrows</p>
                {dirty && <p className="text-amber-300" data-testid="layout-unsaved">Unsaved changes — save to update the takeoff, PNG and reports.</p>}
              </div>
            </div>
          )}
        </div>
        {saved && <DrainTakeoff project={project} refreshKey={refreshKey} pageIndex={idx} />}
      </main>
    </div>
  );
}
