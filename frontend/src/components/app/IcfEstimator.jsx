import { useEffect, useState } from "react";
import { Boxes, AlertTriangle } from "lucide-react";
import { toast } from "sonner";
import { editIcf } from "@/lib/api";
import { ToolGate } from "@/components/app/ToolGate";
import { EditableGrid } from "@/components/app/EditableGrid";

const WALL_COLS = [
  { key: "id", label: "ID", w: "w-12" }, { key: "location", label: "Location", w: "w-44" }, { key: "length_ft", label: "L ft", num: true },
  { key: "height_ft", label: "H ft", num: true }, { key: "core_in", label: "Core in", num: true }, { key: "corners_90", label: "90° crn", num: true, w: "w-12" },
  { key: "corners_45", label: "45° crn", num: true, w: "w-12" }, { key: "openings_sqft", label: "Open ft²", num: true },
  { key: "vertical_bar", label: "Vert bar", w: "w-12" }, { key: "vertical_spacing_in", label: "@ in", num: true, w: "w-12" },
  { key: "horizontal_bar", label: "Horiz bar", w: "w-12" }, { key: "horizontal_bars_per_row", label: "Bars/row", num: true, w: "w-12" },
  { key: "horizontal_every_courses", label: "Every crs", num: true, w: "w-12" },
];
const FOOT_COLS = [
  { key: "id", label: "ID", w: "w-12" }, { key: "location", label: "Location", w: "w-56" }, { key: "length_ft", label: "L ft", num: true },
  { key: "width_in", label: "W in", num: true }, { key: "depth_in", label: "D in", num: true }, { key: "bars", label: "Bar", w: "w-12" },
  { key: "bar_count", label: "Count", num: true, w: "w-12" },
];
const PARAMS = [["block_length_in", "Block length in"], ["block_height_in", "Block height in"], ["waste_pct", "Block waste %"],
  ["concrete_overage_pct", "Concrete overage %"], ["stock_length_ft", "Bar stock ft"], ["lap_bar_diameters", "Lap (bar dia.)"]];

const Stat = ({ id, label, value, unit, accent }) => (
  <div className="bg-[#0B0F17] border border-slate-800 rounded-lg p-3" data-testid={id}>
    <p className="font-mono text-[10px] uppercase tracking-wider text-slate-500">{label}</p>
    <p className={`font-display text-2xl font-semibold mt-1 ${accent || "text-slate-100"}`}>{value ?? "—"}<span className="text-xs text-slate-500 ml-1">{unit}</span></p>
  </div>
);

