import { useEffect, useState } from "react";
import api from "../api.js";
import { KpiCard, ChartCard, Donut, formatMoney } from "../components/ui.jsx";

export default function Apartados() {
  const [lista, setLista] = useState([]);
  const [resumen, setResumen] = useState(null);
  const [clientes, setClientes] = useState([]);
  const [productos, setProductos] = useState([]);
  const [error, setError] = useState("");
  const [msg, setMsg] = useState("");
  const [form, setForm] = useState({ cliente_id: "", abono_inicial: 0, fecha_compromiso: "", nota: "" });
  const [lineas, setLineas] = useState([{ producto_id: "", cantidad: 1, precio: 0 }]);
  const [detalle, setDetalle] = useState(null);

  async function load() {
    api("/apartados").then(setLista).catch((e) => setError(e.message));
    api("/apartados/resumen/estado").then(setResumen).catch(() => {});
  }

  useEffect(() => {
    load();
    api("/clientes").then(setClientes).catch(() => {});
    api("/productos").then(setProductos).catch(() => {});
  }, []);

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

  function setLinea(idx, campo, valor) {
    const next = [...lineas];
    next[idx][campo] = campo === "cantidad" ? Number(valor) : valor;
    setLineas(next);
  }

  async function crear(e) {
    e.preventDefault();
    const detalle = lineas
      .filter((l) => l.producto_id)
      .map((l) => ({
        producto_id: Number(l.producto_id),
        cantidad: Number(l.cantidad),
        precio: l.precio ? Number(l.precio) : productos.find((p) => p.id === Number(l.producto_id))?.precio_venta || 0,
      }));
    await submit(
      () =>
        api("/apartados", {
          method: "POST",
          body: JSON.stringify({ ...form, cliente_id: Number(form.cliente_id), abono_inicial: Number(form.abono_inicial || 0), detalle }),
        }),
      "Apartado creado"
    );
    setLineas([{ producto_id: "", cantidad: 1, precio: 0 }]);
    setForm({ cliente_id: "", abono_inicial: 0, fecha_compromiso: "", nota: "" });
  }

  async function abonar(id, montoRestante) {
    const monto = window.prompt("Monto del abono:", montoRestante);
    if (!monto) return;
    await submit(() => api(`/apartados/${id}/abonos`, { method: "POST", body: JSON.stringify({ monto: Number(monto) }) }), "Abono registrado");
  }

  async function liquidar(id) {
    if (!window.confirm("Liquidar apartado (genera venta y factura)?")) return;
    await submit(() => api(`/apartados/${id}/liquidar`, { method: "POST" }), "Apartado liquidado");
  }

  async function cancelar(id) {
    if (!window.confirm("¿Cancelar apartado?")) return;
    await submit(() => api(`/apartados/${id}/cancelar`, { method: "POST" }), "Apartado cancelado");
  }

  async function verDetalle(id) {
    setError("");
    setMsg("");
    try {
      setDetalle(await api(`/apartados/${id}`));
    } catch (e) {
      setError(e.message);
    }
  }

  const estadoBadge = (e) => <span className={`badge ${e === "abierto" || e === "pagado" ? "badge-success" : ""}`}>{e}</span>;

  return (
    <div className="page">
      <div className="hero" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 16, flexWrap: "wrap" }}>
        <div>
          <h1>Ventas por apartado</h1>
          <p>Separa mercancía, recibe abonos y liquida generando venta y factura electrónica.</p>
        </div>
        <div className="hero-actions">
          <button className="btn" onClick={() => document.getElementById("nuevo-apartado")?.scrollIntoView({ behavior: "smooth" })}>➕ Nuevo apartado</button>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px,1fr))", gap: 16, marginBottom: 18 }}>
        <KpiCard label="Apartados abiertos" value={resumen?.abiertos ?? 0} icon="🔓" accent="#ef4444" />
        <KpiCard label="Por liquidar" value={resumen?.por_liquidar ?? 0} icon="⏳" accent="#f59e0b" />
        <KpiCard label="Pendiente por cobrar" value={formatMoney(resumen?.pendiente_cobrar ?? 0)} icon="🧾" accent="#10b981" />
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px,1fr))", gap: 18, marginBottom: 18 }}>
        <ChartCard title="Estados de apartados" subtitle="Distribución por estado" height={230}>
          <Donut
            data={Object.entries((lista || []).reduce((acc, a) => ({ ...acc, [a.estado]: (acc[a.estado] || 0) + 1 }), {})).map(([name, value]) => ({ name, value }))}
            centerLabel="Total"
            centerValue={lista.length}
          />
        </ChartCard>
        <ChartCard title="Composición de cartera" subtitle="Abonado vs pendiente en apartados" height={230} accent="#f59e0b">
          <Donut
            data={[
              { name: "Abonado", value: lista.reduce((a, x) => a + Number(x.abonado || 0), 0) },
              { name: "Pendiente", value: lista.reduce((a, x) => a + Number(x.pendiente || 0), 0) },
            ]}
            money
            centerLabel="Total valorizado"
            centerValue={formatMoney(lista.reduce((a, x) => a + Number(x.total || 0), 0))}
            colors={["#10b981", "#ef4444"]}
          />
        </ChartCard>
      </div>

      {msg && <div className="badge-success" style={{ display: "inline-block", marginBottom: 8, padding: "6px 10px", borderRadius: 6 }}>{msg}</div>}
      {error && <div className="error">{error}</div>}

      <form id="nuevo-apartado" onSubmit={crear} className="card" style={{ padding: 16, marginBottom: 18, display: "grid", gap: 10 }}>
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
          <select required value={form.cliente_id} onChange={(e) => setForm({ ...form, cliente_id: e.target.value })}>
            <option value="">Cliente…</option>
            {clientes.map((c) => (
              <option key={c.id} value={c.id}>{c.nombre}</option>
            ))}
          </select>
          <input type="number" min={0} placeholder="Abono inicial" value={form.abono_inicial} onChange={(e) => setForm({ ...form, abono_inicial: e.target.value })} />
          <input type="date" value={form.fecha_compromiso} onChange={(e) => setForm({ ...form, fecha_compromiso: e.target.value })} />
          <input placeholder="Nota" value={form.nota} onChange={(e) => setForm({ ...form, nota: e.target.value })} />
        </div>
        {lineas.map((l, i) => (
          <div key={i} style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
            <select required value={l.producto_id} onChange={(e) => setLinea(i, "producto_id", e.target.value)}>
              <option value="">Producto…</option>
              {productos.map((p) => (
                <option key={p.id} value={p.id}>{p.nombre} - ${p.precio_venta?.toLocaleString?.("es-CO") || p.precio_venta}</option>
              ))}
            </select>
            <input type="number" min={1} style={{ width: 90 }} value={l.cantidad} onChange={(e) => setLinea(i, "cantidad", e.target.value)} />
            <input type="number" min={0} placeholder="Precio (opcional)" value={l.precio} onChange={(e) => setLinea(i, "precio", e.target.value)} />
            <button type="button" className="btn btn-sm" onClick={() => setLineas(lineas.filter((_, x) => x !== i))}>Quitar</button>
          </div>
        ))}
        <div style={{ display: "flex", gap: 10 }}>
          <button type="button" className="btn" onClick={() => setLineas([...lineas, { producto_id: "", cantidad: 1, precio: 0 }])}>+ Producto</button>
          <button className="btn btn-primary">Crear apartado</button>
        </div>
      </form>

      <table className="table">
        <thead>
          <tr><th>Nº</th><th>Cliente</th><th>Estado</th><th>Total</th><th>Abonado</th><th>Pendiente</th><th>Compromiso</th><th>Acciones</th></tr>
        </thead>
        <tbody>
          {lista.length === 0 && (
            <tr><td colSpan={8}>Sin apartados.</td></tr>
          )}
          {lista.map((a) => (
            <tr key={a.id}>
              <td><b>{a.numero}</b></td>
              <td>{clientes.find((c) => c.id === a.cliente_id)?.nombre || a.cliente_id}</td>
              <td>{estadoBadge(a.estado)}</td>
              <td>${a.total.toLocaleString("es-CO")}</td>
              <td>${a.abonado.toLocaleString("es-CO")}</td>
              <td><b>${a.pendiente.toLocaleString("es-CO")}</b></td>
              <td style={{ fontSize: 12 }}>{a.fecha_compromiso || "-"}</td>
              <td>
                <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                  <button className="btn btn-sm btn-ghost" onClick={() => verDetalle(a.id)}>Detalle</button>
                  {a.estado !== "liquidado" && a.estado !== "cancelado" && (
                    <>
                      <button className="btn btn-sm" onClick={() => abonar(a.id, a.pendiente)}>Abonar</button>
                      <button className="btn btn-sm btn-primary" disabled={a.pendiente > 0.01} onClick={() => liquidar(a.id)}>Liquidar</button>
                    </>
                  )}
                  {a.estado === "abierto" && (
                    <button className="btn btn-sm" onClick={() => cancelar(a.id)}>Cancelar</button>
                  )}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {detalle && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,.45)", display: "grid", placeItems: "center", zIndex: 1100, padding: 20 }}>
          <div className="card" style={{ width: "min(640px, 100%)" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
              <h3>Apartado {detalle.numero} · {clientes.find((c) => c.id === detalle.cliente_id)?.nombre || `cliente #${detalle.cliente_id}`}</h3>
              <button className="btn btn-ghost" onClick={() => setDetalle(null)}>✕</button>
            </div>
            <p className="muted">
              Estado: {estadoBadge(detalle.estado)} · Total <strong>{formatMoney(detalle.total)}</strong> · Abonado {formatMoney(detalle.abonado)} · Pendiente <strong>{formatMoney(detalle.pendiente)}</strong>
              {detalle.fecha_compromiso && <> · Compromiso: {detalle.fecha_compromiso}</>}
            </p>
            {detalle.nota && <p className="muted">Nota: {detalle.nota}</p>}
            <h4 style={{ margin: "12px 0 6px", fontSize: 13 }}>Productos apartados</h4>
            <table className="table">
              <thead><tr><th>Producto</th><th>Cantidad</th><th>Precio</th><th>Subtotal</th></tr></thead>
              <tbody>
                {(detalle.detalle || []).map((d, i) => (
                  <tr key={i}><td>#{d.producto_id}</td><td>{d.cantidad}</td><td>{formatMoney(d.precio)}</td><td>{formatMoney(d.subtotal)}</td></tr>
                ))}
                {(detalle.detalle || []).length === 0 && <tr><td colSpan={4} className="muted" style={{ textAlign: "center" }}>Sin productos</td></tr>}
              </tbody>
            </table>
            {detalle.abonos && detalle.abonos.length > 0 && (
              <>
                <h4 style={{ margin: "12px 0 6px", fontSize: 13 }}>Historial de abonos</h4>
                <table className="table">
                  <thead><tr><th>Fecha</th><th>Monto</th><th>Medio</th></tr></thead>
                  <tbody>
                    {detalle.abonos.map((a, i) => (
                      <tr key={i}><td>{a.created_at ? new Date(a.created_at).toLocaleString() : "—"}</td><td>{formatMoney(a.monto)}</td><td>{a.medio || "—"}</td></tr>
                    ))}
                  </tbody>
                </table>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}