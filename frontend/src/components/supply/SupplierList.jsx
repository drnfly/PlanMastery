import { useState } from "react";
import { Phone, Navigation, Trash2, Plus, Columns3 } from "lucide-react";
import { CATS, money, supplierTotal, directions } from "@/components/supply/calc";

const inputCls = "w-full bg-[#0B0F17] border border-slate-700 rounded-md px-2 py-1.5 text-xs text-slate-100 focus:outline-none focus:ring-1 focus:ring-cyan-500";

const AddSupplier = ({ onAdd }) => {
  const [open, setOpen] = useState(false);
  const [f, setF] = useState({ name: "", category: "building", address: "", phone: "" });
  const [busy, setBusy] = useState(false);
  if (!open) {
    return (
      <button data-testid="supplier-add-open" onClick={() => setOpen(true)} className="flex items-center gap-1.5 text-xs text-cyan-300 hover:text-cyan-200">
        <Plus className="h-3.5 w-3.5" /> Add a supplier the map missed
      </button>
    );
  }
  const submit = async () => { setBusy(true); const ok = await onAdd(f); setBusy(false); if (ok) { setOpen(false); setF({ name: "", category: "building", address: "", phone: "" }); } };
  return (
    <div className="space-y-2 border border-slate-800 rounded-lg p-3" data-testid="supplier-add-form">
      <input data-testid="supplier-add-name" className={inputCls} placeholder="Supplier name" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} />
      <select data-testid="supplier-add-category" className={inputCls} value={f.category} onChange={(e) => setF({ ...f, category: e.target.value })}>
        {Object.entries(CATS).map(([k, c]) => <option key={k} value={k}>{c.label}</option>)}
      </select>
      <input data-testid="supplier-add-address" className={inputCls} placeholder="Street, city, state" value={f.address} onChange={(e) => setF({ ...f, address: e.target.value })} />
      <input data-testid="supplier-add-phone" className={inputCls} placeholder="Phone (optional)" value={f.phone} onChange={(e) => setF({ ...f, phone: e.target.value })} />
      <div className="flex gap-2">
        <button data-testid="supplier-add-submit" disabled={busy || f.name.length < 2 || f.address.length < 3} onClick={submit}
          className="text-xs rounded-md bg-cyan-500 text-[#0B0F17] font-semibold px-3 py-1.5 disabled:opacity-40">{busy ? "Adding…" : "Add"}</button>
        <button data-testid="supplier-add-cancel" onClick={() => setOpen(false)} className="text-xs text-slate-400 px-2">Cancel</button>
      </div>
    </div>
  );
};

export const SupplierList = ({ doc, shown, selected, onSelect, compare, toggleCompare, onRemove, onAdd }) => (
  <div className="bg-[#111827] border border-slate-800 rounded-xl p-4 space-y-3" data-testid="supplier-list">
    <div className="flex items-baseline justify-between">
      <p className="font-semibold text-slate-200 text-sm">{shown.length} suppliers</p>
      <p className="font-mono text-[10px] uppercase tracking-[0.15em] text-slate-500">cheapest first</p>
    </div>
    <AddSupplier onAdd={onAdd} />
    <div className="space-y-1.5 max-h-[470px] overflow-y-auto pr-1">
      {shown.map((s) => {
        const t = supplierTotal(doc, s.id);
        const hot = selected?.id === s.id;
        const cmp = compare.includes(s.id);
        return (
          <div key={s.id} data-testid={`supplier-row-${s.id}`} onClick={() => onSelect(s)}
            className={`rounded-lg border p-2.5 cursor-pointer transition-colors ${hot ? "border-cyan-500 bg-cyan-500/5" : "border-slate-800 hover:bg-slate-800/50"}`}>
            <div className="flex items-start gap-2">
              <span className="h-2.5 w-2.5 rounded-full mt-1.5 shrink-0" style={{ background: CATS[s.category]?.color }} />
              <div className="min-w-0 flex-1">
                <p className="text-sm text-slate-100 truncate">{s.name}</p>
                <p className="text-[11px] text-slate-500">{CATS[s.category]?.label} · {s.distance_mi} mi{s.source === "Added by you" ? " · added by you" : ""}</p>
              </div>
              <div className="text-right shrink-0">
                <p className="font-mono text-xs text-amber-300" data-testid={`supplier-total-${s.id}`}>{t.n ? money(t.total) : "—"}</p>
                <p className="text-[10px] text-slate-500">{t.n ? `${t.n} items${t.quoted ? ` · ${t.quoted} quoted` : " · est."}` : "not priced"}</p>
              </div>
            </div>
            <div className="flex items-center gap-3 mt-2 text-[11px]">
              <button data-testid={`supplier-compare-${s.id}`} onClick={(e) => { e.stopPropagation(); toggleCompare(s.id); }}
                className={`flex items-center gap-1 ${cmp ? "text-cyan-300" : "text-slate-400 hover:text-slate-200"}`}>
                <Columns3 className="h-3 w-3" />{cmp ? "Comparing" : "Compare"}
              </button>
              <a data-testid={`supplier-directions-${s.id}`} href={directions(s)} target="_blank" rel="noreferrer" onClick={(e) => e.stopPropagation()} className="flex items-center gap-1 text-slate-400 hover:text-slate-200">
                <Navigation className="h-3 w-3" />Directions
              </a>
              {s.phone && <a href={`tel:${s.phone}`} onClick={(e) => e.stopPropagation()} className="flex items-center gap-1 text-slate-400 hover:text-slate-200"><Phone className="h-3 w-3" />{s.phone}</a>}
              <button data-testid={`supplier-remove-${s.id}`} onClick={(e) => { e.stopPropagation(); onRemove(s); }} className="ml-auto text-slate-500 hover:text-red-400" title="Remove from list">
                <Trash2 className="h-3 w-3" />
              </button>
            </div>
          </div>
        );
      })}
    </div>
  </div>
);
