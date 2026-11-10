import { useRef } from "react";
import { C, PUMPS, pts, clamp, insertVertex } from "@/components/drain/geometry";

const label = (x, y, color, text, dx = 14, dy = -8, size = 14) => (
  <text x={x + dx} y={y + dy} fill={color} fontSize={size} fontWeight="700" stroke="#fff" strokeWidth="3" paintOrder="stroke" style={{ pointerEvents: "none" }}>{text}</text>
);

export const LayoutCanvas = ({ d, aspect, on, tool, sel, setSel, onAdd, onMove, onBegin, setDraft, url }) => {
  const svgRef = useRef(null);
  const drag = useRef(null);
  const sy = (y) => y * aspect;
  const H = 1000 * aspect;
  const toPt = (e) => {
    const svg = svgRef.current;
    const p = svg.createSVGPoint();
    p.x = e.clientX; p.y = e.clientY;
    const r = p.matrixTransform(svg.getScreenCTM().inverse());
    return [clamp(r.x), clamp(r.y / aspect)];
  };
  const grab = (s) => (e) => {
    if (tool !== "select") return;
    e.stopPropagation(); e.preventDefault();
    const [x, y] = toPt(e);
    drag.current = { s, pushed: false, start: { x, y, orig: s.kind === "slope" ? { ...d.slope_arrows[s.i] } : null } };
    setSel(s);
    svgRef.current.setPointerCapture(e.pointerId);
  };
  const down = (e) => {
    if (tool === "select") { setSel(null); return; }
    const [x, y] = toPt(e);
    onAdd(tool, Math.round(x * 10) / 10, Math.round(y * 10) / 10);
  };
  const move = (e) => {
    if (!drag.current) return;
    if (!drag.current.pushed) { onBegin(); drag.current.pushed = true; }
    const [x, y] = toPt(e);
    onMove(drag.current.s, x, y, drag.current.start);
  };
  const end = () => { drag.current = null; };
  const is = (k, i, v) => sel?.kind === k && (i === undefined || sel.i === i) && (v === undefined || sel.v === v);
  const h = { style: { cursor: tool === "select" ? "grab" : "crosshair", touchAction: "none" } };
  const ring = (x, y, r, color, on_) => <circle cx={x} cy={sy(y)} r={r} fill={on_ ? `${color}40` : "transparent"} stroke={on_ ? color : "transparent"} strokeDasharray="4 3" strokeWidth="2" />;
  const vertexHandles = (key, kind, color) => (d[key] || []).map((p, v) => (
    <g key={`${kind}-${v}`} data-testid={`layout-${kind}-v-${v}`} onPointerDown={grab({ kind, v })} {...h}>
      {ring(p[0], p[1], 16, color, is(kind, undefined, v))}
      <circle cx={p[0]} cy={sy(p[1])} r="6" fill="#fff" stroke={color} strokeWidth="3" />
    </g>
  ));
  const midHandles = (key, color) => tool === "select" && (d[key] || []).slice(0, -1).map((p, v) => {
    const q = d[key][v + 1];
    const mx = (p[0] + q[0]) / 2, my = (p[1] + q[1]) / 2;
    return (
      <g key={`mid-${key}-${v}`} data-testid={`layout-${key}-mid-${v}`} {...h}
        onPointerDown={(e) => {
          e.stopPropagation(); e.preventDefault(); onBegin();
          const s = { kind: key === "drain_tile" ? "tile" : "foot", v: v + 1 };
          setDraft(insertVertex(d, key, v, mx, my)); setSel(s);
          drag.current = { s, pushed: true, start: null };
          svgRef.current.setPointerCapture(e.pointerId);
        }}>
        <circle cx={mx} cy={sy(my)} r="7" fill={`${color}55`} stroke="#fff" strokeWidth="1.5" />
        <text x={mx} y={sy(my) + 4} textAnchor="middle" fontSize="11" fill="#fff" fontWeight="700" style={{ pointerEvents: "none" }}>+</text>
      </g>
    );
  });
  const dis = d.discharge?.points || [];

  return (
    <div className="relative bg-white min-w-[860px] select-none" data-testid="layout-stage">
      <img src={url} alt="sheet" className="w-full h-auto block" draggable={false} data-testid="layout-sheet-image" />
      <svg ref={svgRef} viewBox={`0 0 1000 ${H}`} className="absolute inset-0 w-full h-full" data-testid="layout-svg"
        onPointerDown={down} onPointerMove={move} onPointerUp={end} onPointerCancel={end}
        style={{ cursor: tool === "select" ? "default" : "crosshair", touchAction: tool === "select" ? "auto" : "none" }}>
        <defs>
          {[["slope", C.slope], ["discharge", C.discharge]].map(([k, c]) => (
            <marker key={k} id={`lay-arrow-${k}`} viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill={c} /></marker>
          ))}
        </defs>
        {on.foot && d.footprint?.length > 1 && (
          <polygon points={pts(d.footprint, sy)} fill={`${C.foot}1f`} stroke={C.foot} strokeWidth="2" strokeDasharray="6 4" data-testid="layout-footprint" style={{ pointerEvents: "none" }} />
        )}
        {on.tile && d.drain_tile?.length > 1 && (
          <polyline points={pts(d.drain_tile, sy)} fill="none" stroke={C.tile} strokeWidth="6" strokeLinejoin="round" className="drain-flow" data-testid="layout-tile-line" style={{ pointerEvents: "none" }} />
        )}
        {on.sump && dis.length > 1 && (
          <polyline points={pts(dis, sy)} fill="none" stroke={C.discharge} strokeWidth="5" strokeDasharray="12 8" markerEnd="url(#lay-arrow-discharge)" data-testid="layout-discharge" style={{ pointerEvents: "none" }} />
        )}
        {on.sump && dis.length > 1 && label(dis.at(-1)[0], sy(dis.at(-1)[1]), C.discharge, d.discharge.label || "DISCHARGE", 10, 4, 15)}
        {on.slope && (d.slope_arrows || []).map((s, i) => (
          <g key={`sl-${i}`} data-testid={`layout-slope-${i}`}>
            <line x1={s.x1} y1={sy(s.y1)} x2={s.x2} y2={sy(s.y2)} stroke={is("slope", i) ? "#7e22ce" : C.slope} strokeWidth="4" markerEnd="url(#lay-arrow-slope)" />
            <line x1={s.x1} y1={sy(s.y1)} x2={s.x2} y2={sy(s.y2)} stroke="transparent" strokeWidth="18" onPointerDown={grab({ kind: "slope", i, end: "body" })} {...h} />
            {label((s.x1 + s.x2) / 2, sy((s.y1 + s.y2) / 2), C.slope, s.label, 6, -8)}
            {tool === "select" && is("slope", i) && ["a", "b"].map((e) => (
              <circle key={e} cx={e === "a" ? s.x1 : s.x2} cy={sy(e === "a" ? s.y1 : s.y2)} r="7" fill="#fff" stroke={C.slope} strokeWidth="3"
                data-testid={`layout-slope-${i}-${e}`} onPointerDown={grab({ kind: "slope", i, end: e })} {...h} />
            ))}
          </g>
        ))}
        {on.tile && midHandles("drain_tile", C.tile)}
        {on.tile && vertexHandles("drain_tile", "tile", C.tile)}
        {on.foot && tool === "select" && midHandles("footprint", C.foot)}
        {on.foot && vertexHandles("footprint", "foot", C.foot)}
        {on.sump && dis.slice(1).map((p, j) => (
          <g key={`dp-${j}`} data-testid={`layout-dpt-${j + 1}`} onPointerDown={grab({ kind: "dpt", v: j + 1 })} {...h}>
            {ring(p[0], p[1], 16, C.discharge, is("dpt", undefined, j + 1))}
            <circle cx={p[0]} cy={sy(p[1])} r="7" fill={C.discharge} stroke="#fff" strokeWidth="2.5" />
          </g>
        ))}
        {on.cleanouts && (d.cleanouts || []).map((c, i) => (
          <g key={`co-${i}`} data-testid={`layout-cleanout-${i}`} onPointerDown={grab({ kind: "cleanout", i })} {...h}>
            {ring(c.x, c.y, 20, C.cleanout, is("cleanout", i))}
            <circle cx={c.x} cy={sy(c.y)} r="10" fill={C.cleanout} stroke="#fff" strokeWidth="2.5" />
            {label(c.x, sy(c.y), C.cleanout, c.label || "CO")}
          </g>
        ))}
        {on.sump && d.sump?.x != null && (
          <g data-testid="layout-sump-main" onPointerDown={grab({ kind: "sump" })} {...h}>
            {ring(d.sump.x, d.sump.y, 24, C.sump, is("sump"))}
            <rect x={d.sump.x - 13} y={sy(d.sump.y) - 13} width="26" height="26" fill={C.sump} stroke="#fff" strokeWidth="2.5" />
            {PUMPS.includes(d.sump.type) && <circle cx={d.sump.x} cy={sy(d.sump.y)} r="6" fill="#fff" />}
            {label(d.sump.x, sy(d.sump.y), C.sump, `${d.sump.label || "SUMP"}${d.sump.pump_hp ? ` · ${d.sump.pump_hp} HP` : ""}`, 18, 26, 15)}
          </g>
        )}
        {on.sump && (d.sumps || []).map((s, i) => (
          <g key={`xs-${i}`}>
            {s.outlet && <line x1={s.x} y1={sy(s.y)} x2={s.outlet[0]} y2={sy(s.outlet[1])} stroke={C.discharge} strokeWidth="5" strokeDasharray="12 8" markerEnd="url(#lay-arrow-discharge)" style={{ pointerEvents: "none" }} />}
            <g data-testid={`layout-sump-${i}`} onPointerDown={grab({ kind: "xsump", i })} {...h}>
              {ring(s.x, s.y, 24, C.sump, is("xsump", i))}
              <rect x={s.x - 13} y={sy(s.y) - 13} width="26" height="26" fill={C.sump} stroke="#fff" strokeWidth="2.5" />
              {PUMPS.includes(s.type) && <circle cx={s.x} cy={sy(s.y)} r="6" fill="#fff" />}
              {label(s.x, sy(s.y), C.sump, `${s.label || "SUMP"}${s.pump_hp ? ` · ${s.pump_hp} HP` : ""}`, 18, 26, 15)}
            </g>
            {s.outlet && (
              <g data-testid={`layout-sump-${i}-outlet`} onPointerDown={grab({ kind: "xoutlet", i })} {...h}>
                {ring(s.outlet[0], s.outlet[1], 16, C.discharge, is("xoutlet", i))}
                <circle cx={s.outlet[0]} cy={sy(s.outlet[1])} r="7" fill={C.discharge} stroke="#fff" strokeWidth="2.5" />
              </g>
            )}
          </g>
        ))}
      </svg>
    </div>
  );
};
