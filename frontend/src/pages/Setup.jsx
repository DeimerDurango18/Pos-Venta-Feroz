import { useEffect, useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import api from "../api.js";
import { useAuth } from "../contexts/AuthContext.jsx";

const TIPOS_NEGOCIO = [
  { id: "general", label: "General / Otros", emoji: "🏪" },
  { id: "ferreteria", label: "Ferretería", emoji: "🔧" },
  { id: "restaurante", label: "Restaurante", emoji: "🍽️" },
  { id: "minimarket", label: "Minimarket / Tienda", emoji: "🛒" },
];

export default function Setup() {
  const navigate = useNavigate();
  const { login } = useAuth();
  const [estado, setEstado] = useState(null);
  const [form, setForm] = useState({
    nombre_negocio: "",
    nit: "",
    tipo_negocio: "general",
    admin_nombre: "",
    admin_usuario: "",
    admin_email: "",
    admin_clave: "",
  });
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const [cargando, setCargando] = useState(false);

  useEffect(() => {
    api("/setup/estado")
      .then(setEstado)
      .catch(() => setEstado({ pendiente: false }));
  }, []);

  async function registrar(e) {
    e.preventDefault();
    setError("");
    setOk("");
    setCargando(true);
    try {
      await api("/setup/registro", { method: "POST", body: JSON.stringify(form) });
      await login(form.admin_usuario.trim(), form.admin_clave);
      navigate("/pos");
    } catch (err) {
      setError(err.message);
    } finally {
      setCargando(false);
    }
  }

  const set = (k) => (ev) => setForm((f) => ({ ...f, [k]: ev.target.value }));

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "linear-gradient(130deg, #043a2c 0%, #065f46 45%, #0b7a59 100%)",
        padding: 24,
      }}
    >
      <div className="card" style={{ width: 480, maxWidth: "100%", padding: 26, boxShadow: "0 40px 80px -30px rgba(2,6,23,.6)" }}>
        <div style={{ fontSize: 40, textAlign: "center" }}>🛒</div>
        <h1 style={{ textAlign: "center", margin: "8px 0 4px" }}>Punto de Venta</h1>
        {estado && !estado.pendiente && (
          <div style={{ textAlign: "center", marginBottom: 14 }}>
            <p className="muted" style={{ marginBottom: 12 }}>
              El sistema ya tiene un negocio configurado ({estado.empresas} empresa, {estado.usuarios} usuario
              {estado.usuarios !== 1 ? "s" : ""}).
            </p>
            <Link className="btn" style={{ textDecoration: "none", display: "inline-block" }} to="/login">
              Ingresar
            </Link>
          </div>
        )}

        {(!estado || estado.pendiente) && (
          <>
            <p className="muted" style={{ textAlign: "center", marginBottom: 16 }}>
              Crea tu POS en 1 minuto y empieza a vender el mismo día.
            </p>
            <form onSubmit={registrar} style={{ display: "grid", gap: 10 }}>
              <label style={{ fontSize: 12, color: "#6b7280", fontWeight: 700 }}>
                Nombre del negocio *
                <input value={form.nombre_negocio} onChange={set("nombre_negocio")} placeholder="Mi Tienda" required />
              </label>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
                <label style={{ fontSize: 12, color: "#6b7280", fontWeight: 700 }}>
                  NIT *
                  <input value={form.nit} onChange={set("nit")} placeholder="900000000" required />
                </label>
                <label style={{ fontSize: 12, color: "#6b7280", fontWeight: 700 }}>
                  Tipo de negocio
                  <select value={form.tipo_negocio} onChange={set("tipo_negocio")}>
                    {TIPOS_NEGOCIO.map((t) => (
                      <option key={t.id} value={t.id}>
                        {t.emoji} {t.label}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
                <label style={{ fontSize: 12, color: "#6b7280", fontWeight: 700 }}>
                  Tu nombre
                  <input value={form.admin_nombre} onChange={set("admin_nombre")} placeholder="Administrador" />
                </label>
                <label style={{ fontSize: 12, color: "#6b7280", fontWeight: 700 }}>
                  Usuario *
                  <input value={form.admin_usuario} onChange={set("admin_usuario")} placeholder="admin" required />
                </label>
              </div>
              <label style={{ fontSize: 12, color: "#6b7280", fontWeight: 700 }}>
                Correo (opcional)
                <input type="email" value={form.admin_email} onChange={set("admin_email")} placeholder="tucorreo@empresa.com" />
              </label>
              <label style={{ fontSize: 12, color: "#6b7280", fontWeight: 700 }}>
                Contraseña * (mínimo 6 caracteres)
                <input type="password" value={form.admin_clave} onChange={set("admin_clave")} placeholder="••••••••" required minLength={6} />
              </label>
              {error && <div className="error">{error}</div>}
              {ok && <div className="badge-success" style={{ padding: 8, borderRadius: 6, textAlign: "center" }}>{ok}</div>}
              <button className="btn" style={{ width: "100%", padding: 12 }} disabled={cargando}>
                {cargando ? "Creando…" : "🚀 Crear mi POS gratis (prueba Esencial)"}
              </button>
              <div style={{ textAlign: "center", fontSize: 12.5 }}>
                <Link to="/login">Ya tengo cuenta →</Link>
              </div>
            </form>
          </>
        )}
      </div>
    </div>
  );
}