import { useEffect, useState } from "react";
import api from "../api.js";

export default function Sistema() {
  const [errores, setErrores] = useState([]);
  const [tabla, setTabla] = useState([]);
  const [filtro, setFiltro] = useState({ modulo: "", resuelto: "" });
  const [error, setError] = useState("");
  const [msg, setMsg] = useState("");
  const [sim, setSim] = useState({ modulo: "test", mensaje: "Simulación manual desde el sistema" });

  function load() {
    const params = new URLSearchParams();
    if (filtro.modulo) params.set("modulo", filtro.modulo);
    if (filtro.resuelto !== "") params.set("resuelto", filtro.resuelto);
    const qs = params.toString();
    api(`/sistema/errores${qs ? `?${qs}` : ""}`)
      .then((r) => {
        setErrores(r);
        setTabla(r);
      })
      .catch((e) => setError(e.message));
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filtro]);

  async function simular(e) {
    e.preventDefault();
    setError("");
    setMsg("");
    try {
      await api("/sistema/errores/simular", {
        method: "POST",
        body: JSON.stringify({ modulo: sim.modulo || "test", mensaje: sim.mensaje }),
      });
      setMsg("Error simulado y registrado.");
      load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function resolver(id) {
    setError("");
    setMsg("");
    try {
      await api(`/sistema/errores/${id}/resolver`, { method: "PATCH" });
      setMsg("Error marcado como resuelto.");
      load();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div className="page">
      <div className="page-header">
        <h1>Sistema · Registro de errores</h1>
      </div>

      {error && <div className="error">{error}</div>}
      {msg && <div className="chip" style={{ marginBottom: 12, display: "inline-block" }}>{msg}</div>}

      <div className="card" style={{ marginBottom: 20, display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))", gap: 12 }}>
        <div>
          <label>Filtrar por módulo</label>
          <input placeholder="Ej: ventas, productos, transportes... (vacío = todos)" value={filtro.modulo} onChange={(e) => setFiltro({ ...filtro, modulo: e.target.value })} />
        </div>
        <div>
          <label>Estado</label>
          <select value={filtro.resuelto} onChange={(e) => setFiltro({ ...filtro, resuelto: e.target.value })}>
            <option value="">Todos</option>
            <option value="false">Sin resolver</option>
            <option value="true">Resueltos</option>
          </select>
        </div>
      </div>

      <h2 style={{ fontSize: 17, marginBottom: 12 }}>Simular error (prueba)</h2>
      <form onSubmit={simular} className="card" style={{ marginBottom: 24, display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))", gap: 12 }}>
        <div>
          <label>Módulo</label>
          <select value={sim.modulo} onChange={(e) => setSim({ ...sim, modulo: e.target.value })}>
            {["test", "ventas", "inventario", "facturacion", "productos"].map((m) => (
              <option key={m} value={m}>{m}</option>
            ))}
          </select>
        </div>
        <div>
          <label>Mensaje</label>
          <input value={sim.mensaje} onChange={(e) => setSim({ ...sim, mensaje: e.target.value })} />
        </div>
        <div style={{ display: "flex", alignItems: "flex-end" }}>
          <button className="btn" type="submit">Simular</button>
        </div>
      </form>

      <h2 style={{ fontSize: 17, marginBottom: 12 }}>{tabla.length} errores registrados</h2>
      <table className="table">
        <thead>
          <tr>
            <th>ID</th>
            <th>Fecha</th>
            <th>Módulo</th>
            <th>Endpoint</th>
            <th>Mensaje</th>
            <th>Estado</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {tabla.map((r) => (
            <tr key={r.id}>
              <td>#{r.id}</td>
              <td>{r.created_at ? new Date(r.created_at).toLocaleString() : "—"}</td>
              <td><span className="badge">{r.modulo || "—"}</span></td>
              <td className="muted">{r.endpoint || "—"}</td>
              <td title={r.traceback || ""} style={{ maxWidth: 380, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{r.mensaje}</td>
              <td>
                <span className={`badge ${r.resuelto ? "badge-success" : "badge-danger"}`}>
                  {r.resuelto ? "Resuelto" : "Pendiente"}
                </span>
              </td>
              <td>
                {!r.resuelto && (
                  <button className="btn btn-sm" onClick={() => resolver(r.id)}>Marcar resuelto</button>
                )}
              </td>
            </tr>
          ))}
          {tabla.length === 0 && (
            <tr><td colSpan={7} className="muted" style={{ textAlign: "center", padding: 20 }}>No hay errores registrados.</td></tr>
          )}
        </tbody>
      </table>
    </div>
  );
}