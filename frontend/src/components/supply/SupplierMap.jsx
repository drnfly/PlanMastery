import { MapContainer, TileLayer, CircleMarker, Circle, Popup, useMap } from "react-leaflet";
import { useEffect } from "react";
import "leaflet/dist/leaflet.css";
import { CATS, money, supplierTotal, directions } from "@/components/supply/calc";

const Fit = ({ doc }) => {
  const map = useMap();
  useEffect(() => {
    map.setView([doc.lat, doc.lon], doc.radius_mi > 40 ? 8 : doc.radius_mi > 15 ? 9 : 11);
  }, [map, doc.lat, doc.lon, doc.radius_mi]);
  return null;
};

const Focus = ({ s }) => {
  const map = useMap();
  useEffect(() => { if (s) map.flyTo([s.lat, s.lon], Math.max(map.getZoom(), 12), { duration: 0.6 }); }, [map, s]);
  return null;
};

export const SupplierMap = ({ doc, shown, selected, onSelect }) => (
  <div className="relative h-[460px] lg:h-[560px] rounded-xl overflow-hidden border border-slate-800" data-testid="supplier-map">
    <MapContainer center={[doc.lat, doc.lon]} zoom={10} scrollWheelZoom className="h-full w-full" style={{ background: "#0B0F17" }}>
      <TileLayer attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
      <Fit doc={doc} />
      <Focus s={selected} />
      <Circle center={[doc.lat, doc.lon]} radius={doc.radius_mi * 1609.34} pathOptions={{ color: "#06B6D4", weight: 1, fillOpacity: 0.04, dashArray: "6 6" }} />
      <CircleMarker center={[doc.lat, doc.lon]} radius={9} pathOptions={{ color: "#fff", weight: 3, fillColor: "#0B0F17", fillOpacity: 1 }}>
        <Popup><b>Job site</b><br />{doc.address}</Popup>
      </CircleMarker>
      {shown.map((s) => {
        const t = supplierTotal(doc, s.id);
        const hot = selected?.id === s.id;
        return (
          <CircleMarker key={s.id} center={[s.lat, s.lon]} radius={hot ? 11 : 7}
            pathOptions={{ color: hot ? "#fff" : "#0B0F17", weight: 2, fillColor: CATS[s.category]?.color, fillOpacity: 0.95 }}
            eventHandlers={{ click: () => onSelect(s) }}>
            <Popup>
              <div className="text-xs space-y-0.5" data-testid={`supplier-popup-${s.id}`}>
                <p className="font-semibold text-sm">{s.name}</p>
                <p>{CATS[s.category]?.label} · {s.distance_mi} mi</p>
                {s.address && <p>{s.address}</p>}
                {s.phone && <p><a href={`tel:${s.phone}`}>{s.phone}</a></p>}
                {t.n > 0 && <p><b>{money(t.total)}</b> for {t.n} item{t.n > 1 ? "s" : ""}{t.quoted ? ` (${t.quoted} quoted)` : " (estimate)"}</p>}
                <p><a href={directions(s)} target="_blank" rel="noreferrer">Directions</a>{s.website && <> · <a href={s.website} target="_blank" rel="noreferrer">Website</a></>}</p>
              </div>
            </Popup>
          </CircleMarker>
        );
      })}
    </MapContainer>
    <div className="absolute bottom-3 left-3 z-[400] bg-[#0B0F17]/90 backdrop-blur border border-slate-700 rounded-lg px-3 py-2 text-[11px] text-slate-300 space-y-1" data-testid="supplier-map-legend">
      {Object.entries(CATS).map(([k, c]) => (
        <p key={k} className="flex items-center gap-2"><span className="h-2.5 w-2.5 rounded-full" style={{ background: c.color }} />{c.label}</p>
      ))}
    </div>
  </div>
);
