import { useCallback, useEffect, useState } from "react";
import { ClipboardList, Download, Loader2, RotateCcw } from "lucide-react";
import { toast } from "sonner";
import { getDrainTakeoff, saveDrainTakeoff } from "@/lib/api";

const PARAMS = [
  ["tile_lf", "Drain tile LF"], ["pipe_dia_in", "Pipe dia (in)"], ["pipe_stick_ft", "Stick length (ft)"], ["waste_pct", "Waste %"],
  ["trench_width_in", "Stone width (in)"], ["stone_depth_in", "Stone depth (in)"], ["stone_tons_per_cy", "Tons per CY"],
  ["fabric_overlap_pct", "Fabric overlap %"], ["fabric_roll_sf", "Fabric roll SF"], ["wall_perimeter_lf", "Wall perimeter LF"],
  ["board_height_ft", "Board height (ft)"], ["board_roll_sf", "Board roll SF"], ["cleanout_depth_ft", "Cleanout riser (ft)"],
  ["discharge_lf", "Outlet pipe LF"], ["pump_discharge_lf", "Pump discharge LF"], ["pump_pipe_dia_in", "Pump pipe dia (in)"],
  ["downspouts", "Downspouts"], ["downspout_leader_lf", "Leader LF each"],
];

const toCsv = (rows) => [["Group", "Material", "Spec", "Qty", "Unit", "Notes"], ...rows.map((r) => [r.group, r.item, r.spec, r.qty, r.unit, r.notes])]
  .map((r) => r.map((c) => `"${String(c ?? "").replace(/"/g, '""')}"`).join(",")).join("\n");

