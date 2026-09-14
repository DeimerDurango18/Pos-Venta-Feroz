import { useEffect, useState } from "react";
import api from "../api.js";

export default function Seguridad() {
  const [tab, setTab] = useState("roles");
  const [roles, setRoles] = useState([]);
  const [misPermisos, setMisPermisos] = useState(null);
  const [autorizaciones, setAutorizaciones] = useState([]);
  const [error, setError] = useState("");
  const [msg, setMsg] = useState("");
  const [filtro, setFiltro] = useState("");
  const [permisos, setPermisos] = useState([]);
  const [usuarios, setUsuarios] = useState([]);
  const [sesiones, setSesiones] = useState([]);
  const [usrForm, setUsrForm] = useState({ nombre: "", username: "", email: "", password: "", rol_id: "", es_admin: false, vendedor: true });
  const [editUsr, setEditUsr] = useState(null);
  const [vModulo, setVModulo] = useState("");
  const [vAccion, setVAccion] = useState("");
  const [vResultado, setVResultado] = useState(null);

  async function load() {
    api("/seguridad/roles").then(setRoles).catch(() => {});
    api("/seguridad/mi-permisos").then(setMisPermisos).catch(() => {});
    api("/seguridad/permisos").then(setPermisos).catch(() => {});
    api("/usuarios").then(setUsuarios).catch(() => {});
    api("/auth/sesiones").then(setSesiones).catch(() => {});
    refreshAut();
  }

  async function refreshAut() {
    api(`/seguridad/autorizaciones${filtro ? `?estado=${filtro}` : ""}`).then(setAutorizaciones).catch(() => {});
  }

  useEffect(() => {
    load();
  }, []);

  useEffect(() => refreshAut(), [filtro]);

  async function submit(fn, okMsg) {
    setError("");
    setMsg("");
    try {
      await fn();
      setMsg(okMsg);
      load();
    } catch (e) {
      setError(e.message);
    }
  }

  async function sincronizar() {
    await submit(() => api("/seguridad/permisos/sincronizar", { method: "POST" }), "Permisos sincronizados");
  }

  async function resolver(id, accion) {
    await submit(() => api(`/seguridad/autorizaciones/${id}/${accion}`, { method: "POST" }), `Solicitud ${accion === "aprobar" ? "APROBADA" : "RECHAZADA"}`);
  }

  async function togglePermiso(permiso, rol) {
    const tiene = (permiso.roles || []).includes(rol.id);
    setError("");
    setMsg("");
    try {
      if (tiene) {
        await api(`/seguridad/permisos/${permiso.id}/quitar?rol_id=${rol.id}`, { method: "POST" });
      } else {
        await api(`/seguridad/permisos/${permiso.id}/asignar`, { method: "POST", body: JSON.stringify({ roles: [rol.id] }) });
      }
      api("/seguridad/permisos").then(setPermisos).catch(() => {});
      api("/seguridad/roles").then(setRoles).catch(() => {});
    } catch (e) {
      setError(e.message);
    }
  }

  async function crearUsuario(e) {
    e.preventDefault();
    setError("");
    setMsg("");
    try {
      await api("/usuarios", {
        method: "POST",
        body: JSON.stringify({
          empresa_id: 1,
          sucursal_id: 1,
          nombre: usrForm.nombre,
          username: usrForm.username,
          email: usrForm.email || null,
          password: usrForm.password,
          rol_id: usrForm.rol_id ? Number(usrForm.rol_id) : null,
          es_admin: usrForm.es_admin,
          vendedor: usrForm.vendedor,
        }),
      });
      setUsrForm({ nombre: "", username: "", email: "", password: "", rol_id: "", es_admin: false, vendedor: true });
      api("/usuarios").then(setUsuarios).catch(() => {});
      setMsg("Usuario creado");
    } catch (err) {
      setError(err.message);
    }
  }

  async function guardarUsuario(e) {
    e.preventDefault();
    setError("");
    setMsg("");
    try {
      const body = { nombre: editUsr.nombre, email: editUsr.email || null, activo: editUsr.activo, rol_id: editUsr.rol_id ? Number(editUsr.rol_id) : null, sucursal_id: 1 };
      if (editUsr.password) body.password = editUsr.password;
      await api(`/usuarios/${editUsr.id}`, { method: "PUT", body: JSON.stringify(body) });
      setEditUsr(null);
      api("/usuarios").then(setUsuarios).catch(() => {});
      setMsg("Usuario actualizado");
    } catch (err) {
      setError(err.message);
    }
  }

  async function cerrarSesion(id) {
    try {
      await api(`/auth/sesiones/${id}/cerrar`, { method: "POST" });
      api("/auth/sesiones").then(setSesiones).catch(() => {});
      setMsg("Sesión cerrada");
    } catch (e) {
      setError(e.message);
    }
  }

  const badge = (e) => <span className={`badge ${e === "aprobada" ? "badge-success" : e === "rechazada" ? "badge-danger" : ""}`}>{e}</span>;

  return (
    <div className="page">
      <div className="page-header">
        <h1>Seguridad, permisos y autorizaciones</h1>
        <div className="tabs">
          {[["roles", "Roles y permisos"], ["permisos", "Catálogo"], ["usuarios", "Usuarios"], ["sesiones", "Sesiones"], ["aut", "Autorizaciones"], ["mios", "Mis permisos"]].map(([k, l]) => (
            <button key={k} className={`btn ${tab === k ? "btn-primary" : ""}`} onClick={() => setTab(k)}>{l}</button>
          ))}
        </div>
      </div>

      {msg && <div className="badge-success" style={{ display: "inline-block", marginBottom: 8, padding: "6px 10px", borderRadius: 6 }}>{msg}</div>}
      {error && <div className="error">{error}</div>}

      {tab === "roles" && (
        <>
          <button className="btn" style={{ marginBottom: 12 }} onClick={sincronizar}>Sincronizar catálogo de permisos</button>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(340px,1fr))", gap: 14 }}>
            {roles.map((r) => (
              <div key={r.id} className="card" style={{ padding: 14 }}>
                <h3 style={{ marginBottom: 8 }}>{r.nombre}</h3>
                <table className="table">
                  <thead><tr><th>Módulo</th><th>Acción</th></tr></thead>
                  <tbody>
                    {r.permisos.length === 0 && (
                      <tr><td colSpan={2}>Sin permisos asignados.</td></tr>
                    )}
                    {r.permisos.map((p) => (
                      <tr key={p.id}>
                        <td style={{ fontSize: 13 }}>{p.modulo}</td>
                        <td style={{ fontSize: 13 }}>
                          <span className="badge">{p.accion}</span> {p.nombre}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ))}
          </div>
        </>
      )}

      {tab === "permisos" && (
        <>
          <p className="muted" style={{ marginBottom: 12 }}>
            Catálogo completo de permisos. Marca el rol que puede realizar cada acción (admin tiene acceso total por defecto).
          </p>
          <table className="table">
            <thead>
              <tr>
                <th>Módulo</th><th>Acción</th><th>Descripción</th>
                {roles.map((r) => <th key={r.id} style={{ fontSize: 11, textAlign: "center" }}>{r.nombre}</th>)}
              </tr>
            </thead>
            <tbody>
              {permisos.length === 0 && <tr><td colSpan={3 + roles.length}><button className="btn btn-secondary" onClick={sincronizar}>Sincronizar catálogo</button></td></tr>}
              {permisos.map((p) => (
                <tr key={p.id}>
                  <td style={{ fontSize: 13 }}>{p.modulo}</td>
                  <td style={{ fontSize: 13 }}><span className="badge">{p.accion}</span></td>
                  <td className="muted" style={{ fontSize: 12.5 }}>{p.nombre}</td>
                  {roles.map((r) => (
                    <td key={r.id} style={{ textAlign: "center" }}>
                      <input
                        type="checkbox"
                        checked={(p.roles || []).includes(r.id)}
                        onChange={() => togglePermiso(p, r)}
                        disabled={r.nombre === "Administrador"}
                        title={r.nombre === "Administrador" ? "Admin tiene acceso total" : ""}
                      />
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}

      {tab === "usuarios" && (
        <>
          <form onSubmit={crearUsuario} className="card" style={{ padding: 16, marginBottom: 18, display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px,1fr))", gap: 12 }}>
            <div><label>Nombre *</label><input required value={usrForm.nombre} onChange={(e) => setUsrForm({ ...usrForm, nombre: e.target.value })} /></div>
            <div><label>Usuario *</label><input required minLength={3} value={usrForm.username} onChange={(e) => setUsrForm({ ...usrForm, username: e.target.value })} /></div>
            <div><label>Email</label><input type="email" value={usrForm.email} onChange={(e) => setUsrForm({ ...usrForm, email: e.target.value })} /></div>
            <div><label>Contraseña *</label><input type="password" required minLength={6} value={usrForm.password} onChange={(e) => setUsrForm({ ...usrForm, password: e.target.value })} /></div>
            <div>
              <label>Rol</label>
              <select value={usrForm.rol_id} onChange={(e) => setUsrForm({ ...usrForm, rol_id: e.target.value })}>
                <option value="">Cajero (por defecto)</option>
                {roles.map((r) => <option key={r.id} value={r.id}>{r.nombre}</option>)}
              </select>
            </div>
            <div style={{ display: "flex", gap: 14, alignItems: "flex-end" }}>
              <label className="muted" style={{ fontSize: 12.5 }}><input type="checkbox" checked={usrForm.es_admin} onChange={(e) => setUsrForm({ ...usrForm, es_admin: e.target.checked })} /> Admin</label>
              <label className="muted" style={{ fontSize: 12.5 }}><input type="checkbox" checked={usrForm.vendedor} onChange={(e) => setUsrForm({ ...usrForm, vendedor: e.target.checked })} /> Vendedor</label>
            </div>
            <button className="btn" type="submit" style={{ alignSelf: "flex-end" }}>Crear usuario</button>
          </form>

          <table className="table">
            <thead>
              <tr><th>Nombre</th><th>Usuario</th><th>Rol</th><th>Email</th><th>Vendedor</th><th>Activo</th><th></th></tr>
            </thead>
            <tbody>
              {usuarios.map((u) => (
                <tr key={u.id}>
                  <td><b>{u.nombre}</b></td>
                  <td>{u.username}</td>
                  <td>{roles.find((r) => r.id === u.rol_id)?.nombre || "—"}</td>
                  <td className="muted">{u.email || "—"}</td>
                  <td>{u.vendedor ? "Sí" : "No"}</td>
                  <td><span className={`badge ${u.activo ? "badge-success" : "badge-danger"}`}>{u.activo ? "Activo" : "Inactivo"}</span></td>
                  <td><button className="btn btn-secondary" onClick={() => setEditUsr({ id: u.id, nombre: u.nombre, email: u.email || "", rol_id: u.rol_id || "", activo: u.activo, vendedor: u.vendedor, password: "" })}>Editar</button></td>
                </tr>
              ))}
              {usuarios.length === 0 && <tr><td colSpan={7} className="muted" style={{ textAlign: "center", padding: 20 }}>Sin usuarios</td></tr>}
            </tbody>
          </table>
        </>
      )}

      {tab === "sesiones" && (
        <>
          <p className="muted" style={{ marginBottom: 12 }}>Sesiones activas de tu usuario. Puedes cerrarlas desde otro dispositivo.</p>
          <table className="table">
            <thead><tr><th>#</th><th>IP</th><th>Dispositivo / navegador</th><th>Iniciada</th><th></th></tr></thead>
            <tbody>
              {sesiones.map((s) => (
                <tr key={s.id}>
                  <td>{s.id}</td>
                  <td>{s.ip || "—"}</td>
                  <td style={{ fontSize: 12 }}>{s.user_agent || "—"}</td>
                  <td style={{ fontSize: 12 }}>{s.created_at ? new Date(s.created_at).toLocaleString() : "—"}</td>
                  <td><button className="btn btn-danger" onClick={() => cerrarSesion(s.id)}>Cerrar</button></td>
                </tr>
              ))}
              {sesiones.length === 0 && <tr><td colSpan={5} className="muted" style={{ textAlign: "center", padding: 20 }}>Sin sesiones activas</td></tr>}
            </tbody>
          </table>
        </>
      )}

      {editUsr && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,.45)", display: "grid", placeItems: "center", zIndex: 1100, padding: 20 }}>
          <form onSubmit={guardarUsuario} className="card" style={{ width: "min(520px, 100%)" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
              <h3>Editar usuario · {editUsr.username || `#${editUsr.id}`}</h3>
              <button type="button" className="btn btn-ghost" onClick={() => setEditUsr(null)}>✕</button>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px,1fr))", gap: 12 }}>
              <div><label>Nombre</label><input required value={editUsr.nombre} onChange={(e) => setEditUsr({ ...editUsr, nombre: e.target.value })} /></div>
              <div><label>Email</label><input type="email" value={editUsr.email} onChange={(e) => setEditUsr({ ...editUsr, email: e.target.value })} /></div>
              <div>
                <label>Rol</label>
                <select value={String(editUsr.rol_id || "")} onChange={(e) => setEditUsr({ ...editUsr, rol_id: e.target.value ? Number(e.target.value) : "" })}>
                  <option value="">Sin rol</option>
                  {roles.map((r) => <option key={r.id} value={r.id}>{r.nombre}</option>)}
                </select>
              </div>
              <div><label>Nueva contraseña (opcional)</label><input type="password" minLength={6} value={editUsr.password} onChange={(e) => setEditUsr({ ...editUsr, password: e.target.value })} /></div>
            </div>
            <div style={{ display: "flex", gap: 16, marginTop: 12 }}>
              <label className="muted" style={{ fontSize: 12.5 }}><input type="checkbox" checked={!!editUsr.activo} onChange={(e) => setEditUsr({ ...editUsr, activo: e.target.checked })} /> Activo</label>
              <label className="muted" style={{ fontSize: 12.5 }}><input type="checkbox" checked={!!editUsr.vendedor} onChange={(e) => setEditUsr({ ...editUsr, vendedor: e.target.checked })} /> Vendedor</label>
            </div>
            <div style={{ display: "flex", gap: 8, justifyContent: "flex-end", marginTop: 14 }}>
              <button type="button" className="btn btn-secondary" onClick={() => setEditUsr(null)}>Cancelar</button>
              <button className="btn" type="submit">Guardar cambios</button>
            </div>
          </form>
        </div>
      )}

      {tab === "aut" && (
        <>
          <div style={{ display: "flex", gap: 10, marginBottom: 10 }}>
            <select value={filtro} onChange={(e) => setFiltro(e.target.value)} className="btn">
              {["", "pendiente", "aprobada", "rechazada"].map((e) => (
                <option key={e || "todas"} value={e}>{e === "" ? "Todas las solicitudes" : e}</option>
              ))}
            </select>
          </div>
          <table className="table">
            <thead>
              <tr><th>#</th><th>Solicitud</th><th>Solicitante</th><th>Datos</th><th>Estado</th><th>Acciones</th></tr>
            </thead>
            <tbody>
              {autorizaciones.length === 0 && (
                <tr><td colSpan={6}>Sin solicitudes.</td></tr>
              )}
              {autorizaciones.map((a) => (
                <tr key={a.id}>
                  <td>{a.id}</td>
                  <td><b>{a.modulo}/{a.accion}</b> {a.entidad ? `· ${a.entidad}` : ""}</td>
                  <td>{a.solicitante || "-"}</td>
                  <td style={{ fontSize: 12 }}>{a.datos || "-"}</td>
                  <td>{badge(a.estado)}</td>
                  <td>
                    <div style={{ display: "flex", gap: 6 }}>
                      {a.estado === "pendiente" && (
                        <>
                          <button className="btn btn-sm btn-primary" onClick={() => resolver(a.id, "aprobar")}>Aprobar</button>
                          <button className="btn btn-sm" onClick={() => resolver(a.id, "rechazar")}>Rechazar</button>
                        </>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}

      {tab === "mios" && misPermisos && (
        <div className="card" style={{ padding: 16, maxWidth: 640 }}>
          <h3 style={{ marginBottom: 12 }}>Verificar permiso</h3>
          <form
            className="chip"
            style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 16, background: "#f1f0ff" }}
            onSubmit={async (e) => {
              e.preventDefault();
              setError("");
              setVResultado(null);
              try {
                const r = await api(`/seguridad/verificar/${encodeURIComponent(vModulo)}/${encodeURIComponent(vAccion)}`);
                setVResultado(r);
              } catch (err) {
                setError(err.message);
              }
            }}
          >
            <input required className="input" placeholder="módulo (ej: ventas)" value={vModulo} onChange={(e) => setVModulo(e.target.value)} style={{ width: 150 }} />
            <input required className="input" placeholder="acción (ej: crear)" value={vAccion} onChange={(e) => setVAccion(e.target.value)} style={{ width: 150 }} />
            <button className="btn btn-sm" type="submit">Verificar</button>
          </form>
          {vResultado && (
            <p style={{ fontSize: 13.5 }}>
              {vResultado.permitido ? (
                <span className="badge-success" style={{ padding: "4px 10px", borderRadius: 6 }}>✓ Permitido</span>
              ) : (
                <span className="badge-danger" style={{ padding: "4px 10px", borderRadius: 6 }}>✗ Denegado</span>
              )}
              {vResultado.rol && <span className="muted" style={{ marginLeft: 8 }}>Rol: {vResultado.rol}</span>}
            </p>
          )}
          {misPermisos.es_admin ? (
            <p><b>Administrador:</b> acceso total (todos los permisos otorgados).</p>
          ) : (
            <>
              <h3 style={{ marginBottom: 8 }}>Permisos del rol actual</h3>
              <table className="table">
                <thead><tr><th>Módulo</th><th>Acción</th></tr></thead>
                <tbody>
                  {misPermisos.permisos.length === 0 && (
                    <tr><td colSpan={2}>Sin permisos asignados.</td></tr>
                  )}
                  {misPermisos.permisos.map((p, i) => (
                    <tr key={i}>
                      <td>{p.modulo}</td>
                      <td><span className="badge">{p.accion}</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}
        </div>
      )}
    </div>
  );
}