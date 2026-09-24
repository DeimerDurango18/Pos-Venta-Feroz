import { useEffect, useState } from "react";
import api from "../api.js";
import { formatMoney, WhatsAppButton } from "../components/ui.jsx";

const ESTADOS = { vigente: "Vigente", vencida: "Vencida", convertida: "Convertida", anulada: "Anulada" };
const COLOR = { vigente: "#16a34a", vencida: "#d97706", convertida: "#0e9f74", anulada: "#9ca3af" };

export default function Cotizaciones() {
  const [rows, setRows] = useState([]);
  const [filtro, setFiltro] = useState("vigente");
  const [abierta, setAbierta] = useState(null);
  const [message, setMessage] = useState("");
  const [err, setErr] = useState("");
  const [q, setQ] = useState("");
  const [result, setResult] = useState([]);
  const [item, setItem] = useState(null);
  const [cliente, setCliente] = useState("");
  const [cliNombre, setCliNombre] = useState("");
  const [cliTel, setCliTel] = useState("");
  const [cliDoc, setCliDoc] = useState("");
  const [vence, setVence] = useState("");
  const [descto, setDescto] = useState(0);
  const [nota, setNota] = useState("");
  const [lineas, setLineas] = useState([]);
  const [cargandoLinea, setCargandoLinea] = useState(false);

  const cargar = () => api(`/cotizaciones${filtro && filtro !== "todos" ? `?estado=${filtro}` : ""}`).then(setRows).catch((e) => setErr(e.message));
  useEffect(() => { cargar(); /* eslint-disable-next-line */ }, [filtro]);

  useEffect(() => {
    if (!q || q.trim().length < 2) { setResult([]); return; }
    const t = setTimeout(() => {
      api(`/productos?q=${encodeURIComponent(q.trim())}`).then(setResult).catch(() => {});
    }, 250);
    return () => clearTimeout(t);
  }, [q]);

  async function buscarCliente(texto) {
    setCliente(texto);
    if (texto.trim().length < 3) return;
    try {
      const r = await api(`/clientes?q=${encodeURIComponent(texto.trim())}`);
      const c = r?.[0];
      if (c) {
        setCliNombre(c.nombre || c.razon_social || "");
        setCliDoc(c.documento || "");
        setCliTel(c.telefono || "");
        setCliente("");
      }
    } catch {}
  }

  function agregarProducto(p) {
    if (lineas.find((l) => l.producto_id === p.id)) return;
    setLineas([...lineas, { producto_id: p.id, nombre: p.nombre, codigo: p.codigo, precio: Number(p.precio_venta ?? 0), cantidad: 1 }]);
    if (Number(p.precio_venta ?? 0) > 0) {
      setCliNombre((n) => n || ""); // no-op, nur zur Normalisierung
    }
    setItem(null);
    setQ("");
  }

  const setLinea = (i, campo, valor) => setLineas((ls) => ls.map((l, k) => (k === i ? { ...l, [campo]: valor } : l)));

  const subtotalLineas = lineas.reduce((a, l) => a + l.cantidad * l.precio * (1 - (l.descuento || 0) / 100), 0);
  const total = subtotalLineas * (1 - (Number(descto) || 0) / 100);

  async function crear() {
    if (!lineas.length) return setErr("Agrega al menos un producto");
    setErr("");
    try {
      await api("/cotizaciones", {
        method: "POST",
        body: JSON.stringify({
          empresa_id: 1,
          sucursal_id: 1,
          cliente_nombre: cliNombre || null,
          cliente_documento: cliDoc || null,
          cliente_telefono: cliTel || null,
          vence: vence || null,
          observaciones: nota || null,
          descuento_global: Number(descto) || 0,
          detalle: lineas.map((l) => ({ producto_id: l.producto_id, cantidad: l.cantidad, precio: l.precio, descuento: l.descuento || 0 })),
        }),
      });
      setMessage("Cotización creada ✅");
      setAbierta(false);
      setLineas([]);
      cargar();
    } catch (e) {
      setErr(e.message);
    }
  }

  async function convertir(c) {
    if (!window.confirm(`Convertir ${c.numero} en venta? Se descontará inventario.`)) return;
    setErr("");
    try {
      const r = await api(`/cotizaciones/${c.id}/convertir`, { method: "POST" });
      setMessage(`Venta ${r.numero_venta} creada por ${formatMoney(r.total)} ✅`);
      cargar();
    } catch (e) {
      setErr(e.message);
    }
  }

  async function anular(c) {
    if (!window.confirm(`Anular la cotización ${c.numero}?`)) return;
    try {
      await api(`/cotizaciones/${c.id}/anular`, { method: "POST" });
      cargar();
    } catch (e) {
      setErr(e.message);
    }
  }

  return (
    <div className="page">
      <div className="hero" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 16, flexWrap: "wrap" }}>
        <div>
          <h1>Cotizaciones</h1>
          <p>Presupuestos para clientes: envíalos por WhatsApp y conviértelos en venta en un clic.</p>
        </div>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <button className="btn btn-primary" onClick={() => { setAbierta(true); setErr(""); }}>➕ Nueva cotización</button>
          <a className="btn" href="/clientes">👥 Clientes</a>
        </div>
      </div>

      {message && <div className="badge-success" style={{ display: "block", padding: "8px 12px", borderRadius: 8, marginBottom: 12 }}>{message}</div>}
      {err && <div className="error">{err}</div>}

      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 16 }}>
        {Object.entries({ vigente: "Vigentes", vencida: "Vencidas", convertida: "Convertidas", anulada: "Anuladas", todos: "Todas" }).map(([k, lbl]) => (
          <button key={k} className={`btn btn-sm${filtro === k ? " btn-primary" : ""}`} onClick={() => setFiltro(k)}>{lbl}</button>
        ))}
      </div>

      {!abierta && (
        <div className="card" style={{ padding: 0, overflow: "hidden" }}>
          {rows.length === 0 ? (
            <div style={{ padding: 30, textAlign: "center", color: "var(--muted)" }}>Sin cotizaciones en esta vista.</div>
          ) : (
            <table className="table">
              <thead>
                <tr><th>#</th><th>Cliente</th><th>Estado</th><th>Vence</th><th style={{ textAlign: "right" }}>Total</th><th></th></tr>
              </thead>
              <tbody>
                {rows.map((c) => (
                  <tr key={c.id}>
                    <td style={{ whiteSpace: "nowrap" }}>
                      <b>{c.numero}</b>
                      <div style={{ fontSize: 11.5, color: "var(--muted)" }}>{c.creado_por || ""}</div>
                    </td>
                    <td>
                      {c.cliente_nombre || "Consumidor final"}
                      {c.cliente_documento && <div style={{ fontSize: 11.5, color: "var(--muted)" }}>{c.cliente_documento}</div>}
                    </td>
                    <td><span className="badge" style={{ background: `${COLOR[c.estado]}1a`, color: COLOR[c.estado] }}>{ESTADOS[c.estado] || c.estado}</span></td>
                    <td style={{ whiteSpace: "nowrap" }}>{c.vence ? new Date(`${c.vence}T00:00:00`).toLocaleDateString("es-CO") : "—"}</td>
                    <td style={{ textAlign: "right", fontWeight: 700 }}>{formatMoney(c.total)}</td>
                    <td>
                      <div style={{ display: "flex", gap: 6, justifyContent: "flex-end", flexWrap: "wrap" }}>
                        <WhatsAppButton
                          telefono={c.cliente_telefono}
                          mensaje={`Hola ${c.cliente_nombre || ""} 👋,\nTu cotización ${c.numero} está por ${formatMoney(c.total)} y vence el ${c.vence || "por definir"}.\n¿La convertimos en venta?`}
                          label="💬 WhatsApp"
                        />
                        {c.estado === "vigente" && <button className="btn btn-sm btn-primary" onClick={() => convertir(c)}>✅ Convertir</button>}
                        {(c.estado === "vigente" || c.estado === "vencida") && <button className="btn btn-sm" onClick={() => anular(c)}>✕</button>}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {abierta && (
        <div className="card">
          <div style={{ display: "flex", justifyContent: "space-between", gap: 8, marginBottom: 14 }}>
            <h2>Nueva cotización</h2>
            <button className="btn btn-ghost" onClick={() => setAbierta(false)}>✕</button>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(170px,1fr))", gap: 12, marginBottom: 16 }}>
            <div>
              <label>Buscar cliente (teléfono)</label>
              <input value={cliente} onChange={(e) => buscarCliente(e.target.value)} placeholder="Nombre o documento" />
            </div>
            <div><label>Nombre cliente</label><input value={cliNombre} onChange={(e) => setCliNombre(e.target.value)} /></div>
            <div><label>Teléfono (WhatsApp)</label><input value={cliTel} onChange={(e) => setCliTel(e.target.value)} placeholder="3012345678" /></div>
            <div><label>Documento</label><input value={cliDoc} onChange={(e) => setCliDoc(e.target.value)} /></div>
            <div><label>Vence el</label><input type="date" value={vence} onChange={(e) => setVence(e.target.value)} /></div>
            <div><label>Descuento %</label><input type="number" min="0" max="100" value={descto} onChange={(e) => setDescto(e.target.value)} /></div>
          </div>

          <div style={{ marginBottom: 10 }}>
            <label>Agregar producto</label>
            <div style={{ position: "relative" }}>
              <input value={q} onChange={(e) => { setQ(e.target.value); setCargandoLinea(true); }} onBlur={() => setTimeout(() => setCargandoLinea(false), 200)} placeholder="Buscar por nombre o código…" />
              {cargandoLinea && result.length > 0 && (
                <div style={{ position: "absolute", top: "100%", left: 0, right: 0, zIndex: 20, background: "var(--card)", border: "1px solid var(--line)", borderRadius: 12, maxHeight: 260, overflow: "auto", boxShadow: "0 18px 40px -18px rgba(0,0,0,.4)" }}>
                  {result.map((p) => (
                    <div key={p.id} onMouseDown={() => agregarProducto(p)} style={{ padding: "9px 12px", cursor: "pointer", display: "flex", justifyContent: "space-between", gap: 8, borderBottom: "1px solid var(--line)" }}>
                      <span><b>{p.nombre}</b> <span style={{ color: "var(--muted)", fontSize: 12 }}>{p.codigo || ""}</span></span>
                      <span style={{ fontWeight: 700, color: "var(--brand1)" }}>{formatMoney(p.precio_venta)}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {lineas.length > 0 && (
            <div style={{ overflowX: "auto", marginBottom: 12 }}>
              <table className="table">
                <thead><tr><th>Producto</th><th style={{ textAlign: "right" }}>Precio</th><th style={{ textAlign: "right" }}>Cant</th><th style={{ textAlign: "right" }}>Desc %</th><th style={{ textAlign: "right" }}>Subtotal</th><th></th></tr></thead>
                <tbody>
                  {lineas.map((l, i) => (
                    <tr key={i}>
                      <td><b>{l.nombre}</b></td>
                      <td><input type="number" min="0" value={l.precio} onChange={(e) => setLinea(i, "precio", Number(e.target.value))} style={{ width: 110, textAlign: "right" }} /></td>
                      <td><input type="number" min="0.01" step="0.01" value={l.cantidad} onChange={(e) => setLinea(i, "cantidad", Number(e.target.value))} style={{ width: 80, textAlign: "right" }} /></td>
                      <td><input type="number" min="0" max="100" value={l.descuento || 0} onChange={(e) => setLinea(i, "descuento", Number(e.target.value))} style={{ width: 70, textAlign: "right" }} /></td>
                      <td style={{ textAlign: "right", fontWeight: 700 }}>{formatMoney(l.cantidad * l.precio * (1 - (l.descuento || 0) / 100))}</td>
                      <td><button className="btn btn-ghost" onClick={() => setLineas((ls) => ls.filter((_, k) => k !== i))}>✕</button></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <div>
            <label>Observaciones</label>
            <textarea rows={2} value={nota} onChange={(e) => setNota(e.target.value)} placeholder="Condiciones de pago, garantías…" />
          </div>

          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 14, flexWrap: "wrap", gap: 10 }}>
            <b style={{ fontSize: 18 }}>Total: {formatMoney(total)}</b>
            <div style={{ display: "flex", gap: 8 }}>
              <button className="btn" onClick={() => setAbierta(false)}>Cancelar</button>
              <button className="btn btn-primary" onClick={crear}>💾 Guardar cotización</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}