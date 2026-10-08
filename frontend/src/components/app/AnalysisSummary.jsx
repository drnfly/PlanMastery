import { AlertTriangle, RefreshCw, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { reanalyze } from "@/lib/api";

const Stat = ({ label, value, id }) => (
  <div className="border border-slate-800 rounded-lg p-3 bg-[#0B0F17]">
    <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-slate-500">{label}</p>
    <p className="font-mono text-sm text-amber-400 mt-1 truncate" data-testid={id}>{value || "—"}</p>
  </div>
);

export const AnalysisSummary = ({ project, onReanalyze }) => {
  const a = project.analysis;
  const rerun = async () => { await reanalyze(project.id); toast.info("Re-analyzing drawing"); onReanalyze(); };

  if (project.status === "analyzing") return (
    <div className="bg-[#111827] border border-slate-800 rounded-xl p-6 flex items-center gap-3" data-testid="analysis-pending">
      <Loader2 className="h-5 w-5 animate-spin text-cyan-400" />
      <div><p className="text-sm font-medium">Reading dimensions, room tags and schedules…</p><p className="text-xs text-slate-500">Detailed drawings can take up to a minute or two.</p></div>
    </div>
  );

  if (project.status === "failed") return (
    <div className="bg-[#111827] border border-red-500/30 rounded-xl p-6 flex items-center justify-between gap-4" data-testid="analysis-failed">
      <p className="text-sm text-red-300">Analysis failed: {project.error}</p>
      <button data-testid="retry-analysis-button" onClick={rerun} className="text-xs border border-slate-700 rounded-md px-3 py-2 hover:bg-slate-800 transition-colors flex items-center gap-1.5"><RefreshCw className="h-3.5 w-3.5" />Retry</button>
    </div>
  );

  return (
    <div className="bg-[#111827] border border-slate-800 rounded-xl p-6 fade-up" data-testid="analysis-summary">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-cyan-400">{a.drawing_type}</p>
          <h2 className="font-display text-lg font-semibold mt-1" data-testid="analysis-title">{a.title}</h2>
        </div>
        <button data-testid="reanalyze-button" onClick={rerun} className="shrink-0 text-xs border border-slate-700 rounded-md px-3 py-2 hover:bg-slate-800 transition-colors flex items-center gap-1.5"><RefreshCw className="h-3.5 w-3.5" />Re-run</button>
      </div>
      <p className="text-sm text-slate-300 leading-relaxed mt-3" data-testid="analysis-summary-text">{a.summary}</p>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-5">
        <Stat label="Scale" value={a.scale} id="stat-scale" />
        <Stat label="Overall W" value={a.overall?.width} id="stat-width" />
        <Stat label="Overall L" value={a.overall?.length} id="stat-length" />
        <Stat label="Total area" value={a.overall?.total_area} id="stat-area" />
      </div>
      {a.warnings?.length > 0 && (
        <div className="mt-4 border border-amber-500/30 bg-amber-500/5 rounded-lg p-3" data-testid="analysis-warnings">
          <p className="flex items-center gap-1.5 text-xs font-medium text-amber-400"><AlertTriangle className="h-3.5 w-3.5" />Verify on site</p>
          <ul className="mt-1.5 space-y-1 text-xs text-slate-400 list-disc pl-5">{a.warnings.map((w, i) => <li key={i}>{w}</li>)}</ul>
        </div>
      )}
    </div>
  );
};
