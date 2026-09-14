import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api from "../api.js";
import { KpiCard, ChartCard, Donut, TrendChart, ProgressList, formatMoney, PALETA } from "../components/ui.jsx";

export default function Dashboard() {
  const [data, setData] = useState(null);
  const [ventas, setVentas] = useState(null);
  const [trend, setTrend] = useState([]);
  const [top, setTop] = useState([]);
  const [alertas, setAlertas] = useState(null);
  const [sug, setSug] = useState([]);
  const [error, setError] = useState("");

  useEffect(() => {
    api("/reportes/dashboard")
      .then(setData)
      .catch((e) => setError(e.message));
    api("/reportes/ventas")
      .then(setVentas)
      .catch(() => {});
    api("/reportes/ventas-dia?dias=14")
      .then(setTrend)
      .catch(() => {});
    api("/reportes/ventas-por-producto")
      .then((r) => setTop(r.slice(0, 6)))
      .catch(() => {});
    api("/reportes/alertas")
      .then(setAlertas)
      .catch(() => {});
    api("/inventario/sugerir-reposicion")
      .then((r) => setSug((r?.sugerencias || []).slice(0, 6)))
      .catch(() => {});
  }, []);

  if (error) return <div className="page"><div className="error">{error}</div></div>;
  if (!data) return <div className="page"><div className="spinner" /></div>;

  const medios = Object.entries(ventas?.por_medio_pago || {}).map(([name, value]) => ({ name, value }));
  const porCajero = Object.entries(ventas?.por_cajero || {})
    .map(([name, value]) => ({ name: name.replace("usuario_", ""), value }))
    .sort((a, b) => b.value - a.value);

  const hoy = new Date();
  const saludo = hoy.getHours() < 12 ? "Buenos días" : hoy.getHours() < 19 ? "Buenas tardes" : "Buenas noches";

  return (
    <div className="page">
      <div className="hero" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 16, flexWrap: "wrap" }}>
        <div>
          <h1>Panel de control</h1>
          <p>
            {saludo} · Resumen del negocio en tiempo real ·{" "}
            {hoy.toLocaleDateString("es-CO", { day: "numeric", month: "long" })}
          </p>
        </div>
        <div className="hero-actions">
          <Link className="btn" to="/pos">➕ Nueva venta</Link>
          <Link className="btn" to="/pedidos">🛵 Pedidos</Link>
          <Link className="btn" to="/fidelizacion">⭐ Fidelización</Link>
        </div>
      </div>

      {alertas && (
        <div className="card" style={{ padding: 14, marginBottom: 20 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10, flexWrap: "wrap", gap: 8 }}>
            <h2 style={{ fontSize: 15 }}>Alertas del día</h2>
            <Link to="/reportes" className="btn btn-sm">Ir a reportes</Link>
          </div>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            {[
              { n: alertas.bajo_inventario, txt: "productos con stock bajo", c: "#f59e0b", a: "/productos" },
              { n: alertas.productos_proximos_a_vencer, txt: "por vencer en 30 días", c: "#0284c7", a: "/inventario" },
              { n: alertas.productos_vencidos, txt: "productos vencidos", c: "#dc2626", a: "/inventario" },
              { n: alertas.cajas_abiertas, txt: "cajas abiertas", c: "#16a34a", a: "/caja" },
              ...(alertas.sin_ventas_hoy ? [{ n: "", txt: "sin ventas hoy", c: "#6b7280", a: "/pos" }] : []),
              ...(Number(alertas.cuentas_pagar_proximas) > 0 ? [{ n: "", txt: `$${Number(alertas.cuentas_pagar_proximas).toLocaleString("es-CO")} por pagar pronto`, c: "#d97706", a: "/compras" }] : []),
            ]
              .filter((chip) => chip.n !== 0)
              .map((chip) => (
                <Link key={chip.txt} to={chip.a} style={{ display: "inline-flex", alignItems: "center", gap: 7, padding: "7px 12px", borderRadius: 999, border: "1px solid var(--line)", background: "var(--card)", fontSize: 12.5, fontWeight: 600, color: "var(--ink)" }}>
                  <span style={{ width: 9, height: 9, borderRadius: 999, background: chip.c, display: "inline-block" }} />
                  {chip.n !== "" && <b style={{ color: chip.c }}>{chip.n}</b>}
                  {chip.txt}
                </Link>
              ))}
          </div>
          {sug.length > 0 && (
            <div style={{ marginTop: 12, borderTop: "1px solid var(--line)", paddingTop: 12 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8, flexWrap: "wrap", gap: 8 }}>
                <h3 style={{ fontSize: 13.5 }}>Sugerencia de compra · productos bajo reorden</h3>
                <Link to="/compras" className="btn btn-sm">Crear orden de compra →</Link>
              </div>
              <table className="table">
                <thead>
                  <tr><th>Producto</th><th>Código</th><th style={{ textAlign: "right" }}>Existencias</th><th style={{ textAlign: "right" }}>Reorden</th><th style={{ textAlign: "right" }}>Comprar</th></tr>
                </thead>
                <tbody>
                  {sug.map((s) => (
                    <tr key={s.producto_id}>
                      <td><b>{s.producto}</b></td>
                      <td style={{ fontSize: 12 }}>{s.codigo || "-"}</td>
                      <td style={{ textAlign: "right" }}>{s.existencias}</td>
                      <td style={{ textAlign: "right" }}>{s.punto_reorden}</td>
                      <td style={{ textAlign: "right", color: "#059669", fontWeight: 700 }}>{s.cantidad_sugerida}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 210px), 1fr))", gap: 16, marginBottom: 20 }}>
        <KpiCard
          label="Ventas hoy"
          value={formatMoney(data.ventas_hoy)}
          icon="💵"
          accent="#f43f5e"
          sub={`${data.productos_vendidos_hoy ?? 0} productos vendidos`}
        />
        <KpiCard
          label="Utilidad hoy"
          value={formatMoney(data.utilidad_hoy)}
          icon="📈"
          accent="#10b981"
          sub={`${(((data.utilidad_hoy || 0) / (data.ventas_hoy || 1)) * 100).toFixed(1)}% de margen`}
        />
        <KpiCard
          label="Ventas del mes"
          value={formatMoney(data.ventas_mes)}
          icon="🗓️"
          accent="#f59e0b"
        />
        <KpiCard
          label="Ticket promedio"
          value={formatMoney(ventas?.ticket_promedio ?? 0)}
          icon="🎫"
          accent="#a855f7"
          sub={`${ventas?.numero_transacciones ?? 0} transacciones`}
        />
        <KpiCard
          label="Gastos del mes"
          value={formatMoney(data.gastos_mes)}
          icon="💸"
          accent="#f43f5e"
        />
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 320px), 1fr))", gap: 18, marginBottom: 20 }}>
        <ChartCard title="Medios de pago" subtitle="Distribución de la recaudación" height={250}>
          <Donut data={medios} nameKey="name" valueKey="value" money centerLabel="Recaudado" centerValue={formatMoney(medios.reduce((a, m) => a + Number(m.value), 0))} />
        </ChartCard>

        <ChartCard title="Ventas de los últimos 14 días" subtitle="Evolución diaria" height={250} accent="#06b6d4">
          <TrendChart data={trend} money accent="#06b6d4" />
        </ChartCard>

        <ChartCard title="Top productos vendidos" subtitle="Por unidades" height={250} accent="#f59e0b">
          <ProgressList items={top} labelKey="producto" valueKey="cantidad" accent="#f59e0b" />
        </ChartCard>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 320px), 1fr))", gap: 18 }}>
        <ChartCard title="Ventas por cajero" subtitle="Total facturado" height={250} accent="#4f46e5">
          <Donut data={porCajero} nameKey="name" valueKey="value" money centerLabel="Total" colors={PALETA.slice(2)} />
        </ChartCard>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 140px), 1fr))", gap: 16 }}>
          <KpiCard label="Inventario valorizado" value={formatMoney(data.inventario_valorizado)} icon="🏬" accent="#4f46e5" />
          <KpiCard label="Productos agotados" value={data.productos_agotados ?? 0} icon="🚫" accent="#f43f5e" />
          <KpiCard label="Clientes" value={data.clientes ?? 0} icon="👥" accent="#3b82f6" />
          <KpiCard label="Cuentas por cobrar" value={formatMoney(data.cuentas_por_cobrar)} icon="🧾" accent="#f59e0b" />
        </div>
      </div>
    </div>
  );
}