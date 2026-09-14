import { useEffect, useState } from "react";
import api from "../api.js";
import { KpiCard, ChartCard, Donut, formatMoney } from "../components/ui.jsx";
import MapaDomicilios from "../components/MapaDomicilios.jsx";

export default function Pedidos() {
  const [lista, setLista] = useState([]);
  const [domicilios, setDomicilios] = useState(null);
  const [productos, setProductos] = useState([]);
  const [clientes, setClientes] = useState([]);
  const [usuarios, setUsuarios] = useState([]);
  const [filtro, setFiltro] = useState("");
  const [vista, setVista] = useState("lista");
  const [repartidores, setRepartidores] = useState([]);
  const [refreshMapa, setRefreshMapa] = useState(0);
  const [error, setError] = useState("");
  const [msg, setMsg] = useState("");
  const [form, setForm] = useState({ cliente_id: "", tipo: "mostrador", direccion_entrega: "", costo_domicilio: 0, repartidor_id: "", nota: "" });
  const [lineas, setLineas] = useState([{ producto_id: "", cantidad: 1 }]);
  const [verPedido, setVerPedido] = useState(null);
  const [tracking, setTracking] = useState(null);
  const [rutas, setRutas] = useState([]);
  const [rutForm, setRutForm] = useState({ nombre: "", tarifa: 0, repartidor_id: "", detalle: "" });
  const [repForm, setRepForm] = useState({ nombre: "", telefono: "", placa: "", vehiculo: "moto" });

  async function load() {
    api("/pedidos").then(setLista).catch((e) => setError(e.message));
    api("/pedidos/domicilios/resumen").then(setDomicilios).catch(() => {});
  }

  useEffect(() => {
    load();
    api("/productos").then(setProductos).catch(() => {});
    api("/clientes").then(setClientes).catch(() => {});
    api("/usuarios").then(setUsuarios).catch(() => {});
    api("/domicilios/repartidores").then(setRepartidores).catch(() => {});
    loadRutas();
  }, []);

  useEffect(() => {
    api(`/pedidos${filtro ? `?estado=${filtro}` : ""}`).then(setLista).catch(() => {});
  }, [filtro]);

  async function submit(fn, okMsg) {
    setError("");
    setMsg("");
    try {
      await fn();
      setMsg(okMsg);
      load();
    } catch (e) {
      setError(e.message);
    }
  }

  function setLinea(idx, campo, valor) {
    const next = [...lineas];
    next[idx][campo] = campo === "cantidad" ? Number(valor) : valor;
    setLineas(next);
  }

  async function crear(e) {
    e.preventDefault();
    const detalle = lineas
      .filter((l) => l.producto_id)
      .map((l) => ({
        producto_id: Number(l.producto_id),
        cantidad: Number(l.cantidad),
        precio: productos.find((p) => p.id === Number(l.producto_id))?.precio_venta || 0,
      }));
    await submit(
      () =>
        api("/pedidos", {
          method: "POST",
          body: JSON.stringify({
            ...form,
            cliente_id: form.cliente_id ? Number(form.cliente_id) : null,
            costo_domicilio: Number(form.costo_domicilio || 0),
            repartidor_id: form.repartidor_id ? Number(form.repartidor_id) : null,
            detalle,
          }),
        }),
      "Pedido creado"
    );
    setLineas([{ producto_id: "", cantidad: 1 }]);
  }

  async function estado(id, est) {
    await submit(() => api(`/pedidos/${id}/estado?estado=${est}`, { method: "POST" }), `Pedido ${est}`);
  }

  async function entregar(id) {
    if (!window.confirm("Entregar pedido (descarga stock)?")) return;
    await submit(() => api(`/pedidos/${id}/entregar`, { method: "POST" }), "Pedido entregado");
  }

  async function despachar(id) {
    const repartidorId = window.prompt("Repartidor ID:", 1);
    if (!repartidorId) return;
    await submit(() => api(`/pedidos/${id}/despachar?repartidor_id=${repartidorId}`, { method: "POST" }), "Despachado a reparto");
  }

  function despacharGps(id) {
    const rep = repartidores.find((r) => r.disponible === "disponible") || repartidores[0];
    if (!rep) {
      setError("No hay repartidores disponibles");
      return;
    }
    const dlat = ((id * 37) % 100) / 10000 - 0.003;
    const dlng = ((id * 53) % 100) / 10000 - 0.003;
    submit(
      () =>
        api("/domicilios/seguimiento", {
          method: "POST",
          body: JSON.stringify({
            pedido_id: id,
            repartidor_id: rep.id,
            lat: rep.lat,
            lng: rep.lng,
            dest_lat: Number((4.6601 + dlat).toFixed(6)),
            dest_lng: Number((-74.061 + dlng).toFixed(6)),
          }),
        }),
      `Despachado a ${rep.nombre}`
    ).then(() => setVista("mapa"));
  }

  async function despEstado(id, est) {
    await submit(() => api(`/pedidos/${id}/estado-domicilio?estado=${est}`, { method: "POST" }), `Domicilio ${est}`);
  }

  async function loadRutas() {
    api("/domicilios/rutas").then(setRutas).catch(() => {});
  }

  async function verDetallePedido(id) {
    setError("");
    setMsg("");
    try {
      setVerPedido(await api(`/pedidos/${id}`));
    } catch (e) {
      setError(e.message);
    }
  }

  async function verTracking(id) {
    setError("");
    setMsg("");
    try {
      setTracking(await api(`/domicilios/pedidos/${id}/tracking`));
    } catch (e) {
      setError(e.message);
    }
  }

  async function crearRepartidor(e) {
    e.preventDefault();
    await submit(() =>
      api("/domicilios/repartidores", { method: "POST", body: JSON.stringify({ ...repForm }) }),
      "Repartidor creado"
    );
    setRepForm({ nombre: "", telefono: "", placa: "", vehiculo: "moto" });
    api("/domicilios/repartidores").then(setRepartidores).catch(() => {});
    loadRutas();
  }

  async function estadoRepartidor(r, disponible) {
    await submit(() => api(`/domicilios/repartidores/${r.id}/estado?disponible=${disponible}`, { method: "POST" }), `${r.nombre} → ${disponible}`);
    api("/domicilios/repartidores").then(setRepartidores).catch(() => {});
  }

  async function verGps(r) {
    setError("");
    setMsg("");
    try {
      const g = await api(`/domicilios/repartidores/${r.id}/gps`);
      setMsg(`📍 ${r.nombre}: ${g.lat.toFixed(5)}, ${g.lng.toFixed(5)} · ${g.disponible}`);
    } catch (e) {
      setError(e.message);
    }
  }

  async function crearRuta(e) {
    e.preventDefault();
    await submit(() =>
      api("/domicilios/rutas", {
        method: "POST",
        body: JSON.stringify({ ...rutForm, tarifa: Number(rutForm.tarifa || 0), repartidor_id: rutForm.repartidor_id ? Number(rutForm.repartidor_id) : null }),
      }),
      "Ruta creada"
    );
    setRutForm({ nombre: "", tarifa: 0, repartidor_id: "", detalle: "" });
    loadRutas();
  }

  async function updateGps(id) {
    const lat = window.prompt("Latitud:", "4.6762");
    const lng = window.prompt("Longitud:", "-74.0487");
    if (lat === null || lng === null) return;
    await submit(() => api(`/domicilios/pedidos/${id}/gps`, { method: "POST", body: JSON.stringify({ lat: Number(lat), lng: Number(lng) }) }), `GPS actualizado pedido #${id}`);
  }

  const badge = (e) => <span className={`badge ${e === "entregado" || e === "listo" ? "badge-success" : ""}`}>{e || "-"}</span>;
  const ESTADOS = ["", "pendiente", "en_preparacion", "listo", "entregado", "cancelado"];

  return (
    <div className="page">
      <div className="hero" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 16, flexWrap: "wrap" }}>
        <div>
          <h1>Pedidos y domicilios</h1>
          <p>Gestión del ciclo completo: preparación, entrega en mostrador y reparto a domicilio.</p>
        </div>
        <div className="page-header" style={{ marginBottom: 0, display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
          <div className="tabs">
            <button className={`tab ${vista === "lista" ? "tab-active" : ""}`} onClick={() => setVista("lista")}>📋 Lista</button>
            <button className={`tab ${vista === "mapa" ? "tab-active" : ""}`} onClick={() => setVista("mapa")}>🗺️ Mapa GPS</button>
          </div>
          {vista === "lista" && (
            <select value={filtro} onChange={(e) => setFiltro(e.target.value)} style={{ width: "auto", background: "rgba(255,255,255,.95)" }}>
              {ESTADOS.map((e) => (
                <option key={e || "todos"} value={e}>{e === "" ? "Todos los estados" : e}</option>
              ))}
            </select>
          )}
        </div>
      </div>

      {vista === "mapa" && (
        <MapaDomicilios refresh={refreshMapa} onPick={() => setRefreshMapa((n) => n + 1)} />
      )}

      {vista === "lista" && (
        <>
      {domicilios && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(190px,1fr))", gap: 16, marginBottom: 18 }}>
          <KpiCard label="Domicilios pendientes" value={domicilios.pendientes ?? 0} icon="📦" accent="#f59e0b" />
          <KpiCard label="En ruta" value={domicilios.en_ruta ?? 0} icon="🛵" accent="#ef4444" />
          <KpiCard label="Entregados" value={domicilios.entregados ?? 0} icon="✅" accent="#10b981" />
        </div>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px,1fr))", gap: 18, marginBottom: 18 }}>
        <ChartCard title="Domicilios por estado" subtitle="Ruta de los repartos" height={230} accent="#f59e0b">
          <Donut
            data={[
              { name: "Pendientes", value: domicilios?.pendientes ?? 0 },
              { name: "En ruta", value: domicilios?.en_ruta ?? 0 },
              { name: "Entregados", value: domicilios?.entregados ?? 0 },
            ]}
            centerLabel="Domicilios"
            centerValue={(domicilios?.pendientes ?? 0) + (domicilios?.en_ruta ?? 0) + (domicilios?.entregados ?? 0)}
          />
        </ChartCard>
        <ChartCard title="Estado de pedidos" subtitle="Todos los pedidos (mostrador + domicilio)" height={230}>
          <Donut
            data={Object.entries(
              (lista || []).reduce((acc, p) => ({ ...acc, [p.estado]: (acc[p.estado] || 0) + 1 }), {})
            ).map(([name, value]) => ({ name, value }))}
            centerLabel="Pedidos"
            centerValue={lista.length}
          />
        </ChartCard>
      </div>

      {msg && <div className="badge-success" style={{ display: "inline-block", marginBottom: 8, padding: "6px 10px", borderRadius: 6 }}>{msg}</div>}
      {error && <div className="error">{error}</div>}

      <form onSubmit={crear} className="card" style={{ padding: 14, marginBottom: 16, display: "grid", gap: 10 }}>
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
          <select value={form.tipo} onChange={(e) => setForm({ ...form, tipo: e.target.value })}>
            <option value="mostrador">Mostrador</option>
            <option value="domicilio">Domicilio</option>
          </select>
          <select value={form.cliente_id} onChange={(e) => setForm({ ...form, cliente_id: e.target.value })}>
            <option value="">Cliente (opcional)</option>
            {clientes.map((c) => (
              <option key={c.id} value={c.id}>{c.nombre}</option>
            ))}
          </select>
          {form.tipo === "domicilio" && (
            <>
              <input required placeholder="Dirección de entrega" value={form.direccion_entrega} onChange={(e) => setForm({ ...form, direccion_entrega: e.target.value })} />
              <input type="number" min={0} placeholder="Costo domicilio" value={form.costo_domicilio} onChange={(e) => setForm({ ...form, costo_domicilio: e.target.value })} />
              <select value={form.repartidor_id} onChange={(e) => setForm({ ...form, repartidor_id: e.target.value })}>
                <option value="">Repartidor…</option>
                {usuarios.map((u) => (
                  <option key={u.id} value={u.id}>{u.nombre}</option>
                ))}
              </select>
            </>
          )}
          <input placeholder="Nota" value={form.nota} onChange={(e) => setForm({ ...form, nota: e.target.value })} />
        </div>
        {lineas.map((l, i) => (
          <div key={i} style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
            <select required value={l.producto_id} onChange={(e) => setLinea(i, "producto_id", e.target.value)}>
              <option value="">Producto…</option>
              {productos.map((p) => (
                <option key={p.id} value={p.id}>{p.nombre}</option>
              ))}
            </select>
            <input type="number" min={1} style={{ width: 90 }} value={l.cantidad} onChange={(e) => setLinea(i, "cantidad", e.target.value)} />
            <button type="button" className="btn btn-sm" onClick={() => setLineas(lineas.filter((_, x) => x !== i))}>Quitar</button>
          </div>
        ))}
        <div style={{ display: "flex", gap: 10 }}>
          <button type="button" className="btn" onClick={() => setLineas([...lineas, { producto_id: "", cantidad: 1 }])}>+ Producto</button>
          <button className="btn btn-primary">Crear pedido</button>
        </div>
      </form>

      <table className="table">
        <thead>
          <tr><th>Nº</th><th>Tipo</th><th>Estado</th><th>Domicilio</th><th>Repartidor</th><th>Total</th><th>Acciones</th></tr>
        </thead>
        <tbody>
          {lista.length === 0 && (
            <tr><td colSpan={7}>Sin pedidos.</td></tr>
          )}
          {lista.map((p) => (
            <tr key={p.id}>
              <td><b>{p.numero}</b></td>
              <td>{p.tipo}</td>
              <td>{badge(p.estado)}</td>
              <td>{badge(p.estado_domicilio)}</td>
              <td>{p.repartidor || "-"}</td>
              <td>${p.total.toLocaleString("es-CO")}</td>
              <td>
                <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                  <button className="btn btn-sm btn-ghost" onClick={() => verDetallePedido(p.id)}>Detalle</button>
                  {p.estado === "pendiente" && (
                    <button className="btn btn-sm" onClick={() => estado(p.id, "en_preparacion")}>Preparar</button>
                  )}
                  {p.estado === "en_preparacion" && (
                    <button className="btn btn-sm" onClick={() => estado(p.id, "listo")}>Listo</button>
                  )}
                  {p.estado === "listo" && (
                    <button className="btn btn-sm btn-primary" onClick={() => entregar(p.id)}>Entregar</button>
                  )}
                  {p.tipo === "domicilio" && p.estado_domicilio === "pendiente" && (
                    <button className="btn btn-sm" onClick={() => despachar(p.id)}>Despachar</button>
                  )}
                  {p.tipo === "domicilio" && p.estado_domicilio === "pendiente" && repartidores.length > 0 && (
                    <button className="btn btn-sm btn-primary" onClick={() => despacharGps(p.id)}>🛰️ GPS</button>
                  )}
                  {p.tipo === "domicilio" && p.estado_domicilio === "en_ruta" && (
                    <>
                      <button className="btn btn-sm" onClick={() => setVista("mapa")}>🗺️ Ver en mapa</button>
                      <button className="btn btn-sm" onClick={() => verTracking(p.id)}>🛰️ Tracking</button>
                      <button className="btn btn-sm" onClick={() => updateGps(p.id)}>GPS</button>
                      <button className="btn btn-sm" onClick={() => despEstado(p.id, "entregado")}>Entregado</button>
                    </>
                  )}
                  {p.estado !== "cancelado" && p.estado !== "entregado" && (
                    <button className="btn btn-sm" onClick={() => estado(p.id, "cancelado")}>Cancelar</button>
                  )}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(340px,1fr))", gap: 16, marginTop: 18 }}>
        <form onSubmit={crearRepartidor} className="card" style={{ padding: 14, display: "grid", gap: 10 }}>
          <h3 style={{ fontSize: 15 }}>🛵 Repartidores</h3>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <input required placeholder="Nombre" value={repForm.nombre} onChange={(e) => setRepForm({ ...repForm, nombre: e.target.value })} />
            <input placeholder="Teléfono" value={repForm.telefono} onChange={(e) => setRepForm({ ...repForm, telefono: e.target.value })} />
            <input placeholder="Placa" value={repForm.placa} onChange={(e) => setRepForm({ ...repForm, placa: e.target.value })} />
            <select value={repForm.vehiculo} onChange={(e) => setRepForm({ ...repForm, vehiculo: e.target.value })}>
              {["moto", "bicicleta", "carro"].map((v) => <option key={v} value={v}>{v}</option>)}
            </select>
            <button className="btn btn-primary">+ Repartidor</button>
          </div>
          <div style={{ display: "grid", gap: 8, marginTop: 6 }}>
            {repartidores.length === 0 && <p className="muted">Sin repartidores registrados.</p>}
            {repartidores.map((r) => (
              <div key={r.id} style={{ border: "1px solid var(--line)", borderRadius: 10, padding: 10 }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 6 }}>
                  <b>{r.nombre}</b>
                  <span className={`badge ${r.disponible === "disponible" ? "badge-success" : r.disponible === "en_ruta" ? "badge-warning" : "badge-danger"}`}>{r.disponible}</span>
                </div>
                <div style={{ fontSize: 12, color: "var(--muted)", margin: "4px 0 8px" }}>
                  {r.vehiculo}{r.placa ? ` · ${r.placa}` : ""} · {r.telefono || "sin teléfono"}
                </div>
                <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                  <button className="btn btn-sm" onClick={() => verGps(r)}>📍 GPS</button>
                  {r.disponible !== "disponible" && <button className="btn btn-sm btn-primary" onClick={() => estadoRepartidor(r, "disponible")}>Disponible</button>}
                  {r.disponible === "disponible" && (
                    <>
                      <button className="btn btn-sm" onClick={() => estadoRepartidor(r, "en_ruta")}>En ruta</button>
                      <button className="btn btn-sm" onClick={() => estadoRepartidor(r, "inactivo")}>Inactivo</button>
                    </>
                  )}
                </div>
              </div>
            ))}
          </div>
        </form>

        <form onSubmit={crearRuta} className="card" style={{ padding: 14, display: "grid", gap: 10 }}>
          <h3 style={{ fontSize: 15 }}>🗺️ Rutas de entrega</h3>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <input required placeholder="Nombre ruta (Zona Norte…)" value={rutForm.nombre} onChange={(e) => setRutForm({ ...rutForm, nombre: e.target.value })} />
            <input type="number" min={0} placeholder="Tarifa" value={rutForm.tarifa} onChange={(e) => setRutForm({ ...rutForm, tarifa: e.target.value })} />
            <select value={rutForm.repartidor_id} onChange={(e) => setRutForm({ ...rutForm, repartidor_id: e.target.value })}>
              <option value="">Repartidor (opcional)</option>
              {repartidores.map((r) => <option key={r.id} value={r.id}>{r.nombre}</option>)}
            </select>
            <input placeholder="Detalle" value={rutForm.detalle} onChange={(e) => setRutForm({ ...rutForm, detalle: e.target.value })} />
            <button className="btn btn-primary" onClick={() => loadRutas()}>↻ Cargar</button>
          </div>
          <table className="table">
            <thead><tr><th>Ruta</th><th>Tarifa</th><th>Repartidor</th><th>Detalle</th></tr></thead>
            <tbody>
              {rutas.length === 0 && <tr><td colSpan={4} className="muted" style={{ textAlign: "center" }}>Sin rutas. Crea la primera arriba y pulsa Cargar.</td></tr>}
              {rutas.map((r) => (
                <tr key={r.id}>
                  <td><b>{r.nombre}</b></td>
                  <td>${r.tarifa.toLocaleString("es-CO")}</td>
                  <td>{r.repartidor || "—"}</td>
                  <td style={{ fontSize: 12 }}>{r.detalle || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </form>
      </div>
      </>
      )}

      {verPedido && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,.45)", display: "grid", placeItems: "center", zIndex: 1100, padding: 20 }}>
          <div className="card" style={{ width: "min(640px, 100%)" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
              <h3>Pedido {verPedido.numero}</h3>
              <button className="btn btn-ghost" onClick={() => setVerPedido(null)}>✕</button>
            </div>
            <p className="muted">
              <b>{verPedido.tipo}</b> · {badge(verPedido.estado)} · Domicilio: {badge(verPedido.estado_domicilio)} · {verPedido.repartidor || "sin repartidor"} · Total <strong>${Number(verPedido.total || 0).toLocaleString("es-CO")}</strong>
            </p>
            {verPedido.direccion_entrega && <p className="muted">Dirección: {verPedido.direccion_entrega}</p>}
            <table className="table" style={{ marginTop: 10 }}>
              <thead><tr><th>Producto</th><th>Cantidad</th><th>Precio</th><th>Subtotal</th></tr></thead>
              <tbody>
                {(verPedido.detalle || []).map((d, i) => (
                  <tr key={i}><td>#{d.producto_id}</td><td>{d.cantidad}</td><td>${Number(d.precio || 0).toLocaleString("es-CO")}</td><td>${Number(d.subtotal || 0).toLocaleString("es-CO")}</td></tr>
                ))}
                {(verPedido.detalle || []).length === 0 && <tr><td colSpan={4} className="muted" style={{ textAlign: "center" }}>Sin detalle</td></tr>}
              </tbody>
            </table>
            {verPedido.created_at && <p className="muted" style={{ marginTop: 8 }}>{new Date(verPedido.created_at).toLocaleString()}</p>}
          </div>
        </div>
      )}

      {tracking && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,.45)", display: "grid", placeItems: "center", zIndex: 1100, padding: 20 }}>
          <div className="card" style={{ width: "min(620px, 100%)" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
              <h3>Tracking {tracking.numero}</h3>
              <button className="btn btn-ghost" onClick={() => setTracking(null)}>✕</button>
            </div>
            <p className="muted">
              Pedido: {badge(tracking.estado)} · Domicilio: {badge(tracking.estado_domicilio)}
            </p>
            {tracking.ubicacion && (
              <div className="card" style={{ padding: 12, margin: "8px 0" }}>
                <div><b>{tracking.ubicacion.repartidor}</b>{tracking.ubicacion.vehiculo ? ` · ${tracking.ubicacion.vehiculo}` : ""}</div>
                <div style={{ fontSize: 12, color: "var(--muted)" }}>
                  📍 {tracking.ubicacion.lat?.toFixed?.(5)}, {tracking.ubicacion.lng?.toFixed?.(5)} → destino {tracking.ubicacion.dest_lat?.toFixed?.(5)}, {tracking.ubicacion.dest_lng?.toFixed?.(5)}
                </div>
                <div style={{ fontSize: 12 }}>{tracking.ubicacion.direccion || "—"}</div>
              </div>
            )}
            <h4 style={{ fontSize: 13, margin: "10px 0 6px" }}>Línea de tiempo</h4>
            <table className="table">
              <thead><tr><th>Fecha</th><th>Estado</th><th>Nota</th></tr></thead>
              <tbody>
                {(tracking.eventos || []).map((e, i) => (
                  <tr key={i}>
                    <td style={{ fontSize: 12 }}>{e.created_at ? new Date(e.created_at).toLocaleString() : "—"}</td>
                    <td>{badge(e.estado)}</td>
                    <td style={{ fontSize: 12 }}>{e.nota || "—"}</td>
                  </tr>
                ))}
                {(tracking.eventos || []).length === 0 && <tr><td colSpan={3} className="muted" style={{ textAlign: "center" }}>Sin eventos registrados</td></tr>}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}