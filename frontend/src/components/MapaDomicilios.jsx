import { useEffect, useRef, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import api from "../api.js";
import { formatMoney } from "../components/ui.jsx";

const CENTRO = [4.6762, -74.0487];

const iconRep = (color = "#4f46e5") =>
  L.divIcon({
    className: "",
    html: `<div style="display:grid;place-items:center;width:34px;height:34px;border-radius:50%;background:${color};color:#fff;font-size:17px;box-shadow:0 6px 16px -4px rgba(0,0,0,.55);border:2px solid #fff">🛵</div>`,
    iconSize: [34, 34],
    iconAnchor: [17, 17],
  });

const iconDest = L.divIcon({
  className: "",
  html: `<div style="display:grid;place-items:center;width:24px;height:24px;border-radius:50%;background:#4338ca;color:#fff;font-size:13px;box-shadow:0 4px 10px -2px rgba(0,0,0,.5)">🏠</div>`,
  iconSize: [24, 24],
  iconAnchor: [12, 12],
});

export default function MapaDomicilios({ refresh = 0, onPick }) {
  const divRef = useRef(null);
  const mapRef = useRef(null);
  const markersRef = useRef(new Map());
  const repMarkersRef = useRef(new Map());
  const polylinesRef = useRef([]);
  const [items, setItems] = useState([]);
  const [reps, setReps] = useState([]);
  const [sel, setSel] = useState(null);
  const [selRep, setSelRep] = useState(null);
  const [paused, setPaused] = useState(false);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  useEffect(() => {
    if (!divRef.current || mapRef.current) return;
    const map = L.map(divRef.current, { zoomControl: true, attributionControl: true }).setView(CENTRO, 14);
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    }).addTo(map);
    mapRef.current = map;
    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  function pintarRepartidores(data) {
    if (!mapRef.current) return;
    const ids = new Set(data.filter((r) => r.disponible === "disponible" && r.activo).map((r) => r.id));
    for (const [rid, mk] of repMarkersRef.current) {
      if (!ids.has(rid) && mk.layer && mk.layer.remove) {
        mapRef.current.removeLayer(mk.layer);
        repMarkersRef.current.delete(rid);
      }
    }
    for (const r of data) {
      if (r.disponible !== "disponible" || !r.activo) continue;
      let mk = repMarkersRef.current.get(r.id);
      if (!mk) {
        const layer = L.marker([r.lat, r.lng], { icon: iconRep("#10b981") }).addTo(mapRef.current);
        layer.on("click", () => setSelRep(r));
        mk = { layer };
        repMarkersRef.current.set(r.id, mk);
      } else {
        mk.layer.setLatLng([r.lat, r.lng]);
        if (selRep && selRep.id === r.id) setSelRep(r);
      }
    }
  }

  useEffect(() => {
    let alive = true;
    async function load() {
      try {
        const [data, repsData] = await Promise.all([api("/domicilios/mapa"), api("/domicilios/repartidores")]);
        if (!alive) return;
        setItems(data);
        setReps(repsData);
        if (mapRef.current) pintarRepartidores(repsData);
        // Marker cleanup (los que ya no aplican)
        const ids = new Set(data.map((d) => d.pedido_id));
        for (const [pid, mk] of markersRef.current) {
          if (!ids.has(pid) && mk.layer && mk.layer.remove) {
            mapRef.current?.removeLayer(mk.layer);
            markersRef.current.delete(pid);
          }
        }
        // Trazas de líneas
        polylinesRef.current.forEach((l) => mapRef.current?.removeLayer(l));
        polylinesRef.current = [];

        for (const d of data) {
          let mk = markersRef.current.get(d.pedido_id);
          const latlng = [d.lat, d.lng];
          if (!mk) {
            const layer = L.marker(latlng, { icon: iconRep() }).addTo(mapRef.current);
            layer.on("click", () => setSel(d));
            mk = { layer };
            markersRef.current.set(d.pedido_id, mk);
          } else {
            mk.layer.setLatLng(latlng);
            if (sel && sel.pedido_id === d.pedido_id) setSel(d);
          }
          if (d.dest_lat != null) {
            const line = L.polyline([[d.lat, d.lng], [d.dest_lat, d.dest_lng]], {
              color: "#4f46e5", weight: 3, dashArray: "6 8", opacity: 0.9,
            }).addTo(mapRef.current);
            polylinesRef.current.push(line);
            L.marker([d.dest_lat, d.dest_lng], { icon: iconDest }).addTo(mapRef.current);
          }
        }
        if (data.length && !sel) setSel(data[0]);
      } catch (e) {
        if (alive) setErr(e.message);
      }
    }
    load();
    return () => {
      alive = false;
    };
  }, [refresh, paused]);

  useEffect(() => {
    if (paused) return;
    const t = setInterval(async () => {
      try {
        const [data, repsData] = await Promise.all([api("/domicilios/mapa"), api("/domicilios/repartidores")]);
        setItems(data);
        setReps(repsData);
        if (mapRef.current) pintarRepartidores(repsData);
      } catch {}
    }, 6000);
    return () => clearInterval(t);
  }, [paused]);

  async function simular(pid) {
    setMsg("");
    setErr("");
    try {
      const j = await api(`/domicilios/pedidos/${pid}/simular`, { method: "POST" });
      setMsg(`${j.estado_domicilio === "entregado" ? "Entrega completada" : "Repartidor avanzó en ruta"} · ${j.lat.toFixed(4)}, ${j.lng.toFixed(4)}`);
      const [data, repsData] = await Promise.all([api("/domicilios/mapa"), api("/domicilios/repartidores")]);
      setItems(data);
      setReps(repsData);
      if (mapRef.current) pintarRepartidores(repsData);
    } catch (e) {
      setErr(e.message);
    }
  }

  async function terminar(pid) {
    setErr("");
    try {
      const data = await api(`/pedidos/${pid}/entregar`, { method: "POST" });
      setMsg("Domicilio marcado como entregado");
      setSel(null);
      const [mapa, repsData] = await Promise.all([api("/domicilios/mapa"), api("/domicilios/repartidores")]);
      setItems(mapa);
      setReps(repsData);
      if (mapRef.current) pintarRepartidores(repsData);
      onPick && onPick(1);
    } catch (e) {
      setErr(e.message);
    }
  }

  const disponibles = reps.filter((r) => r.disponible === "disponible" && r.activo).length;

  return (
    <div className="card" style={{ padding: 0, overflow: "hidden" }}>
      <div className="map-shell">
        <div ref={divRef} className="map-canvas" />
        <div className="map-legend">
          <span><i style={{ background: "#4f46e5" }} /> Repartidor en ruta</span>
          <span><i style={{ background: "#10b981" }} /> Repartidor disponible</span>
          <span><i style={{ background: "#4338ca" }} /> Destino</span>
        </div>
      </div>

      <div style={{ padding: 14, display: "grid", gap: 12 }}>
        <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
          <span className="chip">🛰️ {items.length} pedidos en ruta</span>
          <span className="chip">🟢 {disponibles} repartidores disponibles</span>
          <button className="btn btn-sm" onClick={() => setPaused(!paused)}>
            {paused ? "▶ Reanudar auto-refresh" : "⏸ Pausar"}
          </button>
          {msg && <span className="badge-success" style={{ padding: "4px 8px", borderRadius: 6 }}>{msg}</span>}
          {err && <span className="error" style={{ margin: 0 }}>{err}</span>}
        </div>

        {selRep && (
          <div className="map-item" style={{ border: "1px solid #10b981", borderRadius: 14, padding: 12, background: "var(--card)" }}>
            <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
              <b>🟢 {selRep.nombre}</b>
              <button className="btn btn-ghost" style={{ padding: 0 }} onClick={() => setSelRep(null)} title="Cerrar">✕</button>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(180px,1fr))", gap: 6, fontSize: 13, marginTop: 6 }}>
              <span>📞 {selRep.telefono || "—"}</span>
              <span>{selRep.vehiculo ? `🛵 ${selRep.vehiculo}` : "🛵 moto"}{selRep.placa ? ` · ${selRep.placa}` : ""}</span>
              <span>📍 {selRep.lat?.toFixed(4)}, {selRep.lng?.toFixed(4)}</span>
              <span><span className="badge badge-success">Disponible</span></span>
            </div>
          </div>
        )}

        {items.length === 0 ? (
          <div style={{ padding: 18, textAlign: "center", color: "var(--muted)" }}>
            No hay domicilios en ruta. Despacha un pedido pendiente desde la tabla para verlo en el mapa.
            {disponibles > 0 && " Los puntos verdes son repartidores listos para asignar."}
          </div>
        ) : (
          <div style={{ display: "grid", gap: 10, gridTemplateColumns: "repeat(auto-fit,minmax(260px,1fr))" }}>
            {items.map((d) => (
              <div
                key={d.pedido_id}
                className="map-item"
                style={{
                  border: sel?.pedido_id === d.pedido_id ? "1px solid var(--brand1)" : "1px solid var(--line)",
                  borderRadius: 14,
                  padding: 12,
                  background: "var(--card)",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
                  <b>{d.numero}</b>
                  <span className="badge">{d.estado_domicilio}</span>
                </div>
                <div style={{ fontSize: 13, color: "var(--muted)", marginTop: 6 }}>
                  {d.repartidor ? `🛵 ${d.repartidor}${d.vehiculo ? ` · ${d.vehiculo}` : ""}` : "🛵 Sin repartidor"}
                </div>
                <div style={{ fontSize: 13, marginTop: 4 }}>📍 {d.direccion || "Sin dirección"}</div>
                <div style={{ fontSize: 13, fontWeight: 700, color: "var(--brand1)", marginTop: 4 }}>{formatMoney(d.total)}</div>
                <div style={{ display: "flex", gap: 6, marginTop: 10 }}>
                  <button className="btn btn-sm btn-primary" onClick={() => select_and_sim(d)}>▶ Simular avance</button>
                  <button className="btn btn-sm" onClick={() => terminar(d.pedido_id)}>Entregado</button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );

  function select_and_sim(d) {
    selectOnMap(d);
    simular(d.pedido_id);
  }

  function selectOnMap(d) {
    setSel(d);
    const mk = markersRef.current.get(d.pedido_id);
    if (mk) mapRef.current?.panTo(mk.layer.getLatLng());
  }
}