import { useEffect, useState } from "react";
import api from "../api.js";
import { formatMoney } from "../components/ui.jsx";

export default function Offline() {
  const [online, setOnline] = useState(navigator.onLine);
  const [catalogo, setCatalogo] = useState(null);
  const [pendientes, setPendientes] = useState([]);
  const [novedades, setNovedades] = useState(null);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [of, setOf] = useState({ cliente_id: "", producto_id: "", cantidad: 1, medio: "efectivo", monto: "" });

  function checkOnline() {
    setOnline(navigator.onLine);
  }

  function loadPendientes() {
    api("/offline/pendientes").then(setPendientes).catch(() => {});
  }

  useEffect(() => {
    window.addEventListener("online", checkOnline);
    window.addEventListener("offline", checkOnline);
    const cat = localStorage.getItem("catalogo_offline");
    if (cat) setCatalogo(JSON.parse(cat));
    loadPendientes();
    return () => {
      window.removeEventListener("online", checkOnline);
      window.removeEventListener("offline", checkOnline);
    };
  }, []);

  async function descargarCatalogo() {
    setError("");
    setSuccess("");
    try {
      const cat = await api("/offline/catalogo");
      localStorage.setItem("catalogo_offline", JSON.stringify(cat));
      setCatalogo(cat);
      setSuccess(`Catálogo descargado (${cat.productos.length} productos, ${cat.clientes.length} clientes). Listo para operar sin conexión.`);
    } catch (err) {
      setError(err.message);
    }
  }

  function calcularTotal() {
    if (!catalogo) return 0;
    const p = catalogo.productos.find((x) => x.id === Number(of.producto_id));
    if (!p) return 0;
    return Number(p.precio_venta) * Number(of.cantidad || 0);
  }

  async function crearVentaOffline(e) {
    e.preventDefault();
    setError("");
    setSuccess("");
    const p = catalogo?.productos.find((x) => x.id === Number(of.producto_id));
    if (!p) {
      setError("Selecciona un producto del catálogo descargado");
      return;
    }
    const total = calcularTotal();
    try {
      const res = await api("/offline/pendientes", {
        method: "POST",
        body: JSON.stringify({
          cliente_uuid: `off-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`,
          tipo: "venta",
          payload: {
            empresa_id: 1,
            sucursal_id: 1,
            caja_id: 1,
            cliente_id: of.cliente_id ? Number(of.cliente_id) : null,
            tipo: "contado",
            descuento_global: 0,
            propina: 0,
            nota: "registrada offline (pendiente de sincronizar)",
            detalle: [{ producto_id: p.id, cantidad: Number(of.cantidad), precio: Number(p.precio_venta) }],
            pagos: [{ medio: of.medio, monto: of.monto ? Number(of.monto) : total }],
          },
        }),
      });
      setSuccess(`Venta offline encolada (#${res.id}). Se aplicará al sincronizar.`);
      loadPendientes();
      setOf({ cliente_id: "", producto_id: "", cantidad: 1, medio: "efectivo", monto: "" });
    } catch (err) {
      setError(err.message);
    }
  }

  async function sincronizar() {
    setError("");
    setSuccess("");
    try {
      const res = await api("/offline/sincronizar", { method: "POST" });
      setSuccess(
        res.procesadas
          ? `${res.procesadas} operación(es) sincronizada(s): ${res.sincronizadas.map((s) => s.resultado?.numero || s.tipo).join(", ")}`
          : res.errores
            ? `${res.errores} operación(es) con error`
            : "No hay operaciones pendientes por sincronizar"
      );
      loadPendientes();
    } catch (err) {
      setError(err.message);
    }
  }

  async function verNovedades() {
    setError("");
    try {
      const desde = new Date(Date.now() - 24 * 3600 * 1000).toISOString();
      const d = await api(`/offline/novedades?desde=${encodeURIComponent(desde)}`);
      setNovedades(d);
    } catch (err) {
      setError(err.message);
    }
  }

  async function sincronizarUno(id) {
    setError("");
    setSuccess("");
    try {
      const res = await api(`/offline/pendientes/${id}/sincronizar`, { method: "POST" });
      setSuccess(res.venta_id ? `Pendiente #${id} sincronizado → venta V-${String(res.venta_id).padStart(6, "0")}` : `Pendiente #${id} sincronizado`);
      loadPendientes();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div className="page" style={{ padding: 16 }}>
      <div className="page-header">
        <h1 style={{ fontSize: 20 }}>
          Operación offline & sincronización
        </h1>
        <span className={online ? "badge badge-success" : "badge badge-danger"}>
          {online ? "● En línea" : "● Sin conexión"}
        </span>
      </div>

      {!online && (
        <div className="error" style={{ marginBottom: 12 }}>
          Estás desconectado. Las ventas que registres aquí quedarán en la cola y se aplicarán cuando vuelva la conexión.
        </div>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: 18 }}>
        <div className="card sec">
          <h3 className="card-title">Catálogo para offline</h3>
          {catalogo ? (
            <p className="muted">
              {catalogo.productos.length} productos · {catalogo.clientes.length} clientes (guardado en el navegador)
            </p>
          ) : (
            <p className="muted">Aún no hay catálogo descargado.</p>
          )}
          <button className="btn btn-primary" style={{ marginTop: 10 }} onClick={descargarCatalogo}>
            {catalogo ? "⟳ Redescargar catálogo" : "Descargar catálogo"}
          </button>
        </div>

        <div className="card sec">
          <h3 className="card-title">Venta sin conexión</h3>
          <form onSubmit={crearVentaOffline}>
            <div className="grid2">
              <div>
                <label>Cliente</label>
                <select value={of.cliente_id} onChange={(e) => setOf({ ...of, cliente_id: e.target.value })}>
                  <option value="">Ocasional</option>
                  {(catalogo?.clientes || []).map((c) => (
                    <option key={c.id} value={c.id}>{c.nombre}</option>
                  ))}
                </select>
              </div>
              <div>
                <label>Producto</label>
                <select required value={of.producto_id} onChange={(e) => setOf({ ...of, producto_id: e.target.value })}>
                  <option value="">Selecciona...</option>
                  {(catalogo?.productos || []).map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.nombre} · disp {p.existencias} · {formatMoney(p.precio_venta)}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            <div className="grid2">
              <div>
                <label>Cantidad</label>
                <input type="number" min="0.001" step="0.001" required value={of.cantidad} onChange={(e) => setOf({ ...of, cantidad: e.target.value })} />
              </div>
              <div>
                <label>Medio de pago</label>
                <select value={of.medio} onChange={(e) => setOf({ ...of, medio: e.target.value })}>
                  {["efectivo", "tarjeta", "transferencia", "QR", "nequi", "daviplata", "breb", "otro"].map((m) => (
                    <option key={m} value={m}>{m}</option>
                  ))}
                </select>
              </div>
            </div>
            <div>
              <label>Monto pagado</label>
              <input type="number" step="0.01" placeholder={formatMoney(calcularTotal())} value={of.monto} onChange={(e) => setOf({ ...of, monto: e.target.value })} />
            </div>
            <button className="btn btn-primary" style={{ width: "100%", marginTop: 10 }} disabled={!catalogo}>
              Encolar venta ({formatMoney(of.monto ? Number(of.monto) : calcularTotal())})
            </button>
          </form>
        </div>

        <div className="card sec">
          <h3 className="card-title">Cola de sincronización</h3>
          <div style={{ display: "flex", gap: 10, marginBottom: 10 }}>
            <button className="btn btn-primary" onClick={sincronizar}>⟳ Sincronizar ahora</button>
            <button className="btn btn-secondary" onClick={verNovedades}>Novedades 24h</button>
          </div>
          {error && <div className="error">{error}</div>}
          {success && <div className="badge-success" style={{ display: "block", padding: 8, borderRadius: 6, marginBottom: 10 }}>{success}</div>}
          <table className="table">
            <thead><tr><th>#</th><th>Tipo</th><th>Estado</th><th>Resultado</th><th></th></tr></thead>
            <tbody>
              {pendientes.map((p) => (
                <tr key={p.id}>
                  <td>{p.id}</td>
                  <td>{p.tipo}</td>
                  <td>
                    {p.estado === "sincronizada" ? <span className="badge badge-success">sincronizada</span>
                      : p.estado === "error" ? <span className="badge badge-danger">error</span>
                      : <span className="badge badge-warning">{p.estado}</span>}
                    {p.error && <span className="muted" title={p.error}> ⚠</span>}
                  </td>
                  <td>{p.estado === "sincronizada" ? `V-${String(p.resultado_id).padStart(6, "0")}` : "—"}</td>
                  <td>{p.estado === "pendiente" && (
                    <button className="btn btn-sm" onClick={() => sincronizarUno(p.id)}>Sincronizar</button>
                  )}</td>
                </tr>
              ))}
              {!pendientes.length && <tr><td colSpan={5} className="muted" style={{ textAlign: "center", padding: 16 }}>Sin operaciones pendientes</td></tr>}
            </tbody>
          </table>
          {novedades && (
            <div style={{ marginTop: 10 }}>
              <h4 style={{ fontSize: 13, marginBottom: 6 }}>Novedades desde {novedades.desde}</h4>
              <p className="muted">{novedades.ventas_nuevas.length} ventas nuevas · {novedades.sincronizaciones.length} sincronizaciones</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}