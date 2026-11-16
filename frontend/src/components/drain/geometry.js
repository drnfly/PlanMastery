export const C = { tile: "#2563EB", discharge: "#16A34A", cleanout: "#EA580C", sump: "#DC2626", slope: "#C026D3", foot: "#06B6D4" };
export const PUMPS = ["pump", "pit_pump", "ejector"];
export const pts = (a, sy) => (a || []).filter((p) => Array.isArray(p) && p.length >= 2).map((p) => `${p[0]},${sy(p[1])}`).join(" ");
export const clamp = (v) => Math.max(0, Math.min(1000, v));
export const clone = (o) => JSON.parse(JSON.stringify(o));

const nextLabel = (list, prefix, start = 1) => {
  const used = new Set(list.map((x) => x?.label));
  let k = start;
  while (used.has(`${prefix}-${k}`)) k++;
  return `${prefix}-${k}`;
};

export const TOOLS = [
  ["select", "Select / move"], ["tile", "Drain tile"], ["cleanout", "Cleanout"], ["sump", "Sump / pump"],
  ["discharge", "Discharge"], ["slope", "Slope arrow"], ["footprint", "Footing outline"],
];

const closed = (a) => a?.length > 2 && a[0][0] === a.at(-1)[0] && a[0][1] === a.at(-1)[1];
const segDist = (p, a, b) => {
  const dx = b[0] - a[0], dy = b[1] - a[1];
  const t = Math.max(0, Math.min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / (dx * dx + dy * dy || 1)));
  return Math.hypot(p[0] - (a[0] + t * dx), p[1] - (a[1] + t * dy));
};
const appendPt = (a, p) => {
  if (!closed(a)) return [...(a || []), p];
  let best = 0;
  a.slice(1).forEach((q, i) => { if (segDist(p, a[i], q) < segDist(p, a[best], a[best + 1])) best = i; });
  return [...a.slice(0, best + 1), p, ...a.slice(best + 1)];
};
const addedIdx = (before, after) => after.findIndex((p, i) => !before[i] || p[0] !== before[i][0] || p[1] !== before[i][1]);

export function addAt(d, tool, x, y) {
  const o = clone(d);
  if (tool === "tile") { const b = o.drain_tile || []; o.drain_tile = appendPt(b, [x, y]); return [o, { kind: "tile", v: addedIdx(b, o.drain_tile) }]; }
  if (tool === "footprint") { const b = o.footprint || []; o.footprint = appendPt(b, [x, y]); return [o, { kind: "foot", v: addedIdx(b, o.footprint) }]; }
  if (tool === "cleanout") {
    o.cleanouts = [...(o.cleanouts || []), { x, y, label: nextLabel(o.cleanouts || [], "CO") }];
    return [o, { kind: "cleanout", i: o.cleanouts.length - 1 }];
  }
  if (tool === "sump") {
    if (!o.sump || o.sump.x == null) { o.sump = { x, y, label: "SUMP", type: "pit_pump", pump_hp: "1/3", pit_size: "18\" x 24\"", notes: "" }; return [o, { kind: "sump" }]; }
    const all = [o.sump, ...(o.sumps || [])];
    o.sumps = [...(o.sumps || []), { x, y, label: nextLabel(all, "SP", 2), type: "pit_pump", pump_hp: "1/3", pit_size: "18\" x 24\"", notes: "", outlet: [clamp(x + 70), clamp(y - 50)] }];
    return [o, { kind: "xsump", i: o.sumps.length - 1 }];
  }
  if (tool === "discharge") {
    const cur = o.discharge?.points || [];
    if (cur.length) { o.discharge = { ...o.discharge, points: [...cur, [x, y]] }; return [o, { kind: "dpt", v: cur.length }]; }
    const start = o.sump?.x != null ? [o.sump.x, o.sump.y] : [clamp(x - 60), y];
    o.discharge = { points: [start, [x, y]], to: "daylight", label: "TO DAYLIGHT" };
    return [o, { kind: "dpt", v: 1 }];
  }
  if (tool === "slope") {
    o.slope_arrows = [...(o.slope_arrows || []), { x1: x, y1: y, x2: clamp(x + 80), y2: y, label: '1/8"/ft' }];
    return [o, { kind: "slope", i: o.slope_arrows.length - 1, end: "b" }];
  }
  return [o, null];
}

