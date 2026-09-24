import { useEffect, useState } from "react";
import api from "../api.js";

function formatMoney(n) {
  return new Intl.NumberFormat("es-CO", {
    style: "currency",
    currency: "COP",
    maximumFractionDigits: 0,
  }).format(n || 0);
}

const ETIQUETA_ESTADO = {
  activo: ["Activo", "badge-success"],
  pagado: ["Pagado", "badge-info"],
  cancelado: ["Cancelado", "badge-danger"],
  vencido: ["Vencido", "badge-warning"],
};

export default function LinksPago() {
  const [links, setLinks] = useState([]);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ descripcion: "", monto: "", medio: "", vence_dias: "7" });

  async function load() {
    try {
      setLinks(await api("/links-pago"));
    } catch (e) {
      setError(e.message);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function crear(e) {
    e.preventDefault();
    setError("");
    setOk("");
    try {
      const creado = await api("/links-pago", {
        method: "POST",
        body: JSON.stringify({
          empresa_id: 1,
          descripcion: form.descripcion.trim(),
          monto: Number(form.monto) || 0,
          medio: form.medio,
          vence_dias: Number(form.vence_dias) || null,
        }),
      });
      setForm({ descripcion: "", monto: "", medio: "", vence_dias: "7" });
      setShowForm(false);
      setOk(`Link creado. Compártelo para cobrar ${formatMoney(creado.monto)}.`);
      load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function pagar(link) {
    setError("");
    try {
      await api(`/links-pago/${link.id}/pagar`, { method: "POST" });
      load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function cancelar(link) {
    setError("");
    if (!window.confirm(`¿Cancelar el link "${link.descripcion || link.token}"?`)) return;
    try {
      await api(`/links-pago/${link.id}/cancelar`, { method: "POST" });
      load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function copiar(link) {
    if (!link.url) return setError("Configura `pos.url_publica` en Configuración para generar enlaces compartibles.");
    try {
      await navigator.clipboard.writeText(link.url);
      setOk("Enlace copiado al portapapeles.");
    } catch {
      setError("No se pudo copiar.");
    }
  }

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>🔗 Links de pago</h1>
          <p className="muted">Crea un enlace de cobro y compártelo por WhatsApp: el cliente paga con QR (Nequi, Daviplata o Bre-B) y te envía el comprobante.</p>
        </div>
        <button className="btn btn-primary" onClick={() => setShowForm((s) => !s)}>
          {showForm ? "Cerrar" : "+ Crear link"}
        </button>
      </div>

      {error && <div className="alert alert-danger">{error}</div>}
      {ok && <div className="alert alert-success">{ok}</div>}

      {showForm && (
        <div className="card" style={{ padding: 18, marginBottom: 16 }}>
          <h2>Nuevo link de cobro</h2>
          <form onSubmit={crear} style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(200px,1fr))", gap: 12, marginTop: 12 }}>
            <div>
              <label>Concepto / descripción</label>
              <input type="text" value={form.descripcion} onChange={(e) => setForm({ ...form, descripcion: e.target.value })} placeholder="Ej: Pedido #123" />
            </div>
            <div>
              <label>Monto a cobrar ($)</label>
              <input type="number" min="1" step="any" value={form.monto} onChange={(e) => setForm({ ...form, monto: e.target.value })} placeholder="0" />
            </div>
            <div>
              <label>Medio sugerido (opcional)</label>
              <select value={form.medio} onChange={(e) => setForm({ ...form, medio: e.target.value })}>
                <option value="">Cualquiera</option>
                <option value="efectivo">Efectivo</option>
                <option value="nequi">Nequi</option>
                <option value="daviplata">Daviplata</option>
                <option value="breb">Bre-B</option>
                <option value="tarjeta">Tarjeta</option>
                <option value="transferencia">Transferencia</option>
              </select>
            </div>
            <div>
              <label>Vigencia (días)</label>
              <input type="number" min="1" value={form.vence_dias} onChange={(e) => setForm({ ...form, vence_dias: e.target.value })} />
            </div>
            <div style={{ display: "flex", alignItems: "flex-end", gap: 8 }}>
              <button className="btn btn-success" disabled={!form.monto && !form.descripcion}>
                Crear link
              </button>
            </div>
          </form>
        </div>
      )}

      <div className="card">
        <table className="table">
          <thead>
            <tr>
              <th>#</th>
              <th>Concepto</th>
              <th>Monto</th>
              <th>Medio</th>
              <th>Visitas</th>
              <th>Estado</th>
              <th style={{ textAlign: "right" }}>Acciones</th>
            </tr>
          </thead>
          <tbody>
            {links.length === 0 && (
              <tr>
                <td colSpan={7} className="muted" style={{ textAlign: "center", padding: 24 }}>
                  Aún no hay links de pago.
                </td>
              </tr>
            )}
            {links.map((link) => {
              const [etq, cls] = ETIQUETA_ESTADO[link.estado] || [link.estado, "badge"];
              const inactivo = link.estado !== "activo";
              return (
                <tr key={link.id} style={{ opacity: inactivo ? 0.6 : 1 }}>
                  <td>#{link.id}</td>
                  <td>
                    <div>{link.descripcion || <span className="muted">—</span>}</div>
                    <div className="muted" style={{ fontSize: 12 }}>
                      {link.token}
                    </div>
                  </td>
                  <td style={{ fontWeight: 700 }}>{formatMoney(link.monto)}</td>
                  <td>{link.medio || <span className="muted">cualquiera</span>}</td>
                  <td>{link.visitas || 0}</td>
                  <td>
                    <span className={`badge ${cls}`}>{etq}</span>
                  </td>
                  <td style={{ textAlign: "right", whiteSpace: "nowrap" }}>
                    <button className="btn btn-ghost btn-sm" onClick={() => copiar(link)} title="Copiar enlace">
                      Copiar
                    </button>
                    {link.url && (
                      <a className="btn btn-ghost btn-sm" href={link.url} target="_blank" rel="noreferrer" title="Abrir página de pago">
                        Ver
                      </a>
                    )}
                    {link.estado === "activo" && (
                      <>
                        <button className="btn btn-success btn-sm" onClick={() => pagar(link)}>
                          Cobrado
                        </button>
                        <button className="btn btn-danger btn-sm" onClick={() => cancelar(link)}>
                          Cancelar
                        </button>
                      </>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}