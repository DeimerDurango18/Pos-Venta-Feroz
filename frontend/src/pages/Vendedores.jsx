import { useEffect, useState } from "react";
import api from "../api.js";

function formatMoney(n) {
  return new Intl.NumberFormat("es-CO", {
    style: "currency",
    currency: "COP",
    maximumFractionDigits: 0,
  }).format(n || 0);
}

export default function Vendedores() {
  const [vendedores, setVendedores] = useState([]);
  const [productos, setProductos] = useState([]);
  const [reglas, setReglas] = useState([]);
  const [error, setError] = useState("");
  const [msg, setMsg] = useState("");
  const [meta, setMeta] = useState({ vendedor_id: "", periodo: "", meta_ventas: "", meta_utilidad: "" });
  const [regla, setRegla] = useState({ vendedor_id: "", producto_id: "", porcentaje: "" });

  useEffect(() => {
    loadVendedores();
    api("/productos").then(setProductos).catch(() => {});
    api("/vendedores/reglas-comision").then(setReglas).catch(() => {});
  }, []);

  function loadVendedores() {
    api("/vendedores").then(setVendedores).catch((e) => setError((p) => p || e.message));
  }

  async function crearMeta(e) {
    e.preventDefault();
    setError("");
    setMsg("");
    try {
      await api("/vendedores/metas", {
        method: "POST",
        body: JSON.stringify({
          vendedor_id: Number(meta.vendedor_id),
          periodo: meta.periodo,
          meta_ventas: Number(meta.meta_ventas) || 0,
          meta_utilidad: Number(meta.meta_utilidad) || 0,
        }),
      });
      setMsg("Meta asignada/actualizada.");
      setMeta({ vendedor_id: "", periodo: "", meta_ventas: "", meta_utilidad: "" });
      loadVendedores();
    } catch (err) {
      setError(err.message);
    }
  }

  async function crearRegla(e) {
    e.preventDefault();
    setError("");
    setMsg("");
    if (!regla.porcentaje) {
      setError("Indica el porcentaje de comisión.");
      return;
    }
    try {
      await api("/vendedores/reglas-comision", {
        method: "POST",
        body: JSON.stringify({
          empresa_id: 1,
          vendedor_id: regla.vendedor_id ? Number(regla.vendedor_id) : null,
          producto_id: regla.producto_id ? Number(regla.producto_id) : null,
          porcentaje: Number(regla.porcentaje),
        }),
      });
      setMsg("Regla de comisión creada.");
      setRegla({ vendedor_id: "", producto_id: "", porcentaje: "" });
      api("/vendedores/reglas-comision").then(setReglas).catch(() => {});
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div className="page">
      <div className="page-header">
        <h1>Vendedores · Metas y comisiones</h1>
      </div>

      {error && <div className="error">{error}</div>}
      {msg && <div className="chip" style={{ marginBottom: 12, display: "inline-block" }}>{msg}</div>}

      <h2 style={{ fontSize: 18, marginBottom: 12 }}>Vendedores</h2>
      <table className="table" style={{ marginBottom: 24 }}>
        <thead>
          <tr>
            <th>Vendedor</th>
            <th>Usuario</th>
            <th>Meta actual</th>
            <th>Periodo</th>
          </tr>
        </thead>
        <tbody>
          {vendedores.map((v) => (
            <tr key={v.id}>
              <td>{v.nombre}</td>
              <td className="muted">{v.username}</td>
              <td>
                {v.meta_actual ? (
                  <>
                    Ventas: <b>{formatMoney(v.meta_actual.meta_ventas)}</b>
                    {" · "}Utilidad: <b>{formatMoney(v.meta_actual.meta_utilidad)}</b>
                  </>
                ) : (
                  <span className="muted">Sin meta asignada</span>
                )}
              </td>
              <td>{v.meta_actual?.periodo || "—"}</td>
            </tr>
          ))}
          {vendedores.length === 0 && (
            <tr><td colSpan={4} className="muted" style={{ textAlign: "center", padding: 20 }}>No hay usuarios marcados como vendedores. Márcalos en Seguridad → Usuarios.</td></tr>
          )}
        </tbody>
      </table>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(360px, 1fr))", gap: 16, marginBottom: 24 }}>
        <form onSubmit={crearMeta} className="card" style={{ display: "grid", gap: 12 }}>
          <h2 style={{ fontSize: 16 }}>Asignar / actualizar meta</h2>
          <div>
            <label>Vendedor *</label>
            <select required value={meta.vendedor_id} onChange={(e) => setMeta({ ...meta, vendedor_id: e.target.value })}>
              <option value="">Seleccionar...</option>
              {vendedores.map((v) => <option key={v.id} value={v.id}>{v.nombre}</option>)}
            </select>
          </div>
          <div><label>Periodo *</label><input required placeholder="Ej: 2026-09" value={meta.periodo} onChange={(e) => setMeta({ ...meta, periodo: e.target.value })} /></div>
          <div><label>Meta de ventas ($)</label><input type="number" value={meta.meta_ventas} onChange={(e) => setMeta({ ...meta, meta_ventas: e.target.value })} /></div>
          <div><label>Meta de utilidad ($)</label><input type="number" value={meta.meta_utilidad} onChange={(e) => setMeta({ ...meta, meta_utilidad: e.target.value })} /></div>
          <button className="btn" type="submit">Guardar meta</button>
        </form>

        <form onSubmit={crearRegla} className="card" style={{ display: "grid", gap: 12 }}>
          <h2 style={{ fontSize: 16 }}>Regla de comisión</h2>
          <div>
            <label>Vendedor (opcional: todos)</label>
            <select value={regla.vendedor_id} onChange={(e) => setRegla({ ...regla, vendedor_id: e.target.value })}>
              <option value="">Todos los vendedores</option>
              {vendedores.map((v) => <option key={v.id} value={v.id}>{v.nombre}</option>)}
            </select>
          </div>
          <div>
            <label>Producto (opcional: todos)</label>
            <select value={regla.producto_id} onChange={(e) => setRegla({ ...regla, producto_id: e.target.value })}>
              <option value="">Todos los productos</option>
              {productos.slice(0, 500).map((p) => <option key={p.id} value={p.id}>{p.nombre}</option>)}
            </select>
          </div>
          <div><label>Porcentaje de comisión *</label><input required type="number" step="0.01" value={regla.porcentaje} onChange={(e) => setRegla({ ...regla, porcentaje: e.target.value })} /></div>
          <button className="btn" type="submit">Guardar regla</button>
        </form>
      </div>

      <h2 style={{ fontSize: 18, marginBottom: 12 }}>Reglas de comisión activas</h2>
      <table className="table">
        <thead>
          <tr>
            <th>#</th>
            <th>Vendedor</th>
            <th>Producto</th>
            <th>% Comisión</th>
          </tr>
        </thead>
        <tbody>
          {reglas.map((r) => {
            const v = vendedores.find((x) => x.id === r.vendedor_id);
            const p = productos.find((x) => x.id === r.producto_id);
            return (
              <tr key={r.id}>
                <td>{r.id}</td>
                <td>{r.vendedor_id ? v?.nombre || `#${r.vendedor_id}` : "Todos"}</td>
                <td>{r.producto_id ? p?.nombre || `#${r.producto_id}` : "Todos"}</td>
                <td><strong>{r.porcentaje}%</strong></td>
              </tr>
            );
          })}
          {reglas.length === 0 && (
            <tr><td colSpan={4} className="muted" style={{ textAlign: "center", padding: 20 }}>Sin reglas de comisión</td></tr>
          )}
        </tbody>
      </table>
    </div>
  );
}