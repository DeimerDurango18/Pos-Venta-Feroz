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

const FORM_BASE = {
  nombre: "",
  tipo_documento: "CC",
  documento: "",
  telefono: "",
  email: "",
  direccion: "",
  ciudad: "",
  tipo: "ocasional",
  limite_credito: "",
};

export default function Clientes() {
  const [clientes, setClientes] = useState([]);
  const [error, setError] = useState("");
  const [q, setQ] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(FORM_BASE);
  const [editando, setEditando] = useState(null);
  const [detalle, setDetalle] = useState(null);

  function load() {
    api(`/clientes${q ? `?q=${encodeURIComponent(q)}` : ""}`).then(setClientes).catch((e) => setError(e.message));
  }

  useEffect(() => {
    const t = setTimeout(load, 300);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q]);

  async function guardar(e, modo) {
    e.preventDefault();
    setError("");
    try {
      if (modo === "crear") {
        await api("/clientes?empresa_id=1", {
          method: "POST",
          body: JSON.stringify({
            ...form,
            email: form.email || null,
            limite_credito: Number(form.limite_credito) || 0,
          }),
        });
        setShowForm(false);
        setForm(FORM_BASE);
      } else if (modo === "editar" && editando) {
        await api(`/clientes/${editando.id}`, {
          method: "PUT",
          body: JSON.stringify({
            nombre: editando.nombre,
            tipo_documento: editando.tipo_documento,
            documento: editando.documento,
            email: editando.email || null,
            telefono: editando.telefono,
            direccion: editando.direccion,
            ciudad: editando.ciudad,
            tipo: editando.tipo,
            limite_credito: Number(editando.limite_credito) || 0,
            activo: editando.activo,
          }),
        });
        setEditando(null);
        if (detalle?.id === editando.id) abrirDetalle(editando);
      }
      load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function abrirDetalle(p) {
    setError("");
    try {
      const d = await api(`/clientes/${p.id}`);
      setDetalle(d);
    } catch (err) {
      setError(err.message);
    }
  }

  function setECampo(key, val) {
    setEditando((prev) => ({ ...prev, [key]: val }));
  }

  return (
    <div className="page">
      <div className="page-header">
        <h1>Clientes</h1>
        <button className="btn btn-secondary" onClick={() => downloadCsv("/exportar/clientes", "clientes").catch((e) => setError(e.message))}>Exportar CSV</button>
        <ImportarCsv path="/importar/clientes" etiqueta="Importar CSV" onOk={load} />
        <button className="btn" onClick={() => setShowForm(!showForm)}>
          {showForm ? "Cerrar" : "+ Nuevo cliente"}
        </button>
      </div>

      {error && <div className="error">{error}</div>}

      {showForm && (
        <form onSubmit={(e) => guardar(e, "crear")} className="card" style={{ marginBottom: 20, display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(170px, 1fr))", gap: 12 }}>
          <div>
            <label>Nombre *</label>
            <input required value={form.nombre} onChange={(e) => setForm({ ...form, nombre: e.target.value })} />
          </div>
          <div>
            <label>Tipo doc.</label>
            <select value={form.tipo_documento} onChange={(e) => setForm({ ...form, tipo_documento: e.target.value })}>
              {["CC", "CE", "NIT", "TI", "PASS"].map((t) => (
                <option key={t} value={t}>{t}</option>
              ))}
            </select>
          </div>
          <div>
            <label>Documento</label>
            <input value={form.documento} onChange={(e) => setForm({ ...form, documento: e.target.value })} />
          </div>
          <div>
            <label>Teléfono</label>
            <input value={form.telefono} onChange={(e) => setForm({ ...form, telefono: e.target.value })} />
          </div>
          <div>
            <label>Email</label>
            <input type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
          </div>
          <div>
            <label>Ciudad</label>
            <input value={form.ciudad} onChange={(e) => setForm({ ...form, ciudad: e.target.value })} />
          </div>
          <div>
            <label>Tipo</label>
            <select value={form.tipo} onChange={(e) => setForm({ ...form, tipo: e.target.value })}>
              <option value="ocasional">Ocasional</option>
              <option value="frecuente">Frecuente</option>
              <option value="mayorista">Mayorista</option>
              <option value="institucional">Institucional</option>
            </select>
          </div>
          <div>
            <label>Límite de crédito</label>
            <input type="number" value={form.limite_credito} onChange={(e) => setForm({ ...form, limite_credito: e.target.value })} />
          </div>
          <div style={{ display: "flex", alignItems: "flex-end" }}>
            <button className="btn" type="submit">Guardar</button>
          </div>
        </form>
      )}

      <input placeholder="Buscar por nombre, documento o teléfono..." value={q} onChange={(e) => setQ(e.target.value)} style={{ maxWidth: 400, marginBottom: 16 }} />

      <table className="table">
        <thead>
          <tr>
            <th>Nombre</th>
            <th>Documento</th>
            <th>Teléfono</th>
            <th>Tipo</th>
            <th>Crédito</th>
            <th>Estado</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {clientes.map((c) => (
            <tr key={c.id}>
              <td>{c.nombre}</td>
              <td>{c.tipo_documento} {c.documento}</td>
              <td>{c.telefono}</td>
              <td>
                <span className={`badge ${c.tipo === "mayorista" ? "badge-warning" : c.tipo === "frecuente" ? "badge-info" : c.tipo === "institucional" ? "badge-success" : "badge-secondary"}`}>{c.tipo}</span>
              </td>
              <td>{formatMoney(c.creditos)}</td>
              <td><span className={`badge ${c.activo ? "badge-success" : "badge-danger"}`}>{c.activo ? "Activo" : "Inactivo"}</span></td>
              <td>
                <button className="btn btn-ghost" title="Ver detalle" onClick={() => abrirDetalle(c)}>👁</button>
                <button className="btn btn-ghost" title="Editar" onClick={() => setEditando({ ...c })}>✏️</button>
              </td>
            </tr>
          ))}
          {clientes.length === 0 && (
            <tr><td colSpan={7} className="muted" style={{ textAlign: "center", padding: 20 }}>Sin clientes</td></tr>
          )}
        </tbody>
      </table>

      {editando && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,.45)", display: "grid", placeItems: "center", zIndex: 1100, padding: 20 }}>
          <form onSubmit={(e) => guardar(e, "editar")} className="card" style={{ width: "min(640px, 100%)", maxHeight: "86vh", overflow: "auto", display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(170px, 1fr))", gap: 12 }}>
            <div style={{ gridColumn: "1 / -1", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <h2 style={{ fontSize: 17 }}>Editar cliente · #{editando.id}</h2>
              <button type="button" className="btn btn-ghost" onClick={() => setEditando(null)}>✕</button>
            </div>
            <div><label>Nombre</label><input value={editando.nombre} onChange={(e) => setECampo("nombre", e.target.value)} /></div>
            <div>
              <label>Tipo doc.</label>
              <select value={editando.tipo_documento || "CC"} onChange={(e) => setECampo("tipo_documento", e.target.value)}>
                {["CC", "CE", "NIT", "TI", "PASS"].map((t) => <option key={t} value={t}>{t}</option>)}
              </select>
            </div>
            <div><label>Documento</label><input value={editando.documento || ""} onChange={(e) => setECampo("documento", e.target.value)} /></div>
            <div><label>Teléfono</label><input value={editando.telefono || ""} onChange={(e) => setECampo("telefono", e.target.value)} /></div>
            <div><label>Email</label><input type="email" value={editando.email || ""} onChange={(e) => setECampo("email", e.target.value)} /></div>
            <div><label>Ciudad</label><input value={editando.ciudad || ""} onChange={(e) => setECampo("ciudad", e.target.value)} /></div>
            <div>
              <label>Tipo</label>
              <select value={editando.tipo} onChange={(e) => setECampo("tipo", e.target.value)}>
                <option value="ocasional">Ocasional</option>
                <option value="frecuente">Frecuente</option>
                <option value="mayorista">Mayorista</option>
                <option value="institucional">Institucional</option>
              </select>
            </div>
            <div><label>Límite de crédito</label><input type="number" value={editando.limite_credito || ""} onChange={(e) => setECampo("limite_credito", e.target.value)} /></div>
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

      {detalle && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,.45)", display: "grid", placeItems: "center", zIndex: 1150, padding: 20 }}>
          <div className="card" style={{ width: "min(560px, 100%)", maxHeight: "86vh", overflow: "auto" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
              <h2 style={{ fontSize: 18 }}>{detalle.nombre} <span className="muted" style={{ fontSize: 13 }}>#{detalle.id}</span></h2>
              <button className="btn btn-ghost" onClick={() => setDetalle(null)}>✕</button>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, fontSize: 14 }}>
              <div><span className="muted">Documento: </span>{detalle.tipo_documento} {detalle.documento}</div>
              <div><span className="muted">Tipo: </span><span className={`badge ${detalle.tipo === "institucional" ? "badge-success" : "badge-secondary"}`}>{detalle.tipo}</span></div>
              <div><span className="muted">Teléfono: </span>{detalle.telefono || "—"}</div>
              <div><span className="muted">Email: </span>{detalle.email || "—"}</div>
              <div><span className="muted">Ciudad: </span>{detalle.ciudad || "—"}</div>
              <div><span className="muted">Dirección: </span>{detalle.direccion || "—"}</div>
              <div><span className="muted">Límite crédito: </span>{formatMoney(detalle.limite_credito)}</div>
              <div><span className="muted">Crédito usado: </span><strong>{formatMoney(detalle.creditos)}</strong></div>
              <div><span className="muted">Estado: </span><span className={`badge ${detalle.activo ? "badge-success" : "badge-danger"}`}>{detalle.activo ? "Activo" : "Inactivo"}</span></div>
            </div>
            {detalle.tipo === "institucional" && (
              <div className="chip" style={{ marginTop: 14 }}>Este cliente aplica precios institucionales en las ventas.</div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}