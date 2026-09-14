import { useEffect, useState } from "react";
import api from "../api.js";
import { formatMoney } from "../components/ui.jsx";

export default function Integraciones() {
  const [tab, setTab] = useState("monedas");
  const [error, setError] = useState("");

  const [monedas, setMonedas] = useState([]);
  const [moneda, setMoneda] = useState({ codigo: "", nombre: "", simbolo: "", tasa_cambio: "", activa: true });
  const [convertir, setConvertir] = useState({ id: "", monto: "", base: "COP" });

  const [balanzas, setBalanzas] = useState([]);
  const [balanza, setBalanza] = useState({ nombre: "", modelo: "", puerto: "", formato: "SAP", tasa: 1, activa: true });
  const [peso, setPeso] = useState(null);

  const [cuentas, setCuentas] = useState([]);
  const [cuenta, setCuenta] = useState({ banco: "", numero_cuenta: "", tipo: "corriente", titular: "", saldo_inicial: "" });
  const [movForm, setMovForm] = useState({ cuenta_id: "", tipo: "ingreso", monto: "", concepto: "" });
  const [movs, setMovs] = useState([]);

  const [webhooks, setWebhooks] = useState([]);
  const [webhook, setWebhook] = useState({ evento: "venta.creada", url: "", token: "", activo: true });

  const [wa, setWa] = useState({ telefono: "", mensaje: "" });

  const [backups, setBackups] = useState([]);
  const [haciendo, setHaciendo] = useState(false);

  const [tarjetas, setTarjetas] = useState([]);

  useEffect(() => {
    api("/monedas").then(setMonedas).catch(() => {});
    api("/balanzas").then(setBalanzas).catch(() => {});
    api("/bancos/cuentas").then(setCuentas).catch(() => {});
    api("/bancos/movimientos").then(setMovs).catch(() => {});
    api("/webhooks").then(setWebhooks).catch(() => {});
    api("/backups").then(setBackups).catch(() => {});
    api("/pagos/tarjeta").then(setTarjetas).catch(() => {});
  }, []);

  async function crearMoneda(e) {
    e.preventDefault();
    setError("");
    try {
      await api("/monedas", { method: "POST", body: JSON.stringify({ ...moneda, tasa_cambio: Number(moneda.tasa_cambio) || 1 }) });
      setMoneda({ codigo: "", nombre: "", simbolo: "", tasa_cambio: "", activa: true });
      api("/monedas").then(setMonedas);
    } catch (err) {
      setError(err.message);
    }
  }

  async function doConvertir(e) {
    e.preventDefault();
    setError("");
    try {
      const r = await api(`/monedas/${convertir.id}/convertir?monto=${convertir.monto}&base=${convertir.base}`);
      alert(`${Number(convertir.monto).toLocaleString()} ${convertir.base} = ${r.monto.toLocaleString()} ${r.codigo}`);
    } catch (err) {
      setError(err.message);
    }
  }

  async function crearBalanza(e) {
    e.preventDefault();
    setError("");
    try {
      await api("/balanzas", { method: "POST", body: JSON.stringify({ ...balanza, tasa: Number(balanza.tasa) || 1 }) });
      setBalanza({ nombre: "", modelo: "", puerto: "", formato: "SAP", tasa: 1, activa: true });
      api("/balanzas").then(setBalanzas);
    } catch (err) {
      setError(err.message);
    }
  }

  async function pesar(id) {
    setError("");
    try {
      setPeso(await api(`/balanzas/${id}/pesar`, { method: "POST" }));
    } catch (err) {
      setError(err.message);
    }
  }

  async function crearCuenta(e) {
    e.preventDefault();
    setError("");
    try {
      await api("/bancos/cuentas", { method: "POST", body: JSON.stringify({ ...cuenta, saldo_inicial: Number(cuenta.saldo_inicial) || 0 }) });
      setCuenta({ banco: "", numero_cuenta: "", tipo: "corriente", titular: "", saldo_inicial: "" });
      api("/bancos/cuentas").then(setCuentas);
    } catch (err) {
      setError(err.message);
    }
  }

  async function registrarMov(e) {
    e.preventDefault();
    setError("");
    try {
      await api("/bancos/movimientos", { method: "POST", body: JSON.stringify({ ...movForm, monto: Number(movForm.monto) }) });
      setMovForm({ cuenta_id: "", tipo: "ingreso", monto: "", concepto: "" });
      api("/bancos/movimientos").then(setMovs);
      api("/bancos/cuentas").then(setCuentas);
    } catch (err) {
      setError(err.message);
    }
  }

  async function conciliar(id) {
    setError("");
    try {
      await api(`/bancos/movimientos/${id}/conciliar`, { method: "POST" });
      api("/bancos/movimientos").then(setMovs);
    } catch (err) {
      setError(err.message);
    }
  }

  async function crearWebhook(e) {
    e.preventDefault();
    setError("");
    try {
      await api("/webhooks", { method: "POST", body: JSON.stringify(webhook) });
      setWebhook({ evento: "venta.creada", url: "", token: "", activo: true });
      api("/webhooks").then(setWebhooks);
    } catch (err) {
      setError(err.message);
    }
  }

  async function enviarWa(e) {
    e.preventDefault();
    setError("");
    try {
      await api(`/whatsapp/enviar?telefono=${wa.telefono}&mensaje=${encodeURIComponent(wa.mensaje)}`, { method: "POST" });
      setWa({ telefono: "", mensaje: "" });
      alert("Mensaje enviado (simulado)");
    } catch (err) {
      setError(err.message);
    }
  }

  async function editarMoneda(m) {
    const tasa = window.prompt(`Tasa de ${m.codigo} (1 moneda en COP):`, m.tasa_cambio);
    if (tasa === null) return;
    const a = window.prompt("¿Activa? (s/n):", m.activa ? "s" : "n");
    const activa = a !== null ? a.trim().toLowerCase()[0] === "s" : m.activa;
    try {
      await api(`/monedas/${m.id}`, { method: "PUT", body: JSON.stringify({ ...m, tasa_cambio: Number(tasa) || 1, activa }) });
      api("/monedas").then(setMonedas);
    } catch (err) {
      setError(err.message);
    }
  }

  async function editarBalanza(b) {
    const puerto = window.prompt("Puerto:", b.puerto || "COM1");
    if (puerto === null) return;
    const formato = window.prompt("Formato (SAP/NCR/CAS):", b.formato || "SAP");
    if (formato === null) return;
    const a = window.prompt("¿Activa? (s/n):", b.activa ? "s" : "n");
    const activa = a !== null ? a.trim().toLowerCase()[0] === "s" : b.activa;
    try {
      await api(`/balanzas/${b.id}`, { method: "PUT", body: JSON.stringify({ ...b, puerto, formato, activa }) });
      api("/balanzas").then(setBalanzas);
    } catch (err) {
      setError(err.message);
    }
  }

  async function editarCuenta(c) {
    const titular = window.prompt("Titular:", c.titular || "");
    if (titular === null) return;
    const banco = window.prompt("Banco:", c.banco);
    if (banco === null) return;
    try {
      await api(`/bancos/cuentas/${c.id}`, { method: "PUT", body: JSON.stringify({ ...c, titular, banco }) });
      api("/bancos/cuentas").then(setCuentas);
    } catch (err) {
      setError(err.message);
    }
  }

  async function editarWebhook(w) {
    const url = window.prompt("URL:", w.url);
    if (url === null) return;
    const a = window.prompt("¿Activo? (s/n):", w.activo ? "s" : "n");
    const activo = a !== null ? a.trim().toLowerCase()[0] === "s" : w.activo;
    try {
      await api(`/webhooks/${w.id}`, { method: "PUT", body: JSON.stringify({ ...w, url, activo }) });
      api("/webhooks").then(setWebhooks);
    } catch (err) {
      setError(err.message);
    }
  }

  async function crearBackup() {
    setError("");
    setHaciendo(true);
    try {
      const r = await api("/backups", { method: "POST" });
      alert(`Backup #${r.id} creado: ${r.registros} registros en ${r.tablas} tablas`);
      api("/backups").then(setBackups);
    } catch (err) {
      setError(err.message);
    } finally {
      setHaciendo(false);
    }
  }

  async function restaurar(id) {
    setError("");
    if (!window.confirm("¿Restaurar este backup? Sobrescribirá los datos actuales.")) return;
    try {
      await api(`/backups/${id}/restaurar`, { method: "POST" });
      alert("Backup restaurado");
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div className="page">
      <div className="page-header">
        <h1>Integraciones</h1>
        <div className="tabs">
          {["monedas", "balanzas", "bancos", "pagos-tarjeta", "webhooks", "whatsapp", "backups"].map((t) => (
            <button key={t} className={`btn ${tab === t ? "btn-primary" : ""}`} onClick={() => setTab(t)}>
              {t === "monedas" ? "Monedas" : t === "balanzas" ? "Balanzas" : t === "bancos" ? "Bancos" : t === "pagos-tarjeta" ? "Pagos tarjeta" : t === "webhooks" ? "Webhooks" : t === "whatsapp" ? "WhatsApp" : "Backups"}
            </button>
          ))}
        </div>
      </div>

      {error && <div className="error">{error}</div>}

      {tab === "monedas" && (
        <>
          <form onSubmit={crearMoneda} className="card" style={{ marginBottom: 20, display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))", gap: 12 }}>
            <div><label>Código *</label><input required value={moneda.codigo} onChange={(e) => setMoneda({ ...moneda, codigo: e.target.value })} placeholder="USD" /></div>
            <div><label>Nombre</label><input value={moneda.nombre} onChange={(e) => setMoneda({ ...moneda, nombre: e.target.value })} /></div>
            <div><label>Símbolo</label><input value={moneda.simbolo} onChange={(e) => setMoneda({ ...moneda, simbolo: e.target.value })} /></div>
            <div><label>Tasa (1 moneda en COP)</label><input type="number" value={moneda.tasa_cambio} onChange={(e) => setMoneda({ ...moneda, tasa_cambio: e.target.value })} /></div>
            <div style={{ display: "flex", alignItems: "flex-end" }}><button className="btn" type="submit">Agregar</button></div>
          </form>
          <form onSubmit={doConvertir} className="card" style={{ marginBottom: 20, display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))", gap: 12 }}>
            <div>
              <label>Convertir</label>
              <select required value={convertir.id} onChange={(e) => setConvertir({ ...convertir, id: e.target.value })}>
                <option value="">Moneda...</option>
                {monedas.map((m) => <option key={m.id} value={m.id}>{m.codigo}</option>)}
              </select>
            </div>
            <div><label>Monto</label><input required type="number" value={convertir.monto} onChange={(e) => setConvertir({ ...convertir, monto: e.target.value })} /></div>
            <div>
              <label>Base</label>
              <select value={convertir.base} onChange={(e) => setConvertir({ ...convertir, base: e.target.value })}>
                <option value="COP">COP</option>
                <option value="MONEDA">Moneda</option>
              </select>
            </div>
            <div style={{ display: "flex", alignItems: "flex-end" }}><button className="btn btn-secondary" type="submit">Convertir</button></div>
          </form>
          <table className="table">
            <thead><tr><th>Código</th><th>Nombre</th><th>Tasa (1 = COP)</th><th>Estado</th><th></th></tr></thead>
            <tbody>
              {monedas.map((m) => (
                <tr key={m.id}>
                  <td><strong>{m.simbolo || ""} {m.codigo}</strong></td>
                  <td>{m.nombre || "—"}</td>
                  <td>{m.tasa_cambio}</td>
                  <td><span className={`badge ${m.activa ? "badge-success" : "badge-danger"}`}>{m.activa ? "Activa" : "Inactiva"}</span></td>
                  <td><button className="btn btn-sm" onClick={() => editarMoneda(m)}>Editar</button></td>
                </tr>
              ))}
              {monedas.length === 0 && <tr><td colSpan={5} className="muted" style={{ textAlign: "center", padding: 20 }}>Sin monedas registradas</td></tr>}
            </tbody>
          </table>
        </>
      )}

      {tab === "balanzas" && (
        <>
          <form onSubmit={crearBalanza} className="card" style={{ marginBottom: 20, display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))", gap: 12 }}>
            <div><label>Nombre *</label><input required value={balanza.nombre} onChange={(e) => setBalanza({ ...balanza, nombre: e.target.value })} placeholder="Balanza caja 1" /></div>
            <div><label>Modelo</label><input value={balanza.modelo} onChange={(e) => setBalanza({ ...balanza, modelo: e.target.value })} /></div>
            <div><label>Puerto</label><input value={balanza.puerto} onChange={(e) => setBalanza({ ...balanza, puerto: e.target.value })} placeholder="COM1" /></div>
            <div>
              <label>Formato</label>
              <select value={balanza.formato} onChange={(e) => setBalanza({ ...balanza, formato: e.target.value })}>
                <option value="SAP">SAP</option>
                <option value="NCR">NCR</option>
                <option value="CAS">CAS</option>
              </select>
            </div>
            <div style={{ display: "flex", alignItems: "flex-end" }}><button className="btn" type="submit">Agregar</button></div>
          </form>
          <table className="table">
            <thead><tr><th>Nombre</th><th>Modelo</th><th>Puerto</th><th>Estado</th><th></th></tr></thead>
            <tbody>
              {balanzas.map((b) => (
                <tr key={b.id}>
                  <td><strong>{b.nombre}</strong></td>
                  <td>{b.modelo || "—"}</td>
                  <td>{b.puerto || "—"}</td>
                  <td><span className={`badge ${b.activa ? "badge-success" : "badge-danger"}`}>{b.activa ? "Activa" : "Inactiva"}</span></td>
                  <td style={{ display: "flex", gap: 6 }}>
                    <button className="btn btn-sm" onClick={() => editarBalanza(b)}>Editar</button>
                    <button className="btn btn-sm btn-secondary" onClick={() => pesar(b.id)}>Pesar</button>
                  </td>
                </tr>
              ))}
              {balanzas.length === 0 && <tr><td colSpan={5} className="muted" style={{ textAlign: "center", padding: 20 }}>Sin balanzas</td></tr>}
            </tbody>
          </table>
          {peso && (
            <div className="card" style={{ marginTop: 16, textAlign: "center" }}>
              <div className="muted">Última lectura — {peso.balanza}</div>
              <div style={{ fontSize: 40, fontWeight: 800, color: "#4f46e5" }}>{peso.peso} <small>kg</small></div>
              <div className="muted">{peso.estable ? "Peso estable ✓" : "Inestable"}</div>
            </div>
          )}
        </>
      )}

      {tab === "bancos" && (
        <>
          <form onSubmit={crearCuenta} className="card" style={{ marginBottom: 20, display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(170px, 1fr))", gap: 12 }}>
            <div><label>Banco *</label><input required value={cuenta.banco} onChange={(e) => setCuenta({ ...cuenta, banco: e.target.value })} /></div>
            <div><label>N° cuenta</label><input value={cuenta.numero_cuenta} onChange={(e) => setCuenta({ ...cuenta, numero_cuenta: e.target.value })} /></div>
            <div>
              <label>Tipo</label>
              <select value={cuenta.tipo} onChange={(e) => setCuenta({ ...cuenta, tipo: e.target.value })}>
                <option value="corriente">Corriente</option>
                <option value="ahorros">Ahorros</option>
              </select>
            </div>
            <div><label>Titular</label><input value={cuenta.titular} onChange={(e) => setCuenta({ ...cuenta, titular: e.target.value })} /></div>
            <div><label>Saldo inicial</label><input type="number" value={cuenta.saldo_inicial} onChange={(e) => setCuenta({ ...cuenta, saldo_inicial: e.target.value })} /></div>
            <div style={{ display: "flex", alignItems: "flex-end" }}><button className="btn" type="submit">Agregar cuenta</button></div>
          </form>

          <table className="table" style={{ marginBottom: 20 }}>
            <thead><tr><th>Banco</th><th>Cuenta</th><th>Tipo</th><th>Saldo</th><th></th></tr></thead>
            <tbody>
              {cuentas.map((c) => (
                <tr key={c.id}>
                  <td><strong>{c.banco}</strong></td>
                  <td>{c.numero_cuenta || c.titular || "—"}</td>
                  <td>{c.tipo}</td>
                  <td><strong style={{ color: "#4f46e5" }}>{formatMoney(c.saldo)}</strong></td>
                  <td><button className="btn btn-sm" onClick={() => editarCuenta(c)}>Editar</button></td>
                </tr>
              ))}
              {cuentas.length === 0 && <tr><td colSpan={5} className="muted" style={{ textAlign: "center", padding: 20 }}>Sin cuentas bancarias</td></tr>}
            </tbody>
          </table>

          <h2 style={{ fontSize: 16, marginBottom: 10 }}>Movimientos bancarios</h2>
          <form onSubmit={registrarMov} className="card" style={{ marginBottom: 20, display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))", gap: 12 }}>
            <div>
              <label>Cuenta *</label>
              <select required value={movForm.cuenta_id} onChange={(e) => setMovForm({ ...movForm, cuenta_id: e.target.value })}>
                <option value="">Cuenta...</option>
                {cuentas.map((c) => <option key={c.id} value={c.id}>{c.banco} {c.numero_cuenta || ""}</option>)}
              </select>
            </div>
            <div>
              <label>Tipo</label>
              <select value={movForm.tipo} onChange={(e) => setMovForm({ ...movForm, tipo: e.target.value })}>
                <option value="ingreso">Ingreso</option>
                <option value="egreso">Egreso</option>
              </select>
            </div>
            <div><label>Monto</label><input required type="number" value={movForm.monto} onChange={(e) => setMovForm({ ...movForm, monto: e.target.value })} /></div>
            <div><label>Concepto</label><input value={movForm.concepto} onChange={(e) => setMovForm({ ...movForm, concepto: e.target.value })} /></div>
            <div style={{ display: "flex", alignItems: "flex-end" }}><button className="btn" type="submit">Registrar</button></div>
          </form>

          <table className="table">
            <thead><tr><th>Fecha</th><th>Cuenta</th><th>Tipo</th><th>Monto</th><th>Concepto</th><th>Conciliado</th><th></th></tr></thead>
            <tbody>
              {movs.map((mv) => (
                <tr key={mv.id}>
                  <td>{mv.fecha ? new Date(mv.fecha).toLocaleDateString() : "—"}</td>
                  <td>{cuentas.find((c) => c.id === mv.cuenta_id)?.banco || mv.cuenta_id}</td>
                  <td><span className={`badge ${mv.tipo === "ingreso" ? "badge-success" : "badge-danger"}`}>{mv.tipo}</span></td>
                  <td>{formatMoney(mv.monto)}</td>
                  <td>{mv.concepto || "—"}</td>
                  <td><span className={`badge ${mv.conciliado ? "badge-success" : "badge-warning"}`}>{mv.conciliado ? "Sí" : "No"}</span></td>
                  <td>{!mv.conciliado && <button className="btn btn-secondary" onClick={() => conciliar(mv.id)}>Conciliar</button>}</td>
                </tr>
              ))}
              {movs.length === 0 && <tr><td colSpan={7} className="muted" style={{ textAlign: "center", padding: 20 }}>Sin movimientos</td></tr>}
            </tbody>
          </table>
        </>
      )}

      {tab === "pagos-tarjeta" && (
        <>
          <div className="card" style={{ padding: 14, marginBottom: 16 }}>
            <h3 style={{ fontSize: 15 }}>Transacciones de tarjeta (datáfono)</h3>
            <p className="muted" style={{ fontSize: 12.5 }}>
              Registro de autorizaciones, confirmaciones y reversos emitidos desde el punto de venta. El cobro de tarjeta se inicia en la caja.
            </p>
          </div>
          <table className="table">
            <thead><tr><th>ID</th><th>Fecha</th><th>Monto</th><th>Marca</th><th>Últimos 4</th><th>Estado</th><th>Autorización</th><th>Venta</th></tr></thead>
            <tbody>
              {tarjetas.map((t) => (
                <tr key={t.id}>
                  <td>#{t.id}</td>
                  <td style={{ fontSize: 12 }}>{t.created_at ? new Date(t.created_at).toLocaleString() : "—"}</td>
                  <td><strong>{formatMoney(t.monto)}</strong></td>
                  <td>{t.marca}</td>
                  <td>{t.ultimos4 ? `•••• ${t.ultimos4}` : "—"}</td>
                  <td><span className={`badge ${t.estado === "confirmado" ? "badge-success" : t.estado === "reversado" ? "badge-danger" : "badge-warning"}`}>{t.estado}</span></td>
                  <td>{t.codigo_autorizacion || t.referencia || "—"}</td>
                  <td>{t.venta_id ? `V-${String(t.venta_id).padStart(6, "0")}` : "—"}</td>
                </tr>
              ))}
              {tarjetas.length === 0 && <tr><td colSpan={8} className="muted" style={{ textAlign: "center", padding: 20 }}>Sin transacciones de tarjeta registradas</td></tr>}
            </tbody>
          </table>
        </>
      )}

      {tab === "webhooks" && (
        <>
          <form onSubmit={crearWebhook} className="card" style={{ marginBottom: 20, display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))", gap: 12 }}>
            <div>
              <label>Evento *</label>
              <select value={webhook.evento} onChange={(e) => setWebhook({ ...webhook, evento: e.target.value })}>
                <option value="venta.creada">venta.creada</option>
                <option value="cliente.creado">cliente.creado</option>
                <option value="producto.creado">producto.creado</option>
              </select>
            </div>
            <div><label>URL *</label><input required type="url" value={webhook.url} onChange={(e) => setWebhook({ ...webhook, url: e.target.value })} placeholder="http://..." /></div>
            <div><label>Token (opcional)</label><input value={webhook.token} onChange={(e) => setWebhook({ ...webhook, token: e.target.value })} /></div>
            <div style={{ display: "flex", alignItems: "flex-end" }}><button className="btn" type="submit">Agregar webhook</button></div>
          </form>
          <table className="table">
            <thead><tr><th>Evento</th><th>URL</th><th>Estado</th><th></th></tr></thead>
            <tbody>
              {webhooks.map((w) => (
                <tr key={w.id}>
                  <td><strong>{w.evento}</strong></td>
                  <td className="muted">{w.url}</td>
                  <td><span className={`badge ${w.activo ? "badge-success" : "badge-danger"}`}>{w.activo ? "Activo" : "Inactivo"}</span></td>
                  <td><button className="btn btn-sm" onClick={() => editarWebhook(w)}>Editar</button></td>
                </tr>
              ))}
              {webhooks.length === 0 && <tr><td colSpan={4} className="muted" style={{ textAlign: "center", padding: 20 }}>Sin webhooks configurados</td></tr>}
            </tbody>
          </table>
        </>
      )}

      {tab === "whatsapp" && (
        <form onSubmit={enviarWa} className="card" style={{ maxWidth: 520, display: "grid", gap: 12 }}>
          <h3>Enviar mensaje de WhatsApp</h3>
          <div><label>Teléfono *</label><input required value={wa.telefono} onChange={(e) => setWa({ ...wa, telefono: e.target.value })} placeholder="3001234567" /></div>
          <div><label>Mensaje *</label><textarea rows={3} required value={wa.mensaje} onChange={(e) => setWa({ ...wa, mensaje: e.target.value })} /></div>
          <div><button className="btn" type="submit">Enviar</button></div>
          <p className="muted" style={{ fontSize: 12 }}>Integración simulada: registra el envío para trazabilidad sin requerir conexión a la API de WhatsApp.</p>
        </form>
      )}

      {tab === "backups" && (
        <>
          <div className="card" style={{ marginBottom: 20, display: "flex", gap: 12, alignItems: "center" }}>
            <div style={{ flex: 1 }}>
              <h3 style={{ fontSize: 15 }}>Backup de base de datos</h3>
              <p className="muted" style={{ fontSize: 12.5 }}>Vuelca 12 tablas núcleo (productos, clientes, ventas, compras, stock...) a un registro JSON listo para restaurar.</p>
            </div>
            <button className="btn btn-primary" onClick={crearBackup} disabled={haciendo}>{haciendo ? "Creando..." : "Crear backup"}</button>
          </div>
          <table className="table">
            <thead><tr><th>N°</th><th>Nombre</th><th>Tipo</th><th>Tamaño</th><th>Fecha</th><th></th></tr></thead>
            <tbody>
              {backups.map((b) => (
                <tr key={b.id}>
                  <td>{b.id}</td>
                  <td><strong>{b.nombre}</strong></td>
                  <td><span className="badge badge-info">{b.tipo}</span></td>
                  <td>{b.tamano ? `${(b.tamano / 1024).toFixed(1)} KB` : "—"}</td>
                  <td>{b.created_at ? new Date(b.created_at).toLocaleString() : "—"}</td>
                  <td>{b.tipo === "manual" && <button className="btn btn-secondary" onClick={() => restaurar(b.id)}>Restaurar</button>}</td>
                </tr>
              ))}
              {backups.length === 0 && <tr><td colSpan={6} className="muted" style={{ textAlign: "center", padding: 20 }}>Sin backups</td></tr>}
            </tbody>
          </table>
        </>
      )}
    </div>
  );
}