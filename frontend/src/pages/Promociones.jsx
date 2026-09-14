import { useEffect, useState } from "react";
import api from "../api.js";

const TIPOS = [
  { value: "porcentaje", label: "% de descuento" },
  { value: "valor", label: "Descuento por valor" },
  { value: "2x1", label: "2x1" },
  { value: "3x2", label: "3x2" },
];

export default function Promociones() {
  const [promos, setPromos] = useState([]);
  const [productos, setProductos] = useState([]);
  const [error, setError] = useState("");
  const [form, setForm] = useState({
    nombre: "",
    tipo: "porcentaje",
    valor: "",
    aplica_a: "general",
    desde: "",
    hasta: "",
    descripcion: "",
  });
  const [ids, setIds] = useState([]);
  const [editing, setEditing] = useState(null);
  const [editIds, setEditIds] = useState([]);

  async function load() {
    api("/promociones").then(setPromos).catch(() => {});
    api("/productos").then(setProductos).catch(() => {});
  }

  useEffect(() => {
    load();
  }, []);

  function toggle(p) {
    api(`/promociones/${p.id}/toggle`, { method: "POST" }).then(() => load()).catch((e) => setError(e.message));
  }

  async function crear(e) {
    e.preventDefault();
    setError("");
    try {
      await api("/promociones", {
        method: "POST",
        body: JSON.stringify({
          empresa_id: 1,
          nombre: form.nombre,
          tipo: form.tipo,
          valor: Number(form.valor || 0),
          aplica_a: form.aplica_a,
          desde: form.desde || null,
          hasta: form.hasta || null,
          descripcion: form.descripcion,
          productos: ids.map((i) => ({ producto_id: Number(i) })),
        }),
      });
      setForm({ nombre: "", tipo: "porcentaje", valor: "", aplica_a: "general", desde: "", hasta: "", descripcion: "" });
      setIds([]);
      load();
    } catch (e) {
      setError(e.message);
    }
  }

  function abrirEdicion(p) {
    setEditing({
      id: p.id,
      nombre: p.nombre,
      tipo: p.tipo || "porcentaje",
      valor: p.valor ?? "",
      aplica_a: p.aplica_a || "general",
      desde: p.desde || "",
      hasta: p.hasta || "",
      descripcion: p.descripcion || "",
    });
    setEditIds((p.productos || []).map((x) => String(x.producto_id)));
  }

  async function guardarEdicion(e) {
    e.preventDefault();
    setError("");
    try {
      await api(`/promociones/${editing.id}`, {
        method: "PUT",
        body: JSON.stringify({
          empresa_id: 1,
          nombre: editing.nombre,
          tipo: editing.tipo,
          valor: Number(editing.valor || 0),
          aplica_a: editing.aplica_a,
          desde: editing.desde || null,
          hasta: editing.hasta || null,
          descripcion: editing.descripcion,
          productos: editIds.map((i) => ({ producto_id: Number(i) })),
        }),
      });
      setEditing(null);
      setEditIds([]);
      load();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div className="page">
      <div className="page-header"><h1>Promociones</h1></div>
      {error && <div className="error">{error}</div>}

      <form onSubmit={crear} className="card" style={{ marginBottom: 20 }}>
        <h3 style={{ marginBottom: 12 }}>Nueva promoción</h3>
        <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginBottom: 12 }}>
          <div style={{ flex: 1, minWidth: 160 }}>
            <label>Nombre *</label>
            <input required value={form.nombre} onChange={(e) => setForm({ ...form, nombre: e.target.value })} />
          </div>
          <div>
            <label>Tipo</label>
            <select value={form.tipo} onChange={(e) => setForm({ ...form, tipo: e.target.value })}>
              {TIPOS.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
            </select>
          </div>
          <div>
            <label>{form.tipo === "porcentaje" ? "Porcentaje" : form.tipo === "valor" ? "Valor" : "Valor (0)"}</label>
            <input type="number" step="0.01" value={form.valor} onChange={(e) => setForm({ ...form, valor: e.target.value })} />
          </div>
          <div>
            <label>Aplica a</label>
            <select value={form.aplica_a} onChange={(e) => setForm({ ...form, aplica_a: e.target.value })}>
              <option value="general">Toda la tienda</option>
              <option value="producto">Productos específicos</option>
            </select>
          </div>
        </div>
        <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginBottom: 12 }}>
          <div><label>Desde</label><input type="date" value={form.desde} onChange={(e) => setForm({ ...form, desde: e.target.value })} /></div>
          <div><label>Hasta</label><input type="date" value={form.hasta} onChange={(e) => setForm({ ...form, hasta: e.target.value })} /></div>
          <div style={{ flex: 1, minWidth: 200 }}><label>Descripción</label><input value={form.descripcion} onChange={(e) => setForm({ ...form, descripcion: e.target.value })} /></div>
        </div>
        {form.aplica_a === "producto" && (
          <div style={{ marginBottom: 12 }}>
            <label>Productos en promoción</label>
            <select multiple style={{ height: 120 }} onChange={(e) => setIds(Array.from(e.target.selectedOptions).map((o) => o.value))}>
              {productos.map((p) => <option key={p.id} value={p.id}>{p.nombre}</option>)}
            </select>
          </div>
        )}
        <button className="btn" type="submit">Crear promoción</button>
      </form>

      <table className="table">
        <thead>
          <tr><th>Nombre</th><th>Tipo</th><th>Valor</th><th>Alcance</th><th>Vigencia</th><th>Productos</th><th>Activa</th><th></th></tr>
        </thead>
        <tbody>
          {promos.map((p) => (
            <tr key={p.id}>
              <td><strong>{p.nombre}</strong></td>
              <td><span className="badge badge-info">{p.tipo}</span></td>
              <td>{p.tipo === "porcentaje" ? `${p.valor}%` : p.tipo === "valor" ? formatMoney(p.valor) : "—"}</td>
              <td>{p.aplica_a}</td>
              <td>{p.desde && p.hasta ? `${p.desde} → ${p.hasta}` : "Permanente"}</td>
              <td>{p.productos?.length || 0}</td>
              <td><span className={`badge ${p.activa ? "badge-success" : "badge-danger"}`}>{p.activa ? "Sí" : "No"}</span></td>
              <td>
                <button className="btn btn-secondary" onClick={() => toggle(p)}>
                  {p.activa ? "Desactivar" : "Activar"}
                </button>
                <button className="btn btn-secondary" style={{ marginLeft: 6 }} onClick={() => abrirEdicion(p)}>Editar</button>
              </td>
            </tr>
          ))}
          {promos.length === 0 && <tr><td colSpan={8} className="muted" style={{ textAlign: "center", padding: 20 }}>Sin promociones</td></tr>}
        </tbody>
      </table>

      {editing && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,.45)", display: "grid", placeItems: "center", zIndex: 1100, padding: 20 }}>
          <form onSubmit={guardarEdicion} className="card" style={{ width: "min(640px, 100%)" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
              <h3>Editar promoción · #{editing.id}</h3>
              <button type="button" className="btn btn-ghost" onClick={() => setEditing(null)}>✕</button>
            </div>
            <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginBottom: 12 }}>
              <div style={{ flex: 1, minWidth: 160 }}>
                <label>Nombre *</label>
                <input required value={editing.nombre} onChange={(e) => setEditing({ ...editing, nombre: e.target.value })} />
              </div>
              <div>
                <label>Tipo</label>
                <select value={editing.tipo} onChange={(e) => setEditing({ ...editing, tipo: e.target.value })}>
                  {TIPOS.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
                </select>
              </div>
              <div>
                <label>{editing.tipo === "porcentaje" ? "Porcentaje" : editing.tipo === "valor" ? "Valor" : "Valor (0)"}</label>
                <input type="number" step="0.01" value={editing.valor} onChange={(e) => setEditing({ ...editing, valor: e.target.value })} />
              </div>
              <div>
                <label>Aplica a</label>
                <select value={editing.aplica_a} onChange={(e) => setEditing({ ...editing, aplica_a: e.target.value })}>
                  <option value="general">Toda la tienda</option>
                  <option value="producto">Productos específicos</option>
                </select>
              </div>
              <div><label>Desde</label><input type="date" value={editing.desde} onChange={(e) => setEditing({ ...editing, desde: e.target.value })} /></div>
              <div><label>Hasta</label><input type="date" value={editing.hasta} onChange={(e) => setEditing({ ...editing, hasta: e.target.value })} /></div>
              <div style={{ flex: 1, minWidth: 220 }}><label>Descripción</label><input value={editing.descripcion} onChange={(e) => setEditing({ ...editing, descripcion: e.target.value })} /></div>
            </div>
            {editing.aplica_a === "producto" && (
              <div style={{ marginBottom: 12 }}>
                <label>Productos en promoción</label>
                <select multiple style={{ height: 120 }} value={editIds} onChange={(e) => setEditIds(Array.from(e.target.selectedOptions).map((o) => o.value))}>
                  {productos.map((p) => <option key={p.id} value={p.id}>{p.nombre}</option>)}
                </select>
              </div>
            )}
            <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
              <button type="button" className="btn btn-secondary" onClick={() => setEditing(null)}>Cancelar</button>
              <button className="btn btn-primary" type="submit">Guardar cambios</button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}

function formatMoney(n) {
  return new Intl.NumberFormat("es-CO", { style: "currency", currency: "COP", maximumFractionDigits: 0 }).format(n || 0);
}