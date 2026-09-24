import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "../api.js";
import { useAuth } from "../contexts/AuthContext.jsx";

function beep() {
  try {
    const AC = window.AudioContext || window.webkitAudioContext;
    if (!AC) return;
    const ctx = beep.ctx || (beep.ctx = new AC());
    const ahora = ctx.currentTime;
    [880, 1174, 1568].forEach((f, i) => {
      const o = ctx.createOscillator();
      const g = ctx.createGain();
      o.connect(g);
      g.connect(ctx.destination);
      o.frequency.value = f;
      o.type = "sine";
      g.gain.setValueAtTime(0.0001, ahora + i * 0.14);
      g.gain.exponentialRampToValueAtTime(0.22, ahora + i * 0.14 + 0.02);
      g.gain.exponentialRampToValueAtTime(0.0001, ahora + i * 0.14 + 0.13);
      o.start(ahora + i * 0.14);
      o.stop(ahora + i * 0.14 + 0.15);
    });
  } catch {}
}

function mmss(ms) {
  const s = Math.max(0, Math.floor(ms / 1000));
  const m = Math.floor(s / 60);
  const h = Math.floor(m / 60);
  return h > 0
    ? `${h}:${String(m % 60).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`
    : `${String(m).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
}

export default function Cocina() {
  const navigate = useNavigate();
  const { logout } = useAuth();
  const [comandas, setComandas] = useState([]);
  const [err, setErr] = useState("");
  const [, setPulso] = useState(0);
  const [flash, setFlash] = useState("");
  const [fs, setFs] = useState(false);
  const llegada = useRef({});
  const prevIds = useRef([]);

  useEffect(() => {
    const onFs = () => setFs(Boolean(document.fullscreenElement));
    document.addEventListener("fullscreenchange", onFs);
    const onKey = (e) => {
      if (e.key === "Escape" && document.fullscreenElement) {
        document.exitFullscreen().catch(() => {});
      }
    };
    window.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("fullscreenchange", onFs);
      window.removeEventListener("keydown", onKey);
    };
  }, []);

  async function load() {
    try {
      const data = await api("/restaurante/comandas?estado=abierta");
      setComandas(data || []);
    } catch (e) {
      setErr(e.message);
    }
  }

  useEffect(() => {
    load();
    const t = setInterval(load, 5000);
    const reloj = setInterval(() => setPulso((x) => x + 1), 1000);
    return () => {
      clearInterval(t);
      clearInterval(reloj);
    };
  }, []);

  useEffect(() => {
    const conPend = comandas.map((c) => c.id);
    const nuevas = conPend.filter((x) => !prevIds.current.includes(x));
    if (nuevas.length > 0 && prevIds.current.length > 0) {
      beep();
      setFlash(`🔔 Nueva comanda · ${comandas.filter((c) => nuevas.includes(c.id)).map((c) => c.numero).join(", ")}`);
      setTimeout(() => setFlash(""), 6000);
    }
    prevIds.current = conPend;
    comandas.forEach((c) => {
      if (!llegada.current[c.id]) llegada.current[c.id] = Date.now();
    });
  }, [comandas]);

  const pendientes = comandas.filter((c) => c.estado === "abierta" && c.detalle.some((d) => !d.entregado));
  const contador = pendientes.reduce((n, c) => n + c.detalle.filter((d) => !d.entregado).length, 0);

  async function listo(comandaId, lineaId) {
    setErr("");
    try {
      await api(`/restaurante/comandas/${comandaId}/lineas/${lineaId}/servir`, { method: "POST" });
      load();
    } catch (e) {
      setErr(e.message);
    }
  }

  async function servirTodo(comandaId) {
    const c = pendientes.find((x) => x.id === comandaId);
    if (!c) return;
    for (const d of c.detalle.filter((x) => !x.entregado)) {
      await listo(comandaId, d.id);
    }
  }

  const fullscreen = () => {
    if (document.fullscreenElement) document.exitFullscreen();
    else document.documentElement.requestFullscreen?.();
  };

  const salirSesion = () => {
    logout();
    navigate("/login");
  };

  return (
    <div className="cocina">
      <style>{`
        .cocina { background: #0b1220; min-height: 100vh; color: #f1f5f9; padding: 16px; }
        .cocina .kds-barra { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; margin-bottom: 16px; }
        .cocina .kds-titulo { font-size: 26px; font-weight: 900; letter-spacing: .5px; }
        .cocina .kds-reloj { font-family: 'Courier New', monospace; font-size: 30px; font-weight: 800; background: #111c33; border: 1px solid #1e293b; border-radius: 12px; padding: 4px 16px; }
        .cocina .kds-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(285px, 1fr)); gap: 14px; }
        .cocina .kds-comanda { background: #111c33; border: 2px solid #1e293b; border-radius: 14px; padding: 12px; display: flex; flex-direction: column; gap: 8px; }
        .cocina .kds-comanda.nueva { border-color: #f59e0b; box-shadow: 0 0 0 3px rgba(245,158,11,.25); }
        .cocina .kds-comanda.vieja { border-color: #ef4444; }
        .cocina .kds-cab { display: flex; justify-content: space-between; align-items: center; gap: 8px; }
        .cocina .kds-num { font-size: 17px; font-weight: 900; }
        .cocina .kds-mesa { font-size: 13px; color: #94a3b8; }
        .cocina .kds-tiempo { font-family: 'Courier New', monospace; font-size: 15px; font-weight: 800; padding: 3px 10px; border-radius: 999px; background: #1e293b; }
        .cocina .kds-tiempo.tardado { background: #ef4444; color: #fff; }
        .cocina .kds-linea { background: #0b1220; border: 1px solid #1e293b; border-radius: 10px; padding: 8px 10px; display: flex; align-items: center; gap: 10px; }
        .cocina .kds-linea.listo { background: #052018; border-color: #34d399; }
        .cocina .kds-cant { font-size: 18px; font-weight: 900; color: #34d399; }
        .cocina .kds-prod { font-size: 14px; font-weight: 700; flex: 1; }
        .cocina .kds-pre { color: #f59e0b; font-size: 12.5px; font-weight: 600; }
        .cocina .kds-btn { background: #34d399; color: #052018; border: 0; border-radius: 10px; padding: 10px 14px; font-weight: 800; font-size: 15px; cursor: pointer; }
        .cocina .kds-btn:hover { filter: brightness(1.08); }
        .cocina .kds-vacio { display: grid; place-items: center; min-height: 55vh; color: #64748b; font-size: 26px; }
        .cocina .kds-flash { position: fixed; top: 14px; left: 50%; transform: translateX(-50%); background: #f59e0b; color: #0b1220; font-weight: 800; padding: 12px 22px; border-radius: 999px; z-index: 300; box-shadow: 0 12px 30px rgba(0,0,0,.5); font-size: 17px; animation: kds-in .3s ease; }
        @keyframes kds-in { from { opacity: 0; transform: translate(-50%, -14px); } }
      `}</style>

      <div className="kds-barra">
        <div>
          <div className="kds-titulo">👨‍🍳 Pantalla de Cocina</div>
          <div style={{ color: "#94a3b8", fontSize: 13 }}>
            {contador} líneas pendientes · {pendientes.length} comandas activas · actualiza cada 5 s
          </div>
        </div>
        <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
          <span className="kds-reloj">{new Date().toLocaleTimeString("es-CO")}</span>
          <button className="btn btn-sm" onClick={() => navigate("/")}>🏠 Salir de módulo</button>
          <button className="btn btn-sm" onClick={salirSesion} title="Cerrar sesión y volver al login">⎋ Cerrar sesión</button>
          <button className="btn btn-sm" onClick={() => document.location.reload()}>↻</button>
          <button className="btn btn-sm" onClick={fullscreen}>{fs ? "⤓ Salir pantalla" : "⛶ Pantalla"}</button>
        </div>
      </div>

      {flash && <div className="kds-flash">{flash}</div>}
      {err && <div className="error">{err}</div>}

      {pendientes.length === 0 ? (
        <div className="kds-vacio">🎉 Cocina al día</div>
      ) : (
        <div className="kds-grid">
          {pendientes.map((c) => {
            const mins = (Date.now() - (llegada.current[c.id] || Date.now())) / 60000;
            return (
              <div key={c.id} className={`kds-comanda${mins >= 15 ? " vieja" : mins >= 6 ? " nueva" : ""}`}>
                <div className="kds-cab">
                  <span className="kds-num">{c.numero}</span>
                  <span className={`kds-tiempo${mins >= 12 ? " tardado" : ""}`}>{mmss(Date.now() - (llegada.current[c.id] || Date.now()))}</span>
                </div>
                <div className="kds-mesa">
                  🪑 Mesa {c.mesa_id}
                  {c.detalle.some((d) => d.entregado) && (
                    <span style={{ color: "#34d399", marginLeft: 8 }}>✔ {c.detalle.filter((d) => d.entregado).length} lista(s)</span>
                  )}
                </div>
                {c.detalle.map((d) =>
                  d.entregado ? (
                    <div key={d.id} className="kds-linea listo">
                      <span className="kds-cant">✓</span>
                      <span className="kds-prod" style={{ textDecoration: "line-through", color: "#34d399" }}>{d.cantidad} × {d.producto || `#${d.producto_id}`}</span>
                    </div>
                  ) : (
                    <div key={d.id} className="kds-linea">
                      <span className="kds-cant">{d.cantidad}</span>
                      <span className="kds-prod">
                        {d.producto || `#${d.producto_id}`}
                        {d.preparacion && <div className="kds-pre">🔥 {d.preparacion}</div>}
                      </span>
                      <button className="kds-btn" onClick={() => listo(c.id, d.id)}>✓ Listo</button>
                    </div>
                  )
                )}
                {c.detalle.some((d) => !d.entregado) && (
                  <button className="btn btn-sm" style={{ marginTop: 4 }} onClick={() => servirTodo(c.id)}>
                    🍽️ Servir todo
                  </button>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}