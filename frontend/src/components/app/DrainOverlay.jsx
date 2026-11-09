import { useEffect, useMemo, useRef, useState } from "react";
import { Loader2, Download, PenLine, RefreshCw, Move, Plus, Trash2, Undo2, Save } from "lucide-react";
import { toast } from "sonner";
import { fetchPageImage, startDrainOverlay, fetchDrainPng, editDrainOverlay } from "@/lib/api";

const C = { tile: "#2563EB", discharge: "#16A34A", cleanout: "#EA580C", sump: "#DC2626", slope: "#C026D3", foot: "#06B6D4" };
const LAYERS = [["tile", "Drain tile"], ["cleanouts", "Cleanouts"], ["sump", "Sump & discharge"], ["slope", "Slope arrows"]];
const pts = (a) => (a || []).filter((p) => Array.isArray(p) && p.length >= 2).map((p) => p.join(",")).join(" ");

const Arrow = ({ s }) => (
  <g>
    <line x1={s.x1} y1={s.y1} x2={s.x2} y2={s.y2} stroke={C.slope} strokeWidth="3" markerEnd="url(#arrow-slope)" vectorEffect="non-scaling-stroke" />
    <text x={(s.x1 + s.x2) / 2 + 6} y={(s.y1 + s.y2) / 2 - 6} fill={C.slope} fontSize="14" fontWeight="700" stroke="#fff" strokeWidth="3" paintOrder="stroke">{s.label}</text>
  </g>
);

const Overlay = ({ ov, aspect, on, edit, sel, onDrag, onSelect }) => {
  const svgRef = useRef(null);
  const drag = useRef(null);
  const sy = (y) => y * aspect;
  const t = (a) => (a || []).map((p) => [p[0], sy(p[1])]);
  const H = 1000 * aspect;
  const dis = ov.discharge || {};
  const outlet = dis.points?.length > 1 ? dis.points.at(-1) : null;

  const toSvg = (e) => {
    const svg = svgRef.current;
    const p = svg.createSVGPoint();
    p.x = e.clientX; p.y = e.clientY;
    const r = p.matrixTransform(svg.getScreenCTM().inverse());
    return [Math.max(0, Math.min(1000, r.x)), Math.max(0, Math.min(1000, r.y / aspect))];
  };
  const grab = (target) => (e) => {
    if (!edit) return;
    e.preventDefault(); e.stopPropagation();
    drag.current = target;
    onSelect(target);
    svgRef.current.setPointerCapture(e.pointerId);
  };
  const move = (e) => { if (drag.current) { const [x, y] = toSvg(e); onDrag(drag.current, x, y); } };
  const end = () => { drag.current = null; };
  const isSel = (kind, i) => sel?.kind === kind && sel?.i === i;
  const handle = edit ? { style: { cursor: "grab", touchAction: "none" } } : {};

  return (
    <svg ref={svgRef} viewBox={`0 0 1000 ${H}`} className={`absolute inset-0 w-full h-full ${edit ? "drain-editing" : ""}`} data-testid="drain-overlay-svg"
      onPointerMove={move} onPointerUp={end} onPointerCancel={end}>
      <defs>
        {[["slope", C.slope], ["discharge", C.discharge]].map(([k, c]) => (
          <marker key={k} id={`arrow-${k}`} viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill={c} /></marker>
        ))}
      </defs>
      {ov.footprint?.length > 2 && <polygon points={pts(t(ov.footprint))} fill={`${C.foot}22`} stroke={C.foot} strokeWidth="1.5" strokeDasharray="6 4" />}
      {on.tile && ov.drain_tile?.length > 1 && (
        <polyline points={pts(t(ov.drain_tile))} fill="none" stroke={C.tile} strokeWidth="6" strokeLinejoin="round" className="drain-flow" data-testid="drain-tile-line" />
      )}
      {on.sump && dis.points?.length > 1 && (
        <g data-testid="drain-discharge">
          <polyline points={pts(t(dis.points))} fill="none" stroke={C.discharge} strokeWidth="5" strokeDasharray="12 8" markerEnd="url(#arrow-discharge)" />
          <text x={outlet[0] + 8} y={sy(outlet[1])} fill={C.discharge} fontSize="15" fontWeight="700" stroke="#fff" strokeWidth="3" paintOrder="stroke">{dis.label || "DISCHARGE"}</text>
        </g>
      )}
      {on.slope && (ov.slope_arrows || []).map((s, i) => <Arrow key={i} s={{ ...s, y1: sy(s.y1), y2: sy(s.y2) }} />)}
      {on.cleanouts && (ov.cleanouts || []).map((c, i) => (
        <g key={i} data-testid={`drain-cleanout-${i}`} onPointerDown={grab({ kind: "cleanout", i })} {...handle}>
          {edit && <circle cx={c.x} cy={sy(c.y)} r="24" fill={isSel("cleanout", i) ? `${C.cleanout}44` : "transparent"} stroke={isSel("cleanout", i) ? C.cleanout : "none"} strokeDasharray="4 3" />}
          <circle cx={c.x} cy={sy(c.y)} r="10" fill={C.cleanout} stroke="#fff" strokeWidth="2.5" />
          <text x={c.x + 14} y={sy(c.y) - 8} fill={C.cleanout} fontSize="14" fontWeight="700" stroke="#fff" strokeWidth="3" paintOrder="stroke">{c.label || "CO"}</text>
        </g>
      ))}
      {on.sump && ov.sump?.x != null && (
        <g data-testid="drain-sump" onPointerDown={grab({ kind: "sump" })} {...handle}>
          {edit && <circle cx={ov.sump.x} cy={sy(ov.sump.y)} r="28" fill={isSel("sump") ? `${C.sump}33` : "transparent"} stroke={isSel("sump") ? C.sump : "none"} strokeDasharray="4 3" />}
          <rect x={ov.sump.x - 13} y={sy(ov.sump.y) - 13} width="26" height="26" fill={C.sump} stroke="#fff" strokeWidth="2.5" />
          <text x={ov.sump.x + 18} y={sy(ov.sump.y) + 24} fill={C.sump} fontSize="15" fontWeight="700" stroke="#fff" strokeWidth="3" paintOrder="stroke">{ov.sump.label || "SUMP"}</text>
        </g>
      )}
      {edit && on.sump && outlet && (
        <g data-testid="drain-outlet-handle" onPointerDown={grab({ kind: "outlet" })} {...handle}>
          <circle cx={outlet[0]} cy={sy(outlet[1])} r="24" fill={isSel("outlet") ? `${C.discharge}44` : "transparent"} stroke={C.discharge} strokeDasharray="4 3" strokeWidth="2" />
          <circle cx={outlet[0]} cy={sy(outlet[1])} r="9" fill={C.discharge} stroke="#fff" strokeWidth="2.5" />
        </g>
      )}
    </svg>
  );
};