export function moveSel(d, s, x, y, start) {
  const o = clone(d);
  const setPt = (arr, v) => {
    const wasClosed = closed(arr);
    arr[v] = [x, y];
    if (wasClosed && v === 0) arr[arr.length - 1] = [x, y];
    if (wasClosed && v === arr.length - 1) arr[0] = [x, y];
  };
  switch (s.kind) {
    case "tile": setPt(o.drain_tile, s.v); break;
    case "foot": setPt(o.footprint, s.v); break;
    case "dpt": setPt(o.discharge.points, s.v); break;
    case "cleanout": Object.assign(o.cleanouts[s.i], { x, y }); break;
    case "xsump": Object.assign(o.sumps[s.i], { x, y }); break;
    case "xoutlet": o.sumps[s.i].outlet = [x, y]; break;
    case "sump":
      Object.assign(o.sump, { x, y });
      if (o.discharge?.points?.length) o.discharge.points[0] = [x, y];
      break;
    case "slope": {
      const a = o.slope_arrows[s.i];
      if (s.end === "a") Object.assign(a, { x1: x, y1: y });
      else if (s.end === "b") Object.assign(a, { x2: x, y2: y });
      else if (start) {
        const dx = x - start.x, dy = y - start.y, b = start.orig;
        Object.assign(a, { x1: clamp(b.x1 + dx), y1: clamp(b.y1 + dy), x2: clamp(b.x2 + dx), y2: clamp(b.y2 + dy) });
      }
      break;
    }
    default: break;
  }
  return o;
}

export function removeSel(d, s) {
  const o = clone(d);
  const drop = (arr, k) => arr.filter((_, j) => j !== k);
  switch (s.kind) {
    case "tile": o.drain_tile = drop(o.drain_tile, s.v); break;
    case "foot": o.footprint = drop(o.footprint, s.v); break;
    case "dpt": o.discharge = o.discharge.points.length <= 2 ? null : { ...o.discharge, points: drop(o.discharge.points, s.v) }; break;
    case "cleanout": o.cleanouts = drop(o.cleanouts, s.i); break;
    case "xsump": o.sumps = drop(o.sumps, s.i); break;
    case "xoutlet": o.sumps[s.i].outlet = null; break;
    case "sump": o.sump = null; break;
    case "slope": o.slope_arrows = drop(o.slope_arrows, s.i); break;
    default: break;
  }
  return o;
}

export const insertVertex = (d, key, after, x, y) => {
  const o = clone(d);
  o[key] = [...o[key].slice(0, after + 1), [x, y], ...o[key].slice(after + 1)];
  return o;
};

export const toBody = (d) => ({
  sump: d.sump?.x != null ? { x: d.sump.x, y: d.sump.y, label: d.sump.label || "", type: d.sump.type || "", pump_hp: d.sump.pump_hp || "", pit_size: d.sump.pit_size || "", notes: d.sump.notes || "" } : null,
  sumps: (d.sumps || []).map((s) => ({ x: s.x, y: s.y, label: s.label || "", type: s.type || "", pump_hp: s.pump_hp || "", pit_size: s.pit_size || "", notes: s.notes || "", outlet: s.outlet || null })),
  cleanouts: (d.cleanouts || []).map((c) => ({ x: c.x, y: c.y, label: c.label || "" })),
  discharge: d.discharge?.points?.length > 1 ? { points: d.discharge.points, to: d.discharge.to || "", label: d.discharge.label || "" } : null,
  drain_tile: d.drain_tile || [],
  footprint: d.footprint || [],
  slope_arrows: (d.slope_arrows || []).map((s) => ({ x1: s.x1, y1: s.y1, x2: s.x2, y2: s.y2, label: s.label || "" })),
  pipe_spec: d.pipe_spec || "",
});

export const svgLen = (a, aspect) => (a || []).slice(1).reduce((s, p, i) => s + Math.hypot(p[0] - a[i][0], (p[1] - a[i][1]) * aspect), 0);

// Feet per SVG unit (x 0-1000, y scaled by aspect); a typed length freezes the scale in draft._k
export function ftPerUnit(saved, draft, page, aspect) {
  if (draft?._length_set && draft._k) return draft._k;
  if (saved?.ft_per_px && page?.img_w) return saved.ft_per_px * page.img_w / 1000;
  const L = svgLen(saved?.drain_tile, aspect);
  return L && saved?.length_ft ? Number(saved.length_ft) / L : 0;
}

export const tileFt = (d, k, aspect) => svgLen(d.drain_tile, aspect) * k;

