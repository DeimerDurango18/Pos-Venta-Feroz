import { useEffect, useState } from "react";
import api from "../api.js";
import { KpiCard, ChartCard, Donut, ProgressList, formatMoney } from "../components/ui.jsx";

export default function Fidelizacion() {
  const [tab, setTab] = useState("cupones");
  const [resumen, setResumen] = useState(null);
  const [cupones, setCupones] = useState([]);
  const [bonos, setBonos] = useState([]);
  const [tarjetas, setTarjetas] = useState([]);
  const [clientes, setClientes] = useState([]);
  const [puntos, setPuntos] = useState([]);
  const [historial, setHistorial] = useState([]);
  const [error, setError] = useState("");
  const [msg, setMsg] = useState("");
  const [form, setForm] = useState({
    codigo: "", tipo: "valor", valor: 0, usos_max: 1, cliente_id: "", vigencia_hasta: "", descripcion: "",
  });
  const [bonoForm, setBonoForm] = useState({ cliente_id: "", codigo: "", valor_total: 0, motivo: "" });
  const [tarjForm, setTarjForm] = useState({ cliente_id: "", codigo: "", saldo: 0 });
  const [ajuste, setAjuste] = useState({ cliente_id: "", delta: 0, motivo: "" });

  async function load() {
    api("/fidelizacion/resumen").then(setResumen).catch(() => {});
    api("/fidelizacion/cupones").then(setCupones).catch((e) => setError(e.message));
    api("/fidelizacion/bonos").then(setBonos).catch(() => {});
    api("/fidelizacion/tarjetas-regalo").then(setTarjetas).catch(() => {});
    api("/fidelizacion/puntos").then(setPuntos).catch(() => {});
    api("/clientes").then(setClientes).catch(() => {});
  }

  useEffect(() => load(), []);

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

  async function crearCupon(e) {
    e.preventDefault();
    submit(
      () =>
        api("/fidelizacion/cupones", {
          method: "POST",
          body: JSON.stringify({ ...form, cliente_id: form.cliente_id ? Number(form.cliente_id) : null }),
        }),
      "Cupón creado"
    );
  }

  async function toggleCupon(id) {
    submit(() => api(`/fidelizacion/cupones/${id}/toggle`, { method: "POST" }), "Cupón actualizado");
  }

  async function crearBono(e) {
    e.preventDefault();
    submit(
      () => api("/fidelizacion/bonos", { method: "POST", body: JSON.stringify({ ...bonoForm, cliente_id: Number(bonoForm.cliente_id) }) }),
      "Bono creado"
    );
  }

  async function crearTarjeta(e) {
    e.preventDefault();
    submit(
      () => api("/fidelizacion/tarjetas-regalo", { method: "POST", body: JSON.stringify({ ...tarjForm, cliente_id: Number(tarjForm.cliente_id) }) }),
      "Tarjeta creada"
    );
  }

  async function recargar(id, monto) {
    submit(() => api(`/fidelizacion/tarjetas-regalo/${id}/recargar?monto=${monto}`, { method: "POST" }), "Tarjeta recargada");
  }

  async function consumirBono(b) {
    const monto = window.prompt(`Consumir bono ${b.codigo}\nSaldo disponible: $${(b.saldo || 0).toLocaleString("es-CO")}`, String(b.saldo || 0));
    if (monto === null || monto === "" || Number(monto) <= 0) return;
    submit(() => api(`/fidelizacion/bonos/${b.id}/consumir?monto=${Number(monto)}`, { method: "POST" }), "Bono consumido");
  }

  async function consumirTarjeta(t) {
    const monto = window.prompt(`Consumir tarjeta ${t.codigo}\nSaldo disponible: $${(t.saldo || 0).toLocaleString("es-CO")}`, String(t.saldo || 0));
    if (monto === null || monto === "" || Number(monto) <= 0) return;
    submit(() => api(`/fidelizacion/tarjetas-regalo/${t.id}/consumir?monto=${Number(monto)}`, { method: "POST" }), "Tarjeta consumida");
  }

  async function ajustarPuntos(e) {
    e.preventDefault();
    await submit(
      () => api("/fidelizacion/puntos/ajustar", { method: "POST", body: JSON.stringify({ ...ajuste, cliente_id: Number(ajuste.cliente_id), delta: Number(ajuste.delta) }) }),
      "Puntos ajustados"
    );
    if (ajuste.cliente_id) api(`/fidelizacion/puntos/historial/${ajuste.cliente_id}`).then(setHistorial).catch(() => {});
  }

  const selCliente = (
    <select value={form.cliente_id} onChange={(e) => setForm({ ...form, cliente_id: e.target.value })}>
      <option value="">Cualquier cliente</option>
      {clientes.map((c) => (
        <option key={c.id} value={c.id}>{c.nombre}</option>
      ))}
    </select>
  );

  return (
    <div className="page">
      <div className="hero" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 16, flexWrap: "wrap" }}>
        <div>
          <h1>Fidelización de clientes</h1>
          <p>Programa de lealtad, cupones, bonos, tarjetas de regalo y puntos por consumo.</p>
        </div>
        <div className="hero-actions">
          <button className="btn" onClick={() => setTab("cupones")}>🎟️ Cupones</button>
          <button className="btn" onClick={() => setTab("bonos")}>🎁 Bonos</button>
          <button className="btn" onClick={() => setTab("puntos")}>⭐ Puntos</button>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(190px,1fr))", gap: 16, marginBottom: 16 }}>
        <KpiCard label="Puntos totales" value={(resumen?.puntos_total ?? 0).toLocaleString("es-CO")} icon="⭐" accent="#f59e0b" sub={`${resumen?.clientes_con_puntos ?? 0} clientes`} />
        <KpiCard label="Cupones activos" value={resumen?.cupones_activos ?? 0} icon="🎟️" accent="#ef4444" />
        <KpiCard label="Bonos activos" value={resumen?.bonos_activos ?? 0} icon="🎁" accent="#10b981" />
        <KpiCard label="Tarjetas activas" value={resumen?.tarjetas_activas ?? 0} icon="💳" accent="#f59e0b" />
        <KpiCard label="Saldo en tarjetas" value={formatMoney(resumen?.saldo_tarjetas ?? 0)} icon="💰" accent="#22d3ee" />
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px,1fr))", gap: 18, marginBottom: 18 }}>
        <ChartCard title="Composición del programa" subtitle="Distribución de activos de fidelización" height={240}>
          <Donut
            data={[
              { name: "Cupones", value: resumen?.cupones_activos ?? 0 },
              { name: "Bonos", value: resumen?.bonos_activos ?? 0 },
              { name: "Tarjetas", value: resumen?.tarjetas_activas ?? 0 },
            ]}
            centerLabel="Activos"
            centerValue={(resumen?.cupones_activos ?? 0) + (resumen?.bonos_activos ?? 0) + (resumen?.tarjetas_activas ?? 0)}
          />
        </ChartCard>
        <ChartCard title="Clientes con más puntos" subtitle="Top acumuladores del programa" height={240} accent="#f59e0b">
          <ProgressList items={puntos.slice(0, 6)} labelKey="cliente" valueKey="puntos" accent="#f59e0b" />
        </ChartCard>
      </div>

      {msg && <div className="badge-success" style={{ display: "inline-block", marginBottom: 8, padding: "6px 10px", borderRadius: 6 }}>{msg}</div>}
      {error && <div className="error">{error}</div>}

      {tab === "cupones" && (
        <>
          <form onSubmit={crearCupon} className="card" style={{ padding: 14, marginBottom: 14, display: "grid", gap: 10, gridTemplateColumns: "repeat(auto-fit, minmax(130px,1fr))" }}>
            <input required placeholder="Código (CUP10)" value={form.codigo} onChange={(e) => setForm({ ...form, codigo: e.target.value })} />
            <select value={form.tipo} onChange={(e) => setForm({ ...form, tipo: e.target.value })}>
              <option value="valor">Valor fijo</option>
              <option value="porcentaje">Porcentaje</option>
            </select>
            <input required type="number" min={0} placeholder="Valor / %" value={form.valor} onChange={(e) => setForm({ ...form, valor: Number(e.target.value) })} />
            <input type="number" min={1} placeholder="Usos máx" value={form.usos_max} onChange={(e) => setForm({ ...form, usos_max: Number(e.target.value) })} />
            {selCliente}
            <input type="date" value={form.vigencia_hasta} onChange={(e) => setForm({ ...form, vigencia_hasta: e.target.value })} />
            <input placeholder="Descripción" value={form.descripcion} onChange={(e) => setForm({ ...form, descripcion: e.target.value })} />
            <button className="btn btn-primary">Crear cupón</button>
          </form>
          <table className="table">
            <thead><tr><th>Código</th><th>Tipo</th><th>Valor</th><th>Usos</th><th>Vigencia</th><th>Cliente</th><th>Estado</th></tr></thead>
            <tbody>
              {cupones.map((c) => (
                <tr key={c.id}>
                  <td><b>{c.codigo}</b></td>
                  <td>{c.tipo}</td>
                  <td>{c.tipo === "porcentaje" ? `${c.valor}%` : `$${c.valor.toLocaleString("es-CO")}`}</td>
                  <td>{c.usos_actuales}/{c.usos_max}</td>
                  <td style={{ fontSize: 12 }}>{c.vigencia_hasta || "sin límite"}</td>
                  <td>{clientes.find((x) => x.id === c.cliente_id)?.nombre || "Cualquiera"}</td>
                  <td>
                    <button className={`btn btn-sm ${c.activo ? "badge-success" : ""}`} onClick={() => toggleCupon(c.id)}>
                      {c.activo ? "Activo" : "Inactivo"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}

      {tab === "bonos" && (
        <>
          <form onSubmit={crearBono} className="card" style={{ padding: 14, marginBottom: 14, display: "grid", gap: 10, gridTemplateColumns: "repeat(auto-fit, minmax(130px,1fr))" }}>
            <select required value={bonoForm.cliente_id} onChange={(e) => setBonoForm({ ...bonoForm, cliente_id: e.target.value })}>
              <option value="">Cliente…</option>
              {clientes.map((c) => (
                <option key={c.id} value={c.id}>{c.nombre}</option>
              ))}
            </select>
            <input required placeholder="Código" value={bonoForm.codigo} onChange={(e) => setBonoForm({ ...bonoForm, codigo: e.target.value })} />
            <input required type="number" min={0} placeholder="Valor total" value={bonoForm.valor_total} onChange={(e) => setBonoForm({ ...bonoForm, valor_total: Number(e.target.value) })} />
            <input placeholder="Motivo" value={bonoForm.motivo} onChange={(e) => setBonoForm({ ...bonoForm, motivo: e.target.value })} />
            <button className="btn btn-primary">Crear bono</button>
          </form>
          <table className="table">
            <thead><tr><th>Código</th><th>Cliente</th><th>Valor</th><th>Saldo</th><th>Motivo</th><th>Estado</th><th></th></tr></thead>
            <tbody>
              {bonos.map((b) => (
                <tr key={b.id}>
                  <td><b>{b.codigo}</b></td>
                  <td>{b.cliente}</td>
                  <td>${b.valor_total.toLocaleString("es-CO")}</td>
                  <td>${b.saldo.toLocaleString("es-CO")}</td>
                  <td style={{ fontSize: 12 }}>{b.motivo || "-"}</td>
                  <td>{b.estado}</td>
                  <td>
                    {b.estado === "activo" && Number(b.saldo || 0) > 0 && (
                      <button className="btn btn-sm" onClick={() => consumirBono(b)}>Consumir</button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}

      {tab === "tarjetas" && (
        <>
          <form onSubmit={crearTarjeta} className="card" style={{ padding: 14, marginBottom: 14, display: "grid", gap: 10, gridTemplateColumns: "repeat(auto-fit, minmax(130px,1fr))" }}>
            <select required value={tarjForm.cliente_id} onChange={(e) => setTarjForm({ ...tarjForm, cliente_id: e.target.value })}>
              <option value="">Cliente…</option>
              {clientes.map((c) => (
                <option key={c.id} value={c.id}>{c.nombre}</option>
              ))}
            </select>
            <input required placeholder="Código tarjeta" value={tarjForm.codigo} onChange={(e) => setTarjForm({ ...tarjForm, codigo: e.target.value })} />
            <input required type="number" min={0} placeholder="Saldo inicial" value={tarjForm.saldo} onChange={(e) => setTarjForm({ ...tarjForm, saldo: Number(e.target.value) })} />
            <button className="btn btn-primary">Crear tarjeta</button>
          </form>
          <table className="table">
            <thead><tr><th>Código</th><th>Cliente</th><th>Saldo</th><th>Estado</th><th></th></tr></thead>
            <tbody>
              {tarjetas.map((t) => (
                <tr key={t.id}>
                  <td><b>{t.codigo}</b></td>
                  <td>{t.cliente}</td>
                  <td>${t.saldo.toLocaleString("es-CO")}</td>
                  <td>{t.estado}</td>
                  <td>
                    <button className="btn btn-sm" onClick={() => recargar(t.id, 5000)}>+$5.000</button>
                    {t.estado === "activa" && Number(t.saldo || 0) > 0 && (
                      <button className="btn btn-sm" style={{ marginLeft: 6 }} onClick={() => consumirTarjeta(t)}>Consumir</button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}

      {tab === "puntos" && (
        <>
          <form onSubmit={ajustarPuntos} className="card" style={{ padding: 14, marginBottom: 14, display: "flex", gap: 10, flexWrap: "wrap" }}>
            <select required value={ajuste.cliente_id} onChange={(e) => setAjuste({ ...ajuste, cliente_id: e.target.value })}>
              <option value="">Cliente…</option>
              {clientes.map((c) => (
                <option key={c.id} value={c.id}>{c.nombre} ({c.puntos || 0} pts)</option>
              ))}
            </select>
            <input required type="number" placeholder="Delta (+/-)" value={ajuste.delta} onChange={(e) => setAjuste({ ...ajuste, delta: e.target.value })} />
            <input placeholder="Motivo" value={ajuste.motivo} onChange={(e) => setAjuste({ ...ajuste, motivo: e.target.value })} />
            <button className="btn btn-primary">Ajustar puntos</button>
          </form>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
            <table className="table">
              <thead><tr><th>Cliente</th><th>Puntos</th></tr></thead>
              <tbody>
                {puntos.map((p) => (
                  <tr key={p.cliente_id}>
                    <td>{p.cliente}</td>
                    <td><b>{p.puntos}</b></td>
                  </tr>
                ))}
              </tbody>
            </table>
            <table className="table">
              <thead><tr><th>Historial</th><th>Delta</th><th>Saldo</th></tr></thead>
              <tbody>
                {historial.map((h) => (
                  <tr key={h.id}>
                    <td style={{ fontSize: 12 }}>{h.motivo}</td>
                    <td>{h.delta > 0 ? `+${h.delta}` : h.delta}</td>
                    <td>{h.saldo_nuevo}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}