const applyDrag = (ov, target, x, y) => {
  if (target.kind === "cleanout") return { ...ov, cleanouts: ov.cleanouts.map((c, i) => (i === target.i ? { ...c, x, y } : c)) };
  const pts0 = ov.discharge?.points || [];
  if (target.kind === "outlet") return { ...ov, discharge: { ...ov.discharge, points: [...pts0.slice(0, -1), [x, y]] } };
  return { ...ov, sump: { ...ov.sump, x, y }, discharge: pts0.length > 1 ? { ...ov.discharge, points: [[x, y], ...pts0.slice(1)] } : ov.discharge };
};

const EditBar = ({ draft, sel, setDraft, setSel, save, cancel, reset, saving, edited }) => {
  const add = () => {
    const n = (draft.cleanouts || []).length;
    const used = new Set((draft.cleanouts || []).map((c) => c.label));
    let k = n + 1;
    while (used.has(`CO-${k}`)) k++;
    setDraft({ ...draft, cleanouts: [...(draft.cleanouts || []), { x: 500, y: 500, label: `CO-${k}` }] });
    setSel({ kind: "cleanout", i: n });
  };
  const remove = () => { setDraft({ ...draft, cleanouts: draft.cleanouts.filter((_, i) => i !== sel.i) }); setSel(null); };
  const btn = "text-xs rounded-md border px-3 py-1.5 transition-colors disabled:opacity-40";
  return (
    <div className="px-4 py-2 flex flex-wrap items-center gap-2 border-b border-amber-500/40 bg-amber-500/5" data-testid="drain-edit-bar">
      <p className="text-[11px] text-amber-300 mr-auto flex items-center gap-1.5"><Move className="h-3.5 w-3.5" />Drag the sump, cleanouts or the green outlet to where they really are on site.</p>
      <button data-testid="drain-add-cleanout" onClick={add} className={`${btn} border-slate-700 hover:bg-slate-800 flex items-center gap-1`}><Plus className="h-3.5 w-3.5" />Cleanout</button>
      <button data-testid="drain-remove-cleanout" onClick={remove} disabled={sel?.kind !== "cleanout"} className={`${btn} border-slate-700 hover:bg-slate-800 flex items-center gap-1`}><Trash2 className="h-3.5 w-3.5" />Remove</button>
      {edited && <button data-testid="drain-reset-ai" onClick={reset} disabled={saving} className={`${btn} border-slate-700 hover:bg-slate-800 flex items-center gap-1`}><Undo2 className="h-3.5 w-3.5" />AI layout</button>}
      <button data-testid="drain-edit-cancel" onClick={cancel} disabled={saving} className={`${btn} border-slate-700 hover:bg-slate-800`}>Cancel</button>
      <button data-testid="drain-edit-save" onClick={save} disabled={saving} className={`${btn} border-amber-500 bg-amber-500 text-[#0B0F17] font-semibold hover:bg-amber-400 flex items-center gap-1`}>
        {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Save className="h-3.5 w-3.5" />}Save layout
      </button>
    </div>
  );
};

