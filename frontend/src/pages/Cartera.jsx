import { useEffect, useState } from "react";
import api from "../api.js";

function formatMoney(n) {
  return new Intl.NumberFormat("es-CO", { style: "currency", currency: "COP", maximumFractionDigits: 0 }).format(n || 0);
}

export default function Cartera() {
  const [tab, setTab] = useState("cartera");
  const [recibir, setRecibir] = useState({ total_cartera: 0, clientes: [] });
  const [pagar, setPagar] = useState({ total_deuda: 0, proveedores: [] });
  const [error, setError] = useState("");
  const [estado, setEstado] = useState(null);
  const [abono, setAbono] = useState({ cliente: {}, proveedor: {} });

  const [acuerdos, setAcuerdos] = useState([]);
  const [clientes, setClientes] = useState([]);
  const [cobranza, setCobranza] = useState(null);
  const [acuerdoForm, setAcuerdoForm] = useState({
    cliente_id: "",
    monto_total: "",
    numero_cuotas: "3",
    periodicidad: "mensual",
    fecha_inicio: "",
    notas: "",
  });
  const [detAcuerdo, setDetAcuerdo] = useState(null);

  async function load() {
    api("/cartera/cuentas-cobrar").then(setRecibir).catch(() => {});
    api("/cartera/cuentas-pagar").then(setPagar).catch(() => {});
  }

  useEffect(() => {
    load();
    api("/acuerdos-pago").then(setAcuerdos).catch(() => {});
    api("/clientes").then(setClientes).catch(() => {});
  }, []);

  useEffect(() => {
    if (tab === "acuerdos") api("/acuerdos-pago").then(setAcuerdos).catch(() => {});
    if (tab === "cobranza") api("/cartera/cobranza").then(setCobranza).catch(() => {});
  }, [tab]);

  async function crearAcuerdo(e) {
    e.preventDefault();
    setError("");
    try {
      const res = await api("/acuerdos-pago", {
        method: "POST",
        body: JSON.stringify({ ...acuerdoForm, monto_total: Number(acuerdoForm.monto_total), numero_cuotas: Number(acuerdoForm.numero_cuotas) }),
      });
      setAcuerdoForm({ cliente_id: "", monto_total: "", numero_cuotas: "3", periodicidad: "mensual", fecha_inicio: "", notas: "" });
      setAcuerdos((prev) => [res, ...prev]);
    } catch (err) {
      setError(err.message);
    }
  }

  async function pagarCuota(acuerdoId, cuotaId) {
    setError("");
    try {
      const ac = await api(`/acuerdos-pago/${acuerdoId}/pagar-cuota?cuota_id=${cuotaId}`, { method: "POST" });
      setAcuerdos((prev) => prev.map((x) => (x.id === ac.id ? ac : x)));
    } catch (err) {
      setError(err.message);
    }
  }

  async function abonarCliente(venta, clienteId) {
    const monto = abono.cliente[venta.venta_id];
    if (!monto || monto <= 0) return;
    setError("");
    try {
      await api("/cartera/abonos/clientes", {
        method: "POST",
        body: JSON.stringify({ empresa_id: 1, cliente_id: clienteId, venta_id: venta.venta_id, monto: Number(monto), medio: "efectivo" }),
      });
      setAbono({ ...abono, cliente: { ...abono.cliente, [venta.venta_id]: "" } });
      load();
      if (estado) verEstado(clienteId);
    } catch (err) {
      setError(err.message);
    }
  }

  async function abonarProveedor(cuenta) {
    const monto = abono.proveedor[cuenta.id];
    if (!monto || monto <= 0) return;
    setError("");
    try {
      await api(`/compras/cuentas-pagar/${cuenta.id}/abonos`, {
        method: "POST",
        body: JSON.stringify({ cuenta_id: cuenta.id, monto: Number(monto), medio: "efectivo" }),
      });
      setAbono({ ...abono, proveedor: { ...abono.proveedor, [cuenta.id]: "" } });
      load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function verEstado(clienteId) {
    setError("");
    try {
      setEstado(await api(`/cartera/estado-cuenta/${clienteId}`));
    } catch (err) {
      setError(err.message);
    }
  }

  async function verAcuerdo(acuerdoId) {
    setError("");
    try {
      setDetAcuerdo(await api(`/acuerdos-pago/${acuerdoId}`));
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div className="page">
      <div className="page-header">
        <h1>Cartera</h1>
        <div className="tabs">
          {["cartera", "cobranza", "acuerdos"].map((t) => (
            <button key={t} className={`btn ${tab === t ? "btn-primary" : ""}`} onClick={() => setTab(t)}>
              {t === "cartera" ? "Cartera" : t === "cobranza" ? "Cobranza" : "Acuerdos de pago"}
            </button>
          ))}
        </div>
      </div>

      {error && <div className="error">{error}</div>}

      {tab === "cobranza" && (
        <>
          <div style={{ display: "flex", gap: 16, marginBottom: 24, flexWrap: "wrap" }}>
            <div className="card" style={{ flex: 1, minWidth: 200 }}>
              <div className="muted">Cartera en mora / vigente</div>
              <div style={{ fontSize: 24, fontWeight: 700, color: "#dc2626" }}>{formatMoney(cobranza?.total_cartera)}</div>
            </div>
          </div>
          {cobranza?.tramos.map((t) => (
            <div key={t.tramo} className="card" style={{ marginBottom: 16 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
                <h3 style={{ fontSize: 15 }}>{t.tramo}</h3>
                <strong style={{ color: t.tramo === "corriente" ? "#059669" : "#dc2626" }}>{formatMoney(t.saldo)}</strong>
              </div>
              <table className="table">
                <thead><tr><th>Cliente</th><th>Saldo</th></tr></thead>
                <tbody>
                  {Object.values(t.clientes).map((c) => (
                    <tr key={c.cliente_id}>
                      <td>{c.cliente}</td>
                      <td><strong>{formatMoney(c.saldo)}</strong></td>
                    </tr>
                  ))}
                  {Object.values(t.clientes).length === 0 && <tr><td colSpan={2} className="muted" style={{ textAlign: "center" }}>Sin clientes</td></tr>}
                </tbody>
              </table>
            </div>
          ))}
          {cobranza === null && <p className="muted">Cargando cobranza…</p>}
        </>
      )}

      {tab === "acuerdos" && (
        <>
          <form onSubmit={crearAcuerdo} className="card" style={{ marginBottom: 20, display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(170px, 1fr))", gap: 12 }}>
            <div>
              <label>Cliente *</label>
              <select required value={acuerdoForm.cliente_id} onChange={(e) => setAcuerdoForm({ ...acuerdoForm, cliente_id: e.target.value })}>
                <option value="">Seleccionar...</option>
                {clientes.map((c) => (
                  <option key={c.id} value={c.id}>{c.nombre}</option>
                ))}
              </select>
            </div>
            <div><label>Monto total *</label><input required type="number" min="1" value={acuerdoForm.monto_total} onChange={(e) => setAcuerdoForm({ ...acuerdoForm, monto_total: e.target.value })} /></div>
            <div><label>N° cuotas</label><input required type="number" min="1" value={acuerdoForm.numero_cuotas} onChange={(e) => setAcuerdoForm({ ...acuerdoForm, numero_cuotas: e.target.value })} /></div>
            <div>
              <label>Periodicidad</label>
              <select value={acuerdoForm.periodicidad} onChange={(e) => setAcuerdoForm({ ...acuerdoForm, periodicidad: e.target.value })}>
                <option value="semanal">Semanal</option>
                <option value="quincenal">Quincenal</option>
                <option value="mensual">Mensual</option>
              </select>
            </div>
            <div><label>Fecha inicio</label><input type="date" value={acuerdoForm.fecha_inicio} onChange={(e) => setAcuerdoForm({ ...acuerdoForm, fecha_inicio: e.target.value })} /></div>
            <div><label>Notas</label><input value={acuerdoForm.notas} onChange={(e) => setAcuerdoForm({ ...acuerdoForm, notas: e.target.value })} /></div>
            <div style={{ display: "flex", alignItems: "flex-end" }}>
              <button className="btn" type="submit">Crear acuerdo</button>
            </div>
          </form>

          <h2 style={{ fontSize: 16, marginBottom: 10 }}>Acuerdos de pago</h2>
          <table className="table">
            <thead>
              <tr><th>N°</th><th>Cliente</th><th>Total</th><th>Abonado</th><th>Saldo</th><th>Estado</th><th>Cuotas</th><th></th></tr>
            </thead>
            <tbody>
              {acuerdos.map((ac) => (
                <tr key={ac.id}>
                  <td>{ac.numero}</td>
                  <td><strong>{ac.cliente}</strong></td>
                  <td>{formatMoney(ac.monto_total)}</td>
                  <td>{formatMoney(ac.abonado)}</td>
                  <td><strong style={{ color: "#4f46e5" }}>{formatMoney(ac.saldo)}</strong></td>
                  <td>
                    <span className={`badge ${ac.estado === "pagado" ? "badge-success" : ac.estado === "activo" && ac.abonado > 0 ? "badge-info" : "badge-warning"}`}>
                      {ac.estado}
                    </span>
                  </td>
                  <td>
                    {ac.cuotas.map((c) => (
                      <span key={c.id} className="badge" style={{ margin: "0 4px 4px 0", background: c.estado === "pagada" ? "rgba(16,185,129,.15)" : "rgba(244,63,94,.12)", color: c.estado === "pagada" ? "#059669" : "#e11d48" }}>
                        {c.numero}·{formatMoney(c.monto)}
                        {c.estado === "pendiente" && (
                          <button className="btn btn-ghost" style={{ marginLeft: 6, padding: 0, fontSize: 12, color: "inherit" }} onClick={() => pagarCuota(ac.id, c.id)} title="Pagar cuota">pagar</button>
                        )}
                      </span>
                    ))}
                  </td>
                  <td><button className="btn btn-sm btn-ghost" onClick={() => verAcuerdo(ac.id)}>Detalle</button></td>
                </tr>
              ))}
              {acuerdos.length === 0 && <tr><td colSpan={8} className="muted" style={{ textAlign: "center", padding: 20 }}>Sin acuerdos de pago. Crea el primero arriba.</td></tr>}
            </tbody>
          </table>
        </>
      )}

      {tab === "cartera" && (
      <>
      <div style={{ display: "flex", gap: 16, marginBottom: 24, flexWrap: "wrap" }}>
        <div className="card" style={{ flex: 1, minWidth: 200 }}>
          <div className="muted">Por cobrar (clientes)</div>
          <div style={{ fontSize: 24, fontWeight: 700, color: "#4f46e5" }}>{formatMoney(recibir.total_cartera)}</div>
        </div>
        <div className="card" style={{ flex: 1, minWidth: 200 }}>
          <div className="muted">Por pagar (proveedores)</div>
          <div style={{ fontSize: 24, fontWeight: 700, color: "#4f46e5" }}>{formatMoney(pagar.total_deuda)}</div>
        </div>
      </div>

      <h2 style={{ fontSize: 16, marginBottom: 10 }}>Cuentas por cobrar</h2>
      <table className="table" style={{ marginBottom: 28 }}>
        <thead>
          <tr><th>Cliente</th><th>Saldo total</th><th>Detalle ventas</th><th>Estado</th></tr>
        </thead>
        <tbody>
          {recibir.clientes.map((c) => (
            <tr key={c.cliente_id}>
              <td>{c.cliente}</td>
              <td><strong>{formatMoney(c.saldo)}</strong></td>
              <td>
                {c.ventas.map((vt) => (
                  <div key={vt.venta_id} style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 6 }}>
                    <span style={{ minWidth: 110 }}>{vt.numero} — {formatMoney(vt.saldo)}</span>
                    <input
                      type="number"
                      style={{ width: 100 }}
                      placeholder="Monto"
                      value={abono.cliente[vt.venta_id] || ""}
                      onChange={(e) => setAbono({ ...abono, cliente: { ...abono.cliente, [vt.venta_id]: e.target.value } })}
                    />
                    <button className="btn btn-secondary" onClick={() => abonarCliente(vt, c.cliente_id)}>Abonar</button>
                  </div>
                ))}
              </td>
              <td>
                <button className="btn btn-ghost" onClick={() => verEstado(c.cliente_id)}>{estado?.cliente_id === c.cliente_id ? "Ocultar" : "Ver"}</button>
              </td>
            </tr>
          ))}
          {recibir.clientes.length === 0 && <tr><td colSpan={4} className="muted" style={{ textAlign: "center", padding: 20 }}>Sin cuentas por cobrar</td></tr>}
        </tbody>
      </table>

      {estado && (
        <div className="card" style={{ marginBottom: 28 }}>
          <h3>Estado de cuenta — {estado.cliente}</h3>
          <p className="muted">Saldo pendiente: <strong>{formatMoney(estado.saldo_total)}</strong></p>
          <table className="table" style={{ marginTop: 10 }}>
            <thead><tr><th>Venta</th><th>Fecha</th><th>Total</th><th>Saldo</th></tr></thead>
            <tbody>
              {estado.ventas.map((v) => (
                <tr key={v.id}>
                  <td>{v.numero}</td>
                  <td>{new Date(v.fecha).toLocaleString()}</td>
                  <td>{formatMoney(v.total)}</td>
                  <td>{formatMoney(v.saldo)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <h2 style={{ fontSize: 16, marginBottom: 10 }}>Cuentas por pagar</h2>
      <table className="table">
        <thead>
          <tr><th>Proveedor</th><th>Saldo total</th><th>Cuentas</th></tr>
        </thead>
        <tbody>
          {pagar.proveedores.map((p) => (
            <tr key={p.proveedor_id}>
              <td>{p.proveedor}</td>
              <td><strong>{formatMoney(p.saldo)}</strong></td>
              <td>
                {p.cuentas.map((c) => (
                  <div key={c.id} style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 6 }}>
                    <span style={{ minWidth: 110 }}>Cta #{c.id} — {formatMoney(c.saldo)}</span>
                    <input
                      type="number"
                      style={{ width: 100 }}
                      placeholder="Monto"
                      value={abono.proveedor[c.id] || ""}
                      onChange={(e) => setAbono({ ...abono, proveedor: { ...abono.proveedor, [c.id]: e.target.value } })}
                    />
                    <button className="btn btn-secondary" onClick={() => abonarProveedor(c)}>Abonar</button>
                  </div>
                ))}
              </td>
            </tr>
          ))}
          {pagar.proveedores.length === 0 && <tr><td colSpan={3} className="muted" style={{ textAlign: "center", padding: 20 }}>Sin cuentas por pagar</td></tr>}
        </tbody>
      </table>
      </>
      )}

      {detAcuerdo && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,.45)", display: "grid", placeItems: "center", zIndex: 1100, padding: 20 }}>
          <div className="card" style={{ width: "min(620px, 100%)" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
              <h3>Acuerdo {detAcuerdo.numero} · {detAcuerdo.cliente}</h3>
              <button className="btn btn-ghost" onClick={() => setDetAcuerdo(null)}>✕</button>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(150px,1fr))", gap: 10, marginBottom: 12 }}>
              <div>Monto total<br /><strong>{formatMoney(detAcuerdo.monto_total)}</strong></div>
              <div>Abonado<br /><strong>{formatMoney(detAcuerdo.abonado)}</strong></div>
              <div>Saldo<br /><strong style={{ color: "#4f46e5" }}>{formatMoney(detAcuerdo.saldo)}</strong></div>
              <div>Estado<br /><span className="badge">{detAcuerdo.estado}</span></div>
              <div>Periodicidad<br /><strong>{detAcuerdo.periodicidad}</strong></div>
            </div>
            {detAcuerdo.notas && <p className="muted" style={{ fontSize: 13 }}>Notas: {detAcuerdo.notas}</p>}
            <table className="table">
              <thead><tr><th>#</th><th>Monto</th><th>Programada</th><th>Pagada</th><th>Estado</th></tr></thead>
              <tbody>
                {(detAcuerdo.cuotas || []).map((c) => (
                  <tr key={c.id}>
                    <td>{c.numero}</td>
                    <td>{formatMoney(c.monto)}</td>
                    <td>{c.fecha_programada || "—"}</td>
                    <td>{c.fecha_pago || "—"}</td>
                    <td><span className={`badge ${c.estado === "pagada" ? "badge-success" : "badge-warning"}`}>{c.estado}</span></td>
                  </tr>
                ))}
                {(detAcuerdo.cuotas || []).length === 0 && <tr><td colSpan={5} className="muted" style={{ textAlign: "center" }}>Sin cuotas</td></tr>}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}