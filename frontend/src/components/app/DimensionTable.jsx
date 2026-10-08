import { useState } from "react";
import { Download, Search } from "lucide-react";

const COLS = {
  rooms: ["name", "width", "length", "area", "ceiling_height", "source", "notes"],
  walls: ["id", "location", "length", "thickness", "type", "source", "notes"],
  openings: ["id", "type", "location", "width", "height", "source", "notes"],
};
const MONO = new Set(["width", "length", "area", "ceiling_height", "thickness", "height"]);
const label = (c) => c.replace("_", " ");

const toCsv = (rows, cols) =>
  [cols.join(","), ...rows.map((r) => cols.map((c) => `"${String(r[c] ?? "").replace(/"/g, '""')}"`).join(","))].join("\n");

export const DimensionTable = ({ project }) => {
  const [tab, setTab] = useState("rooms");
  const [q, setQ] = useState("");
  if (project.status !== "ready") return null;

  const cols = COLS[tab];
  const rows = (project.analysis[tab] || []).filter((r) => JSON.stringify(r).toLowerCase().includes(q.toLowerCase()));

  const exportCsv = () => {
    const blob = new Blob([toCsv(project.analysis[tab] || [], cols)], { type: "text/csv" });
    const a = Object.assign(document.createElement("a"), { href: URL.createObjectURL(blob), download: `${project.name}-${tab}.csv` });
    a.click();
  };

  return (
    <div data-testid="dimension-table-container" className="bg-[#111827] border border-slate-800 rounded-xl fade-up">
      <div className="flex flex-wrap items-center justify-between gap-3 p-4 border-b border-slate-800">
        <div className="flex gap-1 bg-[#0B0F17] border border-slate-800 rounded-lg p-1">
          {Object.keys(COLS).map((t) => (
            <button key={t} data-testid={`tab-${t}`} onClick={() => setTab(t)}
              className={`px-3 py-1.5 rounded-md text-xs font-medium capitalize transition-colors ${tab === t ? "bg-amber-500 text-[#0B0F17]" : "text-slate-400 hover:text-slate-100"}`}>
              {t} <span className="font-mono opacity-70">{(project.analysis[t] || []).length}</span>
            </button>
          ))}
        </div>
        <div className="flex gap-2">
          <div className="relative">
            <Search className="h-3.5 w-3.5 absolute left-2.5 top-2.5 text-slate-500" />
            <input data-testid="table-search-input" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Filter"
              className="bg-[#0B0F17] border border-slate-800 rounded-md pl-8 pr-2 py-2 text-xs w-36 focus:outline-none focus:ring-2 focus:ring-cyan-500" />
          </div>
          <button data-testid="export-csv-button" onClick={exportCsv} className="flex items-center gap-1.5 text-xs border border-slate-700 rounded-md px-3 py-2 hover:bg-slate-800 transition-colors">
            <Download className="h-3.5 w-3.5" /> CSV
          </button>
        </div>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead><tr>{cols.map((c) => <th key={c} className="text-left font-mono text-[10px] uppercase tracking-[0.15em] text-slate-500 font-medium px-4 py-3 border-b border-slate-800 whitespace-nowrap">{label(c)}</th>)}</tr></thead>
          <tbody>
            {rows.length === 0 && <tr><td colSpan={cols.length} className="px-4 py-6 text-xs text-slate-500" data-testid="table-empty">No {tab} found on this drawing.</td></tr>}
            {rows.map((r, i) => (
              <tr key={i} data-testid="dimension-row-item" className="border-b border-slate-800/60 hover:bg-slate-800/40 transition-colors">
                {cols.map((c) => (
                  <td key={c} className={`px-4 py-2.5 align-top ${MONO.has(c) ? "font-mono text-xs text-amber-400 whitespace-nowrap" : c === "notes" ? "text-xs text-slate-400 min-w-[180px]" : "text-slate-200"}`}>
                    {c === "source" ? <span className={`font-mono text-[10px] uppercase border rounded px-1.5 py-0.5 ${r[c] === "labeled" ? "text-emerald-400 border-emerald-500/40" : "text-cyan-400 border-cyan-500/40"}`}>{r[c] || "—"}</span> : (r[c] || "—")}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};
