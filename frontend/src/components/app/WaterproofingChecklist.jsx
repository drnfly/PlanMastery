import { useEffect, useState } from "react";
import { Droplets, Waves } from "lucide-react";
import { toast } from "sonner";
import { patchWp } from "@/lib/api";
import { ToolGate } from "@/components/app/ToolGate";
import { DrainOverlay } from "@/components/app/DrainOverlay";
import { DrainTakeoff } from "@/components/app/DrainTakeoff";

const STATUS = {
  missing: "text-red-300 border-red-500/40 bg-red-500/10",
  unclear: "text-amber-300 border-amber-500/40 bg-amber-500/10",
  specified: "text-emerald-300 border-emerald-500/40 bg-emerald-500/10",
};
const SEV = { high: "text-red-400", medium: "text-amber-400", low: "text-slate-400" };
const FILTERS = ["all", "missing", "unclear", "specified"];

const WpBody = ({ project, data, onChange, tool = "waterproofing" }) => {
  const [filter, setFilter] = useState("all");
  const [items, setItems] = useState(data.items || []);
  useEffect(() => { setItems(data.items || []); }, [data]);
  const count = (s) => items.filter((i) => i.status === s).length;
  const toggle = async (idx) => {
    const v = !items[idx].verified;
    setItems(items.map((it, j) => (j === idx ? { ...it, verified: v } : it)));
    try { await patchWp(project.id, idx, v, tool); onChange(); } catch { toast.error("Could not save"); }
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
              {it.quantity && <p className="font-mono text-xs text-cyan-300 mt-1" data-testid={`wp-item-qty-${it.idx}`}>{it.quantity}</p>}
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

const Steps = ({ id, title, items, mark }) => items?.length ? (
  <div className="bg-[#111827] border border-slate-800 rounded-xl p-4" data-testid={id}>
    <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-slate-500 mb-2">{title}</p>
    <ul className="space-y-1.5">{items.map((x, i) => <li key={i} className="text-xs text-slate-300 flex gap-2"><span className="font-mono text-amber-400">{mark || `${i + 1}.`}</span>{String(x).replace(/^\s*\d+[.)]\s*/, "")}</li>)}</ul>
  </div>
) : null;

export const DrainagePlan = ({ project, onChange }) => (
  <div className="space-y-4">
  <ToolGate project={project} tool="drainage" title="Drainage plan" icon={Waves} onChange={onChange}
    blurb="Builds a full drainage plan from the set: footing drain tile with quantities, gravel and fabric, discharge and sump, cleanouts, grading, swales, downspouts, window wells and under-slab drainage — flagging what's missing.">
    {(data) => (
      <div className="space-y-4" data-testid="drainage-plan">
        {data.strategy && (
          <div className="bg-[#111827] border border-cyan-500/30 rounded-xl p-4" data-testid="drainage-strategy">
            <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-cyan-400 mb-1">Water path / strategy</p>
            <p className="text-sm text-slate-200 leading-relaxed">{data.strategy}</p>
          </div>
        )}
        <WpBody project={project} data={data} onChange={onChange} tool="drainage" />
        <div className="grid md:grid-cols-3 gap-4">
          <Steps id="drainage-sequence" title="Installation sequence" items={data.sequence} />
          <Steps id="drainage-inspections" title="Hold points & inspections" items={data.inspections} mark="✓" />
          <Steps id="drainage-rfis" title="Questions / RFIs" items={data.rfis} mark="?" />
        </div>
      </div>
    )}
  </ToolGate>
  <DrainOverlay project={project} onChange={onChange} />
  <DrainTakeoff project={project} refreshKey={project.pages.map((p) => `${p.drain_status}:${p.drain_overlay?.edited_at || ""}:${p.drain_overlay?.edited}`).join("|")} />
  </div>
);
