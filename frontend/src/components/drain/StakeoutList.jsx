import { MapPin } from "lucide-react";
import { fmtFt, sfmt } from "@/components/drain/geometry";

export const StakeoutList = ({ rows, sel, setSel, hasCorners }) => (
  <div className="bg-[#111827] border border-slate-800 rounded-xl p-4 text-xs space-y-2" data-testid="stakeout-list">
    <p className="flex items-center gap-1.5 text-slate-200 font-semibold"><MapPin className="h-3.5 w-3.5 text-amber-400" />Stake-out distances</p>
    <p className="text-slate-500">Straight line to the nearest footing corner, plus offsets along each wall from that corner (minus = behind the corner, outside that wall line).</p>
    {!hasCorners && <p className="text-amber-300" data-testid="stakeout-no-corners">Trace the footing outline to get corner distances.</p>}
    {hasCorners && !rows.length && <p className="text-slate-400" data-testid="stakeout-empty">Add a cleanout or sump to see distances.</p>}
    {rows.length > 0 && (
      <table className="w-full font-mono">
        <thead><tr className="text-slate-500 text-left"><th className="py-1 font-normal">Item</th><th className="font-normal">Corner</th><th className="font-normal text-right">Distance</th></tr></thead>
        <tbody>
          {rows.map((r) => {
            const on = sel?.kind === r.kind && (r.i === undefined || sel.i === r.i);
            return (
              <tr key={`${r.kind}-${r.i ?? 0}`} data-testid={`stakeout-row-${r.kind}-${r.i ?? 0}`} onClick={() => setSel({ kind: r.kind, ...(r.i !== undefined && { i: r.i }) })}
                className={`cursor-pointer border-t border-slate-800 transition-colors ${on ? "bg-amber-500/15 text-amber-200" : "text-slate-300 hover:bg-slate-800/60"}`}>
                <td className="py-1.5 pl-1">{r.label}<span className="text-slate-500 ml-1 font-sans">{r.type.toLowerCase()}</span></td>
                <td>C{r.corner + 1}</td>
                <td className="text-right pr-1 text-amber-300" data-testid={`stakeout-dist-${r.kind}-${r.i ?? 0}`}>
                  {r.ft != null ? fmtFt(r.ft) : "—"}
                  {r.aTo != null && r.aFt != null && (
                    <span className="block text-[10px] text-teal-300" data-testid={`stakeout-offsets-${r.kind}-${r.i ?? 0}`}>
                      {sfmt(r.aFt)} → C{r.aTo + 1} · {sfmt(r.bFt)} → C{r.bTo + 1}
                    </span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    )}
    {rows.length > 0 && rows[0].ft == null && <p className="text-slate-500">Enter the measured tile length to show feet.</p>}
  </div>
);
