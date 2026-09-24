import { useId, useState, useEffect } from "react";
import {
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Tooltip as RTooltip,
  AreaChart,
  Area,
  CartesianGrid,
  XAxis,
  YAxis,
} from "recharts";

export const PALETA = ["#0e9f74", "#3eb489", "#38bdf8", "#f59e0b", "#10b981", "#a855f7", "#fb7185", "#94a3b8", "#22d3ee"];

function useIsDark() {
  const [dark, setDark] = useState(document.documentElement.getAttribute("data-theme") === "dark");
  useEffect(() => {
    const obs = new MutationObserver(() =>
      setDark(document.documentElement.getAttribute("data-theme") === "dark")
    );
    obs.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    return () => obs.disconnect();
  }, []);
  return dark;
}

export function formatMoney(n) {
  return new Intl.NumberFormat("es-CO", {
    style: "currency",
    currency: "COP",
    maximumFractionDigits: 0,
  }).format(n || 0);
}

export function waLink(telefono, mensaje) {
  let tel = String(telefono || "").replace(/\D/g, "");
  if (!tel) return "";
  if (tel.length === 10 && tel.startsWith("3")) tel = `57${tel}`;
  return `https://wa.me/${tel}?text=${encodeURIComponent(mensaje || "")}`;
}

export function abrirWhatsApp(telefono, mensaje) {
  const link = waLink(telefono, mensaje);
  if (link) window.open(link, "_blank", "noopener");
  return !!link;
}

export function WhatsAppButton({ telefono, mensaje, label = "💬 WhatsApp", size = "sm", estilo }) {
  const [num, setNum] = useState("");
  const [edit, setEdit] = useState(false);
  const abrir = (t) => {
    if (abrirWhatsApp(t, mensaje)) setEdit(false);
  };
  if (edit) {
    return (
      <span style={{ display: "inline-flex", gap: 6, alignItems: "center", width: "100%" }}>
        <input
          className="input"
          placeholder="3xxxxxxxxx"
          value={num}
          onChange={(e) => setNum(e.target.value.replace(/\D/g, ""))}
          maxLength={13}
          style={{ width: 140, flexShrink: 1 }}
          autoFocus
        />
        <button className={`btn btn-primary btn-${size}`} disabled={!num} onClick={() => abrir(num)}>Abrir chat</button>
        <button className={`btn btn-${size}`} onClick={() => setEdit(false)}>✕</button>
      </span>
    );
  }
  return (
    <button
      className={`btn btn-${size}`}
      onClick={() => (telefono ? abrir(telefono) : setEdit(true))}
      style={estilo}
      title={telefono ? "Abrir WhatsApp con el mensaje listo para enviar" : "Escriba el número del cliente para abrir WhatsApp directo"}
    >
      {label}
    </button>
  );
}

export function KpiCard({ label, value, icon = "📊", accent = "#0e9f74", sub, trend }) {
  return (
    <div className="kpi" style={{ "--accent": accent, "--accent-soft": accent + "1a" }}>
      <div className="kpi-icon">{icon}</div>
      <div className="kpi-body">
        <div className="kpi-label">{label}</div>
        <div className="kpi-value">{value}</div>
        {sub && <div className="kpi-sub">{sub}</div>}
        {trend && <div className="kpi-trend">{trend}</div>}
      </div>
    </div>
  );
}

function tooltipBox(rows) {
  return (
    <div className="chart-tip">
      {rows.map((r, i) => (
        <div key={i} className="chart-tip-row">{r}</div>
      ))}
    </div>
  );
}

export function ChartCard({ title, subtitle, children, height = 240, accent }) {
  return (
    <div className="card chart-card" style={accent ? { "--accent": accent } : undefined}>
      <div className="chart-title">{title}</div>
      {subtitle && <div className="muted" style={{ marginBottom: 10, fontSize: 12.5 }}>{subtitle}</div>}
      <div style={{ height }}>{children}</div>
    </div>
  );
}

