export const CATS = {
  rental: { label: "Equipment rental", color: "#F59E0B" },
  big_box: { label: "Home center", color: "#F97316" },
  building: { label: "Building / lumber supply", color: "#06B6D4" },
  landscape: { label: "Stone / landscape supply", color: "#22C55E" },
  plumbing: { label: "Plumbing supply", color: "#3B82F6" },
  hardware: { label: "Hardware store", color: "#A855F7" },
};

export const money = (v) => (v == null ? "—" : `$${v.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`);

export const priceOf = (doc, sid, key) => {
  const q = doc.quotes?.[sid]?.[key];
  if (q != null) return { p: q, quoted: true };
  const e = doc.estimates?.[sid]?.[key];
  return e != null ? { p: e, quoted: false } : null;
};

export const activeItems = (doc) => (doc.items || []).filter((i) => i.on && i.qty > 0);

export const supplierTotal = (doc, sid) => {
  let total = 0;
  let n = 0;
  let quoted = 0;
  activeItems(doc).forEach((i) => {
    const pr = priceOf(doc, sid, i.key);
    if (pr) { total += pr.p * i.qty; n += 1; if (pr.quoted) quoted += 1; }
  });
  return { total, n, quoted };
};

export const bestFor = (doc, key) => {
  let best = null;
  (doc.suppliers || []).forEach((s) => {
    const pr = priceOf(doc, s.id, key);
    if (pr && (!best || pr.p < best.p)) best = { ...pr, sid: s.id, name: s.name };
  });
  return best;
};

export const mixTotal = (doc) => activeItems(doc).reduce((t, i) => {
  const b = bestFor(doc, i.key);
  return b ? t + b.p * i.qty : t;
}, 0);

export const directions = (s) => `https://www.google.com/maps/dir/?api=1&destination=${s.lat},${s.lon}`;
