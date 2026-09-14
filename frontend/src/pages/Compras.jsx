import { useEffect, useState } from "react";
import api from "../api.js";

function formatMoney(n) {
  return new Intl.NumberFormat("es-CO", { style: "currency", currency: "COP", maximumFractionDigits: 0 }).format(n || 0);
}

export default function Compras() {
  const [compras, setCompras] = useState([]);
  const [ordenes, setOrdenes] = useState([]);
  const [devoluciones, setDevoluciones] = useState([]);
  const [cotizaciones, setCotizaciones] = useState([]);
  const [estadoCuenta, setEstadoCuenta] = useState(null);
  const [productos, setProductos] = useState([]);
  const [proveedores, setProveedores] = useState([]);
  const [error, setError] = useState("");
  const [tab, setTab] = useState("compras");
  const [form, setForm] = useState({ proveedor_id: "", tipo: "contado", otros_costos: 0 });
  const [items, setItems] = useState([{ producto_id: "", cantidad: 1, costo_unitario: "", descuento: 0 }]);
  const [ordenForm, setOrdenForm] = useState({ proveedor_id: "" });
  const [ordenItems, setOrdenItems] = useState([{ producto_id: "", cantidad: 1, costo_unitario: "" }]);
  const [devForm, setDevForm] = useState({ proveedor_id: "", motivo: "" });
  const [devItems, setDevItems] = useState([{ producto_id: "", cantidad: 1 }]);
  const [cotForm, setCotForm] = useState({ proveedor_id: "", notas: "" });
  const [cotItems, setCotItems] = useState([{ producto_id: "", cantidad: 1, costo_unitario: "" }]);
  const [cuentaProveedor, setCuentaProveedor] = useState("");
  const [cuentasPagar, setCuentasPagar] = useState([]);
  const [compraDet, setCompraDet] = useState(null);

  async function load() {
    api("/compras").then(setCompras).catch(() => {});
    api("/compras/ordenes").then(setOrdenes).catch(() => {});
    api("/compras/devoluciones").then(setDevoluciones).catch(() => {});
    api("/compras/cotizaciones").then(setCotizaciones).catch(() => {});
    api("/productos").then(setProductos).catch(() => {});
    api("/proveedores").then(setProveedores).catch(() => {});
    api("/compras/cuentas-pagar").then(setCuentasPagar).catch(() => {});
  }

  async function verCompra(id) {
    setError("");
    try {
      setCompraDet(await api(`/compras/${id}`));
    } catch (err) {
      setError(err.message);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function verEstadoCuenta() {
    if (!cuentaProveedor) return;
    api(`/compras/estado-cuenta/${cuentaProveedor}`).then(setEstadoCuenta).catch((e) => setError(e.message));
  }

  async function createDevolucion(e) {
    e.preventDefault();
    setError("");
    try {
      await api("/compras/devoluciones", {
        method: "POST",
        body: JSON.stringify({
          empresa_id: 1,
          sucursal_id: 1,
          proveedor_id: Number(devForm.proveedor_id),
          tipo: "parcial",
          motivo: devForm.motivo,
          detalle: devItems.map((it) => ({ producto_id: Number(it.producto_id), cantidad: Number(it.cantidad) })),
        }),
      });
      setDevItems([{ producto_id: "", cantidad: 1 }]);
      load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function createCotizacion(e) {
    e.preventDefault();
    setError("");
    try {
      await api("/compras/cotizaciones", {
        method: "POST",
        body: JSON.stringify({
          empresa_id: 1,
          proveedor_id: Number(cotForm.proveedor_id),
          notas: cotForm.notas,
          detalle: cotItems.map((it) => ({
            producto_id: Number(it.producto_id),
            cantidad: Number(it.cantidad),
            costo_unitario: Number(it.costo_unitario),
          })),
        }),
      });
      setCotItems([{ producto_id: "", cantidad: 1, costo_unitario: "" }]);
      load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function aprobarCotizacion(id) {
    api(`/compras/cotizaciones/${id}/aprobar`, { method: "POST" })
      .then(load)
      .catch((e) => setError(e.message));
  }

  function onItems(setter) {
    return (i, field, value) =>
      setter((prev) => prev.map((it, idx) => (idx === i ? { ...it, [field]: value } : it)));
  }

  function addItem(setter) {
    setter((prev) => [...prev, { producto_id: "", cantidad: 1, costo_unitario: "", descuento: 0 }]);
  }

  async function createCompra(e) {
    e.preventDefault();
    setError("");
    try {
      await api("/compras", {
        method: "POST",
        body: JSON.stringify({
          empresa_id: 1,
          sucursal_id: 1,
          proveedor_id: Number(form.proveedor_id),
          tipo: form.tipo,
          otros_costos: Number(form.otros_costos || 0),
          detalle: items.map((it) => ({
            producto_id: Number(it.producto_id),
            cantidad: Number(it.cantidad),
            costo_unitario: Number(it.costo_unitario),
            descuento: Number(it.descuento || 0),
          })),
        }),
      });
      setItems([{ producto_id: "", cantidad: 1, costo_unitario: "", descuento: 0 }]);
      load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function createOrden(e) {
    e.preventDefault();
    setError("");
    try {
      await api("/compras/ordenes", {
        method: "POST",
        body: JSON.stringify({
          empresa_id: 1,
          sucursal_id: 1,
          proveedor_id: Number(ordenForm.proveedor_id),
          detalle: ordenItems.map((it) => ({
            producto_id: Number(it.producto_id),
            cantidad: Number(it.cantidad),
            costo_unitario: Number(it.costo_unitario),
          })),
        }),
      });
      setOrdenItems([{ producto_id: "", cantidad: 1, costo_unitario: "" }]);
      load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function ordenAccion(id, accion) {
    setError("");
    try {
      await api(`/compras/ordenes/${id}/${accion}`, { method: "POST" });
      load();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div className="page">
      <div className="page-header">
        <h1>Compras</h1>
        <div style={{ display: "flex", gap: 8 }}>
          {["compras", "ordenes", "devoluciones", "cotizaciones", "estado"].map((t) => (
            <button key={t} className={`btn ${tab === t ? "" : "btn-secondary"}`} onClick={() => setTab(t)}>
              {t === "compras" ? "Compras directas" : t === "ordenes" ? "Órdenes" : t === "devoluciones" ? "Devoluciones" : t === "cotizaciones" ? "Cotizaciones" : "Estado de cuenta"}
            </button>
          ))}
        </div>
      </div>

      {error && <div className="error">{error}</div>}

      {tab === "compras" && (
        <>
          <form onSubmit={createCompra} className="card" style={{ marginBottom: 20 }}>
            <h3 style={{ marginBottom: 12 }}>Nueva compra</h3>
            <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginBottom: 12 }}>
              <div style={{ flex: 1, minWidth: 150 }}>
                <label>Proveedor *</label>
                <select required value={form.proveedor_id} onChange={(e) => setForm({ ...form, proveedor_id: e.target.value })}>
                  <option value="">Seleccione...</option>
                  {proveedores.map((p) => <option key={p.id} value={p.id}>{p.nombre}</option>)}
                </select>
              </div>
              <div><label>Tipo</label>
                <select value={form.tipo} onChange={(e) => setForm({ ...form, tipo: e.target.value })}>
                  <option value="contado">Contado</option>
                  <option value="credito">Crédito</option>
                </select>
              </div>
              <div><label>Otros costos (flete, etc.)</label><input type="number" value={form.otros_costos} onChange={(e) => setForm({ ...form, otros_costos: e.target.value })} /></div>
              <div style={{ display: "flex", alignItems: "flex-end" }}><button className="btn" type="submit">Registrar compra</button></div>
            </div>

            {items.map((it, i) => (
              <div key={i} style={{ display: "flex", gap: 10, marginBottom: 8, flexWrap: "wrap" }}>
                <div style={{ flex: 2, minWidth: 180 }}>
                  <label>Producto</label>
                  <select required value={it.producto_id} onChange={(e) => onItems(setItems)(i, "producto_id", e.target.value)}>
                    <option value="">Seleccione...</option>
                    {productos.map((p) => <option key={p.id} value={p.id}>{p.nombre}</option>)}
                  </select>
                </div>
                <div><label>Cantidad</label><input type="number" min="1" value={it.cantidad} onChange={(e) => onItems(setItems)(i, "cantidad", e.target.value)} /></div>
                <div><label>Costo unitario</label><input type="number" step="0.01" placeholder="0" value={it.costo_unitario} onChange={(e) => onItems(setItems)(i, "costo_unitario", e.target.value)} /></div>
                <div><label>Descuento</label><input type="number" step="0.01" value={it.descuento} onChange={(e) => onItems(setItems)(i, "descuento", e.target.value)} /></div>
              </div>
            ))}
            <button type="button" className="btn btn-secondary" onClick={() => addItem(setItems)}>+ Agregar línea</button>
          </form>

          <table className="table">
            <thead>
              <tr><th>Número</th><th>Fecha</th><th>Tipo</th><th>Estado</th><th>Subtotal</th><th>Impuesto</th><th>Total</th><th></th></tr>
            </thead>
            <tbody>
              {compras.map((c) => (
                <tr key={c.id}>
                  <td>{c.numero}</td>
                  <td>{c.created_at ? new Date(c.created_at).toLocaleString() : "—"}</td>
                  <td><span className={`badge ${c.tipo === "credito" ? "badge-warning" : "badge-info"}`}>{c.tipo}</span></td>
                  <td><span className={`badge ${c.estado === "recibida" ? "badge-success" : "badge-warning"}`}>{c.estado}</span></td>
                  <td>{formatMoney(c.subtotal)}</td>
                  <td>{formatMoney(c.impuesto)}</td>
                  <td><strong>{formatMoney(c.total)}</strong></td>
                  <td><button className="btn btn-secondary" onClick={() => verCompra(c.id)}>Ver</button></td>
                </tr>
              ))}
              {compras.length === 0 && <tr><td colSpan={8} className="muted" style={{ textAlign: "center", padding: 20 }}>Sin compras</td></tr>}
            </tbody>
          </table>
        </>
      )}

      {tab === "ordenes" && (
        <>
          <form onSubmit={createOrden} className="card" style={{ marginBottom: 20 }}>
            <h3 style={{ marginBottom: 12 }}>Nueva orden de compra</h3>
            <div style={{ display: "flex", gap: 12, marginBottom: 12, flexWrap: "wrap" }}>
              <div style={{ flex: 1, minWidth: 150 }}>
                <label>Proveedor *</label>
                <select required value={ordenForm.proveedor_id} onChange={(e) => setOrdenForm({ ...ordenForm, proveedor_id: e.target.value })}>
                  <option value="">Seleccione...</option>
                  {proveedores.map((p) => <option key={p.id} value={p.id}>{p.nombre}</option>)}
                </select>
              </div>
              <div style={{ display: "flex", alignItems: "flex-end" }}><button className="btn" type="submit">Crear orden</button></div>
            </div>
            {ordenItems.map((it, i) => (
              <div key={i} style={{ display: "flex", gap: 10, marginBottom: 8, flexWrap: "wrap" }}>
                <div style={{ flex: 2, minWidth: 180 }}>
                  <label>Producto</label>
                  <select required value={it.producto_id} onChange={(e) => onItems(setOrdenItems)(i, "producto_id", e.target.value)}>
                    <option value="">Seleccione...</option>
                    {productos.map((p) => <option key={p.id} value={p.id}>{p.nombre}</option>)}
                  </select>
                </div>
                <div><label>Cantidad</label><input type="number" min="1" value={it.cantidad} onChange={(e) => onItems(setOrdenItems)(i, "cantidad", e.target.value)} /></div>
                <div><label>Costo unitario</label><input type="number" step="0.01" placeholder="0" value={it.costo_unitario} onChange={(e) => onItems(setOrdenItems)(i, "costo_unitario", e.target.value)} /></div>
              </div>
            ))}
            <button type="button" className="btn btn-secondary" onClick={() => addItem(setOrdenItems)}>+ Agregar línea</button>
          </form>

          <table className="table">
            <thead>
              <tr><th>Número</th><th>Fecha</th><th>Estado</th><th>Productos</th><th>Acciones</th></tr>
            </thead>
            <tbody>
              {ordenes.map((o) => (
                <tr key={o.id}>
                  <td>{o.numero}</td>
                  <td>{o.created_at ? new Date(o.created_at).toLocaleString() : "—"}</td>
                  <td><span className={`badge ${o.estado === "recibida" ? "badge-success" : o.estado === "cancelada" ? "badge-danger" : "badge-warning"}`}>{o.estado}</span></td>
                  <td>{o.detalle.reduce((a, d) => a + Number(d.cantidad || 0), 0)}</td>
                  <td>
                    {o.estado === "pendiente" && (
                      <button className="btn btn-secondary" onClick={() => ordenAccion(o.id, "aprobar")}>Aprobar</button>
                    )}
                    {o.estado === "aprobada" && (
                      <button className="btn" onClick={() => ordenAccion(o.id, "recibir")}>Recibir mercancía</button>
                    )}
                    {o.estado === "pendiente" && (
                      <button className="btn btn-danger" style={{ marginLeft: 6 }} onClick={() => ordenAccion(o.id, "cancelar")}>Cancelar</button>
                    )}
                  </td>
                </tr>
              ))}
              {ordenes.length === 0 && <tr><td colSpan={5} className="muted" style={{ textAlign: "center", padding: 20 }}>Sin órdenes</td></tr>}
            </tbody>
          </table>
        </>
      )}

      {tab === "devoluciones" && (
        <>
          <form onSubmit={createDevolucion} className="card" style={{ marginBottom: 20 }}>
            <h3 style={{ marginBottom: 12 }}>Devolución a proveedor</h3>
            <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginBottom: 12 }}>
              <div style={{ flex: 1, minWidth: 150 }}>
                <label>Proveedor *</label>
                <select required value={devForm.proveedor_id} onChange={(e) => setDevForm({ ...devForm, proveedor_id: e.target.value })}>
                  <option value="">Seleccione...</option>
                  {proveedores.map((p) => <option key={p.id} value={p.id}>{p.nombre}</option>)}
                </select>
              </div>
              <div style={{ flex: 2, minWidth: 200 }}><label>Motivo</label><input value={devForm.motivo} onChange={(e) => setDevForm({ ...devForm, motivo: e.target.value })} placeholder="Mercancía en mal estado..." /></div>
            </div>
            {devItems.map((it, i) => (
              <div key={i} style={{ display: "flex", gap: 10, marginBottom: 8, flexWrap: "wrap" }}>
                <div style={{ flex: 2, minWidth: 180 }}>
                  <label>Producto</label>
                  <select required value={it.producto_id} onChange={(e) => onItems(setDevItems)(i, "producto_id", e.target.value)}>
                    <option value="">Seleccione...</option>
                    {productos.map((p) => <option key={p.id} value={p.id}>{p.nombre}</option>)}
                  </select>
                </div>
                <div><label>Cantidad</label><input type="number" min="1" value={it.cantidad} onChange={(e) => onItems(setDevItems)(i, "cantidad", e.target.value)} /></div>
              </div>
            ))}
            <button type="button" className="btn btn-secondary" onClick={() => setDevItems([...devItems, { producto_id: "", cantidad: 1 }])}>+ Línea</button>
            <button className="btn" type="submit" style={{ marginLeft: 8 }}>Registrar devolución</button>
          </form>

          <table className="table">
            <thead>
              <tr><th>Número</th><th>Fecha</th><th>Tipo</th><th>Estado</th><th>Detalle</th><th>Total</th></tr>
            </thead>
            <tbody>
              {devoluciones.map((d) => (
                <tr key={d.id}>
                  <td>{d.numero}</td>
                  <td>{d.created_at ? new Date(d.created_at).toLocaleString() : "—"}</td>
                  <td><span className="badge badge-warning">{d.tipo}</span></td>
                  <td><span className={`badge ${d.estado === "aplicada" ? "badge-success" : "badge-warning"}`}>{d.estado}</span></td>
                  <td>{d.detalle?.length || 0} productos</td>
                  <td><strong>{formatMoney(d.total_devolucion)}</strong></td>
                </tr>
              ))}
              {devoluciones.length === 0 && <tr><td colSpan={6} className="muted" style={{ textAlign: "center", padding: 20 }}>Sin devoluciones</td></tr>}
            </tbody>
          </table>
        </>
      )}

      {tab === "cotizaciones" && (
        <>
          <form onSubmit={createCotizacion} className="card" style={{ marginBottom: 20 }}>
            <h3 style={{ marginBottom: 12 }}>Cotización de proveedor</h3>
            <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginBottom: 12 }}>
              <div style={{ flex: 1, minWidth: 150 }}>
                <label>Proveedor *</label>
                <select required value={cotForm.proveedor_id} onChange={(e) => setCotForm({ ...cotForm, proveedor_id: e.target.value })}>
                  <option value="">Seleccione...</option>
                  {proveedores.map((p) => <option key={p.id} value={p.id}>{p.nombre}</option>)}
                </select>
              </div>
              <div style={{ flex: 2, minWidth: 200 }}><label>Notas</label><input value={cotForm.notas} onChange={(e) => setCotForm({ ...cotForm, notas: e.target.value })} /></div>
            </div>
            {cotItems.map((it, i) => (
              <div key={i} style={{ display: "flex", gap: 10, marginBottom: 8, flexWrap: "wrap" }}>
                <div style={{ flex: 2, minWidth: 180 }}>
                  <label>Producto</label>
                  <select required value={it.producto_id} onChange={(e) => onItems(setCotItems)(i, "producto_id", e.target.value)}>
                    <option value="">Seleccione...</option>
                    {productos.map((p) => <option key={p.id} value={p.id}>{p.nombre}</option>)}
                  </select>
                </div>
                <div><label>Cantidad</label><input type="number" min="1" value={it.cantidad} onChange={(e) => onItems(setCotItems)(i, "cantidad", e.target.value)} /></div>
                <div><label>Costo unitario</label><input type="number" step="0.01" value={it.costo_unitario} onChange={(e) => onItems(setCotItems)(i, "costo_unitario", e.target.value)} /></div>
              </div>
            ))}
            <button type="button" className="btn btn-secondary" onClick={() => setCotItems([...cotItems, { producto_id: "", cantidad: 1, costo_unitario: "" }])}>+ Línea</button>
            <button className="btn" type="submit" style={{ marginLeft: 8 }}>Guardar cotización</button>
          </form>

          <table className="table">
            <thead>
              <tr><th>Número</th><th>Fecha</th><th>Proveedor</th><th>Total estimado</th><th>Estado</th><th></th></tr>
            </thead>
            <tbody>
              {cotizaciones.map((c) => (
                <tr key={c.id}>
                  <td>{c.numero}</td>
                  <td>{c.created_at ? new Date(c.created_at).toLocaleString() : "—"}</td>
                  <td>{c.proveedor_id}</td>
                  <td>{formatMoney(c.total_estimado)}</td>
                  <td><span className={`badge ${c.estado === "aprobada" ? "badge-success" : c.estado === "rechazada" ? "badge-danger" : "badge-info"}`}>{c.estado}</span></td>
                  <td>
                    {c.estado === "pendiente" && <button className="btn" onClick={() => aprobarCotizacion(c.id)}>Aprobar</button>}
                  </td>
                </tr>
              ))}
              {cotizaciones.length === 0 && <tr><td colSpan={6} className="muted" style={{ textAlign: "center", padding: 20 }}>Sin cotizaciones</td></tr>}
            </tbody>
          </table>
        </>
      )}

      {tab === "estado" && (
        <div className="card" style={{ marginBottom: 20 }}>
          <h3 style={{ marginBottom: 12 }}>Cuentas por pagar a proveedores</h3>
          <table className="table" style={{ marginBottom: 8 }}>
            <thead><tr><th>Cta</th><th>Proveedor</th><th>Compra</th><th>Total</th><th>Saldo</th><th>Estado</th><th>Vence</th></tr></thead>
            <tbody>
              {cuentasPagar.map((c) => {
                const prov = proveedores.find((p) => p.id === c.proveedor_id);
                return (
                  <tr key={c.id}>
                    <td>#{c.id}</td>
                    <td>{prov?.nombre || `#${c.proveedor_id}`}</td>
                    <td>{c.compra_id ? `#${c.compra_id}` : "—"}</td>
                    <td>{formatMoney(c.monto_total)}</td>
                    <td><strong>{formatMoney(c.saldo)}</strong></td>
                    <td><span className={`badge ${c.estado === "pagada" ? "badge-success" : "badge-warning"}`}>{c.estado}</span></td>
                    <td>{c.fecha_vencimiento || "—"}</td>
                  </tr>
                );
              })}
              {cuentasPagar.length === 0 && <tr><td colSpan={7} className="muted" style={{ textAlign: "center", padding: 16 }}>Sin cuentas por pagar</td></tr>}
            </tbody>
          </table>
        </div>
      )}

      {tab === "estado" && (
        <div className="card">
          <h3 style={{ marginBottom: 12 }}>Estado de cuenta por proveedor</h3>
          <div style={{ display: "flex", gap: 12, alignItems: "flex-end", marginBottom: 16 }}>
            <div style={{ flex: 1, minWidth: 150 }}>
              <label>Proveedor</label>
              <select value={cuentaProveedor} onChange={(e) => setCuentaProveedor(e.target.value)}>
                <option value="">Seleccione...</option>
                {proveedores.map((p) => <option key={p.id} value={p.id}>{p.nombre}</option>)}
              </select>
            </div>
            <button className="btn" onClick={verEstadoCuenta}>Consultar</button>
          </div>

          {estadoCuenta && (
            <>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(180px, 1fr))", gap: 12, marginBottom: 16 }}>
                <div className="card" style={{ margin: 0 }}><div className="muted" style={{ fontSize: 12 }}>Total comprado</div><div style={{ fontSize: 18, fontWeight: 700 }}>{formatMoney(estadoCuenta.total_comprado)}</div></div>
                <div className="card" style={{ margin: 0 }}><div className="muted" style={{ fontSize: 12 }}>Devoluciones</div><div style={{ fontSize: 18, fontWeight: 700 }}>{formatMoney(estadoCuenta.total_devoluciones)}</div></div>
                <div className="card" style={{ margin: 0 }}><div className="muted" style={{ fontSize: 12 }}>Abonado</div><div style={{ fontSize: 18, fontWeight: 700 }}>{formatMoney(estadoCuenta.total_abonos)}</div></div>
                <div className="card" style={{ margin: 0 }}><div className="muted" style={{ fontSize: 12 }}>Saldo pendiente</div><div style={{ fontSize: 18, fontWeight: 700, color: "#4f46e5" }}>{formatMoney(estadoCuenta.saldo_pendiente)}</div></div>
              </div>
              <h4 style={{ fontSize: 14, marginBottom: 8 }}>Cuentas por pagar</h4>
              <table className="table">
                <thead><tr><th>Compra</th><th>Total</th><th>Saldo</th><th>Estado</th></tr></thead>
                <tbody>
                  {estadoCuenta.cuentas.map((c) => (
                    <tr key={c.id}>
                      <td>#{c.compra_id}</td>
                      <td>{formatMoney(c.monto_total)}</td>
                      <td>{formatMoney(c.saldo)}</td>
                      <td><span className={`badge ${c.estado === "pagada" ? "badge-success" : "badge-warning"}`}>{c.estado}</span></td>
                    </tr>
                  ))}
                  {estadoCuenta.cuentas.length === 0 && <tr><td colSpan={4} className="muted" style={{ textAlign: "center", padding: 16 }}>Sin cuentas</td></tr>}
                </tbody>
              </table>
            </>
          )}
        </div>
      )}

      {compraDet && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,.45)", display: "grid", placeItems: "center", zIndex: 1100, padding: 20 }}>
          <div className="card" style={{ width: "min(640px, 100%)" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
              <h3>Compra {compraDet.numero} <span className="muted" style={{ fontSize: 13 }}>#{compraDet.id}</span></h3>
              <button className="btn btn-ghost" onClick={() => setCompraDet(null)}>✕</button>
            </div>
            <p className="muted">
              {new Date(compraDet.created_at).toLocaleString()} · {compraDet.tipo} · Estado: <strong>{compraDet.estado}</strong> · Proveedor #{compraDet.proveedor_id}
            </p>
            <table className="table" style={{ marginTop: 10 }}>
              <thead><tr><th>Producto</th><th>Cantidad</th><th>Costo u.</th><th>Descuento</th><th>Subtotal</th></tr></thead>
              <tbody>
                {compraDet.detalle.map((d) => (
                  <tr key={d.id}>
                    <td>{productos.find((p) => p.id === d.producto_id)?.nombre || `#${d.producto_id}`}</td>
                    <td>{d.cantidad}</td>
                    <td>{formatMoney(d.costo_unitario)}</td>
                    <td>{formatMoney(d.descuento)}</td>
                    <td>{formatMoney(d.subtotal)}</td>
                  </tr>
                ))}
                {compraDet.detalle.length === 0 && <tr><td colSpan={5} className="muted" style={{ textAlign: "center" }}>Sin detalle</td></tr>}
              </tbody>
            </table>
            <div style={{ display: "flex", justifyContent: "flex-end", gap: 16, marginTop: 10 }}>
              <span className="muted">Subtotal: {formatMoney(compraDet.subtotal)}</span>
              <span className="muted">Impuesto: {formatMoney(compraDet.impuesto)}</span>
              <strong>Total: {formatMoney(compraDet.total)}</strong>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}