export function Donut({ data = [], nameKey = "name", valueKey = "value", colors = PALETA, centerLabel, centerValue, money = false, height = 230 }) {
  const isDark = useIsDark();
  const sum = data.reduce((a, d) => a + (Number(d[valueKey]) || 0), 0);
  const valid = data.filter((d) => Number(d[valueKey]) > 0);
  return (
    <div className="donut-wrap" style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie
            data={valid.length ? valid : [{ [nameKey]: "Sin datos", [valueKey]: 1 }]}
            dataKey={valueKey}
            nameKey={nameKey}
            innerRadius="60%"
            outerRadius="88%"
            paddingAngle={3}
            cornerRadius={7}
            stroke="none"
          >
            {valid.length
              ? valid.map((_, i) => <Cell key={i} fill={colors[i % colors.length]} />)
              : [<Cell key={0} fill={isDark ? "#2b3641" : "#e2e8f0"} />]}
          </Pie>
          <RTooltip
            content={({ active, payload }) =>
              active && payload?.length
                ? tooltipBox([
                    <b key="n">{payload[0].name}</b>,
                    <span key="v">{money ? formatMoney(payload[0].value) : payload[0].value}</span>,
                  ])
                : null
            }
          />
        </PieChart>
      </ResponsiveContainer>
      {centerLabel && (
        <div className="donut-center">
          <span className="muted">{centerLabel}</span>
          <b>{centerValue != null ? centerValue : money ? formatMoney(sum) : sum}</b>
        </div>
      )}
    </div>
  );
}

export function TrendChart({ data = [], dataKey = "total", xKey = "dia", money = true, accent = "#0e9f74", suffix = "" }) {
  const gid = useId();
  const isDark = useIsDark();
  const gridColor = isDark ? "#263041" : "#eef2f7";
  const tickColor = isDark ? "#6b7a8d" : "#94a3b8";
  return (
    <ResponsiveContainer width="100%" height="100%">
      <AreaChart data={data} margin={{ top: 6, right: 4, left: 4, bottom: 0 }}>
        <defs>
          <linearGradient id={gid} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={accent} stopOpacity={0.4} />
            <stop offset="100%" stopColor={accent} stopOpacity={0.03} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke={gridColor} vertical={false} />
        <XAxis dataKey={xKey} tick={{ fontSize: 11, fill: tickColor }} tickLine={false} axisLine={false} />
        <YAxis hide />
        <Area
          type="monotone"
          dataKey={dataKey}
          stroke={accent}
          strokeWidth={2.6}
          fill={`url(#${gid})`}
          dot={{ r: 3, fill: accent, stroke: isDark ? "#161f2e" : "#fff", strokeWidth: 2 }}
        />
        <RTooltip
          content={({ active, payload, label }) =>
            active && payload?.length
              ? tooltipBox([
                  <b key="l">{String(label).slice(0, 10)}</b>,
                  <span key="v">{money ? formatMoney(payload[0].value) : `${payload[0].value}${suffix}`}</span>,
                ])
              : null
          }
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}

export function ProgressList({ items = [], labelKey = "name", valueKey = "value", money = false, accent = "#0e9f74", max }) {
  const top = max ?? Math.max(...items.map((i) => Number(i[valueKey]) || 0), 1);
  return (
    <div className="prog-list">
      {items.length === 0 && (
        <div className="muted" style={{ padding: 16, textAlign: "center" }}>
          📊 Sin datos por mostrar
        </div>
      )}
      {items.map((i, idx) => (
        <div className="prog-item" key={idx}>
          <div className="prog-head">
            <span className="prog-name">{i[labelKey]}</span>
            <span className="prog-val">{money ? formatMoney(i[valueKey]) : i[valueKey]}</span>
          </div>
          <div className="prog-track">
            <div className="prog-fill" style={{ width: `${Math.max(4, (Number(i[valueKey]) / top) * 100)}%`, background: `linear-gradient(90deg, ${accent}, ${accent}cc)` }} />
          </div>
        </div>
      ))}
    </div>
  );
}
