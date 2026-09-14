import { useEffect, useState } from "react";
import api, { downloadFile } from "../api.js";
import { KpiCard, ChartCard, Donut, TrendChart, ProgressList, formatMoney } from "../components/ui.jsx";

function StatCard({ label, value }) {
  return (
    <div className="kpi">
      <div className="kpi-icon" style={{ "--accent-soft": "rgba(99,102,241,.12)", background: "rgba(99,102,241,.12)" }}>📊</div>
      <div className="kpi-body">
        <div className="kpi-label">{label}</div>
        <div className="kpi-value">{value}</div>
      </div>
    </div>
  );
}

function aFilas(data) {
  if (!data) return [];
  if (Array.isArray(data)) return data;
  if (typeof data === "object") {
    const arrKey = Object.keys(data).find((k) => Array.isArray(data[k]));
    if (arrKey) return data[arrKey];
    return Object.entries(data).map(([k, v]) => ({
      campo: k,
      valor: Array.isArray(v) ? `${v.length} registros` : typeof v === "object" && v ? JSON.stringify(v) : v,
    }));
  }
  return [];
}

function TablaGenerica({ data }) {
  const filas = aFilas(data);
  if (filas.length === 0) {
    return <p className="muted" style={{ fontSize: 13 }}>Sin datos</p>;
  }
  const keys = Object.keys(filas[0]);
  const etiqueta = (k) => (k === "campo" ? "Concepto" : k === "valor" ? "Valor" : k);
  const valor = (r, k) => {
    const v = r[k];
    if (v == null) return "—";
    if (typeof v === "number" && !Number.isInteger(v) && /precio|total|subtotal|valor/i.test(k)) {
      return new Intl.NumberFormat("es-CO", { style: "currency", currency: "COP" }).format(v);
    }
    if (/fecha|inicio|cierre|created_at|createdAt/i.test(k) && String(v).includes("T")) {
      try {
        const d = new Date(v);
        if (!Number.isNaN(d.getTime())) return d.toLocaleString();
      } catch (e) {
        /* noop */
      }
    }
    return String(v);
  };
  return (
    <table className="table">
      <thead>
        <tr>{keys.map((k) => <th key={k}>{etiqueta(k)}</th>)}</tr>
      </thead>
      <tbody>
        {filas.map((r, i) => (
          <tr key={i}>{keys.map((k) => <td key={k}>{valor(r, k)}</td>)}</tr>
        ))}
      </tbody>
    </table>
  );
}

function Seccion({ titulo, children, acciones }) {
  return (
    <div style={{ marginBottom: 24 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10, flexWrap: "wrap", gap: 8 }}>
        <h2 style={{ fontSize: 16 }}>{titulo}</h2>
        {acciones}
      </div>
      {children}
    </div>
  );
}

