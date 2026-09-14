import { useEffect, useState } from "react";
import api from "../api.js";
import { KpiCard, ChartCard, Donut } from "../components/ui.jsx";

export default function Restaurante() {
  const [salones, setSalones] = useState([]);
  const [mesas, setMesas] = useState([]);
  const [comandas, setComandas] = useState([]);
  const [reservas, setReservas] = useState([]);
  const [resumen, setResumen] = useState(null);
  const [productos, setProductos] = useState([]);
  const [clientes, setClientes] = useState([]);
  const [tab, setTab] = useState("salones");
  const [error, setError] = useState("");
  const [msg, setMsg] = useState("");
  const [salonNombre, setSalonNombre] = useState("");
  const [mesaForm, setMesaForm] = useState({ salon_id: "", nombre: "", capacidad: 4 });
  const [comandaForm, setComandaForm] = useState({ mesa_id: "", cliente_id: "", lineas: [{ producto_id: "", cantidad: 1, precio: 0, preparacion: "" }] });
  const [reservaForm, setReservaForm] = useState({ mesa_id: "", cliente: "", telefono: "" });
  const [detalle, setDetalle] = useState(null);
  const [qrMesa, setQrMesa] = useState(null);

  async function load() {
    api("/restaurante/salones").then(setSalones).catch(() => {});
    api("/restaurante/mesas").then(setMesas).catch(() => {});
    api("/restaurante/comandas").then(setComandas).catch(() => {});
    api("/restaurante/reservas").then(setReservas).catch(() => {});
    api("/restaurante/seguridad").then(setResumen).catch(() => {});
  }

  useEffect(() => {
    load();
    api("/productos").then(setProductos).catch(() => {});
    api("/clientes").then(setClientes).catch(() => {});
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

  async function crearSalon(e) {
    e.preventDefault();
    await submit(() => api("/restaurante/salones", { method: "POST", body: JSON.stringify({ nombre: salonNombre }) }), "Salón creado");
    setSalonNombre("");
  }

  async function crearMesa(e) {
    e.preventDefault();
    await submit(
      () => api(`/restaurante/mesas?salon_id=${mesaForm.salon_id}`, { method: "POST", body: JSON.stringify({ nombre: mesaForm.nombre, capacidad: Number(mesaForm.capacidad) }) }),
      "Mesa creada"
    );
    setMesaForm({ salon_id: "", nombre: "", capacidad: 4 });
  }

  async function ocupar(mesaId) {
    const clienteId = window.prompt("Cliente ID (opcional):");
    await submit(() => api(`/restaurante/mesas/${mesaId}/ocupar?invitados=2${clienteId ? `&cliente_id=${clienteId}` : ""}`, { method: "POST" }), "Mesa ocupada");
  }

  async function liberar(mesaId) {
    await submit(() => api(`/restaurante/mesas/${mesaId}/disponible`, { method: "POST" }), "Mesa liberada");
  }

  function setLinea(idx, campo, valor) {
    const next = [...comandaForm.lineas];
    next[idx][campo] = campo === "cantidad" || campo === "precio" ? Number(valor) : valor;
    setComandaForm({ ...comandaForm, lineas: next });
  }

  async function crearComanda(e) {
    e.preventDefault();
    const detalle = comandaForm.lineas
      .filter((l) => l.producto_id)
      .map((l) => ({
        producto_id: Number(l.producto_id),
        cantidad: Number(l.cantidad),
        precio: l.precio || productos.find((p) => p.id === Number(l.producto_id))?.precio_venta || 0,
        preparacion: l.preparacion || null,
      }));
    await submit(
      () =>
        api("/restaurante/comandas", {
          method: "POST",
          body: JSON.stringify({
            mesa_id: Number(comandaForm.mesa_id),
            cliente_id: comandaForm.cliente_id ? Number(comandaForm.cliente_id) : null,
            detalle,
          }),
        }),
      "Comanda abierta"
    );
    setComandaForm({ mesa_id: "", cliente_id: "", lineas: [{ producto_id: "", cantidad: 1, precio: 0, preparacion: "" }] });
  }

  async function agregarLinea(comandaId) {
    const pid = window.prompt("Producto ID:");
    const cant = window.prompt("Cantidad:", 1);
    if (!pid) return;
    await submit(
      () =>
        api(`/restaurante/comandas/${comandaId}/agregar`, {
          method: "POST",
          body: JSON.stringify([{ producto_id: Number(pid), cantidad: Number(cant), precio: 0 }]),
        }),
      "Línea agregada"
    );
  }

  async function servir(comandaId, lineaId) {
    await submit(() => api(`/restaurante/comandas/${comandaId}/lineas/${lineaId}/servir`, { method: "POST" }), "Línea servida");
  }

  async function cerrar(comandaId) {
    if (!window.confirm("Cerrar comanda (genera venta y factura)?")) return;
    await submit(() => api(`/restaurante/comandas/${comandaId}/cerrar`, { method: "POST" }), "Comanda cerrada");
  }

  async function crearReserva(e) {
    e.preventDefault();
    await submit(
      () =>
        api("/restaurante/reservas", {
          method: "POST",
          body: JSON.stringify({ ...reservaForm, mesa_id: Number(reservaForm.mesa_id) }),
        }),
      "Reserva creada"
    );
    setReservaForm({ mesa_id: "", cliente: "", telefono: "" });
  }

  async function verDetalle(comandaId) {
    setError("");
    setMsg("");
    try {
      setDetalle(await api(`/restaurante/comandas/${comandaId}`));
    } catch (e) {
      setError(e.message);
    }
  }

  const badge = (e) => <span className={`badge ${e === "disponible" || e === "entregado" ? "badge-success" : ""}`}>{e}</span>;

  return (
    <div className="page">
      <div className="hero" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 16, flexWrap: "wrap" }}>
        <div>
          <h1>Restaurante</h1>
          <p>Salones, mesas, comandas y reservas con control de consumos en tiempo real.</p>
        </div>
        <div className="hero-actions">
          <button className="btn" onClick={() => setTab("salones")}>🍽️ Salones</button>
          <button className="btn" onClick={() => setTab("comandas")}>🧾 Comandas</button>
          <button className="btn" onClick={() => setTab("cocina")}>👨‍🍳 Cocina</button>
          <button className="btn" onClick={() => setTab("reservas")}>📅 Reservas</button>
        </div>
      </div>

      {resumen && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px,1fr))", gap: 16, marginBottom: 18 }}>
          <KpiCard label="Salones" value={resumen.salones ?? 0} icon="🍽️" accent="#ef4444" />
          <KpiCard label="Mesas" value={resumen.mesas ?? 0} icon="🪑" accent="#22d3ee" />
          <KpiCard label="Mesas ocupadas" value={resumen.mesas_ocupadas ?? 0} icon="🔴" accent="#f43f5e" sub={`${resumen.mesas - resumen.mesas_ocupadas} disponibles`} />
          <KpiCard label="Comandas abiertas" value={resumen.comandas_abiertas ?? 0} icon="🧾" accent="#f59e0b" />
          <KpiCard label="Reservas de hoy" value={resumen.reservas_hoy ?? 0} icon="📅" accent="#10b981" />
        </div>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px,1fr))", gap: 18, marginBottom: 18 }}>
        <ChartCard title="Ocupación de mesas" subtitle="Disponibles vs ocupadas" height={230}>
          <Donut
            data={[
              { name: "Disponibles", value: (resumen?.mesas ?? 0) - (resumen?.mesas_ocupadas ?? 0) },
              { name: "Ocupadas", value: resumen?.mesas_ocupadas ?? 0 },
            ]}
            centerLabel="Del total"
            centerValue={resumen?.mesas ?? 0}
            colors={["#22d3ee", "#f43f5e"]}
          />
        </ChartCard>
        <ChartCard title="Salones" subtitle="Salas registradas en el restaurante" height={230} accent="#f97316">
          <Donut
            data={salones.map((s) => ({
              name: s.nombre,
              value: (s.mesas || []).length,
            }))}
            centerLabel="Mesas p/ salón"
            centerValue={salones.length}
          />
        </ChartCard>
      </div>

      {msg && <div className="badge-success" style={{ display: "inline-block", marginBottom: 8, padding: "6px 10px", borderRadius: 6 }}>{msg}</div>}
      {error && <div className="error">{error}</div>}

      {tab === "salones" && (
        <>
          <form onSubmit={crearSalon} className="card" style={{ padding: 14, marginBottom: 14, display: "flex", gap: 10 }}>
            <input required placeholder="Nombre del salón" value={salonNombre} onChange={(e) => setSalonNombre(e.target.value)} />
            <button className="btn btn-primary">+ Salón</button>
          </form>
          <form onSubmit={crearMesa} className="card" style={{ padding: 14, marginBottom: 16, display: "flex", gap: 10, flexWrap: "wrap" }}>
            <select required value={mesaForm.salon_id} onChange={(e) => setMesaForm({ ...mesaForm, salon_id: e.target.value })}>
              <option value="">Salón…</option>
              {salones.map((s) => (
                <option key={s.id} value={s.id}>{s.nombre}</option>
              ))}
            </select>
            <input required placeholder="Nombre mesa (M1)" value={mesaForm.nombre} onChange={(e) => setMesaForm({ ...mesaForm, nombre: e.target.value })} />
            <input type="number" min={1} style={{ width: 90 }} value={mesaForm.capacidad} onChange={(e) => setMesaForm({ ...mesaForm, capacidad: e.target.value })} />
            <button className="btn btn-primary">+ Mesa</button>
          </form>
          {salones.map((s) => (
            <div key={s.id} className="card" style={{ padding: 14, marginBottom: 12 }}>
              <h3 style={{ marginBottom: 10 }}>{s.nombre}</h3>
              <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
                {s.mesas.map((m) => (
                  <div key={m.id} style={{ border: "1px solid #ddd", borderRadius: 8, padding: "10px 14px", minWidth: 130 }}>
                    <div><b>{m.nombre}</b> · cap. {m.capacidad}</div>
                    <div style={{ margin: "6px 0" }}>{badge(m.estado)}</div>
                    <div style={{ display: "flex", gap: 4 }}>
                      {m.estado === "disponible" && <button className="btn btn-sm btn-primary" onClick={() => ocupar(m.id)}>Ocupar</button>}
                      {m.estado === "ocupada" && <button className="btn btn-sm" onClick={() => liberar(m.id)}>Liberar</button>}
                      <button className="btn btn-sm" onClick={() => setQrMesa(m.id)}>📱 QR</button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </>
      )}

      {tab === "comandas" && (
        <>
          <form onSubmit={crearComanda} className="card" style={{ padding: 14, marginBottom: 16, display: "grid", gap: 10 }}>
            <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
              <select required value={comandaForm.mesa_id} onChange={(e) => setComandaForm({ ...comandaForm, mesa_id: e.target.value })}>
                <option value="">Mesa…</option>
                {mesas.filter((m) => m.estado === "disponible" || m.estado === "ocupada").map((m) => (
                  <option key={m.id} value={m.id}>{m.nombre} ({m.estado})</option>
                ))}
              </select>
              <select value={comandaForm.cliente_id} onChange={(e) => setComandaForm({ ...comandaForm, cliente_id: e.target.value })}>
                <option value="">Cliente (opcional)</option>
                {clientes.map((c) => (
                  <option key={c.id} value={c.id}>{c.nombre}</option>
                ))}
              </select>
            </div>
            {comandaForm.lineas.map((l, i) => (
              <div key={i} style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
                <select required value={l.producto_id} onChange={(e) => setLinea(i, "producto_id", e.target.value)}>
                  <option value="">Producto…</option>
                  {productos.map((p) => (
                    <option key={p.id} value={p.id}>{p.nombre}</option>
                  ))}
                </select>
                <input type="number" min={1} style={{ width: 80 }} value={l.cantidad} onChange={(e) => setLinea(i, "cantidad", e.target.value)} />
                <input placeholder="Preparación (crudo…)" value={l.preparacion} onChange={(e) => setLinea(i, "preparacion", e.target.value)} />
                <button type="button" className="btn btn-sm" onClick={() => setComandaForm({ ...comandaForm, lineas: comandaForm.lineas.filter((_, x) => x !== i) })}>Quitar</button>
              </div>
            ))}
            <div style={{ display: "flex", gap: 10 }}>
              <button type="button" className="btn" onClick={() => setComandaForm({ ...comandaForm, lineas: [...comandaForm.lineas, { producto_id: "", cantidad: 1, precio: 0, preparacion: "" }] })}>+ Línea</button>
              <button className="btn btn-primary">Abrir comanda</button>
            </div>
          </form>

          <table className="table">
            <thead><tr><th>Nº</th><th>Mesa</th><th>Estado</th><th>Total</th><th>Lineas</th><th>Acciones</th></tr></thead>
            <tbody>
              {comandas.length === 0 && (
                <tr><td colSpan={6}>Sin comandas.</td></tr>
              )}
              {comandas.map((c) => (
                <tr key={c.id}>
                  <td><b>{c.numero}</b></td>
                  <td>{mesas.find((m) => m.id === c.mesa_id)?.nombre || c.mesa_id}</td>
                  <td>{badge(c.estado)}</td>
                  <td>${c.total.toLocaleString("es-CO")}</td>
                  <td style={{ fontSize: 12 }}>
                    {c.detalle.map((d) => (
                      <div key={d.id}>
                        {d.cantidad} × {d.producto || d.producto_id}{d.preparacion ? ` (${d.preparacion})` : ""} {d.entregado ? " ✓" : ""}
                      </div>
                    ))}
                  </td>
                  <td>
                    <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                      <button className="btn btn-sm btn-ghost" onClick={() => verDetalle(c.id)}>Detalle</button>
                      {c.estado === "abierta" && (
                        <>
                          <button className="btn btn-sm" onClick={() => agregarLinea(c.id)}>+ Línea</button>
                          {c.detalle.filter((d) => !d.entregado).map((d) => (
                            <button key={d.id} className="btn btn-sm" onClick={() => servir(c.id, d.id)}>Servir {d.id}</button>
                          ))}
                          <button className="btn btn-sm btn-primary" onClick={() => cerrar(c.id)}>Cerrar (cobrar)</button>
                        </>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}

      {tab === "reservas" && (
        <>
          <form onSubmit={crearReserva} className="card" style={{ padding: 14, marginBottom: 14, display: "flex", gap: 10, flexWrap: "wrap" }}>
            <select required value={reservaForm.mesa_id} onChange={(e) => setReservaForm({ ...reservaForm, mesa_id: e.target.value })}>
              <option value="">Mesa…</option>
              {mesas.map((m) => (
                <option key={m.id} value={m.id}>{m.nombre}</option>
              ))}
            </select>
            <input required placeholder="Cliente" value={reservaForm.cliente} onChange={(e) => setReservaForm({ ...reservaForm, cliente: e.target.value })} />
            <input placeholder="Teléfono" value={reservaForm.telefono} onChange={(e) => setReservaForm({ ...reservaForm, telefono: e.target.value })} />
            <button className="btn btn-primary">Reservar</button>
          </form>
          <table className="table">
            <thead><tr><th>Mesa</th><th>Cliente</th><th>Teléfono</th><th>Fecha</th><th>Estado</th></tr></thead>
            <tbody>
              {reservas.length === 0 && (
                <tr><td colSpan={5}>Sin reservas.</td></tr>
              )}
              {reservas.map((r) => (
                <tr key={r.id}>
                  <td>{mesas.find((m) => m.id === r.mesa_id)?.nombre || r.mesa_id}</td>
                  <td>{r.cliente}</td>
                  <td>{r.telefono || "-"}</td>
                  <td style={{ fontSize: 12 }}>{r.inicio || "-"}</td>
                  <td>{badge(r.estado)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}

      {tab === "cocina" && (
        <CocinaKDS mesas={mesas} onServida={() => load()} />
      )}

      {qrMesa && (
        <QrMesaModal
          mesa={mesas.find((m) => m.id === qrMesa)}
          onClose={() => setQrMesa(null)}
        />
      )}

      {detalle && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,.45)", display: "grid", placeItems: "center", zIndex: 1100, padding: 20 }}>
          <div className="card" style={{ width: "min(640px, 100%)" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
              <h3>Comanda {detalle.numero} · {mesas.find((m) => m.id === detalle.mesa_id)?.nombre || `mesa #${detalle.mesa_id}`}</h3>
              <button className="btn btn-ghost" onClick={() => setDetalle(null)}>✕</button>
            </div>
            <p className="muted">
              Estado: {badge(detalle.estado)} · Total <strong>{detalle.total.toLocaleString("es-CO")}</strong>
              {detalle.cliente_id && <> · Cliente #{detalle.cliente_id}</>}
              {detalle.created_at && <> · {new Date(detalle.created_at).toLocaleString()}</>}
            </p>
            <table className="table" style={{ marginTop: 10 }}>
              <thead><tr><th>Producto</th><th>Cantidad</th><th>Precio</th><th>Subtotal</th><th>Preparación</th><th>Estado</th></tr></thead>
              <tbody>
                {(detalle.detalle || []).map((d) => (
                  <tr key={d.id}>
                    <td>{d.producto || `#${d.producto_id}`}</td>
                    <td>{d.cantidad}</td>
                    <td>{d.precio.toLocaleString("es-CO")}</td>
                    <td>{d.subtotal.toLocaleString("es-CO")}</td>
                    <td style={{ fontSize: 12 }}>{d.preparacion || "—"}</td>
                    <td>{d.entregado ? <span className="badge badge-success">Servida</span> : <span className="badge">Pendiente</span>}</td>
                  </tr>
                ))}
                {(detalle.detalle || []).length === 0 && <tr><td colSpan={6} className="muted" style={{ textAlign: "center" }}>Sin líneas</td></tr>}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

function QrMesaModal({ mesa, onClose }) {
  const [copiado, setCopiado] = useState(false);
  const [baseUrl, setBaseUrl] = useState("");
  useEffect(() => {
    let muerto = false;
    api("/configuracion/general")
      .then((lista) => {
        if (muerto || !Array.isArray(lista)) return;
        const u = lista.find((c) => c.clave === "pos.url_publica");
        if (u && u.valor) setBaseUrl(String(u.valor).replace(/\/+$/, ""));
      })
      .catch(() => {});
    return () => {
      muerto = true;
    };
  }, []);
  if (!mesa) return null;
  const base = baseUrl || window.location.origin;
  const url = `${base}/publico/menu/${mesa.id}`;
  const qrSrc = `/publico/qr?texto=${encodeURIComponent(url)}&tam=460`;
  async function copiar() {
    try {
      await navigator.clipboard.writeText(url);
      setCopiado(true);
      setTimeout(() => setCopiado(false), 1500);
    } catch {}
  }
  return (
    <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,.55)", display: "grid", placeItems: "center", zIndex: 1100, padding: 20 }}>
      <div className="card" style={{ width: "min(560px, 100%)", textAlign: "center" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
          <h3>Menú digital · {mesa.nombre}</h3>
          <button className="btn btn-ghost" onClick={onClose}>✕</button>
        </div>
        <p className="muted" style={{ marginBottom: 12, fontSize: 13 }}>
          El cliente escanea y pide directo desde su celular; el pedido llega a la cocina y a Restaurante.
        </p>
        <div style={{ background: "#fff", borderRadius: 14, padding: 14, display: "inline-block", marginBottom: 12 }}>
          <img src={qrSrc} alt={`QR mesa ${mesa.nombre}`} width={260} height={260} style={{ display: "block" }} />
        </div>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", justifyContent: "center" }}>
          <input readOnly value={url} style={{ flex: 1, minWidth: 220, fontSize: 12 }} onFocus={(e) => e.target.select()} />
          <button className="btn btn-sm" onClick={copiar}>{copiado ? "✓ Copiado" : "Copiar"}</button>
          <button className="btn btn-sm btn-primary" onClick={() => window.open(`/publico/qr?texto=${encodeURIComponent(url)}&tam=900`, "_blank")}>🖨️ Imprimir</button>
        </div>
      </div>
    </div>
  );
}

function CocinaKDS({ mesas, onServida }) {
  const [comandas, setComandas] = useState([]);
  const [err, setErr] = useState("");

  async function load() {
    try {
      const data = await api("/restaurante/comandas");
      setComandas(data.filter((c) => c.estado !== "cerrada"));
    } catch (e) {
      setErr(e.message);
    }
  }

  useEffect(() => {
    load();
    const t = setInterval(load, 5000);
    return () => clearInterval(t);
  }, []);

  async function servir(comandaId, lineaId) {
    setErr("");
    try {
      await api(`/restaurante/comandas/${comandaId}/lineas/${lineaId}/servir`, { method: "POST" });
      onServida();
      load();
    } catch (e) {
      setErr(e.message);
    }
  }

  const pendientes = comandas.filter((c) => c.detalle.some((d) => !d.entregado));
  const totalLineas = pendientes.reduce((n, c) => n + c.detalle.filter((d) => !d.entregado).length, 0);

  return (
    <>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 10, flexWrap: "wrap", marginBottom: 14 }}>
        <span className="chip">🔔 {totalLineas} líneas por preparar · {pendientes.length} comandas activas</span>
        <button className="btn btn-sm" onClick={load}>↻ Refrescar</button>
      </div>
      {err && <div className="error">{err}</div>}
      {pendientes.length === 0 ? (
        <div className="card" style={{ padding: 30, textAlign: "center", color: "var(--muted)" }}>
          🎉 Cocina al día, sin pendientes.
        </div>
      ) : (
        <div style={{ display: "grid", gap: 14, gridTemplateColumns: "repeat(auto-fill,minmax(250px,1fr))" }}>
          {pendientes.map((c) => (
            <div key={c.id} className="kds-card">
              <div className="kds-head">
                <b>{c.numero}</b>
                <span className="badge">{c.estado}</span>
              </div>
              <div style={{ fontSize: 12.5, color: "var(--muted)", marginBottom: 8 }}>
                Mesa: {mesas.find((m) => m.id === c.mesa_id)?.nombre || c.mesa_id}
              </div>
              <div style={{ display: "grid", gap: 6 }}>
                {c.detalle.filter((d) => !d.entregado).map((d) => (
                  <div key={d.id} className="kds-line">
                    <div style={{ flex: 1 }}>
                      <b>{d.cantidad} × {d.producto || d.producto_id}</b>
                      {d.preparacion && <div className="kds-pre">{d.preparacion}</div>}
                    </div>
                    <button className="btn btn-sm btn-primary" onClick={() => servir(c.id, d.id)}>✓ Servir</button>
                  </div>
                ))}
              </div>
              {c.detalle.some((d) => d.entregado) && (
                <div style={{ fontSize: 12, color: "#10b981", marginTop: 8 }}>✔ {c.detalle.filter((d) => d.entregado).length} servidas</div>
              )}
            </div>
          ))}
        </div>
      )}
    </>
  );
}