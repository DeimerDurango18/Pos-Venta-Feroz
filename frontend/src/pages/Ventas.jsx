import { useEffect, useState } from "react";
import api, { openWindow } from "../api.js";

function formatMoney(n) {
  return new Intl.NumberFormat("es-CO", { style: "currency", currency: "COP", maximumFractionDigits: 0 }).format(n || 0);
}

export default function Ventas() {
  const [ventas, setVentas] = useState([]);
  const [devoluciones, setDevoluciones] = useState([]);
  const [detDev, setDetDev] = useState(null);
  const [productos, setProductos] = useState([]);
  const [tab, setTab] = useState("ventas");
  const [cambioForm, setCambioForm] = useState({ venta_id: "", motivo: "" });
  const [reemplazos, setReemplazos] = useState([{ producto_id: "", cantidad: 1 }]);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [dev, setDev] = useState(null);
  const [devForm, setDevForm] = useState({ venta_id: "", tipo: "parcial", motivo: "", reembolso_medio: "efectivo" });
  const [devItems, setDevItems] = useState([{ producto_id: "", cantidad: 1 }]);
  const [div, setDiv] = useState(null);
  const [clientes, setClientes] = useState([]);
  const [partes, setPartes] = useState([{ cliente_id: "", monto: "" }]);
  const [detVenta, setDetVenta] = useState(null);
  const ventaSel = ventas.find((v) => v.id === Number(devForm.venta_id));
  const ventaDiv = ventas.find((v) => v.id === Number(div?.venta_id));

  async function load() {
    api("/ventas").then(setVentas).catch(() => {});
  }

  useEffect(() => {
    load();
    api("/clientes").then(setClientes).catch(() => {});
    api("/productos").then(setProductos).catch(() => {});
    api("/devoluciones").then(setDevoluciones).catch(() => {});
  }, []);

  useEffect(() => {
    if (tab === "devoluciones") api("/devoluciones").then(setDevoluciones).catch(() => {});
  }, [tab]);

  async function verDetalleVenta(id) {
    setError("");
    try {
      setDetVenta(await api(`/ventas/${id}`));
    } catch (err) {
      setError(err.message);
    }
  }

  async function abonar(v) {
    setError("");
    const monto = window.prompt(`Abono para ${v.numero}\nMonto (saldo ${formatMoney(v.saldo)}):`);
    if (monto === null || monto === "") return;
    try {
      const r = await api(`/ventas/${v.id}/pagos`, {
        method: "POST",
        body: JSON.stringify({ medio: "efectivo", monto: Number(monto) }),
      });
      setSuccess(`Abono de ${formatMoney(r.monto)} registrado · nuevo saldo ${formatMoney(r.saldo)}`);
      load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function verDetalleDev(id) {
    setError("");
    try {
      setDetDev(await api(`/devoluciones/${id}`));
    } catch (err) {
      setError(err.message);
    }
  }

  async function crearCambio(e) {
    e.preventDefault();
    setError("");
    try {
      const r = await api("/devoluciones/cambio", {
        method: "POST",
        body: JSON.stringify({
          empresa_id: 1,
          sucursal_id: 1,
          venta_id: Number(cambioForm.venta_id),
          tipo: "total",
          motivo: cambioForm.motivo,
          reembolso_medio: "nota_credito",
          detalle: null,
          reemplazo: reemplazos.filter((x) => x.producto_id).map((x) => ({ producto_id: Number(x.producto_id), cantidad: Number(x.cantidad) })),
        }),
      });
      setCambioForm({ venta_id: "", motivo: "" });
      setReemplazos([{ producto_id: "", cantidad: 1 }]);
      api("/devoluciones").then(setDevoluciones).catch(() => {});
      setSuccess(`Cambio registrado: devolución ${r.devolucion}${r.venta_nueva ? ` + venta nueva ${r.venta_nueva}` : ""}`);
    } catch (err) {
      setError(err.message);
    }
  }

  async function anular(v) {
    setError("");
    if (!window.confirm(`¿Anular la venta ${v.numero}?`)) return;
    try {
      await api(`/ventas/${v.id}/anular`, { method: "POST" });
      load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function suspender(v) {
    setError("");
    try {
      await api(`/ventas/${v.id}/suspender`, { method: "POST" });
      load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function reanudar(v) {
    setError("");
    try {
      await api(`/ventas/${v.id}/reanudar`, { method: "POST" });
      load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function notaDebito(v) {
    setError("");
    const monto = window.prompt(`Nota débito para ${v.numero}\nMonto:`);
    if (monto === null || monto === "") return;
    const concepto = window.prompt("Concepto:") || "Ajuste";
    try {
      await api(`/ventas/${v.id}/nota-debito`, {
        method: "POST",
        body: JSON.stringify({ monto: Number(monto), concepto }),
      });
      load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function imprimirFactura(v) {
    setError("");
    try {
      const docs = await api(`/facturacion/documentos?venta_id=${v.id}`);
      const fac = Array.isArray(docs) ? docs.find((d) => d.tipo_documento === "factura") : null;
      const doc = fac || (Array.isArray(docs) ? docs[0] : null);
      if (!doc) {
        setError(`La venta ${v.numero} no tiene documento fiscal`);
        return;
      }
      await openWindow(`/facturacion/${doc.id}/ticket`);
    } catch (err) {
      setError(err.message);
    }
  }

  async function crearDevolucion(e) {
    e.preventDefault();
    setError("");
    try {
      await api("/devoluciones", {
        method: "POST",
        body: JSON.stringify({
          empresa_id: 1,
          sucursal_id: 1,
          venta_id: Number(devForm.venta_id),
          tipo: devForm.tipo,
          motivo: devForm.motivo,
          reembolso_medio: devForm.reembolso_medio,
          detalle: devItems
            .filter((it) => it.producto_id)
            .map((it) => ({ producto_id: Number(it.producto_id), cantidad: Number(it.cantidad) })),
        }),
      });
      setDev(null);
      setDevForm({ venta_id: "", tipo: "parcial", motivo: "", reembolso_medio: "efectivo" });
      setDevItems([{ producto_id: "", cantidad: 1 }]);
      load();
    } catch (err) {
      setError(err.message);
    }
  }

  function abrirDivision(v) {
    const saldo = Number(v.saldo || 0);
    setDiv({ venta_id: String(v.id), saldo });
    setPartes([{ cliente_id: "", monto: saldo.toFixed(2) }]);
  }

  function cambiarParte(idx, campo, valor) {
    setPartes((prev) => prev.map((x, i) => (i === idx ? { ...x, [campo]: valor } : x)));
  }

  async function dividirCuenta(e) {
    e.preventDefault();
    setError("");
    const montoPartes = partes.reduce((s, p) => s + (Number(p.monto) || 0), 0);
    if (Math.abs(montoPartes - Number(div.saldo)) > 0.01) {
      setError(`La suma de las partes (${formatMoney(montoPartes)}) no coincide con el saldo (${formatMoney(div.saldo)})`);
      return;
    }
    if (partes.some((p) => !p.cliente_id)) {
      setError("Todas las partes deben tener cliente asignado");
      return;
    }
    try {
      const res = await api(`/ventas/${div.venta_id}/dividir`, {
        method: "POST",
        body: JSON.stringify({ partes: partes.map((p) => ({ cliente_id: Number(p.cliente_id), monto: Number(p.monto) })) }),
      });
      setSuccess(`Cuenta dividida: ${res.partes.length} partes generadas`);
      setDiv(null);
      setPartes([{ cliente_id: "", monto: "" }]);
      load();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div className="page">
      <div className="page-header">
        <h1>Ventas</h1>
        <div className="tabs">
          <button className={`btn ${tab === "ventas" ? "btn-primary" : ""}`} onClick={() => setTab("ventas")}>Ventas</button>
          <button className={`btn ${tab === "devoluciones" ? "btn-primary" : ""}`} onClick={() => setTab("devoluciones")}>Devoluciones / Cambios</button>
        </div>
      </div>

      {error && <div className="error">{error}</div>}
      {success && (
        <div className="badge-success" style={{ display: "block", padding: 10, borderRadius: 6, marginBottom: 10 }}>
          {success}
        </div>
      )}

      {div && ventaDiv && (
        <form onSubmit={dividirCuenta} className="card" style={{ marginBottom: 20 }}>
          <h3 style={{ marginBottom: 4 }}>Dividir cuenta — {ventaDiv.numero}</h3>
          <p className="muted" style={{ marginBottom: 12 }}>
            Saldo a repartir: <strong>{formatMoney(div.saldo)}</strong> entre {partes.length} parte(s)
          </p>
          {partes.map((p, i) => (
            <div key={i} style={{ display: "flex", gap: 10, marginBottom: 10, flexWrap: "wrap" }}>
              <select required value={p.cliente_id} style={{ flex: 1, minWidth: 200 }} onChange={(e) => cambiarParte(i, "cliente_id", e.target.value)}>
                <option value="">Cliente...</option>
                {clientes.map((c) => (
                  <option key={c.id} value={c.id}>{c.nombre}</option>
                ))}
              </select>
              <input required type="number" step="0.01" min="0.01" style={{ width: 130 }} placeholder="Monto" value={p.monto} onChange={(e) => cambiarParte(i, "monto", e.target.value)} />
              {partes.length > 1 && (
                <button type="button" className="btn btn-danger" onClick={() => setPartes(partes.filter((_, x) => x !== i))}>×</button>
              )}
            </div>
          ))}
          <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
            <button type="button" className="btn btn-secondary" onClick={() => setPartes([...partes, { cliente_id: "", monto: "" }])}>+ Agregar parte</button>
            <button type="submit" className="btn btn-primary">Dividir cuenta</button>
            <span className="muted">Suma: {formatMoney(partes.reduce((s, x) => s + (Number(x.monto) || 0), 0))}</span>
          </div>
        </form>
      )}

      {tab === "ventas" && (
        <>
      <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 10 }}>
        <button className="btn" onClick={() => setDev(dev ? null : {})}>
          {dev ? "Cerrar" : "Registrar devolución / nota crédito"}
        </button>
      </div>
      {dev && (
        <form onSubmit={crearDevolucion} className="card" style={{ marginBottom: 20 }}>
          <h3 style={{ marginBottom: 12 }}>Nota crédito / devolución</h3>
          <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginBottom: 12 }}>
            <div style={{ flex: 1, minWidth: 180 }}>
              <label>Venta *</label>
              <select required value={devForm.venta_id} onChange={(e) => { setDevForm({ ...devForm, venta_id: e.target.value }); setDevItems([{ producto_id: "", cantidad: 1 }]); }}>
                <option value="">Seleccione...</option>
                {ventas.filter((v) => v.estado === "completada").map((v) => (
                  <option key={v.id} value={v.id}>{v.numero} — {formatMoney(v.total)} ({v.tipo})</option>
                ))}
              </select>
            </div>
            <div>
              <label>Tipo</label>
              <select value={devForm.tipo} onChange={(e) => setDevForm({ ...devForm, tipo: e.target.value })}>
                <option value="parcial">Parcial</option>
                <option value="total">Total</option>
              </select>
            </div>
            <div>
              <label>Reembolso</label>
              <select value={devForm.reembolso_medio} onChange={(e) => setDevForm({ ...devForm, reembolso_medio: e.target.value })}>
                <option value="efectivo">Efectivo</option>
                <option value="transferencia">Transferencia</option>
                <option value="">Sin reembolso</option>
              </select>
            </div>
            <div style={{ flex: 2, minWidth: 200 }}>
              <label>Motivo</label>
              <input value={devForm.motivo} onChange={(e) => setDevForm({ ...devForm, motivo: e.target.value })} placeholder="Motivo de la devolución" />
            </div>
          </div>

          {ventaSel && (
            <div className="muted" style={{ marginBottom: 12 }}>
              Productos en la venta:
              {ventaSel.detalle.map((d) => (
                <span key={d.producto_id} style={{ display: "inline-flex", alignItems: "center", gap: 8, marginRight: 16, marginTop: 8 }}>
                  <strong>P{d.producto_id}</strong> · disp: {Number(d.cantidad)} · {formatMoney(Number(d.subtotal || 0) + Number(d.impuesto || 0))}
                </span>
              ))}
            </div>
          )}

          {devItems.map((it, i) => (
            <div key={i} style={{ display: "flex", gap: 10, marginBottom: 8, flexWrap: "wrap" }}>
              <div>
                <label>Producto ID *</label>
                <input type="number" required value={it.producto_id} placeholder="ID del producto" onChange={(e) => setDevItems((prev) => prev.map((x, idx) => idx === i ? { ...x, producto_id: e.target.value } : x))} />
              </div>
              <div>
                <label>Cantidad *</label>
                <input type="number" min="1" value={it.cantidad} onChange={(e) => setDevItems((prev) => prev.map((x, idx) => idx === i ? { ...x, cantidad: e.target.value } : x))} />
              </div>
              {devForm.tipo === "parcial" && (
                <div style={{ display: "flex", alignItems: "flex-end" }}>
                  <button type="button" className="btn btn-secondary" onClick={() => setDevItems([...devItems, { producto_id: "", cantidad: 1 }])}>+ Línea</button>
                </div>
              )}
            </div>
          ))}

          <button className="btn" type="submit">Registrar devolución</button>
        </form>
      )}

      <table className="table">
        <thead>
          <tr>
            <th>Número</th><th>Fecha</th><th>Tipo</th><th>Estado</th><th>Subtotal</th><th>Impuesto</th><th>Propina</th><th>Total</th><th>Saldo</th><th>Acciones</th>
          </tr>
        </thead>
        <tbody>
          {ventas.map((v) => (
            <tr key={v.id}>
              <td>{v.numero}</td>
              <td>{v.created_at ? new Date(v.created_at).toLocaleString() : "—"}</td>
              <td><span className={`badge ${v.tipo === "credito" ? "badge-warning" : "badge-info"}`}>{v.tipo}</span></td>
              <td><span className={`badge ${v.estado === "completada" ? "badge-success" : v.estado === "anulada" ? "badge-danger" : "badge-warning"}`}>{v.estado}</span></td>
              <td>{formatMoney(v.subtotal)}</td>
              <td>{formatMoney(v.impuesto)}</td>
              <td>{formatMoney(v.propina)}</td>
              <td><strong>{formatMoney(v.total)}</strong></td>
              <td>{v.tipo === "credito" ? formatMoney(v.saldo) : "—"}</td>
              <td style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                {v.estado === "completada" && (
                  <>
                    <button className="btn" onClick={() => verDetalleVenta(v.id)}>Detalle</button>
                    <button className="btn" onClick={() => imprimirFactura(v)}>Imprimir</button>
                    <button className="btn btn-secondary" onClick={() => suspender(v)}>Suspender</button>
                    {v.tipo === "credito" && Number(v.saldo || 0) > 0 && (
                      <>
                        <button className="btn btn-secondary" onClick={() => abonar(v)}>Abonar</button>
                        <button className="btn btn-secondary" onClick={() => abrirDivision(v)}>Dividir</button>
                      </>
                    )}
                    <button className="btn btn-ghost" onClick={() => notaDebito(v)}>Nota débito</button>
                    <button className="btn btn-danger" onClick={() => anular(v)}>Anular</button>
                  </>
                )}
                {v.estado === "suspendida" && (
                  <>
                    <button className="btn" onClick={() => reanudar(v)}>Reanudar</button>
                    <button className="btn btn-danger" onClick={() => anular(v)}>Anular</button>
                  </>
                )}
              </td>
            </tr>
          ))}
          {ventas.length === 0 && <tr><td colSpan={10} className="muted" style={{ textAlign: "center", padding: 20 }}>Sin ventas registradas</td></tr>}
        </tbody>
      </table>
        </>
      )}

      {tab === "devoluciones" && (
        <>
          <form onSubmit={crearCambio} className="card" style={{ marginBottom: 20 }}>
            <h3 style={{ marginBottom: 8 }}>Cambio de productos (devolución + venta de reemplazo)</h3>
            <p className="muted" style={{ fontSize: 12, marginBottom: 12 }}>
              Registra una devolución total y crea una venta inmediata con los productos de reemplazo, pagada con la nota crédito generada.
            </p>
            <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginBottom: 12 }}>
              <div style={{ flex: 1, minWidth: 200 }}>
                <label>Venta a devolver *</label>
                <select required value={cambioForm.venta_id} onChange={(e) => setCambioForm({ ...cambioForm, venta_id: e.target.value })}>
                  <option value="">Seleccione...</option>
                  {ventas.filter((v) => v.estado === "completada").map((v) => (
                    <option key={v.id} value={v.id}>{v.numero} — {formatMoney(v.total)}</option>
                  ))}
                </select>
              </div>
              <div style={{ flex: 2, minWidth: 200 }}>
                <label>Motivo</label>
                <input value={cambioForm.motivo} onChange={(e) => setCambioForm({ ...cambioForm, motivo: e.target.value })} placeholder="Motivo del cambio" />
              </div>
            </div>

            <div style={{ marginBottom: 8 }}><label>Productos de reemplazo</label></div>
            {reemplazos.map((x, i) => (
              <div key={i} style={{ display: "flex", gap: 10, marginBottom: 8, flexWrap: "wrap" }}>
                <div style={{ flex: 2, minWidth: 200 }}>
                  <select required value={x.producto_id} onChange={(e) => setReemplazos((prev) => prev.map((r, idx) => idx === i ? { ...r, producto_id: e.target.value } : r))}>
                    <option value="">Producto...</option>
                    {productos.map((p) => <option key={p.id} value={p.id}>{p.nombre}</option>)}
                  </select>
                </div>
                <div><label>Cantidad</label><input type="number" min="1" value={x.cantidad} onChange={(e) => setReemplazos((prev) => prev.map((r, idx) => idx === i ? { ...r, cantidad: e.target.value } : r))} /></div>
                {reemplazos.length > 1 && (
                  <button type="button" className="btn btn-danger" onClick={() => setReemplazos(reemplazos.filter((_, x2) => x2 !== i))}>×</button>
                )}
              </div>
            ))}
            <div style={{ display: "flex", gap: 8 }}>
              <button type="button" className="btn btn-secondary" onClick={() => setReemplazos([...reemplazos, { producto_id: "", cantidad: 1 }])}>+ Línea</button>
              <button className="btn" type="submit">Registrar cambio</button>
            </div>
          </form>

          <h2 style={{ fontSize: 16, marginBottom: 10 }}>Devoluciones registradas</h2>
          <table className="table">
            <thead>
              <tr><th>N° Nota</th><th>Venta</th><th>Fecha</th><th>Tipo</th><th>Estado</th><th>Reembolso</th><th>Total</th><th></th></tr>
            </thead>
            <tbody>
              {devoluciones.map((d) => (
                <tr key={d.id}>
                  <td><b>{d.numero_nota}</b></td>
                  <td>#{d.venta_id}</td>
                  <td>{d.created_at ? new Date(d.created_at).toLocaleString() : "—"}</td>
                  <td><span className="badge">{d.tipo}</span></td>
                  <td><span className={`badge ${d.estado === "aplicada" ? "badge-success" : "badge-warning"}`}>{d.estado}</span></td>
                  <td>{d.reembolso_medio || "—"}</td>
                  <td><strong>{formatMoney(d.total_devolucion)}</strong></td>
                  <td><button className="btn btn-secondary" onClick={() => verDetalleDev(d.id)}>Detalle</button></td>
                </tr>
              ))}
              {devoluciones.length === 0 && <tr><td colSpan={8} className="muted" style={{ textAlign: "center", padding: 20 }}>Sin devoluciones registradas</td></tr>}
            </tbody>
          </table>
        </>
      )}

      {detDev && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,.45)", display: "grid", placeItems: "center", zIndex: 1100, padding: 20 }}>
          <div className="card" style={{ width: "min(620px, 100%)" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
              <h3>Devolución {detDev.numero_nota} · venta #{detDev.venta_id}</h3>
              <button className="btn btn-ghost" onClick={() => setDetDev(null)}>✕</button>
            </div>
            <p className="muted">
              Estado: <strong>{detDev.estado}</strong> · Tipo: {detDev.tipo} · Reembolso: {detDev.reembolso_medio || "—"} · Total: <strong>{formatMoney(detDev.total_devolucion)}</strong>
            </p>
            {detDev.motivo && <p className="muted">Motivo: {detDev.motivo}</p>}
            <table className="table" style={{ marginTop: 10 }}>
              <thead><tr><th>Producto</th><th>Cantidad</th><th>Precio</th><th>Subtotal</th></tr></thead>
              <tbody>
                {detDev.detalle.map((d) => (
                  <tr key={d.id}>
                    <td>#{d.producto_id}</td>
                    <td>{d.cantidad}</td>
                    <td>{formatMoney(d.precio)}</td>
                    <td>{formatMoney(d.subtotal)}</td>
                  </tr>
                ))}
                {detDev.detalle.length === 0 && <tr><td colSpan={4} className="muted" style={{ textAlign: "center" }}>Sin detalle</td></tr>}
              </tbody>
            </table>
          </div>
        </div>
      )}
    {detVenta && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,.45)", display: "grid", placeItems: "center", zIndex: 1100, padding: 20 }}>
          <div className="card" style={{ width: "min(680px, 100%)" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
              <h3>Venta {detVenta.numero}</h3>
              <button className="btn btn-ghost" onClick={() => setDetVenta(null)}>✕</button>
            </div>
            <p className="muted">
              {detVenta.created_at ? new Date(detVenta.created_at).toLocaleString() : "—"} · <b>{detVenta.tipo}</b> · <span className={`badge ${detVenta.estado === "completada" ? "badge-success" : "badge-warning"}`}>{detVenta.estado}</span>
              {detVenta.tipo === "credito" && <> · Saldo: <strong>{formatMoney(detVenta.saldo)}</strong></>}
            </p>
            <table className="table" style={{ marginTop: 10 }}>
              <thead><tr><th>Producto</th><th>Cantidad</th><th>Precio</th><th>Desc.</th><th>Subtotal</th></tr></thead>
              <tbody>
                {detVenta.detalle.map((d, i) => (
                  <tr key={i}>
                    <td>#{d.producto_id}</td>
                    <td>{d.cantidad}</td>
                    <td>{formatMoney(d.precio)}</td>
                    <td>{d.descuento ? formatMoney(d.descuento) : "—"}</td>
                    <td>{formatMoney(d.subtotal)}</td>
                  </tr>
                ))}
                {detVenta.detalle.length === 0 && <tr><td colSpan={5} className="muted" style={{ textAlign: "center" }}>Sin detalle</td></tr>}
              </tbody>
            </table>
            <div style={{ display: "flex", justifyContent: "flex-end", gap: 10, marginTop: 8 }}>
              <span className="muted">Subtotal {formatMoney(detVenta.subtotal)}</span>
              <span className="muted">Impuesto {formatMoney(detVenta.impuesto)}</span>
              <strong>Total {formatMoney(detVenta.total)}</strong>
            </div>
            {detVenta.pagos && detVenta.pagos.length > 0 && (
              <table className="table" style={{ marginTop: 10 }}>
                <thead><tr><th>Fecha</th><th>Medio</th><th>Monto</th><th>Referencia</th></tr></thead>
                <tbody>
                  {detVenta.pagos.map((p, i) => (
                    <tr key={i}>
                      <td>{p.created_at ? new Date(p.created_at).toLocaleString() : "—"}</td>
                      <td>{p.medio}</td>
                      <td>{formatMoney(p.monto)}</td>
                      <td>{p.referencia || "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
            {detVenta.estado === "completada" && detVenta.tipo === "credito" && Number(detVenta.saldo || 0) > 0 && (
              <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 10 }}>
                <button className="btn btn-primary" onClick={() => { abonar(detVenta); }}>Registrar abono</button>
              </div>
            )}
          </div>
        </div>
      )}

    </div>
  );
}