export default function Reportes() {
  const [tab, setTab] = useState("principales");
  const [ventas, setVentas] = useState(null);
  const [top, setTop] = useState([]);
  const [agotados, setAgotados] = useState([]);
  const [compras, setCompras] = useState(null);
  const [resultados, setResultados] = useState(null);
  const [cartera, setCartera] = useState(null);
  const [sugeridas, setSugeridas] = useState([]);
  const [alertas, setAlertas] = useState(null);
  const [vendedores, setVendedores] = useState([]);
  const [auditoria, setAuditoria] = useState([]);
  const [vSucursal, setVSucursal] = useState([]);
  const [vCaja, setVCaja] = useState([]);
  const [vCliente, setVCliente] = useState([]);
  const [vCategoria, setVCategoria] = useState([]);
  const [vMarca, setVMarca] = useState([]);
  const [vHora, setVHora] = useState([]);
  const [vMes, setVMes] = useState([]);
  const [vAno, setVAno] = useState([]);
  const [proveedores, setProveedores] = useState([]);
  const [pronostico, setPronostico] = useState([]);
  const [error, setError] = useState("");
  const [menosVendidos, setMenosVendidos] = useState([]);
  const [sinMovimiento, setSinMovimiento] = useState([]);
  const [masRentables, setMasRentables] = useState([]);
  const [cliAnalitica, setCliAnalitica] = useState(null);
  const [flujo, setFlujo] = useState(null);
  const [comprasPeriodo, setComprasPeriodo] = useState([]);
  const [comprasPorProveedor, setComprasPorProveedor] = useState([]);
  const [comprasPorProducto, setComprasPorProducto] = useState([]);
  const [comprasPendientes, setComprasPendientes] = useState([]);
  const [comprasRecibidas, setComprasRecibidas] = useState([]);
  const [comprasAnuladas, setComprasAnuladas] = useState([]);
  const [rotacion, setRotacion] = useState([]);
  const [rotDias, setRotDias] = useState(90);
  const [invCategoria, setInvCategoria] = useState([]);
  const [diferencias, setDiferencias] = useState([]);
  const [cajaResumen, setCajaResumen] = useState([]);
  const [vCajero, setVCajero] = useState([]);
  const [vTurno, setVTurno] = useState([]);
  const [porVencer, setPorVencer] = useState([]);
  const [lotesEtiquetas, setLotesEtiquetas] = useState([]);
  const [comprasXSucursal, setComprasXSucursal] = useState([]);
  const [invXBodega, setInvXBodega] = useState([]);
  const [invXSucursal, setInvXSucursal] = useState([]);
  const [proveedoresPpal, setProveedoresPpal] = useState([]);
  const [productosXProveedor, setProductosXProveedor] = useState([]);
  const [provSel, setProvSel] = useState("");
  const [provCat, setProvCat] = useState([]);
  const [provHist, setProvHist] = useState(null);

  useEffect(() => {
    if (tab === "proveedores") {
      api("/reportes/proveedores").then(setProveedores).catch(() => {});
      api("/reportes/proveedores-principales?limite=10").then(setProveedoresPpal).catch(() => {});
      api("/reportes/productos-por-proveedor").then(setProductosXProveedor).catch(() => {});
      setProvSel("");
      setProvCat([]);
      setProvHist(null);
    }
    if (tab === "pronostico") api("/reportes/pronostico?dias=7").then(setPronostico).catch(() => {});
    if (tab === "clientes") api("/reportes/clientes-analitica").then(setCliAnalitica).catch(() => {});
    if (tab === "financiero") api("/reportes/flujo-caja").then(setFlujo).catch(() => {});
    if (tab === "desglose") {
      api("/reportes/productos-menos-vendidos").then(setMenosVendidos).catch(() => {});
      api("/reportes/productos-sin-movimiento").then(setSinMovimiento).catch(() => {});
      api("/reportes/productos-mas-rentables").then(setMasRentables).catch(() => {});
    }
    if (tab === "compras") {
      api("/reportes/compras-periodo").then(setComprasPeriodo).catch(() => {});
      api("/reportes/compras-por-proveedor").then(setComprasPorProveedor).catch(() => {});
      api("/reportes/compras-por-producto").then(setComprasPorProducto).catch(() => {});
      api("/reportes/compras-pendientes").then(setComprasPendientes).catch(() => {});
      api("/reportes/compras-recibidas").then(setComprasRecibidas).catch(() => {});
      api("/reportes/compras-anuladas").then(setComprasAnuladas).catch(() => {});
      api("/reportes/compras-por-sucursal").then(setComprasXSucursal).catch(() => {});
    }
    if (tab === "inventario") {
      cargarRotacion();
      api("/reportes/inventario-por-categoria").then(setInvCategoria).catch(() => {});
      api("/reportes/diferencias-inventario").then(setDiferencias).catch(() => {});
      api("/reportes/inventario-por-bodega").then(setInvXBodega).catch(() => {});
      api("/reportes/inventario-por-sucursal").then(setInvXSucursal).catch(() => {});
    }
    if (tab === "caja") {
      api("/reportes/caja?limite=20").then(setCajaResumen).catch(() => {});
      api("/reportes/ventas-por-cajero").then(setVCajero).catch(() => {});
      api("/reportes/ventas-por-turno").then(setVTurno).catch(() => {});
    }
    if (tab === "vencimientos") {
      api("/reportes/por-vencer").then(setPorVencer).catch(() => {});
      api("/reportes/lotes-etiquetas").then(setLotesEtiquetas).catch(() => {});
    }
  }, [tab, rotDias]);

  function cargarRotacion() {
    api(`/reportes/rotacion?dias=${rotDias}`).then(setRotacion).catch(() => {});
  }

  function cargarProvSel(id) {
    setProvSel(id);
    if (!id) {
      setProvCat([]);
      setProvHist(null);
      return;
    }
    api(`/reportes/precios-proveedor/${id}`).then(setProvCat).catch(() => setProvCat([]));
    api(`/reportes/proveedores-historial/${id}`).then(setProvHist).catch(() => setProvHist(null));
  }

  useEffect(() => {
    api("/reportes/ventas").then(setVentas).catch(() => {});
    api("/reportes/ventas-por-producto").then(setTop).catch(() => {});
    api("/reportes/productos-agotados").then(setAgotados).catch(() => {});
    api("/reportes/compras").then(setCompras).catch(() => {});
    api("/reportes/estado-resultados").then(setResultados).catch(() => {});
    api("/reportes/cartera").then(setCartera).catch(() => {});
    api("/reportes/compras-sugeridas").then(setSugeridas).catch(() => {});
    api("/reportes/alertas").then(setAlertas).catch(() => {});
    api("/reportes/vendedores").then(setVendedores).catch(() => {});
    api("/reportes/auditoria").then(setAuditoria).catch(() => {});
    api("/reportes/ventas-por-sucursal").then(setVSucursal).catch(() => {});
    api("/reportes/ventas-por-caja").then(setVCaja).catch(() => {});
    api("/reportes/ventas-por-cliente").then(setVCliente).catch(() => {});
    api("/reportes/ventas-por-categoria").then(setVCategoria).catch(() => {});
    api("/reportes/ventas-por-marca").then(setVMarca).catch(() => {});
    api("/reportes/ventas-por-hora").then(setVHora).catch(() => {});
    api("/reportes/ventas-por-mes").then(setVMes).catch(() => {});
    api("/reportes/ventas-por-ano").then(setVAno).catch(() => {});
  }, []);

  const tablaDesglose = (data, nombreKey, color = "var(--red)") => {
    const total = data.reduce((s, r) => s + r.ventas, 0);
    const max = Math.max(1, ...data.map((r) => r.ventas));
    return (
      <table className="table">
        <thead>
          <tr><th>{nombreKey}</th><th>Ventas</th><th>Transacciones</th><th style={{ width: "34%" }}>Participación</th></tr>
        </thead>
        <tbody>
          {data.map((r, i) => (
            <tr key={i}>
              <td><strong>{r[nombreKey]}</strong></td>
              <td>{formatMoney(r.ventas)}</td>
              <td>{r.transacciones}</td>
              <td>
                <div className="prog-track">
                  <div className="prog-fill" style={{ width: `${(r.ventas / max) * 100}%`, background: color }} />
                </div>
                <span className="muted">{total ? ((r.ventas / total) * 100).toFixed(1) : "0.0"}%</span>
              </td>
            </tr>
          ))}
          {data.length === 0 && <tr><td colSpan={4} className="muted" style={{ textAlign: "center", padding: 20 }}>Sin datos</td></tr>}
        </tbody>
      </table>
    );
  };

  const tablaDetalle = (data, nombreKey) => (
    <table className="table">
      <thead>
        <tr><th>{nombreKey}</th><th>Cantidad</th><th>Total</th></tr>
      </thead>
      <tbody>
        {data.map((r, i) => (
          <tr key={i}>
            <td><strong>{r[nombreKey]}</strong></td>
            <td>{r.cantidad}</td>
            <td>{formatMoney(r.total)}</td>
          </tr>
        ))}
        {data.length === 0 && <tr><td colSpan={3} className="muted" style={{ textAlign: "center", padding: 20 }}>Sin datos</td></tr>}
      </tbody>
    </table>
  );

  return (
    <div className="page">
      <div className="page-header">
        <h1>Reportes y análisis</h1>
        <div className="tabs">
          {["principales", "desglose", "financiero", "clientes", "compras", "inventario", "caja", "vencimientos", "sugeridas", "pronostico", "proveedores", "alertas", "vendedores", "auditoria"].map((t) => (
            <button key={t} className={`btn ${tab === t ? "btn-primary" : ""}`} onClick={() => setTab(t)}>
              {t === "principales" ? "Principales" : t === "desglose" ? "Ventas por..." : t === "financiero" ? "Financiero" : t === "clientes" ? "Clientes" : t === "compras" ? "Compras" : t === "inventario" ? "Inventario" : t === "caja" ? "Caja" : t === "vencimientos" ? "Vencimientos" : t === "sugeridas" ? "Compras sugeridas" : t === "pronostico" ? "Pronóstico" : t === "proveedores" ? "Proveedores" : t === "alertas" ? "Alertas" : t === "vendedores" ? "Vendedores" : "Auditoría"}
            </button>
          ))}
        </div>
      </div>

      {error && <div className="error">{error}</div>}

      <div className="chip" style={{ marginBottom: 16, display: "inline-block" }}>
        Exportar:{" "}
        <button className="btn btn-secondary" style={{ marginLeft: 6 }} onClick={() => downloadFile("/reportes/exportar/ventas-por-producto?formato=xls", "ventas-por-producto.xls").catch((e) => setError(e.message))}>Ventas por producto (XLS)</button>{" "}
        <button className="btn btn-secondary" onClick={() => downloadFile("/reportes/exportar/ventas-por-producto?formato=pdf", "ventas-por-producto.pdf").catch((e) => setError(e.message))}>Ventas por producto (PDF)</button>{" "}
        <button className="btn btn-secondary" onClick={() => downloadFile("/reportes/exportar/ventas?formato=xls", "ventas.xls").catch((e) => setError(e.message))}>Ventas (XLS)</button>
      </div>

      {tab === "proveedores" && (
        <table className="table">
          <thead>
            <tr><th>Proveedor</th><th>N° compras</th><th>Total compras</th><th>Deuda</th></tr>
          </thead>
          <tbody>
            {proveedores.map((p, i) => (
              <tr key={i}>
                <td><strong>{p.proveedor || p.nombre}</strong></td>
                <td>{p.numero_compras || p.compras}</td>
                <td>{formatMoney(p.total_compras)}</td>
                <td>{formatMoney(p.deuda || 0)}</td>
              </tr>
            ))}
            {proveedores.length === 0 && <tr><td colSpan={4} className="muted" style={{ textAlign: "center", padding: 20 }}>Sin proveedores con compras</td></tr>}
          </tbody>
        </table>
      )}

      {tab === "proveedores" && (
        <>
          <h3 style={{ fontSize: 15, margin: "0 0 10px" }}>Proveedores principales</h3>
          <table className="table">
            <thead><tr><th>#</th><th>Proveedor</th><th>Total compras</th><th>N° compras</th></tr></thead>
            <tbody>
              {proveedoresPpal.map((p, i) => (
                <tr key={i}>
                  <td className="muted">{i + 1}</td>
                  <td><strong>{p.proveedor}</strong></td>
                  <td>{formatMoney(p.total_compras)}</td>
                  <td>{p.numero_compras}</td>
                </tr>
              ))}
              {proveedoresPpal.length === 0 && <tr><td colSpan={4} className="muted" style={{ textAlign: "center", padding: 20 }}>Sin datos</td></tr>}
            </tbody>
          </table>
        </>
      )}

      {tab === "proveedores" && (
        <>
          <h3 style={{ fontSize: 15, margin: "0 0 10px" }}>Productos por proveedor (último costo)</h3>
          <table className="table">
            <thead><tr><th>Producto</th><th>Proveedor</th><th>Cantidad comprada</th><th>Último costo</th></tr></thead>
            <tbody>
              {productosXProveedor.map((r, i) => (
                <tr key={i}>
                  <td><strong>{r.producto}</strong></td>
                  <td>{r.proveedor}</td>
                  <td>{r.cantidad}</td>
                  <td>{formatMoney(r.ultimo_costo)}</td>
                </tr>
              ))}
              {productosXProveedor.length === 0 && <tr><td colSpan={4} className="muted" style={{ textAlign: "center", padding: 20 }}>Sin datos</td></tr>}
            </tbody>
          </table>
        </>
      )}

      {tab === "proveedores" && (
        <>
          <h3 style={{ fontSize: 15, margin: "0 0 10px" }}>Consulta por proveedor</h3>
          <select className="input" style={{ maxWidth: 360 }} value={provSel} onChange={(e) => cargarProvSel(e.target.value)}>
            <option value="">— Seleccionar proveedor —</option>
            {proveedores.map((p, i) => (
              <option key={i} value={p.proveedor_id}>{p.proveedor || p.nombre}</option>
            ))}
          </select>
          {provCat.length > 0 && (
            <>
              <h4 style={{ fontSize: 13.5, margin: "14px 0 6px" }}>Catálogo de precios ofrecidos</h4>
              <table className="table">
                <thead><tr><th>Producto</th><th>Último costo</th><th>Cantidad total</th></tr></thead>
                <tbody>
                  {provCat.map((r, i) => (
                    <tr key={i}>
                      <td><strong>{r.producto}</strong></td>
                      <td>{formatMoney(r.ultimo_costo)}</td>
                      <td>{r.cantidad_total}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}
          {provHist && (
            <>
              <div className="chip" style={{ display: "inline-flex", gap: 12, marginTop: 14 }}>
                <span>Total compras: <strong>{formatMoney(provHist.total_compras)}</strong></span>
                <span>N° compras: <strong>{provHist.numero_compras}</strong></span>
                <span>Deuda pendiente: <strong style={{ color: "var(--red)" }}>{formatMoney(provHist.deuda_pendiente)}</strong></span>
              </div>
              <h4 style={{ fontSize: 13.5, margin: "14px 0 6px" }}>Historial de compras</h4>
              <table className="table">
                <thead><tr><th>N°</th><th>Fecha</th><th>Estado</th><th>Subtotal</th><th>Total</th></tr></thead>
                <tbody>
                  {provHist.historial.map((c) => (
                    <tr key={c.compra_id}>
                      <td>#{c.numero}</td>
                      <td style={{ fontSize: 12 }}>{c.fecha}</td>
                      <td><span className={`badge ${c.estado === "recibida" ? "badge-success" : c.estado === "anulada" ? "badge-danger" : "badge-warning"}`}>{c.estado}</span></td>
                      <td>{formatMoney(c.subtotal)}</td>
                      <td>{formatMoney(c.total)}</td>
                    </tr>
                  ))}
                  {provHist.historial.length === 0 && <tr><td colSpan={5} className="muted" style={{ textAlign: "center", padding: 20 }}>Sin compras</td></tr>}
                </tbody>
              </table>
            </>
          )}
        </>
      )}

      {tab === "pronostico" && (
        <>
          <p className="muted" style={{ marginBottom: 12 }}>Proyección de ventas a 7 días basada en el promedio de los últimos 30 días.</p>
          <table className="table">
            <thead>
              <tr><th>Producto</th><th>Promedio diario</th><th>Días cubiertos</th><th>Pronóstico 7 días</th><th>Existencias</th></tr>
            </thead>
            <tbody>
              {pronostico.map((p, i) => (
                <tr key={i}>
                  <td><strong>{p.producto}</strong></td>
                  <td>{p.promedio_diario != null ? p.promedio_diario.toFixed(2) : "—"}</td>
                  <td>{p.dias}</td>
                  <td>{p.pronostico != null ? p.pronostico.toFixed(2) : "—"}</td>
                  <td>{p.existencias != null ? p.existencias : "—"}</td>
                </tr>
              ))}
              {pronostico.length === 0 && <tr><td colSpan={5} className="muted" style={{ textAlign: "center", padding: 20 }}>Sin datos suficientes para pronosticar</td></tr>}
            </tbody>
          </table>
        </>
      )}

      {tab === "desglose" && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(330px, 1fr))", gap: 18 }}>
          <div className="card sec">
            <h3 className="card-title">Ventas por sucursal</h3>
            {tablaDesglose(vSucursal, "sucursal")}
          </div>
          <div className="card sec">
            <h3 className="card-title">Ventas por caja</h3>
            {tablaDesglose(vCaja, "caja", "var(--red)")}
          </div>
          <div className="card sec">
            <h3 className="card-title">Ventas por cajero</h3>
            <table className="table">
              <thead><tr><th>Cajero</th><th>Ventas</th><th>%</th></tr></thead>
              <tbody>
                {ventas && Object.entries(ventas.por_cajero || {}).map(([k, v], i) => (
                  <tr key={i}><td><strong>{k}</strong></td><td>{formatMoney(v)}</td><td className="muted">{((v / (ventas.total_ventas || 1)) * 100).toFixed(1)}%</td></tr>
                ))}
                {(!ventas || !Object.keys(ventas.por_cajero || {}).length) && <tr><td colSpan={3} className="muted" style={{ textAlign: "center", padding: 20 }}>Sin datos</td></tr>}
              </tbody>
            </table>
          </div>
          <div className="card sec">
            <h3 className="card-title">Ventas por cliente</h3>
            {tablaDesglose(vCliente, "cliente", "var(--red)")}
          </div>
          <div className="card sec">
            <h3 className="card-title">Ventas por categoría</h3>
            {tablaDetalle(vCategoria, "categoria")}
          </div>
          <div className="card sec">
            <h3 className="card-title">Ventas por marca</h3>
            {tablaDetalle(vMarca, "marca")}
          </div>
        </div>
      )}

      {tab === "desglose" && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(330px, 1fr))", gap: 18, marginTop: 18 }}>
          <div className="card sec">
            <h3 className="card-title">Productos menos vendidos</h3>
            <table className="table">
              <thead><tr><th>Producto</th><th>Cantidad</th><th>Total</th></tr></thead>
              <tbody>
                {menosVendidos.map((r, i) => (
                  <tr key={i}><td><strong>{r.producto}</strong></td><td>{r.cantidad}</td><td>{formatMoney(r.total)}</td></tr>
                ))}
                {!menosVendidos.length && <tr><td colSpan={3} className="muted" style={{ textAlign: "center", padding: 16 }}>Sin datos</td></tr>}
              </tbody>
            </table>
          </div>
          <div className="card sec">
            <h3 className="card-title">Productos sin movimiento (30 días)</h3>
            <table className="table">
              <thead><tr><th>Producto</th><th>Existencias</th></tr></thead>
              <tbody>
                {sinMovimiento.map((r, i) => (
                  <tr key={i}><td><strong>{r.producto}</strong></td><td><span className="badge badge-warning">{r.existencias}</span></td></tr>
                ))}
                {!sinMovimiento.length && <tr><td colSpan={2} className="muted" style={{ textAlign: "center", padding: 16 }}>Sin datos</td></tr>}
              </tbody>
            </table>
          </div>
          <div className="card sec">
            <h3 className="card-title">Productos más rentables</h3>
            <table className="table">
              <thead><tr><th>Producto</th><th>Total</th><th>Utilidad</th><th>Margen</th></tr></thead>
              <tbody>
                {masRentables.map((r, i) => (
                  <tr key={i}>
                    <td><strong>{r.producto}</strong></td>
                    <td>{formatMoney(r.total)}</td>
                    <td style={{ color: "#059669", fontWeight: 600 }}>{formatMoney(r.utilidad)}</td>
                    <td>{r.margen}%</td>
                  </tr>
                ))}
                {!masRentables.length && <tr><td colSpan={4} className="muted" style={{ textAlign: "center", padding: 16 }}>Sin datos</td></tr>}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === "desglose" && vHora.length > 0 && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(330px, 1fr))", gap: 18, marginTop: 18 }}>
          <div className="card sec">
            <h3 className="card-title">Ventas por hora del día</h3>
            <div className="prog-track" style={{ height: 180, display: "flex", alignItems: "flex-end", gap: 4, padding: "6px 2px" }}>
              {vHora.map((h) => (
                <div key={h.hora} style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", gap: 4 }}>
                  <span className="muted" style={{ fontSize: 10 }}>{formatMoney(h.total).replace(/[^0-9.,]/g, "").slice(0, 5)}</span>
                  <div className="prog-fill" title={`${h.hora}:00 — ${h.transacciones} ventas`} style={{ width: "100%", height: `${Math.max(3, (h.total / Math.max(1, ...vHora.map((x) => x.total))) * 150)}px`, background: "var(--red)" }} />
                  <span className="muted" style={{ fontSize: 10 }}>{h.hora}h</span>
                </div>
              ))}
            </div>
          </div>
          <div className="card sec">
            <h3 className="card-title">Ventas por mes</h3>
            <table className="table">
              <thead><tr><th>Mes</th><th>Ventas</th><th>Transacciones</th></tr></thead>
              <tbody>
                {vMes.map((r, i) => (
                  <tr key={i}><td><strong>{r.mes}</strong></td><td>{formatMoney(r.total)}</td><td>{r.transacciones}</td></tr>
                ))}
                {!vMes.length && <tr><td colSpan={3} className="muted" style={{ textAlign: "center", padding: 20 }}>Sin datos</td></tr>}
              </tbody>
            </table>
            <h3 className="card-title" style={{ marginTop: 12 }}>Ventas por año</h3>
            <table className="table">
              <thead><tr><th>Año</th><th>Ventas</th><th>Transacciones</th></tr></thead>
              <tbody>
                {vAno.map((r, i) => (
                  <tr key={i}><td><strong>{r.anio}</strong></td><td>{formatMoney(r.total)}</td><td>{r.transacciones}</td></tr>
                ))}
                {!vAno.length && <tr><td colSpan={3} className="muted" style={{ textAlign: "center", padding: 20 }}>Sin datos</td></tr>}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === "sugeridas" && (
        <table className="table">
          <thead>
            <tr><th>Producto</th><th>Existencias</th><th>Punto de reorden</th><th>Stock máximo</th><th>Sugerido comprar</th></tr>
          </thead>
          <tbody>
            {sugeridas.map((s, i) => (
              <tr key={i}>
                <td>{s.producto}</td>
                <td><span className={`badge ${s.existencias === 0 ? "badge-danger" : "badge-warning"}`}>{s.existencias}</span></td>
                <td>{s.punto_reorden}</td>
                <td>{s.stock_maximo}</td>
                <td><strong>{s.sugerido_comprar}</strong></td>
              </tr>
            ))}
            {sugeridas.length === 0 && <tr><td colSpan={5} className="muted" style={{ textAlign: "center", padding: 20 }}>Sin productos por debajo del punto de reorden</td></tr>}
          </tbody>
        </table>
      )}

      {tab === "alertas" && alertas && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(190px, 1fr))", gap: 16 }}>
          <StatCard label="Productos bajo inventario" value={alertas.bajo_inventario} />
          <StatCard label="Sobreinventario" value={alertas.sobreinventario ?? "-"} />
          <StatCard label="Próximos a vencer" value={alertas.productos_proximos_a_vencer ?? "-"} />
          <StatCard label="Productos vencidos" value={alertas.productos_vencidos ?? "-"} />
          <StatCard label="¿Sin ventas hoy?" value={alertas.sin_ventas_hoy ? "Sí" : "No"} />
          <StatCard label="Cajas abiertas" value={alertas.cajas_abiertas ?? "-"} />
          <StatCard label="Cuentas por cobrar" value={formatMoney(alertas.cuentas_por_cobrar)} />
          <StatCard label="Cuentas por pagar" value={formatMoney(alertas.cuentas_por_pagar)} />
          <StatCard label="CxP próximas (30d)" value={formatMoney(alertas.cuentas_pagar_proximas ?? 0)} />
          <StatCard label="Gastos del mes" value={formatMoney(alertas.gastos_mes)} />
          <StatCard label="Facturación pendiente" value={alertas.facturacion_pendiente ?? "-"} />
        </div>
      )}

      {tab === "clientes" && cliAnalitica && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(360px, 1fr))", gap: 18 }}>
          <div className="card sec">
            <h3 className="card-title">Clientes frecuentes (por visitas)</h3>
            <table className="table">
              <thead><tr><th>Cliente</th><th>Tipo</th><th>Ventas</th><th>Total</th></tr></thead>
              <tbody>
                {cliAnalitica.frecuentes.map((r, i) => (
                  <tr key={i}>
                    <td><strong>{r.cliente}</strong></td>
                    <td className="muted">{r.tipo_cliente}</td>
                    <td>{r.transacciones}</td>
                    <td>{formatMoney(r.total)}</td>
                  </tr>
                ))}
                {!cliAnalitica.frecuentes.length && <tr><td colSpan={4} className="muted" style={{ textAlign: "center", padding: 16 }}>Sin datos</td></tr>}
              </tbody>
            </table>
          </div>
          <div className="card sec">
            <h3 className="card-title">Clientes con mayor consumo</h3>
            <table className="table">
              <thead><tr><th>Cliente</th><th>Ventas</th><th>Total</th></tr></thead>
              <tbody>
                {cliAnalitica.mayor_consumo.map((r, i) => (
                  <tr key={i}><td><strong>{r.cliente}</strong></td><td>{r.transacciones}</td><td>{formatMoney(r.total)}</td></tr>
                ))}
                {!cliAnalitica.mayor_consumo.length && <tr><td colSpan={3} className="muted" style={{ textAlign: "center", padding: 16 }}>Sin datos</td></tr>}
              </tbody>
            </table>
          </div>
          <div className="card sec">
            <h3 className="card-title">Clientes nuevos (30 días)</h3>
            <table className="table">
              <thead><tr><th>Cliente</th><th>Documento</th><th>Teléfono</th></tr></thead>
              <tbody>
                {cliAnalitica.nuevos.map((r, i) => (
                  <tr key={i}><td><strong>{r.cliente}</strong></td><td className="muted">{r.documento || "—"}</td><td className="muted">{r.telefono || "—"}</td></tr>
                ))}
                {!cliAnalitica.nuevos.length && <tr><td colSpan={3} className="muted" style={{ textAlign: "center", padding: 16 }}>Sin clientes nuevos</td></tr>}
              </tbody>
            </table>
          </div>
          <div className="card sec">
            <h3 className="card-title">Clientes inactivos (60 días)</h3>
            <table className="table">
              <thead><tr><th>Cliente</th><th>Documento</th><th>Teléfono</th></tr></thead>
              <tbody>
                {cliAnalitica.inactivos.map((r, i) => (
                  <tr key={i}><td><strong>{r.cliente}</strong></td><td className="muted">{r.documento || "—"}</td><td className="muted">{r.telefono || "—"}</td></tr>
                ))}
                {!cliAnalitica.inactivos.length && <tr><td colSpan={3} className="muted" style={{ textAlign: "center", padding: 16 }}>Todos los clientes activos tienen actividad</td></tr>}
              </tbody>
            </table>
          </div>
          <div className="card sec">
            <h3 className="card-title">Clientes con crédito</h3>
            <table className="table">
              <thead><tr><th>Cliente</th><th>Deuda</th><th>Límite</th></tr></thead>
              <tbody>
                {cliAnalitica.con_credito.map((r, i) => (
                  <tr key={i}>
                    <td><strong>{r.cliente}</strong></td>
                    <td style={{ color: "#d97706", fontWeight: 600 }}>{formatMoney(r.deuda)}</td>
                    <td className="muted">{formatMoney(r.limite_credito)}</td>
                  </tr>
                ))}
                {!cliAnalitica.con_credito.length && <tr><td colSpan={3} className="muted" style={{ textAlign: "center", padding: 16 }}>Ningún cliente con saldo pendiente</td></tr>}
              </tbody>
            </table>
          </div>
          <div className="card sec">
            <h3 className="card-title">Cartera vencida (más de 30 días)</h3>
            <table className="table">
              <thead><tr><th>Cliente</th><th>Deuda vencida</th></tr></thead>
              <tbody>
                {cliAnalitica.cartera_vencida.map((r, i) => (
                  <tr key={i}><td><strong>{r.cliente}</strong></td><td style={{ color: "#dc2626", fontWeight: 600 }}>{formatMoney(r.deuda_vencida)}</td></tr>
                ))}
                {!cliAnalitica.cartera_vencida.length && <tr><td colSpan={2} className="muted" style={{ textAlign: "center", padding: 16 }}>Sin deudas vencidas</td></tr>}
              </tbody>
            </table>
          </div>
          <div className="card sec">
            <h3 className="card-title">Historial de abonos (cartera)</h3>
            <table className="table">
              <thead><tr><th>Fecha</th><th>Cliente</th><th>Medio</th><th>Monto</th></tr></thead>
              <tbody>
                {cliAnalitica.historial_abonos.map((r, i) => (
                  <tr key={i}>
                    <td className="muted">{r.fecha}</td>
                    <td><strong>{r.cliente}</strong></td>
                    <td className="muted">{r.medio}</td>
                    <td>{formatMoney(r.monto)}</td>
                  </tr>
                ))}
                {!cliAnalitica.historial_abonos.length && <tr><td colSpan={4} className="muted" style={{ textAlign: "center", padding: 16 }}>Sin abonos registrados</td></tr>}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === "financiero" && flujo && (
        <>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(190px, 1fr))", gap: 16, marginBottom: 20 }}>
            <StatCard label="Ingresos (30d)" value={formatMoney(flujo.total_ingresos)} />
            <StatCard label="Egresos (30d)" value={formatMoney(flujo.total_egresos)} />
            <StatCard label="Neto (30d)" value={formatMoney(flujo.total_neto)} />
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(330px, 1fr))", gap: 18, marginBottom: 20 }}>
            <ChartCard title="Resultados del período" subtitle="Estado de resultados" height={250}>
              {resultados ? (
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
                  {[
                    ["Ingresos por ventas", resultados.ingresos_ventas, "#059669"],
                    ["Costo de ventas", resultados.costo_ventas, "#d97706"],
                    ["Utilidad bruta", resultados.utilidad_bruta, "#4f46e5"],
                    ["Gastos", resultados.gastos, "#dc2626"],
                    ["Utilidad neta", resultados.utilidad_neta, "#0284c7"],
                  ].map(([label, val, color]) => (
                    <div key={label} style={{ background: "var(--bg)", borderRadius: 10, padding: "10px 12px" }}>
                      <div className="muted" style={{ fontSize: 11.5 }}>{label}</div>
                      <div style={{ fontSize: 16, fontWeight: 800, color }}>{formatMoney(val)}</div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="spinner" />
              )}
            </ChartCard>
<ChartCard title="Flujo de caja diario (neto)" subtitle="Últimos 30 días" height={250} accent="#4f46e5">
<TrendChart data={flujo.serie.map((s) => ({ dia: s.fecha, total: s.neto }))} accent="#4f46e5" />
            </ChartCard>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(560px, 1fr))", gap: 18 }}>
            <div className="card sec">
              <h3 className="card-title">Detalle por día</h3>
              <div style={{ maxHeight: 380, overflow: "auto" }}>
                <table className="table">
                  <thead><tr><th>Fecha</th><th>Ingresos</th><th>Egresos</th><th>Neto</th></tr></thead>
                  <tbody>
                    {[...flujo.serie].reverse().map((r, i) => (
                      <tr key={i}>
                        <td className="muted">{r.fecha}</td>
                        <td style={{ color: "#059669" }}>{formatMoney(r.ingresos)}</td>
                        <td style={{ color: "#dc2626" }}>{formatMoney(r.egresos)}</td>
                        <td style={{ fontWeight: 700, color: r.neto >= 0 ? "#10b981" : "#dc2626" }}>{formatMoney(r.neto)}</td>
                      </tr>
                    ))}
                    {!flujo.serie.length && <tr><td colSpan={4} className="muted" style={{ textAlign: "center", padding: 20 }}>Sin movimientos</td></tr>}
                  </tbody>
                </table>
              </div>
            </div>
            <div className="card sec">
              <h3 className="card-title">Comparativo mensual</h3>
              <table className="table">
                <thead><tr><th>Mes</th><th>Ventas</th><th>Transacciones</th></tr></thead>
                <tbody>
                  {vMes.map((r, i) => (
                    <tr key={i}><td><strong>{r.mes}</strong></td><td>{formatMoney(r.total)}</td><td>{r.transacciones}</td></tr>
                  ))}
                  {!vMes.length && <tr><td colSpan={3} className="muted" style={{ textAlign: "center", padding: 20 }}>Sin datos</td></tr>}
                </tbody>
              </table>
              {vMes.length >= 2 && (() => {
                const ult = vMes[vMes.length - 1];
                const ant = vMes[vMes.length - 2];
                const varPct = ant.total ? ((ult.total - ant.total) / ant.total) * 100 : null;
                return (
                  <div style={{ marginTop: 12, padding: "10px 14px", borderRadius: 10, background: "var(--brand-soft)" }}>
                    Variación del último mes frente al anterior:{" "}
                    <b style={{ color: varPct >= 0 ? "#059669" : "#dc2626" }}>
                      {varPct != null ? `${ult.mes} → ${ant.mes}: ${varPct.toFixed(1)}%` : "sin base comparativa"}
                    </b>
                  </div>
                );
              })()}
            </div>
          </div>
        </>
      )}

      {tab === "vendedores" && (
        <table className="table">
          <thead>
            <tr><th>#</th><th>Vendedor</th><th>Ventas</th><th>Utilidad</th><th>Transacciones</th><th>Comisión</th><th>Meta</th><th>Cumpl.</th></tr>
          </thead>
          <tbody>
            {vendedores.map((v, i) => (
              <tr key={v.vendedor_id}>
                <td>{i + 1}</td>
                <td><strong>{v.vendedor}</strong></td>
                <td>{formatMoney(v.ventas)}</td>
                <td>{formatMoney(v.utilidad)}</td>
                <td>{v.transacciones}</td>
                <td>{formatMoney(v.comision)}</td>
                <td>{formatMoney(v.meta_ventas)}</td>
                <td>{v.cumplimiento_meta != null ? `${v.cumplimiento_meta}%` : "—"}</td>
              </tr>
            ))}
            {vendedores.length === 0 && <tr><td colSpan={8} className="muted" style={{ textAlign: "center", padding: 20 }}>Sin vendedores</td></tr>}
          </tbody>
        </table>
      )}

      {tab === "auditoria" && (
        <table className="table">
          <thead>
            <tr><th>Fecha</th><th>Usuario</th><th>Módulo</th><th>Acción</th><th>Detalle</th></tr>
          </thead>
          <tbody>
            {auditoria.slice(0, 100).map((a) => (
              <tr key={a.id}>
                <td>{new Date(a.fecha).toLocaleString()}</td>
                <td>{a.usuario}</td>
                <td><span className="badge badge-info">{a.modulo}</span></td>
                <td>{a.accion}</td>
                <td className="muted">{a.detalle}</td>
              </tr>
            ))}
            {auditoria.length === 0 && <tr><td colSpan={5} className="muted" style={{ textAlign: "center", padding: 20 }}>Sin eventos registrados</td></tr>}
          </tbody>
        </table>
      )}

      {tab === "principales" && (
      <>
      {ventas ? (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))", gap: 16, marginBottom: 24 }}>
          <StatCard label="Total ventas" value={formatMoney(ventas.total_ventas)} />
          <StatCard label="Costo total" value={formatMoney(ventas.costo_total)} />
          <StatCard label="Utilidad bruta" value={formatMoney(ventas.utilidad_bruta)} />
          <StatCard label="Transacciones" value={ventas.numero_transacciones} />
          <StatCard label="Ticket promedio" value={formatMoney(ventas.ticket_promedio)} />
        </div>
      ) : (
        <div className="spinner" />
      )}

      {ventas && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px,1fr))", gap: 18, marginBottom: 24 }}>
          <ChartCard title="Recaudación por medio de pago" subtitle="Distribución desde las ventas" height={250}>
            <Donut
              data={Object.entries(ventas.por_medio_pago || {}).map(([name, value]) => ({ name, value }))}
              money
              centerLabel="Recaudado"
              centerValue={formatMoney(Object.values(ventas.por_medio_pago || {}).reduce((a, v) => a + Number(v), 0))}
            />
          </ChartCard>
          <ChartCard title="Productos más vendidos" subtitle="Top unidades" height={250} accent="#f59e0b">
            <ProgressList items={top.slice(0, 6)} labelKey="producto" valueKey="cantidad" accent="#f59e0b" />
          </ChartCard>
        </div>
      )}

      {compras && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(190px, 1fr))", gap: 16, marginBottom: 24 }}>
          <StatCard label="Compras totales" value={formatMoney(compras.total_compras)} />
          <StatCard label="Compras (subtotal)" value={formatMoney(compras.subtotal)} />
          <StatCard label="Impuesto compras" value={formatMoney(compras.impuesto)} />
          <StatCard label="N° compras" value={compras.numero_compras} />
        </div>
      )}

      {resultados && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(190px, 1fr))", gap: 16, marginBottom: 24 }}>
          <StatCard label="Ingresos por ventas" value={formatMoney(resultados.ingresos_ventas)} />
          <StatCard label="Costo de ventas" value={formatMoney(resultados.costo_ventas)} />
          <StatCard label="Utilidad bruta" value={formatMoney(resultados.utilidad_bruta)} />
          <StatCard label="Gastos" value={formatMoney(resultados.gastos)} />
          <StatCard label="Utilidad neta" value={formatMoney(resultados.utilidad_neta)} />
        </div>
      )}

      {cartera && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(190px, 1fr))", gap: 16, marginBottom: 24 }}>
          <StatCard label="Cuentas por cobrar" value={formatMoney(cartera.cuentas_por_cobrar)} />
          <StatCard label="Cuentas por pagar" value={formatMoney(cartera.cuentas_por_pagar)} />
          <StatCard label="Flujo estimado" value={formatMoney(cartera.flujo_estimado)} />
        </div>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24 }}>
        <div>
          <h2 style={{ fontSize: 16, marginBottom: 12 }}>Productos más vendidos</h2>
          <table className="table">
            <thead>
              <tr>
                <th>Producto</th>
                <th>Cantidad</th>
                <th>Total</th>
              </tr>
            </thead>
            <tbody>
              {top.map((t, i) => (
                <tr key={i}>
                  <td>{t.producto}</td>
                  <td>{t.cantidad}</td>
                  <td>{formatMoney(t.total)}</td>
                </tr>
              ))}
              {top.length === 0 && (
                <tr><td colSpan={3} className="muted" style={{ textAlign: "center", padding: 20 }}>Sin datos</td></tr>
              )}
            </tbody>
          </table>
        </div>

        <div>
          <h2 style={{ fontSize: 16, marginBottom: 12 }}>Productos agotados</h2>
          <table className="table">
            <thead>
              <tr>
                <th>Producto</th>
                <th>Sucursal</th>
                <th>Existencias</th>
              </tr>
            </thead>
            <tbody>
              {agotados.map((a, i) => (
                <tr key={i}>
                  <td>{a.producto}</td>
                  <td>{a.sucursal_id}</td>
                  <td className="badge-danger" style={{ display: "inline-block", margin: 4 }}>{a.existencias}</td>
                </tr>
              ))}
              {agotados.length === 0 && (
                <tr><td colSpan={3} className="muted" style={{ textAlign: "center", padding: 20 }}>Sin productos agotados</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
      </>
      )}

      {tab === "compras" && (
        <>
          <Seccion titulo="Compras del periodo">
            <TablaGenerica data={comprasPeriodo} />
          </Seccion>
          <Seccion titulo="Compras por proveedor">
            <TablaGenerica data={comprasPorProveedor} />
          </Seccion>
          <Seccion titulo="Compras por producto">
            <TablaGenerica data={comprasPorProducto} />
          </Seccion>
          <Seccion titulo="Pendientes de recibir">
            <TablaGenerica data={comprasPendientes} />
          </Seccion>
          <Seccion titulo="Recibidas">
            <TablaGenerica data={comprasRecibidas} />
          </Seccion>
          <Seccion titulo="Anuladas">
            <TablaGenerica data={comprasAnuladas} />
          </Seccion>
          <Seccion titulo="Compras por sucursal">
            <TablaGenerica data={comprasXSucursal} />
          </Seccion>
        </>
      )}

      {tab === "inventario" && (
        <>
          <Seccion
            titulo="Rotación de productos (días para agotar stock)"
            acciones={
              <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                <select value={rotDias} onChange={(e) => setRotDias(Number(e.target.value))} style={{ width: 110 }}>
                  <option value={30}>30 días</option>
                  <option value={60}>60 días</option>
                  <option value={90}>90 días</option>
                  <option value={120}>120 días</option>
                </select>
                <button className="btn btn-sm" onClick={cargarRotacion}>Actualizar</button>
              </div>
            }
          >
            <TablaGenerica data={rotacion} />
          </Seccion>
          <Seccion titulo="Inventario por categoría">
            <TablaGenerica data={invCategoria} />
          </Seccion>
          <Seccion titulo="Diferencias de inventario">
            <TablaGenerica data={diferencias} />
          </Seccion>
          <Seccion titulo="Inventario por sede (sucursal)">
            <TablaGenerica data={invXSucursal} />
          </Seccion>
          <Seccion titulo="Inventario por bodega">
            <TablaGenerica data={invXBodega} />
          </Seccion>
        </>
      )}

      {tab === "caja" && (
        <>
          <Seccion titulo="Resumen de caja por apertura/turno">
            <TablaGenerica data={cajaResumen} />
          </Seccion>
          <Seccion titulo="Ventas por cajero">
            <TablaGenerica data={vCajero} />
          </Seccion>
          <Seccion titulo="Ventas por turno">
            <TablaGenerica data={vTurno} />
          </Seccion>
        </>
      )}

      {tab === "vencimientos" && (
        <>
          {porVencer && typeof porVencer === "object" && !Array.isArray(porVencer) && (
            <div className="chip" style={{ marginBottom: 12, display: "inline-block", background: porVencer.vencidos ? "#fee2e2" : undefined, color: porVencer.vencidos ? "#991b1b" : undefined }}>
              {porVencer.vencidos ?? 0} lote(s) vencido(s) · {porVencer.proximos_a_vencer ?? 0} por vencer
            </div>
          )}
          <Seccion titulo="Lotes por vencer / vencidos">
            <TablaGenerica data={porVencer} />
          </Seccion>
          <Seccion titulo="Etiquetas de lotes">
            <TablaGenerica data={lotesEtiquetas} />
          </Seccion>
        </>
      )}
    </div>
  );
}