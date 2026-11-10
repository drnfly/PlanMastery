import { Plus, Trash2, Droplet } from "lucide-react";

export const SUMP_TYPES = [["pit", "Sump pit"], ["pump", "Sump pump"], ["pit_pump", "Pit + pump"], ["ejector", "Ejector pump"], ["outlet", "Daylight outlet"]];
const typeLabel = (t) => SUMP_TYPES.find(([k]) => k === t)?.[1] || "Sump";

export const newSump = (draft) => {
  const used = new Set([draft.sump?.label, ...(draft.sumps || []).map((s) => s.label)]);
  const n = (draft.sumps || []).length;
  let k = n + 2;
  while (used.has(`SP-${k}`)) k++;
  const o = (n % 5) * 40;
  return { x: 480 + o, y: 480 + o, label: `SP-${k}`, type: "pit_pump", pump_hp: "1/3", pit_size: "18\" x 24\"", notes: "", outlet: [560 + o, 420 + o] };
};

const Field = ({ label, className = "", children }) => (
  <label className={`block ${className}`}>
    <span className="font-mono text-[10px] uppercase tracking-[0.15em] text-slate-500">{label}</span>
    {children}
  </label>
);
const inputCls = "mt-1 w-full bg-[#0B0F17] border border-slate-700 rounded-md px-2 py-1.5 text-xs text-slate-100 focus:outline-none focus:ring-1 focus:ring-cyan-500";

export const SumpForm = ({ s, onPatch, onRemove, isMain }) => (
  <div className="grid grid-cols-2 md:grid-cols-5 gap-3 items-end" data-testid="sump-form">
    <Field label="Label"><input data-testid="sump-field-label" className={inputCls} value={s.label || ""} maxLength={30} onChange={(e) => onPatch({ label: e.target.value })} /></Field>
    <Field label="Type">
      <select data-testid="sump-field-type" className={inputCls} value={s.type || ""} onChange={(e) => onPatch({ type: e.target.value })}>
        <option value="">Not set</option>
        {SUMP_TYPES.map(([k, l]) => <option key={k} value={k}>{l}</option>)}
      </select>
    </Field>
    <Field label="Pump HP"><input data-testid="sump-field-hp" className={inputCls} value={s.pump_hp || ""} maxLength={20} placeholder="1/3" onChange={(e) => onPatch({ pump_hp: e.target.value })} /></Field>
    <Field label="Pit size"><input data-testid="sump-field-pit" className={inputCls} value={s.pit_size || ""} maxLength={40} placeholder={'18" x 24"'} onChange={(e) => onPatch({ pit_size: e.target.value })} /></Field>
    <div className="flex gap-2">
      {!isMain && (
        <button data-testid="sump-toggle-outlet" onClick={() => onPatch({ outlet: s.outlet ? null : [Math.min(s.x + 80, 1000), Math.max(s.y - 60, 0)] })}
          className="flex-1 text-xs border border-emerald-500/50 text-emerald-300 rounded-md px-2 py-1.5 hover:bg-emerald-500/10">{s.outlet ? "No discharge" : "+ Discharge"}</button>
      )}
      {!isMain && <button data-testid="sump-remove" onClick={onRemove} aria-label="Remove sump" title="Remove sump" className="text-xs border border-red-500/50 text-red-300 rounded-md px-2 py-1.5 hover:bg-red-500/10"><Trash2 className="h-3.5 w-3.5" /></button>}
    </div>
    <Field label="Notes" className="col-span-2 md:col-span-5"><input data-testid="sump-field-notes" className={inputCls} value={s.notes || ""} maxLength={300} placeholder="Check valve, discharge to daylight 10 ft min…" onChange={(e) => onPatch({ notes: e.target.value })} /></Field>
  </div>
);

export const SumpPanel = ({ draft, setDraft, sel, setSel, editing }) => {
  const all = [...(draft.sump?.x != null ? [{ ...draft.sump, _key: "main" }] : []), ...(draft.sumps || []).map((s, i) => ({ ...s, _key: i }))];
  const selKey = sel?.kind === "sump" ? "main" : sel?.kind === "xsump" || sel?.kind === "xoutlet" ? sel.i : null;
  const cur = all.find((s) => s._key === selKey);
  const add = () => { const s = newSump(draft); setDraft({ ...draft, sumps: [...(draft.sumps || []), s] }); setSel({ kind: "xsump", i: (draft.sumps || []).length }); };
  const patch = (key, p) => key === "main"
    ? setDraft({ ...draft, sump: { ...draft.sump, ...p } })
    : setDraft({ ...draft, sumps: draft.sumps.map((s, i) => (i === key ? { ...s, ...p } : s)) });
  const remove = (key) => { setDraft({ ...draft, sumps: draft.sumps.filter((_, i) => i !== key) }); setSel(null); };

  return (
    <div className="px-4 py-3 border-b border-slate-800 space-y-3 bg-red-500/[0.03]" data-testid="sump-panel">
      <div className="flex flex-wrap items-center gap-2">
        <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-red-300 mr-1 flex items-center gap-1.5"><Droplet className="h-3.5 w-3.5" />Sumps & pumps</p>
        {all.map((s) => (
          <button key={s._key} data-testid={`sump-tab-${s._key}`} disabled={!editing} onClick={() => setSel(s._key === "main" ? { kind: "sump" } : { kind: "xsump", i: s._key })}
            className={`text-[11px] rounded-full border px-3 py-1 transition-colors disabled:cursor-default ${selKey === s._key ? "border-red-400 bg-red-500/15 text-red-200" : "border-slate-700 text-slate-300 enabled:hover:border-slate-500"}`}>
            {s.label || "SUMP"} <span className="text-slate-500">· {typeLabel(s.type)}{s.pump_hp ? ` · ${s.pump_hp} HP` : ""}</span>
          </button>
        ))}
        {editing && (
          <button data-testid="sump-add-button" onClick={add} className="text-[11px] rounded-full border border-dashed border-red-400/70 text-red-300 px-3 py-1 hover:bg-red-500/10 flex items-center gap-1"><Plus className="h-3 w-3" />Add sump / pump</button>
        )}
      </div>
      {editing && cur && <SumpForm s={cur} isMain={cur._key === "main"} onPatch={(p) => patch(cur._key, p)} onRemove={() => remove(cur._key)} />}
      {editing && !cur && <p className="text-[11px] text-slate-500">Tap a sump on the sheet or a tab above to set its type, pump size and pit — or add a new sump / pump, then drag it into place.</p>}
    </div>
  );
};
