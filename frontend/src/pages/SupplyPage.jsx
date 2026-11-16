import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import { ArrowLeft, Loader2, MapPin, RefreshCw, Search, AlertTriangle } from "lucide-react";
import { getProject, getSupply, searchSupply, repriceSupply, setSupplyItem, setSupplyQuote, addSupplier, removeSupplier } from "@/lib/api";
import { SupplierMap } from "@/components/supply/SupplierMap";
import { SupplierList } from "@/components/supply/SupplierList";
import { PriceCompare } from "@/components/supply/PriceCompare";
import { CATS, supplierTotal } from "@/components/supply/calc";

const RADII = [10, 15, 25, 50, 75];

const SearchBar = ({ doc, onSearch, busy }) => {
  const [address, setAddress] = useState(doc?.address || "");
  const [radius, setRadius] = useState(doc?.radius_mi || 25);
  useEffect(() => { if (doc?.address) { setAddress(doc.address); setRadius(doc.radius_mi); } }, [doc?.address, doc?.radius_mi]);
  return (
    <form className="bg-[#111827] border border-slate-800 rounded-xl p-4 flex flex-wrap items-end gap-3" data-testid="supply-search-form"
      onSubmit={(e) => { e.preventDefault(); onSearch(address.trim(), radius); }}>
      <label className="flex-1 min-w-[240px]">
        <span className="font-mono text-[10px] uppercase tracking-[0.15em] text-slate-500">Job address</span>
        <input data-testid="supply-address-input" value={address} onChange={(e) => setAddress(e.target.value)} placeholder="123 Main St, Columbus, OH"
          className="mt-1 w-full bg-[#0B0F17] border border-slate-700 rounded-md px-3 py-2 text-sm text-slate-100 focus:outline-none focus:ring-1 focus:ring-cyan-500" />
      </label>
      <label>
        <span className="font-mono text-[10px] uppercase tracking-[0.15em] text-slate-500">Radius</span>
        <select data-testid="supply-radius-select" value={radius} onChange={(e) => setRadius(Number(e.target.value))}
          className="mt-1 block bg-[#0B0F17] border border-slate-700 rounded-md px-3 py-2 text-sm text-slate-100">
          {RADII.map((r) => <option key={r} value={r}>{r} miles</option>)}
        </select>
      </label>
      <button data-testid="supply-search-button" type="submit" disabled={busy || address.trim().length < 3}
        className="flex items-center gap-2 rounded-md bg-cyan-500 text-[#0B0F17] font-semibold px-4 py-2 text-sm hover:bg-cyan-400 disabled:opacity-40 active:scale-95 transition-[background-color,transform]">
        {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}{doc?.address ? "Search again" : "Find suppliers"}
      </button>
    </form>
  );
};

const StatusBar = ({ doc, onReprice }) => {
  if (doc.status === "searching") return <p className="flex items-center gap-2 text-sm text-cyan-300" data-testid="supply-status"><Loader2 className="h-4 w-4 animate-spin" />Finding suppliers near {doc.place || doc.address}… (about a minute)</p>;
  if (doc.status === "failed") return <p className="flex items-center gap-2 text-sm text-red-400" data-testid="supply-status"><AlertTriangle className="h-4 w-4" />{doc.error}</p>;
  return (
    <div className="flex flex-wrap items-center gap-3 text-xs text-slate-400" data-testid="supply-status">
      <span className="flex items-center gap-1.5"><MapPin className="h-3.5 w-3.5 text-cyan-400" />{doc.display}</span>
      {doc.price_status === "running" && <span className="flex items-center gap-1.5 text-amber-300"><Loader2 className="h-3.5 w-3.5 animate-spin" />AI is estimating prices…</span>}
      {doc.price_status === "failed" && <span className="text-red-400">Price estimate failed: {doc.price_error}</span>}
      {doc.price_status !== "running" && (
        <button data-testid="supply-reprice-button" onClick={onReprice} className="flex items-center gap-1 text-cyan-300 hover:text-cyan-200"><RefreshCw className="h-3 w-3" />Re-estimate prices</button>
      )}
      {doc.has_takeoff === false && <span className="text-amber-300" data-testid="supply-no-takeoff">No drain tile layout yet — drainage and waterproofing quantities are empty. Draw the layout to fill them.</span>}
    </div>
  );
};

