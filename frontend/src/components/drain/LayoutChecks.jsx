import { AlertTriangle, CheckCircle2, Info, Loader2, ShieldCheck, XCircle } from "lucide-react";
import { flagSel } from "@/components/drain/geometry";

const SEV = {
  error: { icon: XCircle, cls: "text-red-400", tag: "Won't work" },
  warning: { icon: AlertTriangle, cls: "text-amber-400", tag: "Check" },
  info: { icon: Info, cls: "text-sky-400", tag: "Field change" },
};
const VERDICT = { works: ["Works with the plans", "text-emerald-400"], works_with_changes: ["Works with changes", "text-amber-300"], wont_work: ["Won't work as drawn", "text-red-400"] };
const order = { error: 0, warning: 1, info: 2 };

const Issue = ({ f, onPick, testid }) => {
  const s = SEV[f.severity] || SEV.warning;
  const Icon = s.icon;
  const Tag = onPick ? "button" : "div";
  return (
    <Tag data-testid={testid} onClick={onPick ? () => onPick(f) : undefined} className={`w-full text-left flex gap-2 rounded-md p-2 border border-slate-800 ${onPick ? "hover:bg-slate-800/60 transition-colors" : ""}`}>
      <Icon className={`h-4 w-4 shrink-0 mt-0.5 ${s.cls}`} />
      <span className="min-w-0">
        <span className="block text-slate-200"><span className={`font-mono text-[10px] uppercase mr-1.5 ${s.cls}`}>{s.tag}</span>{f.item} — {f.problem}</span>
        {f.why && <span className="block text-slate-500 mt-0.5">Why: {f.why}</span>}
        {f.fix && <span className="block text-cyan-300/90 mt-0.5">Fix: {f.fix}</span>}
      </span>
    </Tag>
  );
};

const AiCheck = ({ check, stale, dirty, onRun }) => {
  const running = check?.status === "running";
  const res = check?.status === "ready" ? check.result : null;
  const [label, cls] = VERDICT[res?.verdict] || ["", ""];
  return (
    <div className="border-t border-slate-800 pt-3 space-y-2" data-testid="layout-ai-check">
      <div className="flex items-center justify-between gap-2">
        <p className="flex items-center gap-1.5 text-slate-200 font-semibold"><ShieldCheck className="h-3.5 w-3.5 text-cyan-400" />Check against plans (AI)</p>
        <button data-testid="layout-ai-check-run" onClick={onRun} disabled={running || dirty} title={dirty ? "Save the layout first" : ""}
          className="flex items-center gap-1.5 text-xs border border-cyan-500/60 text-cyan-300 rounded-md px-2.5 py-1 hover:bg-cyan-500/10 disabled:opacity-40">
          {running && <Loader2 className="h-3 w-3 animate-spin" />}{running ? "Checking…" : res ? "Re-check" : "Run check"}
        </button>
      </div>
      {!check && <p className="text-slate-500">Reads the sheet notes and details and tells you if your moves or additions conflict with the plans.{dirty ? " Save first." : ""}</p>}
      {check?.status === "failed" && <p className="text-red-400" data-testid="layout-ai-check-error">Check failed: {check.error}</p>}
      {res && (
        <>
          <p data-testid="layout-ai-verdict"><span className={`font-semibold ${cls}`}>{label}</span> <span className="text-slate-400">{res.summary}</span></p>
          {stale && <p className="text-amber-300" data-testid="layout-ai-check-stale">Layout changed since this check — re-run it.</p>}
          {(res.issues || []).map((f, n) => <Issue key={n} f={f} testid={`layout-ai-issue-${n}`} />)}
        </>
      )}
    </div>
  );
};

export const LayoutChecks = ({ issues, loading, setSel, check, stale, dirty, onRunAi }) => {
  const sorted = [...(issues || [])].sort((a, b) => order[a.severity] - order[b.severity]);
  const errs = sorted.filter((f) => f.severity === "error").length;
  const warns = sorted.filter((f) => f.severity === "warning").length;
  return (
    <div className="bg-[#111827] border border-slate-800 rounded-xl p-4 text-xs space-y-2" data-testid="layout-checks">
      <div className="flex items-center justify-between">
        <p className="font-semibold text-slate-200">Will this layout work?</p>
        {loading && <Loader2 className="h-3.5 w-3.5 animate-spin text-slate-500" />}
      </div>
      <p data-testid="layout-checks-summary" className={errs ? "text-red-400" : warns ? "text-amber-300" : "text-emerald-400"}>
        {errs ? `${errs} problem${errs > 1 ? "s" : ""} won't work` : warns ? "Works, but check the items below" : <span className="flex items-center gap-1"><CheckCircle2 className="h-3.5 w-3.5" />All layout rules pass</span>}
        {errs > 0 && warns > 0 && ` · ${warns} to check`}
      </p>
      <div className="space-y-1.5 max-h-80 overflow-y-auto">
        {sorted.map((f, n) => <Issue key={n} f={f} testid={`layout-issue-${n}`} onPick={(x) => { const s = flagSel(x); if (s) setSel(s); }} />)}
      </div>
      <AiCheck check={check} stale={stale} dirty={dirty} onRun={onRunAi} />
    </div>
  );
};