const pickDefault = (pages) => (pages.find((p) => /foundation/i.test(`${p.title} ${p.sheet_number}`)) || pages.find((p) => p.drain_status === "ready") || pages[0]).index;

export const DrainOverlay = ({ project, onChange }) => {
  const [idx, setIdx] = useState(() => pickDefault(project.pages));
  const [url, setUrl] = useState(null);
  const [aspect, setAspect] = useState(1);
  const [on, setOn] = useState({ tile: true, cleanouts: true, sump: true, slope: true });
  const page = project.pages.find((p) => p.index === idx) || project.pages[0];
  const [draft, setDraft] = useState(null);
  const [sel, setSel] = useState(null);
  const [saving, setSaving] = useState(false);
  const [kept, setKept] = useState(null);
  const saved = kept || page.drain_overlay;
  const ov = draft || saved;
  const status = page.drain_status || "none";
  const editing = !!draft;

  useEffect(() => { setDraft(null); setSel(null); setKept(null); }, [page.index]);
  useEffect(() => { setKept(null); }, [page.drain_overlay]);

  const startEdit = () => { setOn({ ...on, cleanouts: true, sump: true }); setDraft(JSON.parse(JSON.stringify(saved))); };
  const persist = async (body, msg) => {
    setSaving(true);
    try { setKept(await editDrainOverlay(project.id, page.index, body)); toast.success(msg, { position: "top-center" }); setDraft(null); setSel(null); onChange(); }
    catch (e) { toast.error(e.response?.data?.detail || "Could not save layout"); }
    finally { setSaving(false); }
  };
  const save = () => persist({ sump: draft.sump, cleanouts: draft.cleanouts || [], discharge: draft.discharge }, "Layout saved — PNG and reports now use the field positions");
  const reset = () => persist({ reset: true }, "Restored the AI layout");

  useEffect(() => {
    let u, alive = true;
    setUrl(null);
    fetchPageImage(project.id, page.index).then((b) => {
      if (!alive) return;
      u = URL.createObjectURL(b);
      const im = new Image();
      im.onload = () => alive && setAspect(im.naturalHeight / im.naturalWidth);
      im.src = u;
      setUrl(u);
    }).catch(() => alive && toast.error("Could not load sheet"));
    return () => { alive = false; u && URL.revokeObjectURL(u); };
  }, [project.id, page.index]);

  const draw = async () => {
    try { await startDrainOverlay(project.id, page.index); toast.info("Laying out the drain tile on this sheet…"); onChange(); }
    catch (e) { toast.error(e.response?.data?.detail || "Could not start"); }
  };
  const download = async () => {
    try {
      const blob = await fetchDrainPng(project.id, page.index);
      const href = URL.createObjectURL(blob);
      Object.assign(document.createElement("a"), { href, download: `drain_tile_${page.sheet_number || page.index + 1}.png` }).click();
      setTimeout(() => URL.revokeObjectURL(href), 2000);
    } catch { toast.error("Could not download the layout"); }
  };
  const legend = useMemo(() => [[C.tile, `Drain tile${ov?.length_ft ? ` · ${ov.length_ft} LF` : ""}`], [C.discharge, "Discharge"], [C.cleanout, "Cleanout"], [C.sump, "Sump / low point"], [C.slope, "Slope"]], [ov]);

  return (
    <div className="bg-[#111827] border border-slate-800 rounded-xl overflow-hidden" data-testid="drain-overlay-panel">
      <div className="px-4 py-3 border-b border-slate-800 flex flex-wrap items-center gap-3">
        <p className="font-display font-semibold mr-auto">Drain tile layout</p>
        <select data-testid="drain-sheet-select" value={page.index} onChange={(e) => setIdx(Number(e.target.value))} disabled={editing}
          className="bg-[#0B0F17] border border-slate-700 rounded-md px-2 py-1.5 text-xs max-w-[240px] focus:outline-none focus:ring-1 focus:ring-cyan-500 disabled:opacity-50">
          {project.pages.map((p) => <option key={p.index} value={p.index}>{p.sheet_number ? `${p.sheet_number} · ` : ""}{p.title}{p.drain_status === "ready" ? " ✓" : ""}</option>)}
        </select>
        {status === "ready" && saved?.edited && <span className="font-mono text-[10px] text-amber-300 border border-amber-500/40 rounded px-1.5 py-0.5" data-testid="drain-edited-badge">FIELD-ADJUSTED</span>}
        {status === "ready" && ov?.is_foundation !== false && !editing && (
          <button data-testid="drain-adjust-button" onClick={startEdit} className="flex items-center gap-1.5 text-xs border border-amber-500/60 text-amber-300 rounded-md px-3 py-1.5 hover:bg-amber-500/10 transition-colors"><Move className="h-3.5 w-3.5" />Adjust on site</button>
        )}
        {status === "ready" && ov?.is_foundation !== false && !editing && (
          <button data-testid="drain-download-button" onClick={download} className="flex items-center gap-1.5 text-xs border border-slate-700 rounded-md px-3 py-1.5 hover:bg-slate-800 transition-colors"><Download className="h-3.5 w-3.5" />PNG for crew</button>
        )}
        <button data-testid="drain-draw-button" onClick={draw} disabled={status === "generating" || editing}
          className="flex items-center gap-1.5 text-xs font-semibold rounded-md bg-amber-500 text-[#0B0F17] px-3 py-1.5 hover:bg-amber-400 disabled:opacity-50 active:scale-95 transition-[background-color,transform]">
          {status === "generating" ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : status === "ready" ? <RefreshCw className="h-3.5 w-3.5" /> : <PenLine className="h-3.5 w-3.5" />}
          {status === "generating" ? "Drawing…" : status === "ready" ? "Redraw" : "Draw drain tile"}
        </button>
      </div>
      {status === "ready" && (
        <div className="px-4 py-2 flex flex-wrap gap-2 border-b border-slate-800" data-testid="drain-layer-toggles">
          {LAYERS.map(([k, l]) => (
            <button key={k} data-testid={`drain-layer-${k}`} onClick={() => setOn({ ...on, [k]: !on[k] })}
              className={`text-[11px] rounded-full border px-3 py-1 transition-colors ${on[k] ? "border-cyan-500 text-cyan-300 bg-cyan-500/10" : "border-slate-700 text-slate-500"}`}>{l}</button>
          ))}
          <div className="ml-auto flex flex-wrap gap-3 items-center">
            {legend.map(([c, l]) => <span key={l} className="flex items-center gap-1.5 text-[10px] text-slate-400 font-mono"><span className="h-2.5 w-2.5 rounded-sm" style={{ background: c }} />{l}</span>)}
          </div>
        </div>
      )}
      {editing && <EditBar draft={draft} sel={sel} setDraft={setDraft} setSel={setSel} save={save} cancel={() => { setDraft(null); setSel(null); }} reset={reset} saving={saving} edited={saved?.edited} />}
      <div className="overflow-x-auto bg-white" data-testid="drain-overlay-scroll">
      <div className="relative bg-white min-w-[860px]" data-testid="drain-overlay-stage">
        {!url && <div className="h-80 flex items-center justify-center bg-[#0B0F17]"><Loader2 className="h-6 w-6 animate-spin text-cyan-400" /></div>}
        {url && <img src={url} alt="sheet" className="w-full h-auto block select-none" draggable={false} data-testid="drain-sheet-image" />}
        {url && status === "ready" && ov?.is_foundation !== false && (
          <Overlay ov={ov} aspect={aspect} on={on} edit={editing} sel={sel} onSelect={setSel}
            onDrag={(target, x, y) => setDraft((d) => applyDrag(d, target, x, y))} />
        )}
        {status === "generating" && <div className="scan-line" />}
      </div>
      </div>
      <div className="px-4 py-3 space-y-1" data-testid="drain-overlay-info">
        {status === "none" && <p className="text-xs text-slate-400">Pick the foundation sheet and the AI will draw the drain tile route, cleanouts, sump and discharge on top of it.</p>}
        {status === "failed" && <p className="text-xs text-red-400" data-testid="drain-error">Drawing failed: {page.drain_error}</p>}
        {status === "ready" && ov?.is_foundation === false && <p className="text-xs text-amber-400" data-testid="drain-not-foundation">No foundation outline found on this sheet — pick the foundation plan.</p>}
        {status === "ready" && ov?.pipe_spec && <p className="text-xs text-slate-300"><span className="text-cyan-400 font-mono">PIPE </span>{ov.pipe_spec}{ov.discharge?.to ? ` · discharges to ${ov.discharge.to}` : ""}</p>}
        {status === "ready" && (ov?.notes || []).map((n, i) => <p key={i} className="text-xs text-slate-400">• {n}</p>)}
        {status === "ready" && <p className="text-[10px] text-slate-500 pt-1">AI layout for crew planning — confirm grades, invert elevations and outlet location on site.</p>}
      </div>
    </div>
  );
};