export const DrainTakeoff = ({ project, refreshKey, pageIndex }) => {
  const [data, setData] = useState(null);
  const [vals, setVals] = useState({});
  const [missing, setMissing] = useState(false);
  const [saving, setSaving] = useState(false);

  const load = useCallback(() => getDrainTakeoff(project.id, pageIndex)
    .then((d) => { setData(d); setVals(d.params); setMissing(false); })
    .catch((e) => { if (e.response?.status === 404) setMissing(true); else toast.error("Could not load takeoff"); }), [project.id, pageIndex]);
  useEffect(() => { load(); }, [load, refreshKey]);

  const save = async (params) => {
    setSaving(true);
    try { const d = await saveDrainTakeoff(project.id, data.page_index, params); setData(d); setVals(d.params); }
    catch (e) { toast.error(typeof e.response?.data?.detail === "string" ? e.response.data.detail : "Check the values"); setVals(data.params); }
    finally { setSaving(false); }
  };
  const overrides = (all) => Object.fromEntries(Object.entries(all).filter(([k, v]) => Number(v) !== Number(data.derived[k])));
  const commit = (k) => {
    const v = Number(vals[k]);
    if (String(vals[k]) === String(data.params[k])) return;
    if (!Number.isFinite(v) || v < 0) { toast.error("Enter a positive number"); setVals(data.params); return; }
    save(overrides({ ...data.params, [k]: v }));
  };
  const exportCsv = () => {
    const href = URL.createObjectURL(new Blob([toCsv(data.lines)], { type: "text/csv" }));
    Object.assign(document.createElement("a"), { href, download: `${project.name.replace(/[^\w-]+/g, "_")}_drainage_takeoff.csv` }).click();
    setTimeout(() => URL.revokeObjectURL(href), 2000);
  };

  if (missing) return (
    <div className="bg-[#111827] border border-slate-800 rounded-xl p-5 flex items-center gap-3" data-testid="drain-takeoff-missing">
      <ClipboardList className="h-5 w-5 text-amber-500" />
      <p className="text-sm text-slate-400">Draw the drain tile layout on the foundation sheet above and the drainage material takeoff will build from it.</p>
    </div>
  );
  if (!data) return <div className="h-24 flex items-center justify-center"><Loader2 className="h-5 w-5 animate-spin text-cyan-400" /></div>;

  return (
    <div className="bg-[#111827] border border-slate-800 rounded-xl overflow-hidden" data-testid="drain-takeoff">
      <div className="px-4 py-3 border-b border-slate-800 flex flex-wrap items-center gap-3">
        <ClipboardList className="h-4 w-4 text-amber-500" />
        <div className="mr-auto">
          <p className="font-display font-semibold">Drainage material takeoff</p>
          <p className="font-mono text-[10px] text-slate-500">From {data.sheet} layout · {data.counts.cleanouts} cleanouts · {data.counts.sumps} sumps · {data.counts.pumps} pumps · {data.counts.corners} corners</p>
        </div>
        {saving && <Loader2 className="h-4 w-4 animate-spin text-cyan-400" />}
        {data.edited && (
          <button data-testid="drain-takeoff-reset" onClick={() => save({})} className="flex items-center gap-1.5 text-xs border border-slate-700 rounded-md px-3 py-1.5 hover:bg-slate-800 transition-colors"><RotateCcw className="h-3.5 w-3.5" />Layout values</button>
        )}
        <button data-testid="drain-takeoff-csv" onClick={exportCsv} className="flex items-center gap-1.5 text-xs border border-slate-700 rounded-md px-3 py-1.5 hover:bg-slate-800 transition-colors"><Download className="h-3.5 w-3.5" />CSV</button>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm min-w-[640px]" data-testid="drain-takeoff-table">
          <thead><tr className="text-left font-mono text-[10px] uppercase tracking-[0.15em] text-slate-500 border-b border-slate-800">
            {["Group", "Material", "Qty", "Unit", "Spec", "Notes"].map((h) => <th key={h} className="px-4 py-2 font-medium">{h}</th>)}
          </tr></thead>
          <tbody>
            {data.lines.map((l, i) => (
              <tr key={i} className="border-b border-slate-800/60 hover:bg-slate-800/30" data-testid={`drain-takeoff-row-${i}`}>
                <td className="px-4 py-2 font-mono text-[11px] text-cyan-400">{l.group}</td>
                <td className="px-4 py-2 text-slate-100">{l.item}</td>
                <td className="px-4 py-2 font-mono text-amber-400 font-semibold" data-testid={`drain-takeoff-qty-${i}`}>{l.qty}</td>
                <td className="px-4 py-2 font-mono text-xs text-slate-400">{l.unit}</td>
                <td className="px-4 py-2 text-xs text-slate-400">{l.spec}</td>
                <td className="px-4 py-2 text-xs text-slate-500">{l.notes}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <details className="border-t border-slate-800" data-testid="drain-takeoff-assumptions">
        <summary className="px-4 py-3 cursor-pointer text-xs text-slate-400 hover:text-slate-200">Assumptions & inputs — edit any value to recalculate</summary>
        <div className="px-4 pb-4 grid grid-cols-2 md:grid-cols-6 gap-3">
          {PARAMS.map(([k, l]) => (
            <label key={k} className="block">
              <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-slate-500">{l}</span>
              <input data-testid={`drain-takeoff-param-${k}`} type="number" min="0" step="any" value={vals[k] ?? ""} onChange={(e) => setVals({ ...vals, [k]: e.target.value })}
                onBlur={() => commit(k)} onKeyDown={(e) => e.key === "Enter" && e.currentTarget.blur()}
                className={`mt-1 w-full bg-[#0B0F17] border rounded-md px-2 py-1.5 text-xs font-mono focus:outline-none focus:ring-1 focus:ring-cyan-500 ${Number(vals[k]) !== Number(data.derived[k]) ? "border-amber-500/60 text-amber-200" : "border-slate-700 text-slate-100"}`} />
            </label>
          ))}
        </div>
        <p className="px-4 pb-4 text-[10px] text-slate-500">Lengths come from the drain tile layout scale; amber inputs differ from the layout. Quantities include waste — confirm on site before ordering.</p>
      </details>
    </div>
  );
};
