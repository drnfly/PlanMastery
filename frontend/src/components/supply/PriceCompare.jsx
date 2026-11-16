import { useState } from "react";
import { CATS, money, priceOf, bestFor, supplierTotal, mixTotal, activeItems } from "@/components/supply/calc";

const QuoteCell = ({ doc, s, item, onQuote }) => {
  const pr = priceOf(doc, s.id, item.key);
  const [edit, setEdit] = useState(false);
  const [val, setVal] = useState("");
  const best = bestFor(doc, item.key);
  const isBest = pr && best && best.sid === s.id;
  const id = `${s.id}-${item.key}`;
  if (edit) {
    const save = () => { setEdit(false); const n = parseFloat(val); onQuote(s.id, item.key, Number.isFinite(n) && n > 0 ? n : null); };
    return (
      <td className="px-2 py-1.5">
        <input autoFocus data-testid={`quote-input-${id}`} type="number" min="0" step="0.01" value={val} placeholder="unit $"
          onChange={(e) => setVal(e.target.value)} onBlur={save} onKeyDown={(e) => { if (e.key === "Enter") save(); if (e.key === "Escape") setEdit(false); }}
          className="w-20 bg-[#0B0F17] border border-cyan-600 rounded px-1.5 py-0.5 text-xs text-slate-100 font-mono" />
      </td>
    );
  }
  return (
    <td className="px-2 py-1.5">
      <button data-testid={`quote-cell-${id}`} title={pr ? (pr.quoted ? "Your quote — click to change, clear to remove" : "AI estimate — click to enter your real quote") : "Click to enter a quote"}
        onClick={() => { setVal(doc.quotes?.[s.id]?.[item.key] ?? ""); setEdit(true); }}
        className={`text-left font-mono text-xs rounded px-1.5 py-0.5 hover:bg-slate-800 ${isBest ? "bg-emerald-500/15 text-emerald-300" : "text-slate-300"}`}>
        {pr ? (
          <>
            <span className={pr.quoted ? "font-bold" : "italic"}>{money(pr.p)}</span>
            <span className="ml-1 text-[9px] uppercase text-slate-500">{pr.quoted ? "quote" : "est"}</span>
            <span className="block text-[10px] text-slate-500">{money(pr.p * item.qty)}</span>
          </>
        ) : <span className="text-slate-600">+ quote</span>}
      </button>
    </td>
  );
};

const QtyCell = ({ item, onItem }) => {
  const [v, setV] = useState(String(item.qty));
  return (
    <td className="px-2 py-1.5 whitespace-nowrap">
      <input data-testid={`item-qty-${item.key}`} type="number" min="0" value={v} onChange={(e) => setV(e.target.value)}
        onBlur={() => { const n = parseFloat(v); if (Number.isFinite(n) && n >= 0 && n !== item.qty) onItem(item.key, { qty: n }); }}
        className="w-16 bg-[#0B0F17] border border-slate-700 rounded px-1.5 py-0.5 text-xs text-slate-100 font-mono" />
      <span className="ml-1 text-[10px] text-slate-500">{item.unit}</span>
    </td>
  );
};

export const PriceCompare = ({ doc, cols, onQuote, onItem }) => {
  const sections = [...new Set((doc.items || []).map((i) => i.section))];
  const act = activeItems(doc);
  return (
    <div className="bg-[#111827] border border-slate-800 rounded-xl p-4 space-y-3" data-testid="price-compare">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <div>
          <p className="font-semibold text-slate-200 text-sm">Price comparison</p>
          <p className="text-xs text-slate-500">Italic = AI estimate. Click any price to type your real quote (unit price) — quotes replace estimates everywhere. Green = cheapest.</p>
        </div>
        <p className="text-sm text-slate-300" data-testid="price-mix-total">Cheapest mix: <span className="font-mono text-emerald-300 font-semibold">{money(mixTotal(doc))}</span></p>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-xs min-w-[720px]">
          <thead>
            <tr className="text-left text-slate-500 border-b border-slate-800">
              <th className="px-2 py-2 font-medium">Use</th>
              <th className="px-2 py-2 font-medium">Item</th>
              <th className="px-2 py-2 font-medium">Qty</th>
              <th className="px-2 py-2 font-medium">Best</th>
              {cols.map((s) => (
                <th key={s.id} className="px-2 py-2 font-medium max-w-[140px]" data-testid={`compare-col-${s.id}`}>
                  <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full shrink-0" style={{ background: CATS[s.category]?.color }} /><span className="truncate text-slate-300">{s.name}</span></span>
                  <span className="text-[10px] font-normal">{s.distance_mi} mi</span>
                </th>
              ))}
            </tr>
          </thead>
          {sections.map((sec) => (
            <tbody key={sec}>
              <tr><td colSpan={4 + cols.length} className="px-2 pt-3 pb-1 font-mono text-[10px] uppercase tracking-[0.15em] text-cyan-400">{sec}</td></tr>
              {doc.items.filter((i) => i.section === sec).map((i) => {
                const b = bestFor(doc, i.key);
                return (
                  <tr key={i.key} className={`border-b border-slate-800/60 ${i.on ? "" : "opacity-40"}`} data-testid={`item-row-${i.key}`}>
                    <td className="px-2 py-1.5"><input data-testid={`item-on-${i.key}`} type="checkbox" checked={i.on} onChange={(e) => onItem(i.key, { on: e.target.checked })} className="accent-cyan-500" /></td>
                    <td className="px-2 py-1.5"><p className="text-slate-200">{i.name}</p><p className="text-[10px] text-slate-500 max-w-[220px] truncate">{i.spec}</p></td>
                    <QtyCell key={`${i.key}-${i.qty}`} item={i} onItem={onItem} />
                    <td className="px-2 py-1.5" data-testid={`item-best-${i.key}`}>
                      {b ? <><p className="font-mono text-emerald-300">{money(b.p * i.qty)}</p><p className="text-[10px] text-slate-500 max-w-[130px] truncate">{b.name}</p></> : <span className="text-slate-600">—</span>}
                    </td>
                    {cols.map((s) => <QuoteCell key={s.id} doc={doc} s={s} item={i} onQuote={onQuote} />)}
                  </tr>
                );
              })}
            </tbody>
          ))}
          <tfoot>
            <tr className="border-t border-slate-700 text-slate-200">
              <td colSpan={3} className="px-2 py-2 font-semibold">Total ({act.length} items)</td>
              <td className="px-2 py-2 font-mono text-emerald-300 font-semibold">{money(mixTotal(doc))}</td>
              {cols.map((s) => {
                const t = supplierTotal(doc, s.id);
                return <td key={s.id} className="px-2 py-2 font-mono" data-testid={`compare-total-${s.id}`}>{money(t.total)}<span className="block text-[10px] text-slate-500 font-sans">{t.n}/{act.length} items</span></td>;
              })}
            </tr>
          </tfoot>
        </table>
      </div>
    </div>
  );
};
