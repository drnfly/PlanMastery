export const EditableGrid = ({ id, columns, rows, onChange, onCommit }) => {
  const set = (i, key, val) => onChange(rows.map((r, j) => (j === i ? { ...r, [key]: val } : r)));
  return (
    <div className="overflow-x-auto border border-slate-800 rounded-lg" data-testid={id}>
      <table className="w-full text-xs">
        <thead className="bg-[#0B0F17]">
          <tr>{columns.map((c) => <th key={c.key} className="text-left font-mono text-[10px] uppercase tracking-wider text-slate-500 px-2 py-2 whitespace-nowrap">{c.label}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} className="border-t border-slate-800 hover:bg-slate-800/40">
              {columns.map((c) => (
                <td key={c.key} className="px-1 py-1">
                  <input data-testid={`${id}-${i}-${c.key}`} value={r[c.key] ?? ""} onChange={(e) => set(i, c.key, e.target.value)} onBlur={onCommit}
                    type={c.num ? "number" : "text"} step="any"
                    className={`bg-transparent rounded px-1.5 py-1 font-mono text-slate-200 focus:outline-none focus:ring-1 focus:ring-cyan-500 focus:bg-[#0B0F17] ${c.w || "w-16"}`} />
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};
