import { useState } from "react";
import { toast } from "sonner";
import { ScanSearch, FileDown, Loader2 } from "lucide-react";
import { scanSet } from "@/lib/api";
import { ReportDialog } from "@/components/app/ReportDialog";

export const SetToolbar = ({ project, onChange }) => {
  const [open, setOpen] = useState(false);
  const pages = project.pages;
  const scanned = pages.filter((pg) => pg.status === "ready" && pg.analysis).length;
  const deep = pages.filter((pg) => pg.analysis?.digest).length;
  const running = pages.filter((pg) => pg.status === "analyzing").length;
  const pct = Math.round((scanned / pages.length) * 100);

  const scan = async () => {
    const { queued } = await scanSet(project.id);
    toast.info(queued ? `Scanning ${queued} sheet${queued > 1 ? "s" : ""}…` : "Every sheet is already scanned");
    onChange();
  };

  return (
    <div className="bg-[#111827] border border-slate-800 rounded-xl p-4 flex flex-wrap items-center gap-4" data-testid="set-toolbar">
      <div className="flex-1 min-w-[200px]">
        <div className="flex items-baseline justify-between">
          <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-slate-500">Set scan</p>
          <p className="font-mono text-xs text-cyan-400" data-testid="scan-progress-text">{scanned}/{pages.length} sheets{running ? ` · ${running} scanning` : ""}</p>
        </div>
        <div className="mt-2 h-1.5 rounded-full bg-slate-800 overflow-hidden">
          <div className="h-full bg-emerald-400 transition-[width] duration-500" style={{ width: `${pct}%` }} />
        </div>
      </div>
      <button data-testid="scan-set-button" onClick={scan} disabled={running > 0 || deep === pages.length}
        className="flex items-center gap-2 rounded-md border border-cyan-500/50 text-cyan-300 px-3 py-2 text-sm hover:bg-cyan-500/10 disabled:opacity-40 transition-colors">
        {running ? <Loader2 className="h-4 w-4 animate-spin" /> : <ScanSearch className="h-4 w-4" />}
        {deep === pages.length ? "Set fully scanned" : running ? "Scanning…" : pages.length > 1 ? "Scan entire set" : "Deep scan sheet"}
      </button>
      <button data-testid="open-report-dialog-button" onClick={() => setOpen(true)} disabled={!scanned}
        className="flex items-center gap-2 rounded-md bg-amber-500 text-[#0B0F17] font-semibold px-3 py-2 text-sm hover:bg-amber-400 disabled:opacity-40 active:scale-95 transition-[background-color,transform]">
        <FileDown className="h-4 w-4" /> PDF report
      </button>
      <ReportDialog open={open} onOpenChange={setOpen} project={project} scannedCount={scanned} />
    </div>
  );
};
