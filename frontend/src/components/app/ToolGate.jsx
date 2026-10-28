import { Loader2, Sparkles, RefreshCw } from "lucide-react";
import { toast } from "sonner";
import { runTool } from "@/lib/api";

export const ToolGate = ({ project, tool, title, blurb, icon: Icon, onChange, children }) => {
  const t = project.tools?.[tool] || {};
  const scanned = project.pages.filter((pg) => pg.analysis?.digest).length;
  const run = async () => {
    try { await runTool(project.id, tool); toast.info(`${title}: reading the whole set…`); onChange(); }
    catch (e) { toast.error(e.response?.data?.detail || "Could not start"); }
  };

  if (t.status === "running") return (
    <div className="bg-[#111827] border border-slate-800 rounded-xl p-8 flex items-center gap-4" data-testid={`${tool}-running`}>
      <Loader2 className="h-6 w-6 animate-spin text-cyan-400" />
      <div><p className="font-display font-semibold">{title}</p><p className="text-xs text-slate-400 mt-1">Reviewing every sheet in the set — about 1-2 minutes…</p></div>
    </div>
  );

  if (t.status !== "ready") return (
    <div className="bg-[#111827] border border-slate-800 rounded-xl p-8" data-testid={`${tool}-empty`}>
      <Icon className="h-8 w-8 text-amber-500" />
      <p className="font-display font-semibold text-lg mt-3">{title}</p>
      <p className="text-sm text-slate-400 mt-1 max-w-xl">{blurb}</p>
      {scanned < project.pages.length && (
        <p className="text-xs text-amber-400 mt-3" data-testid={`${tool}-scan-warning`}>{scanned}/{project.pages.length} sheets deep-scanned — scan the entire set first for the most complete result.</p>
      )}
      {t.status === "failed" && <p className="text-xs text-red-400 mt-3" data-testid={`${tool}-error`}>Last run failed: {t.error}</p>}
      <button data-testid={`${tool}-run-button`} onClick={run}
        className="mt-5 flex items-center gap-2 rounded-md bg-amber-500 text-[#0B0F17] font-semibold px-4 py-2 text-sm hover:bg-amber-400 active:scale-95 transition-[background-color,transform]">
        <Sparkles className="h-4 w-4" /> {t.status === "failed" ? "Try again" : `Build ${title.toLowerCase()}`}
      </button>
    </div>
  );

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="font-display font-semibold text-lg flex items-center gap-2"><Icon className="h-5 w-5 text-amber-500" />{title}</p>
        <button data-testid={`${tool}-rerun-button`} onClick={run} className="flex items-center gap-1.5 text-xs border border-slate-700 rounded-md px-3 py-1.5 hover:bg-slate-800 transition-colors">
          <RefreshCw className="h-3.5 w-3.5" /> Re-read plans
        </button>
      </div>
      {children(t.data)}
    </div>
  );
};
