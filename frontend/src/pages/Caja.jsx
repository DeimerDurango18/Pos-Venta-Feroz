import { useEffect, useState } from "react";
import api, { openWindow } from "../api.js";

function formatMoney(n) {
  return new Intl.NumberFormat("es-CO", {
    style: "currency",
    currency: "COP",
    maximumFractionDigits: 0,
  }).format(n || 0);
}

export default function Caja() {
  const [cajas, setCajas] = useState([]);
  const [usuarios, setUsuarios] = useState([]);
  const [gastos, setGastos] = useState([]);
  const [turnos, setTurnos] = useState([]);
  const [filtroCaja, setFiltroCaja] = useState("");
  const [detalle, setDetalle] = useState(null);
  const [error, setError] = useState("");
  const [form, setForm] = useState({ caja_id: "", saldo_inicial: "" });
  const [formGasto, setFormGasto] = useState({ categoria: "", concepto: "", monto: "" });
  const [mov, setMov] = useState({ apertura_caja_id: "", tipo: "ingreso", concepto: "", monto: "", medio: "efectivo" });
  const [arq, setArq] = useState({ apertura_id: "", efectivo_contado: "", observacion: "" });
  const [trf, setTrf] = useState({ origen_apertura_id: "", destino_apertura_id: "", monto: "", concepto: "Transferencia de efectivo" });
  const [cj, setCj] = useState({ apertura_id: "", usuario_id: "" });

  useEffect(() => {
    api("/organizacion/cajas").then(setCajas).catch(() => {});
    api("/usuarios").then(setUsuarios).catch(() => {});
    api("/caja/gastos").then(setGastos).catch(() => {});
    api("/caja/turnos").then(setTurnos).catch(() => {});
  }, []);

  const abiertas = turnos.filter((t) => t.estado === "abierta");

  function cargarTurnos() {
    api("/caja/turnos").then(setTurnos).catch(() => {});
  }

  async function abrir(e) {
    e.preventDefault();
    setError("");
    try {
      await api("/caja/apertura", {
        method: "POST",
        body: JSON.stringify({ caja_id: Number(form.caja_id), saldo_inicial: Number(form.saldo_inicial) || 0 }),
      });
      setForm({ caja_id: "", saldo_inicial: "" });
      cargarTurnos();
    } catch (err) {
      setError(err.message);
    }
  }

  async function crearGasto(e) {
    e.preventDefault();
    setError("");
    try {
      await api("/caja/gastos", {
        method: "POST",
        body: JSON.stringify({
          empresa_id: 1,
          sucursal_id: 1,
          categoria: formGasto.categoria,
          concepto: formGasto.concepto,
          monto: Number(formGasto.monto),
        }),
      });
      setFormGasto({ categoria: "", concepto: "", monto: "" });
      api("/caja/gastos").then(setGastos);
    } catch (err) {
      setError(err.message);
    }
  }

  async function verTurno(id) {
    setError("");
    try {
      const d = await api(`/caja/${id}`);
      setDetalle(d);
    } catch (err) {
      setError(err.message);
    }
  }

  async function cerrar(id) {
    setError("");
    if (!window.confirm("¿Cerrar la caja? Se calculará el saldo de cierre y quedará cerrada.")) return;
    try {
      await api(`/caja/${id}/cierre`, { method: "POST" });
      cargarTurnos();
      if (detalle?.id === id) verTurno(id);
    } catch (err) {
      setError(err.message);
    }
  }

  async function registrarMov(e) {
    e.preventDefault();
    setError("");
    try {
      await api("/caja/movimientos", {
        method: "POST",
        body: JSON.stringify({
          apertura_caja_id: Number(mov.apertura_caja_id),
          tipo: mov.tipo,
          concepto: mov.concepto,
          monto: Number(mov.monto),
          medio: mov.medio,
        }),
      });
      setMov({ apertura_caja_id: "", tipo: "ingreso", concepto: "", monto: "", medio: "efectivo" });
      if (detalle?.id === Number(mov.apertura_caja_id)) verTurno(mov.apertura_caja_id);
    } catch (err) {
      setError(err.message);
    }
  }

  async function arqueo(e) {
    e.preventDefault();
    setError("");
    try {
      const r = await api(`/caja/arqueo?apertura_id=${arq.apertura_id}&efectivo_contado=${Number(arq.efectivo_contado)}&observacion=${encodeURIComponent(arq.observacion || "")}`, { method: "POST" });
      setArq({ apertura_id: "", efectivo_contado: "", observacion: "" });
      setError("");
      setMov((prev) => ({ ...prev, apertura_caja_id: "" }));
      window.alert(`Arqueo: esperado ${formatMoney(r.esperado)}, contado ${formatMoney(r.contado)}, diferencia ${formatMoney(r.diferencia)}`);
      if (detalle?.id === Number(arq.apertura_id)) verTurno(arq.apertura_id);
    } catch (err) {
      setError(err.message);
    }
  }

  async function transferir(e) {
    e.preventDefault();
    setError("");
    try {
      await api("/caja/transferir", {
        method: "POST",
        body: JSON.stringify({
          origen_apertura_id: Number(trf.origen_apertura_id),
          destino_apertura_id: Number(trf.destino_apertura_id),
          monto: Number(trf.monto),
          concepto: trf.concepto,
        }),
      });
      setTrf({ origen_apertura_id: "", destino_apertura_id: "", monto: "", concepto: "Transferencia de efectivo" });
      if (detalle) verTurno(detalle.id);
    } catch (err) {
      setError(err.message);
    }
  }

  async function cambiarCajero(e) {
    e.preventDefault();
    setError("");
    try {
      await api(`/caja/${cj.apertura_id}/cajero`, {
        method: "PATCH",
        body: JSON.stringify({ usuario_id: Number(cj.usuario_id) }),
      });
      setCj({ apertura_id: "", usuario_id: "" });
      cargarTurnos();
      if (detalle?.id === Number(cj.apertura_id)) verTurno(cj.apertura_id);
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div className="page">
      <div className="page-header">
        <h1>Caja</h1>
      </div>

      {error && <div className="error">{error}</div>}

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))", gap: 16, marginBottom: 24 }}>
        <form onSubmit={abrir} className="card">
          <h2 style={{ fontSize: 16, marginBottom: 12 }}>Abrir caja</h2>
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <div>
              <label>Caja</label>
              <select required value={form.caja_id} onChange={(e) => setForm({ ...form, caja_id: e.target.value })}>
                <option value="">Seleccionar...</option>
                {cajas.map((c) => (
                  <option key={c.id} value={c.id}>{c.nombre}</option>
                ))}
              </select>
            </div>
            <div>
              <label>Saldo inicial</label>
              <input type="number" value={form.saldo_inicial} onChange={(e) => setForm({ ...form, saldo_inicial: e.target.value })} />
            </div>
            <button className="btn" type="submit">Abrir caja</button>
          </div>
        </form>

        <form onSubmit={registrarMov} className="card">
          <h2 style={{ fontSize: 16, marginBottom: 12 }}>Ingreso / egreso de fondo</h2>
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <div>
              <label>Apertura (caja abierta)</label>
              <select required value={mov.apertura_caja_id} onChange={(e) => setMov({ ...mov, apertura_caja_id: e.target.value })}>
                <option value="">Seleccionar...</option>
                {abiertas.map((t) => (
                  <option key={t.id} value={t.id}>#{t.id} · {t.caja_nombre} · {t.cajero_nombre}</option>
                ))}
              </select>
            </div>
            <div>
              <label>Tipo</label>
              <select value={mov.tipo} onChange={(e) => setMov({ ...mov, tipo: e.target.value })}>
                <option value="ingreso">Ingreso</option>
                <option value="egreso">Egreso</option>
                <option value="gasto">Gasto</option>
                <option value="retiro">Retiro</option>
              </select>
            </div>
            <div><label>Concepto</label><input required value={mov.concepto} onChange={(e) => setMov({ ...mov, concepto: e.target.value })} /></div>
            <div><label>Monto</label><input required type="number" value={mov.monto} onChange={(e) => setMov({ ...mov, monto: e.target.value })} /></div>
            <div>
              <label>Medio</label>
              <select value={mov.medio} onChange={(e) => setMov({ ...mov, medio: e.target.value })}>
                <option value="efectivo">Efectivo</option>
                <option value="tarjeta">Tarjeta</option>
                <option value="transferencia">Transferencia</option>
              </select>
            </div>
            <button className="btn" type="submit">Registrar</button>
          </div>
        </form>

        <form onSubmit={arqueo} className="card">
          <h2 style={{ fontSize: 16, marginBottom: 12 }}>Arqueo de caja</h2>
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <div>
              <label>Apertura (caja abierta)</label>
              <select required value={arq.apertura_id} onChange={(e) => setArq({ ...arq, apertura_id: e.target.value })}>
                <option value="">Seleccionar...</option>
                {abiertas.map((t) => (
                  <option key={t.id} value={t.id}>#{t.id} · {t.caja_nombre}</option>
                ))}
              </select>
            </div>
            <div><label>Efectivo contado *</label><input required type="number" value={arq.efectivo_contado} onChange={(e) => setArq({ ...arq, efectivo_contado: e.target.value })} /></div>
            <div><label>Observación</label><input value={arq.observacion} onChange={(e) => setArq({ ...arq, observacion: e.target.value })} /></div>
            <button className="btn" type="submit">Registrar arqueo</button>
          </div>
        </form>

        <form onSubmit={transferir} className="card">
          <h2 style={{ fontSize: 16, marginBottom: 12 }}>Transferir entre cajas</h2>
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <div>
              <label>Origen</label>
              <select required value={trf.origen_apertura_id} onChange={(e) => setTrf({ ...trf, origen_apertura_id: e.target.value })}>
                <option value="">Origen...</option>
                {abiertas.map((t) => (
                  <option key={t.id} value={t.id}>#{t.id} · {t.caja_nombre}</option>
                ))}
              </select>
            </div>
            <div>
              <label>Destino</label>
              <select required value={trf.destino_apertura_id} onChange={(e) => setTrf({ ...trf, destino_apertura_id: e.target.value })}>
                <option value="">Destino...</option>
                {abiertas.filter((t) => t.id !== Number(trf.origen_apertura_id)).map((t) => (
                  <option key={t.id} value={t.id}>#{t.id} · {t.caja_nombre}</option>
                ))}
              </select>
            </div>
            <div><label>Monto</label><input required type="number" value={trf.monto} onChange={(e) => setTrf({ ...trf, monto: e.target.value })} /></div>
            <div><label>Concepto</label><input value={trf.concepto} onChange={(e) => setTrf({ ...trf, concepto: e.target.value })} /></div>
            <button className="btn" type="submit">Transferir</button>
          </div>
        </form>

        <form onSubmit={cambiarCajero} className="card">
          <h2 style={{ fontSize: 16, marginBottom: 12 }}>Cambiar cajero</h2>
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <div>
              <label>Apertura (caja abierta)</label>
              <select required value={cj.apertura_id} onChange={(e) => setCj({ ...cj, apertura_id: e.target.value })}>
                <option value="">Seleccionar...</option>
                {abiertas.map((t) => (
                  <option key={t.id} value={t.id}>#{t.id} · {t.cajero_nombre}</option>
                ))}
              </select>
            </div>
            <div>
              <label>Nuevo cajero</label>
              <select required value={cj.usuario_id} onChange={(e) => setCj({ ...cj, usuario_id: e.target.value })}>
                <option value="">Seleccionar...</option>
                {usuarios.map((u) => (
                  <option key={u.id} value={u.id}>{u.nombre} ({u.username})</option>
                ))}
              </select>
            </div>
            <button className="btn" type="submit">Cambiar</button>
          </div>
        </form>

        <form onSubmit={crearGasto} className="card">
          <h2 style={{ fontSize: 16, marginBottom: 12 }}>Registrar gasto</h2>
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <div>
              <label>Categoría</label>
              <input required value={formGasto.categoria} onChange={(e) => setFormGasto({ ...formGasto, categoria: e.target.value })} placeholder="p.ej. Servicios" />
            </div>
            <div>
              <label>Concepto</label>
              <input required value={formGasto.concepto} onChange={(e) => setFormGasto({ ...formGasto, concepto: e.target.value })} />
            </div>
            <div>
              <label>Monto</label>
              <input required type="number" value={formGasto.monto} onChange={(e) => setFormGasto({ ...formGasto, monto: e.target.value })} />
            </div>
            <button className="btn" type="submit">Guardar gasto</button>
          </div>
        </form>
      </div>

      <h2 style={{ fontSize: 18, marginBottom: 12 }}>Turnos de caja</h2>
      <div style={{ marginBottom: 10, maxWidth: 300 }}>
        <select value={filtroCaja} onChange={(e) => setFiltroCaja(e.target.value)}>
          <option value="">Todas las cajas</option>
          {cajas.map((c) => (
            <option key={c.id} value={c.id}>{c.nombre}</option>
          ))}
        </select>
      </div>
      <table className="table" style={{ marginBottom: 24 }}>
        <thead>
          <tr>
            <th>#</th>
            <th>Caja</th>
            <th>Cajero</th>
            <th>Saldo inicial</th>
            <th>Saldo cierre</th>
            <th>Estado</th>
            <th>Abierta el</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {turnos
            .filter((t) => !filtroCaja || String(t.caja_id) === filtroCaja)
            .map((t) => (
              <tr key={t.id}>
                <td>{t.id}</td>
                <td>{t.caja_nombre || t.caja_id}</td>
                <td>{t.cajero_nombre || "—"}</td>
                <td>{formatMoney(t.saldo_inicial)}</td>
                <td>{formatMoney(t.saldo_cierre)}</td>
                <td><span className={`badge ${t.estado === "abierta" ? "badge-success" : "badge-warning"}`}>{t.estado}</span></td>
                <td>{t.created_at ? new Date(t.created_at).toLocaleString() : "—"}</td>
                <td>
                  <button className="btn btn-sm" onClick={() => verTurno(t.id)}>Ver</button>{" "}
                  {t.estado === "abierta" && (
                    <>
                      <button className="btn btn-sm btn-danger" onClick={() => cerrar(t.id)}>Cerrar</button>{" "}
                    </>
                  )}
                  <button className="btn btn-sm" onClick={() => openWindow(`/caja/${t.id}/cierre/reporte`)}>🖨️ Resumen</button>
                </td>
              </tr>
            ))}
          {turnos.length === 0 && <tr><td colSpan={8} className="muted" style={{ textAlign: "center", padding: 20 }}>Sin turnos</td></tr>}
        </tbody>
      </table>

      {detalle && (
        <div style={{ marginBottom: 24 }}>
          <h2 style={{ fontSize: 18, marginBottom: 12 }}>
            Detalle apertura #{detalle.id} · {detalle.cajero} ·{" "}
            <span className={`badge ${detalle.estado === "abierta" ? "badge-success" : "badge-warning"}`}>{detalle.estado}</span>{" "}
            <button className="btn btn-sm" onClick={() => openWindow(`/caja/${detalle.id}/cierre/reporte`)}>🖨️ Imprimir resumen</button>
          </h2>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))", gap: 12, marginBottom: 16 }}>
            <div className="card sec"><b>Saldo inicial</b><div>{formatMoney(detalle.saldo_inicial)}</div></div>
            <div className="card sec"><b>Saldo cierre</b><div>{formatMoney(detalle.saldo_cierre)}</div></div>
            <div className="card sec"><b>Total movimientos</b><div>{detalle.movimientos.length}</div></div>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 18 }}>
            <div>
              <h3 className="card-title" style={{ fontSize: 15 }}>Movimientos</h3>
              <table className="table">
                <thead><tr><th>Tipo</th><th>Concepto</th><th>Monto</th><th>Medio</th></tr></thead>
                <tbody>
                  {detalle.movimientos.map((m) => (
                    <tr key={m.id}>
                      <td><span className={`badge ${m.tipo === "ingreso" ? "badge-success" : "badge-danger"}`}>{m.tipo}</span></td>
                      <td>{m.concepto}</td>
                      <td>{formatMoney(m.monto)}</td>
                      <td>{m.medio}</td>
                    </tr>
                  ))}
                  {detalle.movimientos.length === 0 && <tr><td colSpan={4} className="muted" style={{ textAlign: "center", padding: 16 }}>Sin movimientos</td></tr>}
                </tbody>
              </table>
            </div>
            <div>
              <h3 className="card-title" style={{ fontSize: 15 }}>Arqueos</h3>
              <table className="table">
                <thead><tr><th>Contado</th><th>Esperado</th><th>Diferencia</th><th>Observación</th></tr></thead>
                <tbody>
                  {detalle.arqueos.map((a, i) => (
                    <tr key={i}>
                      <td>{formatMoney(a.contado)}</td>
                      <td>{formatMoney(a.esperado)}</td>
                      <td className={a.diferencia < 0 ? "text-danger" : ""}>{formatMoney(a.diferencia)}</td>
                      <td>{a.observacion || "—"}</td>
                    </tr>
                  ))}
                  {detalle.arqueos.length === 0 && <tr><td colSpan={4} className="muted" style={{ textAlign: "center", padding: 16 }}>Sin arqueos</td></tr>}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      <h2 style={{ fontSize: 18, marginBottom: 12 }}>Gastos registrados</h2>
      <table className="table">
        <thead>
          <tr>
            <th>Fecha</th>
            <th>Categoría</th>
            <th>Concepto</th>
            <th>Monto</th>
            <th>Medio</th>
          </tr>
        </thead>
        <tbody>
          {gastos.map((g) => (
            <tr key={g.id}>
              <td>{g.created_at ? new Date(g.created_at).toLocaleString() : "—"}</td>
              <td>{g.categoria}</td>
              <td>{g.concepto}</td>
              <td>{formatMoney(g.monto)}</td>
              <td>{g.medio}</td>
            </tr>
          ))}
          {gastos.length === 0 && (
            <tr><td colSpan={5} className="muted" style={{ textAlign: "center", padding: 20 }}>Sin gastos</td></tr>
          )}
        </tbody>
      </table>
    </div>
  );
}