import { SumpForm } from "@/components/app/SumpPanel";

const inputCls = "mt-1 w-full bg-[#0B0F17] border border-slate-700 rounded-md px-2 py-1.5 text-xs text-slate-100 focus:outline-none focus:ring-1 focus:ring-cyan-500";
const F = ({ label, children, className = "" }) => (
  <label className={`block ${className}`}><span className="font-mono text-[10px] uppercase tracking-[0.15em] text-slate-500">{label}</span>{children}</label>
);

const NAMES = { tile: "Drain tile point", foot: "Footing outline corner", dpt: "Discharge point", cleanout: "Cleanout", sump: "Main sump", xsump: "Sump / pump", xoutlet: "Sump discharge outlet", slope: "Slope arrow" };

export const Inspector = ({ d, sel, patch, onDelete }) => {
  const edit = (fn) => patch(fn);
  return (
    <div className="bg-[#111827] border border-slate-800 rounded-xl p-4 space-y-4" data-testid="layout-inspector">
      <div className="grid grid-cols-2 gap-3">
        <F label="Drain tile length (LF)">
          <input data-testid="layout-length-input" type="number" min="0" className={inputCls} value={d.length_ft ?? 0}
            onChange={(e) => edit((o) => { o.length_ft = Number(e.target.value); o._length_set = true; })} />
        </F>
        <F label="Pipe spec">
          <input data-testid="layout-pipe-spec" className={inputCls} value={d.pipe_spec || ""} maxLength={200} onChange={(e) => edit((o) => { o.pipe_spec = e.target.value; })} />
        </F>
      </div>
      <p className="text-[10px] text-slate-500">Length updates automatically when you reshape the tile; type a real measured length to recalibrate the scale.</p>
      <div className="border-t border-slate-800 pt-3">
        {!sel && <p className="text-xs text-slate-500" data-testid="layout-inspector-empty">Select an item on the sheet to edit or delete it.</p>}
        {sel && (
          <div className="space-y-3" data-testid="layout-inspector-selected">
            <div className="flex items-center justify-between">
              <p className="text-sm font-semibold text-slate-100">{NAMES[sel.kind]}{sel.v !== undefined ? ` #${sel.v + 1}` : ""}</p>
              <button data-testid="layout-inspector-delete" onClick={onDelete} className="text-xs text-red-300 border border-red-500/50 rounded-md px-2 py-1 hover:bg-red-500/10">Delete</button>
            </div>
            {sel.kind === "cleanout" && (
              <F label="Label"><input data-testid="layout-cleanout-label" className={inputCls} maxLength={30} value={d.cleanouts[sel.i]?.label || ""} onChange={(e) => edit((o) => { o.cleanouts[sel.i].label = e.target.value; })} /></F>
            )}
            {sel.kind === "slope" && (
              <F label="Slope label"><input data-testid="layout-slope-label" className={inputCls} maxLength={30} value={d.slope_arrows[sel.i]?.label || ""} onChange={(e) => edit((o) => { o.slope_arrows[sel.i].label = e.target.value; })} /></F>
            )}
            {sel.kind === "dpt" && d.discharge && (
              <div className="grid grid-cols-2 gap-3">
                <F label="Discharge label"><input data-testid="layout-discharge-label" className={inputCls} maxLength={40} value={d.discharge.label || ""} onChange={(e) => edit((o) => { o.discharge.label = e.target.value; })} /></F>
                <F label="Discharges to">
                  <select data-testid="layout-discharge-to" className={inputCls} value={d.discharge.to || ""} onChange={(e) => edit((o) => { o.discharge.to = e.target.value; })}>
                    {["daylight", "storm", "dry well", "sump"].map((t) => <option key={t} value={t}>{t}</option>)}
                  </select>
                </F>
              </div>
            )}
            {sel.kind === "sump" && d.sump && <SumpForm s={d.sump} isMain onPatch={(p) => edit((o) => { Object.assign(o.sump, p); })} />}
            {(sel.kind === "xsump" || sel.kind === "xoutlet") && d.sumps[sel.i] && (
              <SumpForm s={d.sumps[sel.i]} onPatch={(p) => edit((o) => { Object.assign(o.sumps[sel.i], p); })} onRemove={onDelete} />
            )}
          </div>
        )}
      </div>
    </div>
  );
};
