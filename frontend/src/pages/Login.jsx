import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext.jsx";
import api from "../api.js";

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const tokenInicial = params.get("token") || "";
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [showRec, setShowRec] = useState(false);
  const [recEmail, setRecEmail] = useState("");
  const [recMsg, setRecMsg] = useState("");
  const [recErr, setRecErr] = useState("");
  const [rstToken, setRstToken] = useState(tokenInicial);
  const [rstPass, setRstPass] = useState("");

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await login(username, password);
      navigate("/");
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function recuperar(e) {
    e.preventDefault();
    setRecErr("");
    setRecMsg("");
    try {
      const r = await api("/auth/recuperar", { method: "POST", body: JSON.stringify({ email: recEmail }) });
      setRecMsg(r.mensaje);
    } catch (err) {
      setRecErr(err.message);
    }
  }

  async function restablecer(e) {
    e.preventDefault();
    setRecErr("");
    setRecMsg("");
    try {
      const r = await api("/auth/restablecer", { method: "POST", body: JSON.stringify({ token: rstToken, nueva_password: rstPass }) });
      setRecMsg(r.mensaje || "Contraseña restablecida. Ya puedes ingresar.");
      setRstToken("");
      setRstPass("");
    } catch (err) {
      setRecErr(err.message);
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
        position: "relative",
        overflow: "hidden",
      }}
    >
      <div
        style={{
          position: "absolute",
          width: 420,
          height: 420,
          borderRadius: "50%",
          background: "radial-gradient(circle, rgba(251,191,36,.35), transparent 62%)",
          top: "-120px",
          left: "-80px",
        }}
      />
      <div
        style={{
          position: "absolute",
          width: 460,
          height: 460,
          borderRadius: "50%",
          background: "radial-gradient(circle, rgba(255,255,255,.14), transparent 60%)",
          bottom: "-160px",
          right: "-100px",
        }}
      />

      <div
        style={{
          width: 410,
          position: "relative",
          background: "var(--card)",
          color: "var(--ink)",
          padding: 36,
          borderRadius: 26,
          boxShadow: "0 40px 80px -30px rgba(2,6,23,.7)",
          border: "1px solid var(--line)",
          transition: "background .25s ease",
        }}
      >
        <div style={{ textAlign: "center", marginBottom: 26 }}>
          <div
            style={{
              width: 64,
              height: 64,
              margin: "0 auto 14px",
              borderRadius: 19,
              display: "grid",
              placeItems: "center",
              fontSize: 30,
              color: "#fff",
              background: "linear-gradient(135deg, #0e9f74, #0b7a59)",
              boxShadow: "0 14px 30px -10px rgba(14,159,116,.6)",
            }}
          >
            🛒
          </div>
          <h1 style={{ fontSize: 27, fontWeight: 800, letterSpacing: "-0.03em" }}>
            POS <span style={{ background: "linear-gradient(120deg,#0e9f74,#3eb489)", WebkitBackgroundClip: "text", backgroundClip: "text", color: "transparent" }}>Feroz</span>
          </h1>
          <p style={{ color: "var(--muted)", fontSize: 13.5, marginTop: 4 }}>
            Sistema de Punto de Venta · Tiendas locales
          </p>
        </div>

        {error && <div className="error">{error}</div>}

        <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div>
            <label>Usuario</label>
            <input value={username} onChange={(e) => setUsername(e.target.value)} placeholder="admin" autoFocus />
          </div>
          <div>
            <label>Contraseña</label>
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="••••••••" />
          </div>
          <button className="btn" type="submit" disabled={loading} style={{ padding: 13, borderRadius: 14 }}>
            {loading ? "Ingresando…" : "Ingresar"}
          </button>
        </form>

        <div style={{ display: "flex", gap: 8, justifyContent: "center", marginTop: 22, flexWrap: "wrap" }}>
          <span className="chip">👤 admin · usuario de gestión</span>
          <span className="chip">🛍️ cajero · punto de venta</span>
        </div>

        <div style={{ marginTop: 14, textAlign: "center" }}>
          <button
            className="btn-ghost"
            style={{ background: "none", border: "none", color: "var(--muted)", fontSize: 12.5, cursor: "pointer", textDecoration: "underline" }}
            onClick={() => setShowRec(!showRec)}
          >
            {showRec ? "Cerrar" : "¿Olvidaste tu contraseña?"}
          </button>
        </div>

        {showRec && (
          <div className="card sec" style={{ marginTop: 14, padding: 16, display: "grid", gap: 10 }}>
            <h3 style={{ fontSize: 14 }}>Restablecer contraseña</h3>
            {recMsg && <div className="badge-success" style={{ padding: "6px 10px", borderRadius: 6 }}>{recMsg}</div>}
            {recErr && <div className="error">{recErr}</div>}
            <form onSubmit={recuperar} style={{ display: "grid", gap: 8 }}>
              <label>Correo del usuario</label>
              <input type="email" required value={recEmail} onChange={(e) => setRecEmail(e.target.value)} placeholder="usuario@tienda.com" />
              <button className="btn btn-secondary" type="submit">Solicitar recuperación</button>
            </form>
            <form onSubmit={restablecer} style={{ display: "grid", gap: 8, marginTop: 6 }}>
              <label>Restablecer con token</label>
              <input required value={rstToken} onChange={(e) => setRstToken(e.target.value)} placeholder="Token recibido" />
              <input required type="password" minLength={6} value={rstPass} onChange={(e) => setRstPass(e.target.value)} placeholder="Nueva contraseña" />
              <button className="btn" type="submit">Restablecer contraseña</button>
            </form>
          </div>
        )}
      </div>
    </div>
  );
}