import { useState } from "react";
import { Droplets } from "lucide-react";
import { toast } from "sonner";
import { patchWp } from "@/lib/api";
import { ToolGate } from "@/components/app/ToolGate";

const STATUS = {
  missing: "text-red-300 border-red-500/40 bg-red-500/10",
  unclear: "text-amber-300 border-amber-500/40 bg-amber-500/10",
  specified: "text-emerald-300 border-emerald-500/40 bg-emerald-500/10",
};
const SEV = { high: "text-red-400", medium: "text-amber-400", low: "text-slate-400" };
const FILTERS = ["all", "missing", "unclear", "specified"];

const WpBody = ({ project, data, onChange }) => {
  const [filter, setFilter] = useState("all");
  const [items, setItems] = useState(data.items || []);
  const count = (s) => items.filter((i) => i.status === s).length;
  const toggle = async (idx) => {
    const v = !items[idx].verified;
    setItems(items.map((it, j) => (j === idx ? { ...it, verified: v } : it)));
    try { await patchWp(project.id, idx, v); onChange(); } catch { toast.error("Could not save"); }
  };
  const shown = items.map((it, idx) => ({ ...it, idx })).filter((it) => filter === "all" || it.status === filter);

  return (
    <div className="space-y-4" data-testid="waterproofing-checklist">
      <div className="bg-[#111827] border border-slate-800 rounded-xl p-4">
        <p className="text-sm text-slate-300 leading-relaxed" data-testid="wp-summary">{data.summary}</p>
        <div className="flex flex-wrap gap-2 mt-3">
          {FILTERS.map((f) => (
            <button key={f} data-testid={`wp-filter-${f}`} onClick={() => setFilter(f)}
              className={`text-xs rounded-full border px-3 py-1 capitalize transition-colors ${filter === f ? "bg-cyan-500 text-[#0B0F17] border-cyan-500" : "border-slate-700 text-slate-400 hover:text-slate-100"}`}>
              {f} <span className="font-mono opacity-70">{f === "all" ? items.length : count(f)}</span>
            </button>
          ))}
          <span className="ml-auto font-mono text-xs text-emerald-400 self-center" data-testid="wp-verified-count">{items.filter((i) => i.verified).length}/{items.length} verified on site</span>
        </div>
      </div>
      <div className="space-y-2">
        {shown.map((it) => (
          <div key={it.idx} data-testid={`wp-item-${it.idx}`} className={`bg-[#111827] border rounded-xl p-4 flex gap-4 ${it.verified ? "border-emerald-500/30 opacity-80" : "border-slate-800"}`}>
            <input type="checkbox" checked={!!it.verified} onChange={() => toggle(it.idx)} data-testid={`wp-item-verify-${it.idx}`} className="mt-1 h-4 w-4 accent-emerald-500 shrink-0" />
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <span className={`font-mono text-[10px] uppercase border rounded px-1.5 py-0.5 ${STATUS[it.status] || STATUS.unclear}`}>{it.status}</span>
                <span className={`font-mono text-[10px] uppercase ${SEV[it.severity] || ""}`}>{it.severity}</span>
                <span className="font-mono text-[10px] text-slate-500">{it.category}</span>
                {(it.sheets || []).map((s) => <span key={s} className="font-mono text-[9px] border border-cyan-500/30 text-cyan-300 rounded px-1.5 py-0.5">{s}</span>)}
              </div>
              <p className="text-sm font-medium text-slate-100 mt-1.5">{it.item}</p>
              {it.spec && <p className="text-xs text-slate-400 mt-1"><span className="text-slate-500">Plans say:</span> {it.spec}</p>}
              {it.recommendation && <p className="text-xs text-amber-200/90 mt-1"><span className="text-slate-500">Do:</span> {it.recommendation}</p>}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export const WaterproofingChecklist = ({ project, onChange }) => (
  <ToolGate project={project} tool="waterproofing" title="Waterproofing checklist" icon={Droplets} onChange={onChange}
    blurb="Checks the entire set for membranes, damp-proofing, drainage board, drain tile, waterstops, vapor barriers and every flashing condition — and flags what is missing or unclear.">
    {(data) => <WpBody project={project} data={data} onChange={onChange} />}
  </ToolGate>
);