export default function SupplyPage() {
  const { pid } = useParams();
  const nav = useNavigate();
  const [project, setProject] = useState(null);
  const [doc, setDoc] = useState(null);
  const [busy, setBusy] = useState(false);
  const [selected, setSelected] = useState(null);
  const [cats, setCats] = useState(Object.keys(CATS));
  const [compare, setCompare] = useState(null);

  const load = useCallback(() => getSupply(pid).then((d) => { setDoc(d?.lat != null ? d : null); return d; }), [pid]);
  useEffect(() => { getProject(pid).then(setProject).catch(() => toast.error("Project not found")); load(); }, [pid, load]);
  const pending = doc?.status === "searching" || doc?.price_status === "running";
  useEffect(() => {
    if (!pending) return undefined;
    const t = setInterval(load, 4000);
    return () => clearInterval(t);
  }, [pending, load]);

  const shown = useMemo(() => (doc?.suppliers || []).filter((s) => cats.includes(s.category))
    .map((s) => ({ s, t: supplierTotal(doc, s.id) }))
    .sort((a, b) => (b.t.n ? 1 : 0) - (a.t.n ? 1 : 0) || (a.t.n && b.t.n ? b.t.n - a.t.n || a.t.total - b.t.total : a.s.distance_mi - b.s.distance_mi))
    .map((x) => x.s), [doc, cats]);

  const defaultCols = useMemo(() => {
    if (!doc) return [];
    const pick = [];
    Object.keys(CATS).forEach((c) => {
      const s = shown.find((x) => x.category === c && supplierTotal(doc, x.id).n);
      if (s && pick.length < 4) pick.push(s.id);
    });
    return pick;
  }, [doc, shown]);
  const colIds = compare ?? defaultCols;
  const cols = colIds.map((id) => doc?.suppliers.find((s) => s.id === id)).filter(Boolean);

  const search = async (address, radius) => {
    setBusy(true);
    try { setDoc(await searchSupply(pid, { address, radius_mi: radius })); setCompare(null); setSelected(null); }
    catch (e) { toast.error(e.response?.data?.detail || "Search failed"); }
    finally { setBusy(false); }
  };
  const act = (fn, msg) => async (...a) => {
    try { const r = await fn(...a); await load(); if (msg) toast.success(msg); return r ?? true; }
    catch (e) { toast.error(e.response?.data?.detail || "Something went wrong"); return false; }
  };
  const onQuote = act((sid, key, price) => setSupplyQuote(pid, { supplier_id: sid, item_key: key, price }));
  const onItem = act((key, patch) => setSupplyItem(pid, { key, ...patch }));
  const onAdd = act((f) => addSupplier(pid, f), "Supplier added");
  const onRemove = act((s) => removeSupplier(pid, s.id));
  const onReprice = act(() => repriceSupply(pid));
  const toggleCompare = (id) => setCompare((c) => {
    const cur = c ?? defaultCols;
    if (cur.includes(id)) return cur.filter((x) => x !== id);
    if (cur.length >= 5) { toast.info("Compare up to 5 suppliers at a time"); return cur; }
    return [...cur, id];
  });

  return (
    <div className="min-h-screen bg-[#0B0F17] text-slate-200" data-testid="supply-page">
      <header className="border-b border-slate-800 px-5 py-3 flex items-center gap-4">
        <button data-testid="supply-back-button" onClick={() => nav(`/?project=${pid}`)} className="flex items-center gap-1.5 text-sm border border-slate-700 rounded-md px-3 py-1.5 hover:bg-slate-800">
          <ArrowLeft className="h-4 w-4" />Back
        </button>
        <div>
          <h1 className="text-xl font-bold tracking-tight text-slate-100" style={{ fontFamily: "Outfit, sans-serif" }}>Local suppliers &amp; prices</h1>
          <p className="font-mono text-[11px] text-slate-500">{project?.name} · drainage, waterproofing &amp; equipment rental</p>
        </div>
      </header>
      <main className="max-w-[1500px] mx-auto px-4 sm:px-6 py-6 space-y-5">
        <SearchBar doc={doc} onSearch={search} busy={busy} />
        {!doc && <p className="text-sm text-slate-400" data-testid="supply-empty">Type the job address to map every nearby supply yard, home center, stone yard and rental shop, with estimated prices for this job's materials.</p>}
        {doc && (
          <>
            <StatusBar doc={doc} onReprice={onReprice} />
            <div className="flex flex-wrap gap-2" data-testid="supply-category-filters">
              {Object.entries(CATS).map(([k, c]) => {
                const on = cats.includes(k);
                return (
                  <button key={k} data-testid={`supply-filter-${k}`} onClick={() => setCats((x) => (on ? x.filter((y) => y !== k) : [...x, k]))}
                    className={`flex items-center gap-1.5 text-xs rounded-full border px-3 py-1 transition-colors ${on ? "border-slate-500 text-slate-200" : "border-slate-800 text-slate-500"}`}>
                    <span className="h-2 w-2 rounded-full" style={{ background: on ? c.color : "#334155" }} />{c.label}
                    <span className="text-slate-500">{doc.suppliers.filter((s) => s.category === k).length}</span>
                  </button>
                );
              })}
            </div>
            <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_380px] gap-5 [&>*]:min-w-0">
              <SupplierMap doc={doc} shown={shown} selected={selected} onSelect={setSelected} />
              <SupplierList doc={doc} shown={shown} selected={selected} onSelect={setSelected} compare={colIds}
                toggleCompare={toggleCompare} onRemove={onRemove} onAdd={onAdd} />
            </div>
            {doc.items?.length > 0 && <PriceCompare doc={doc} cols={cols} onQuote={onQuote} onItem={onItem} />}
            {doc.notes && <p className="text-xs text-slate-500" data-testid="supply-notes">AI pricing assumptions: {doc.notes} Estimates are not quotes — call to confirm.</p>}
            <p className="text-[11px] text-slate-600">Supplier listings from OpenStreetMap contributors — some local yards may be missing; add them above.</p>
          </>
        )}
      </main>
    </div>
  );
}
