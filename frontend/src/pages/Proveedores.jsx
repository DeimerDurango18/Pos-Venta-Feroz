import { useEffect, useState } from "react";
import api, { downloadCsv } from "../api.js";
import ImportarCsv from "../components/ImportarCsv.jsx";

function formatMoney(n) {
  return new Intl.NumberFormat("es-CO", {
    style: "currency",
    currency: "COP",
    maximumFractionDigits: 0,
  }).format(n || 0);
}

export default function Proveedores() {
  const [proveedores, setProveedores] = useState([]);
  const [deudas, setDeudas] = useState({ total_deuda: 0, proveedores: [] });
  const [error, setError] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ nombre: "", nit: "", contacto: "", telefono: "", email: "", direccion: "", ciudad: "" });
  const [abono, setAbono] = useState({});
  const [editando, setEditando] = useState(null);

  async function load() {
    api("/proveedores").then(setProveedores).catch((e) => setError(e.message));
    api("/cartera/cuentas-pagar").then(setDeudas).catch(() => {});
  }

  useEffect(() => {
    load();
  }, []);

  async function handleCreate(e) {
    e.preventDefault();
    setError("");
    try {
      await api("/proveedores?empresa_id=1", { method: "POST", body: JSON.stringify({ ...form, email: form.email || null }) });
      setShowForm(false);
      setForm({ nombre: "", nit: "", contacto: "", telefono: "", email: "", direccion: "", ciudad: "" });
      load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function guardarEdicion(e) {
    e.preventDefault();
    if (!editando) return;
    setError("");
    try {
      await api(`/proveedores/${editando.id}`, {
        method: "PUT",
        body: JSON.stringify({
          nombre: editando.nombre,
          nit: editando.nit,
          contacto: editando.contacto,
          email: editando.email || null,
          telefono: editando.telefono,
          direccion: editando.direccion,
          ciudad: editando.ciudad,
          activo: editando.activo,
        }),
      });
      setEditando(null);
      load();
    } catch (err) {
      setError(err.message);
    }
  }

  function setECampo(key, val) {
    setEditando((prev) => ({ ...prev, [key]: val }));
  }

  async function abonar(cuenta) {
    const monto = abono[cuenta.id];
    if (!monto || monto <= 0) return;
    setError("");
    try {
      await api(`/compras/cuentas-pagar/${cuenta.id}/abonos`, {
        method: "POST",
        body: JSON.stringify({ cuenta_id: cuenta.id, monto: Number(monto), medio: "efectivo" }),
      });
      setAbono({ ...abono, [cuenta.id]: "" });
      load();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div className="page">
      <div className="page-header">
        <h1>Proveedores</h1>
        <button className="btn btn-secondary" onClick={() => downloadCsv("/exportar/proveedores", "proveedores").catch((e) => setError(e.message))}>Exportar CSV</button>
        <ImportarCsv path="/importar/proveedores" etiqueta="Importar CSV" onOk={load} />
        <button className="btn" onClick={() => setShowForm(!showForm)}>
          {showForm ? "Cerrar" : "+ Nuevo proveedor"}
        </button>
      </div>

      {error && <div className="error">{error}</div>}

      {showForm && (
        <form onSubmit={handleCreate} className="card" style={{ marginBottom: 20, display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(170px, 1fr))", gap: 12 }}>
          <div><label>Nombre *</label><input required value={form.nombre} onChange={(e) => setForm({ ...form, nombre: e.target.value })} /></div>
          <div><label>NIT</label><input value={form.nit} onChange={(e) => setForm({ ...form, nit: e.target.value })} /></div>
          <div><label>Contacto</label><input value={form.contacto} onChange={(e) => setForm({ ...form, contacto: e.target.value })} /></div>
          <div><label>Teléfono</label><input value={form.telefono} onChange={(e) => setForm({ ...form, telefono: e.target.value })} /></div>
          <div><label>Email</label><input type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></div>
          <div><label>Ciudad</label><input value={form.ciudad} onChange={(e) => setForm({ ...form, ciudad: e.target.value })} /></div>
          <div style={{ display: "flex", alignItems: "flex-end" }}><button className="btn" type="submit">Guardar</button></div>
        </form>
      )}

      <h2 style={{ fontSize: 16, marginBottom: 10 }}>Cuentas por pagar</h2>
      <table className="table" style={{ marginBottom: 24 }}>
        <thead>
          <tr><th>Proveedor</th><th>Deuda total</th><th>Cuentas</th><th style={{ width: 260 }}>Abonar</th></tr>
        </thead>
        <tbody>
          {deudas.proveedores.map((p) => (
            <tr key={p.proveedor_id}>
              <td>{p.proveedor}</td>
              <td><strong>{formatMoney(p.saldo)}</strong></td>
              <td>{p.cuentas.length}</td>
              <td>{p.cuentas.map((c) => (
                <div key={c.id} style={{ display: "flex", gap: 8, marginBottom: 6, alignItems: "center" }}>
                  <span className="muted" style={{ flex: 1 }}>Cta #{c.id}: {formatMoney(c.saldo)}</span>
                  <input
                    type="number"
                    style={{ width: 110 }}
                    placeholder="Monto"
                    value={abono[c.id] || ""}
                    onChange={(e) => setAbono({ ...abono, [c.id]: e.target.value })}
                  />
                  <button className="btn btn-secondary" onClick={() => abonar(c)}>Abonar</button>
                </div>
              ))}</td>
            </tr>
          ))}
          {deudas.proveedores.length === 0 && (
            <tr><td colSpan={4} className="muted" style={{ textAlign: "center", padding: 20 }}>Sin deudas pendientes</td></tr>
          )}
        </tbody>
        <tfoot>
          <tr><td><strong>Total</strong></td><td><strong>{formatMoney(deudas.total_deuda)}</strong></td><td colSpan={2} /></tr>
        </tfoot>
      </table>

      <h2 style={{ fontSize: 16, marginBottom: 10 }}>Directorio</h2>
      <table className="table">
        <thead>
          <tr><th>Nombre</th><th>NIT</th><th>Contacto</th><th>Teléfono</th><th></th></tr>
        </thead>
        <tbody>
          {proveedores.map((p) => (
            <tr key={p.id}>
              <td>{p.nombre}</td>
              <td>{p.nit}</td>
              <td>{p.contacto}</td>
              <td>{p.telefono}</td>
              <td>
                <button className="btn btn-ghost" title="Editar" onClick={() => setEditando({ ...p })}>✏️</button>
              </td>
            </tr>
          ))}
          {proveedores.length === 0 && (
            <tr><td colSpan={5} className="muted" style={{ textAlign: "center", padding: 20 }}>Sin proveedores</td></tr>
          )}
        </tbody>
      </table>

      {editando && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,.45)", display: "grid", placeItems: "center", zIndex: 1100, padding: 20 }}>
          <form onSubmit={guardarEdicion} className="card" style={{ width: "min(560px, 100%)", display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(170px, 1fr))", gap: 12 }}>
            <div style={{ gridColumn: "1 / -1", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <h2 style={{ fontSize: 17 }}>Editar proveedor · #{editando.id}</h2>
              <button type="button" className="btn btn-ghost" onClick={() => setEditando(null)}>✕</button>
            </div>
            <div><label>Nombre</label><input value={editando.nombre} onChange={(e) => setECampo("nombre", e.target.value)} /></div>
            <div><label>NIT</label><input value={editando.nit || ""} onChange={(e) => setECampo("nit", e.target.value)} /></div>
            <div><label>Contacto</label><input value={editando.contacto || ""} onChange={(e) => setECampo("contacto", e.target.value)} /></div>
            <div><label>Teléfono</label><input value={editando.telefono || ""} onChange={(e) => setECampo("telefono", e.target.value)} /></div>
            <div><label>Email</label><input type="email" value={editando.email || ""} onChange={(e) => setECampo("email", e.target.value)} /></div>
            <div><label>Ciudad</label><input value={editando.ciudad || ""} onChange={(e) => setECampo("ciudad", e.target.value)} /></div>
            <div><label>Dirección</label><input value={editando.direccion || ""} onChange={(e) => setECampo("direccion", e.target.value)} /></div>
            <div style={{ display: "flex", gap: 14 }}>
              <label className="muted" style={{ fontSize: 12.5 }}><input type="checkbox" checked={!!editando.activo} onChange={(e) => setECampo("activo", e.target.checked)} /> Activo</label>
            </div>
            <div style={{ gridColumn: "1 / -1", display: "flex", gap: 8, justifyContent: "flex-end" }}>
              <button type="button" className="btn btn-secondary" onClick={() => setEditando(null)}>Cancelar</button>
              <button type="submit" className="btn">Guardar cambios</button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}