export const fmtFt = (f) => {
  let ft = Math.floor(f);
  let inch = Math.round((f - ft) * 12);
  if (inch === 12) { ft += 1; inch = 0; }
  return `${ft}'-${inch}"`;
};

const uniq = (a) => (closed(a) ? a.slice(0, -1) : a || []);

// Snap to footing corners (and tile corners for fittings); returns [x, y, hitPoint|null]
export function snapPoint(d, kind, x, y, aspect, self, tol = 14) {
  const targets = [...uniq(d.footprint).map((p, v) => ({ p, src: "foot", v }))];
  if (!["tile", "foot"].includes(kind)) targets.push(...uniq(d.drain_tile).map((p, v) => ({ p, src: "tile", v })));
  let best = null;
  let bd = tol;
  for (const t of targets) {
    if (self && t.src === self.src && (t.v === self.v || (closed(d[self.src === "foot" ? "footprint" : "drain_tile"]) && self.v === d[self.src === "foot" ? "footprint" : "drain_tile"].length - 1 && t.v === 0))) continue;
    const dist = Math.hypot(t.p[0] - x, (t.p[1] - y) * aspect);
    if (dist < bd) { bd = dist; best = t.p; }
  }
  return best ? [best[0], best[1], best] : [x, y, null];
}

export const corners = (d) => uniq(d.footprint);

// Straight-line distance from each cleanout / sump to its nearest footing corner
export function stakeouts(d, k, aspect) {
  const cs = corners(d);
  if (!cs.length) return [];
  const items = [
    ...(d.cleanouts || []).map((c, i) => ({ kind: "cleanout", i, type: "Cleanout", label: c.label || `CO-${i + 1}`, x: c.x, y: c.y })),
    ...(d.sump?.x != null ? [{ kind: "sump", type: "Sump", label: d.sump.label || "SUMP", x: d.sump.x, y: d.sump.y }] : []),
    ...(d.sumps || []).map((s, i) => ({ kind: "xsump", i, type: "Sump", label: s.label || `SP-${i + 2}`, x: s.x, y: s.y })),
  ];
  return items.map((it) => {
    let best = 0;
    let bd = Infinity;
    cs.forEach((p, j) => { const dd = Math.hypot(p[0] - it.x, (p[1] - it.y) * aspect); if (dd < bd) { bd = dd; best = j; } });
    return { ...it, corner: best, cx: cs[best][0], cy: cs[best][1], ft: k ? bd * k : null, ...wallOffsets(it, cs, best, k, aspect) };
  });
}

// Offsets measured along the two walls meeting at corner j (a toward next corner, b square to it toward previous corner)
function wallOffsets(p, cs, j, k, aspect) {
  const n = cs.length;
  if (n < 3) return {};
  const c = [cs[j][0], cs[j][1] * aspect];
  const nx_ = (j + 1) % n, pv = (j - 1 + n) % n;
  let ux = cs[nx_][0] - c[0], uy = cs[nx_][1] * aspect - c[1];
  const L = Math.hypot(ux, uy);
  if (!L) return {};
  ux /= L; uy /= L;
  let nx = -uy, ny = ux;
  if (nx * (cs[pv][0] - c[0]) + ny * (cs[pv][1] * aspect - c[1]) < 0) { nx = -nx; ny = -ny; }
  const dx = p.x - c[0], dy = p.y * aspect - c[1];
  const a = dx * ux + dy * uy, b = dx * nx + dy * ny;
  return { aTo: nx_, bTo: pv, aFt: k ? a * k : null, bFt: k ? b * k : null, fx: c[0] + ux * a, fy: (c[1] + uy * a) / aspect };
}

export const sfmt = (f) => (f < 0 ? "-" : "") + fmtFt(Math.abs(f));

export const flagPos = (d, f) => {
  const pick = { cleanout: () => d.cleanouts?.[f.i], sump: () => d.sump, xsump: () => d.sumps?.[f.i] }[f.kind];
  if (pick) { const it = pick(); return it?.x != null ? [it.x, it.y] : null; }
  if (f.kind === "xoutlet") return d.sumps?.[f.i]?.outlet || null;
  if (f.kind === "dpt") return d.discharge?.points?.[f.i] || null;
  if (f.kind === "tile") return d.drain_tile?.[f.i] || null;
  return null;
};
export const flagSel = (f) => (["dpt", "tile"].includes(f.kind) ? { kind: f.kind, v: f.i } : f.kind ? { kind: f.kind, ...(f.i != null && { i: f.i }) } : null);
