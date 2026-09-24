import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext.jsx";
import api from "../api.js";

export default function CambiarPassword() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [actual, setActual] = useState("");
  const [nueva, setNueva] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    if (nueva.length < 8) {
      setError("La nueva contraseña debe tener al menos 8 caracteres");
      return;
    }
    if (nueva !== confirm) {
      setError("Las contraseñas no coinciden");
      return;
    }
    setLoading(true);
    try {
      await api("/auth/cambiar-password", {
        method: "POST",
        body: JSON.stringify({ password_actual: actual, password_nueva: nueva }),
      });
      localStorage.setItem("debe_cambiar_password", "0");
      navigate("/");
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "linear-gradient(130deg, #043a2c 0%, #065f46 45%, #0b7a59 100%)",
      }}
    >
      <div
        style={{
          width: 420,
          background: "var(--card)",
          color: "var(--ink)",
          padding: 36,
          borderRadius: 26,
          boxShadow: "0 40px 80px -30px rgba(2,6,23,.7)",
          border: "1px solid var(--line)",
        }}
      >
        <div style={{ textAlign: "center", marginBottom: 22 }}>
          <div
            style={{
              width: 56,
              height: 56,
              margin: "0 auto 12px",
              borderRadius: 17,
              display: "grid",
              placeItems: "center",
              fontSize: 26,
              color: "#fff",
              background: "linear-gradient(135deg, #0e9f74, #0b7a59)",
            }}
          >
            🔐
          </div>
          <h1 style={{ fontSize: 22, fontWeight: 800 }}>Cambia tu contraseña</h1>
          <p style={{ color: "var(--muted)", fontSize: 13, marginTop: 6 }}>
            Por seguridad, debes definir una nueva contraseña antes de usar el sistema
            {user ? ` · ${user.nombre}` : ""}.
          </p>
        </div>

        {error && <div className="error">{error}</div>}

        <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div>
            <label>Contraseña actual</label>
            <input type="password" required value={actual} onChange={(e) => setActual(e.target.value)} placeholder="••••••••" autoFocus />
          </div>
          <div>
            <label>Nueva contraseña (mín. 8 caracteres)</label>
            <input type="password" required minLength={8} value={nueva} onChange={(e) => setNueva(e.target.value)} placeholder="••••••••" />
          </div>
          <div>
            <label>Confirmar nueva contraseña</label>
            <input type="password" required minLength={8} value={confirm} onChange={(e) => setConfirm(e.target.value)} placeholder="••••••••" />
          </div>
          <button className="btn" type="submit" disabled={loading} style={{ padding: 13, borderRadius: 14 }}>
            {loading ? "Guardando…" : "Guardar contraseña"}
          </button>
        </form>

        <div style={{ textAlign: "center", marginTop: 16 }}>
          <button
            className="btn-ghost"
            style={{ background: "none", border: "none", color: "var(--muted)", fontSize: 12.5, cursor: "pointer", textDecoration: "underline" }}
            onClick={logout}
          >
            Cerrar sesión
          </button>
        </div>
      </div>
    </div>
  );
}