const IcfBody = ({ project, data, onChange }) => {
  const [walls, setWalls] = useState(data.extract.walls || []);
  const [footings, setFootings] = useState(data.extract.footings || []);
  const [params, setParams] = useState(data.calc.params);
  const [calc, setCalc] = useState(data.calc);
  useEffect(() => { setWalls(data.extract.walls || []); setFootings(data.extract.footings || []); setParams(data.calc.params); setCalc(data.calc); }, [data]);

  const commit = async () => {
    try { setCalc((await editIcf(project.id, { walls, footings, params })).calc); onChange(); }
    catch { toast.error("Could not recalculate"); }
  };
  const t = calc.totals;
  const ex = data.extract;

  return (
    <div className="space-y-4" data-testid="icf-estimator">
      <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-3">
        <Stat id="icf-total-straight" label="Straight blocks" value={t.straight_blocks} accent="text-amber-400" />
        <Stat id="icf-total-corner" label="Corner blocks" value={t.corner_blocks} accent="text-amber-400" />
        <Stat id="icf-total-wall-cy" label="Wall concrete" value={t.wall_cy} unit="yd³" accent="text-cyan-400" />
        <Stat id="icf-total-footing-cy" label="Footing concrete" value={t.footing_cy} unit="yd³" accent="text-cyan-400" />
        <Stat id="icf-total-cy" label="Total concrete" value={t.total_cy} unit="yd³" />
        <Stat id="icf-total-rebar" label="Rebar" value={t.rebar_lb} unit="lb" />
      </div>
      {walls.some((w) => !Number(w.height_ft) || !Number(w.length_ft)) && (
        <p className="text-xs text-amber-400 flex items-center gap-2" data-testid="icf-zero-warning"><AlertTriangle className="h-4 w-4" />Some walls have no length or height on the plans — enter them below to complete the block and concrete count.</p>
      )}
      <div className="bg-[#111827] border border-slate-800 rounded-xl p-4">
        <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-slate-500 mb-2">System: <span className="text-slate-300 normal-case tracking-normal">{ex.system || "not specified on plans"}</span></p>
        <div className="grid grid-cols-2 md:grid-cols-6 gap-2">
          {PARAMS.map(([k, l]) => (
            <label key={k} className="text-[10px] text-slate-500">{l}
              <input data-testid={`icf-param-${k}`} type="number" step="any" value={params[k] ?? ""} onChange={(e) => setParams({ ...params, [k]: e.target.value })} onBlur={commit}
                className="mt-1 w-full bg-[#0B0F17] border border-slate-800 rounded-md px-2 py-1.5 font-mono text-sm text-slate-100 focus:outline-none focus:ring-1 focus:ring-cyan-500" />
            </label>
          ))}
        </div>
      </div>
      <div className="bg-[#111827] border border-slate-800 rounded-xl p-4 space-y-3">
        <p className="font-display font-semibold">ICF wall runs <span className="text-xs text-slate-500 font-normal">— edit any cell, totals update when you leave it</span></p>
        <EditableGrid id="icf-walls-grid" columns={WALL_COLS} rows={walls} onChange={setWalls} onCommit={commit} />
        <p className="font-display font-semibold pt-2">Footings</p>
        <EditableGrid id="icf-footings-grid" columns={FOOT_COLS} rows={footings} onChange={setFootings} onCommit={commit} />
        {calc.rebar.length > 0 && (
          <div data-testid="icf-rebar-order">
            <p className="font-display font-semibold pt-2 mb-2">Rebar order</p>
            <div className="flex flex-wrap gap-2">
              {calc.rebar.map((r) => (
                <div key={r.size} className="bg-[#0B0F17] border border-slate-800 rounded-md px-3 py-2 font-mono text-xs">
                  <span className="text-amber-400 font-semibold">{r.size}</span> · {r.lf} LF · <span className="text-cyan-400">{r.sticks} × {r.stock_ft}'</span> · {r.weight_lb} lb
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
      {(ex.missing?.length > 0 || ex.assumptions?.length > 0) && (
        <div className="grid md:grid-cols-2 gap-4">
          {ex.missing?.length > 0 && (
            <div className="bg-[#111827] border border-amber-500/30 rounded-xl p-4" data-testid="icf-missing">
              <p className="text-sm font-semibold text-amber-400 flex items-center gap-2"><AlertTriangle className="h-4 w-4" />Missing from plans — confirm before ordering</p>
              <ul className="mt-2 text-xs text-slate-300 list-disc pl-5 space-y-1">{ex.missing.map((m, i) => <li key={i}>{m}</li>)}</ul>
            </div>
          )}
          {ex.assumptions?.length > 0 && (
            <div className="bg-[#111827] border border-slate-800 rounded-xl p-4" data-testid="icf-assumptions">
              <p className="text-sm font-semibold text-slate-300">Assumptions</p>
              <ul className="mt-2 text-xs text-slate-400 list-disc pl-5 space-y-1">{ex.assumptions.map((m, i) => <li key={i}>{m}</li>)}</ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export const IcfEstimator = ({ project, onChange }) => (
  <ToolGate project={project} tool="icf" title="ICF material estimate" icon={Boxes} onChange={onChange}
    blurb="Reads every ICF wall run and footing across the set, then calculates straight and corner blocks, wall and footing concrete yards, and rebar sticks by size. Every input is editable.">
    {(data) => <IcfBody project={project} data={data} onChange={onChange} />}
  </ToolGate>
);
