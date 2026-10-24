const DOT = { pending: "bg-slate-600", analyzing: "bg-cyan-400 animate-pulse", ready: "bg-emerald-400", failed: "bg-red-400" };

export const SheetStrip = ({ pages, active, onSelect }) => {
  if (pages.length <= 1) return null;
  return (
    <div className="bg-[#111827] border border-slate-800 rounded-xl p-3" data-testid="sheet-strip">
      <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-slate-500 mb-2 px-1">{pages.length} sheets in set</p>
      <div className="flex gap-2 overflow-x-auto pb-1">
        {pages.map((pg) => (
          <button key={pg.index} data-testid={`sheet-tab-${pg.index}`} onClick={() => onSelect(pg.index)}
            className={`shrink-0 text-left rounded-lg border px-3 py-2 w-44 transition-colors ${pg.index === active ? "border-amber-500/60 bg-amber-500/10" : "border-slate-800 hover:bg-slate-800/60"}`}>
            <div className="flex items-center gap-1.5">
              <span className={`h-1.5 w-1.5 rounded-full ${DOT[pg.status]}`} />
              <span className="font-mono text-[11px] text-amber-400">{pg.sheet_number || `P${pg.index + 1}`}</span>
              {pg.discipline && <span className="font-mono text-[9px] uppercase text-slate-500 ml-auto">{pg.discipline.slice(0, 6)}</span>}
            </div>
            <p className="text-xs text-slate-300 truncate mt-1">{pg.title}</p>
          </button>
        ))}
      </div>
    </div>
  );
};
