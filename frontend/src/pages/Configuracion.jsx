import { useEffect, useState } from "react";
import api from "../api.js";
import { useAuth } from "../contexts/AuthContext.jsx";
import { usePlan } from "../contexts/PlanContext.jsx";

const TIPOS = [
  { id: "general", label: "General / Otros" },
  { id: "ferreteria", label: "Ferretería" },
  { id: "restaurante", label: "Restaurante" },
  { id: "minimarket", label: "Minimarket / Tienda" },
];

const TIPO_LABELS = Object.fromEntries(TIPOS.map((t) => [t.id, t.label]));

const PLAN_MODULOS = [
  "dashboard", "pos", "productos", "inventario", "compras", "ventas", "caja",
  "clientes", "proveedores", "cartera", "promociones", "facturacion", "fidelizacion",
  "apartados", "domicilios", "restaurante", "seguridad", "vendedores", "sistema",
  "reportes", "integraciones", "offline", "configuracion",
];

const DIAS_CARD = { display: "grid", gap: 10 };

function Label({ children }) {
  return <label>{children}</label>;
}

function Campo({ etiqueta, valor, onChange, tipo = "text", step }) {
  return (
    <div>
      <Label>{etiqueta}</Label>
      {tipo === "checkbox" ? (
        <div style={{ display: "flex", alignItems: "center", gap: 8, paddingTop: 8 }}>
          <input type="checkbox" checked={!!valor} onChange={(e) => onChange(e.target.checked)} style={{ transform: "scale(1.2)" }} />
          <span className="muted">Habilitado</span>
        </div>
      ) : (
        <input type={tipo} step={step} value={valor ?? ""} onChange={(e) => onChange(e.target.value)} />
      )}
    </div>
  );
}

function Tarjeta({ titulo, icono, children, onGuardar, descripcion }) {
  return (
    <div className="card sec">
      <h3 className="card-title">{icono} {titulo}</h3>
      {descripcion && <p className="muted" style={{ fontSize: 12, marginBottom: 10 }}>{descripcion}</p>}
      <div style={DIAS_CARD}>{children}</div>
      <div style={{ marginTop: 14, textAlign: "right" }}>
        <button className="btn" onClick={onGuardar}>Guardar</button>
      </div>
    </div>
  );
}

export default function Configuracion() {
  const { user } = useAuth();
  const { plan, recargar } = usePlan();
  const [tab, setTab] = useState("general");
  const [impuestos, setImpuestos] = useState([]);
  const [config, setConfig] = useState([]);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const [impForm, setImpForm] = useState({ nombre: "", tasa: 0 });
  const [editing, setEditing] = useState(null);
  const [nuevoValor, setNuevoValor] = useState({});

  const [dispo, setDispo] = useState(null);
  const [conexion, setConexion] = useState(null);
  const [conForm, setConForm] = useState({});

  const [org, setOrg] = useState({ empresas: [], sucursales: [], puntos: [], cajas: [] });
  const [empForm, setEmpForm] = useState({ nombre: "", nit: "", tipo_negocio: "general", razon_social: "", direccion: "", telefono: "", email: "", regimen: "" });
  const [sucForm, setSucForm] = useState({ empresa_id: "", nombre: "", codigo: "", direccion: "", telefono: "", ciudad: "" });
  const [pvForm, setPvForm] = useState({ sucursal_id: "", nombre: "", tipo: "" });
  const [cajaForm, setCajaForm] = useState({ punto_venta_id: "", nombre: "", codigo: "", saldo_inicial: 0, es_principal: false });
  const [editEmp, setEditEmp] = useState(null);
  const [editSuc, setEditSuc] = useState(null);

  const [licForm, setLicForm] = useState({ cliente: "", vence: "", modulos_extra: [], modulos_ocultos: [] });

  const [nitBusqueda, setNitBusqueda] = useState("");
  const [establecimiento, setEstablecimiento] = useState(null);
  const [estForm, setEstForm] = useState({});
  const [modelos, setModelos] = useState([]);

  const esAdmin = user?.es_admin || user?.rol?.nombre === "admin";

  async function load() {
    api("/configuracion/impuestos").then(setImpuestos).catch(() => {});
    api("/configuracion/general").then(setConfig).catch(() => {});
    if (esAdmin) {
      api("/configuracion/modelo-negocio").then(setModelos).catch(() => {});
      api("/configuracion/conexion")
        .then((r) => {
          setConexion(r);
          setConForm((p) => ({ ...p, dialecto: r.dialecto || "mssql", host: r.host || "db", puerto: r.puerto || 1433, base: r.base || "posdb" }));
        })
        .catch(() => {});
    }
  }

  useEffect(() => {
    load();
  }, []);

  useEffect(() => {
    if (tab === "dispositivos") {
      api("/configuracion/dispositivos").then(setDispo).catch(() => {});
    }
    if (tab === "organizacion") {
      loadOrganizacion();
    }
  }, [tab]);

  function loadOrganizacion() {
    api("/organizacion/empresas").then((r) => setOrg((p) => ({ ...p, empresas: r }))).catch(() => {});
    api("/organizacion/sucursales").then((r) => setOrg((p) => ({ ...p, sucursales: r }))).catch(() => {});
    api("/organizacion/puntos-venta").then((r) => setOrg((p) => ({ ...p, puntos: r }))).catch(() => {});
    api("/organizacion/cajas").then((r) => setOrg((p) => ({ ...p, cajas: r }))).catch(() => {});
  }

  async function cargarEstablecimiento() {
    setError("");
    setOk("");
    if (!nitBusqueda.trim()) {
      setError("Ingresa el NIT del establecimiento");
      return;
    }
    try {
      const r = await api(`/configuracion/establecimiento?nit=${encodeURIComponent(nitBusqueda.trim())}`);
      setEstablecimiento(r);
      setEstForm({ ...r, id: undefined });
    } catch (err) {
      setError(err.message);
    }
  }

  async function guardarEstablecimiento(e) {
    e.preventDefault();
    setError("");
    setOk("");
    try {
      const r = await api("/configuracion/establecimiento", {
        method: "PUT",
        body: JSON.stringify({ ...estForm, nit: nitBusqueda.trim() }),
      });
      setEstablecimiento(r);
      setOk("Establecimiento guardado correctamente");
      recargar();
    } catch (err) {
      setError(err.message);
    }
  }

  async function crearImpuesto(e) {
    e.preventDefault();
    setError("");
    try {
      if (editing) {
        await api(`/configuracion/impuestos/${editing}`, { method: "PUT", body: JSON.stringify(impForm) });
      } else {
        await api("/configuracion/impuestos", { method: "POST", body: JSON.stringify(impForm) });
      }
      setImpForm({ nombre: "", tasa: 0 });
      setEditing(null);
      load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function guardarConfig(clave, descripcion) {
    const valor = nuevoValor[clave];
    if (valor === undefined) return;
    setError("");
    try {
      await api(`/configuracion/general/${clave}?valor=${encodeURIComponent(valor)}${descripcion ? `&descripcion=${encodeURIComponent(descripcion)}` : ""}`, { method: "PUT" });
      setNuevoValor({ ...nuevoValor, [clave]: undefined });
      load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function guardarDispo(bloque, payload) {
    setError("");
    setOk("");
    try {
      const res = await api(`/configuracion/dispositivos/${bloque}`, { method: "PUT", body: JSON.stringify(payload) });
      setDispo((prev) => ({ ...prev, [bloque === "impresoras" ? "impresoras" : bloque]: res }));
      setOk(`Configuración de ${bloque} guardada`);
      setTimeout(() => setOk(""), 2500);
    } catch (err) {
      setError(err.message);
    }
  }

  function setFactura(patch) {
    setDispo((prev) => ({ ...prev, factura: { ...prev.factura, ...patch } }));
  }

  function setLector(patch) {
    setDispo((prev) => ({ ...prev, lector: { ...prev.lector, ...patch } }));
  }

  function setTerminal(patch) {
    setDispo((prev) => ({ ...prev, terminal: { ...prev.terminal, ...patch } }));
  }

  function setCajon(patch) {
    setDispo((prev) => ({ ...prev, cajon: { ...prev.cajon, ...patch } }));
  }

  function setCorreo(patch) {
    setDispo((prev) => ({ ...prev, correo: { ...prev.correo, ...patch } }));
  }

  function setImpresora(id, patch) {
    setDispo((prev) => ({
      ...prev,
      impresoras: prev.impresoras.map((imp, i) => (i === id ? { ...imp, ...patch } : imp)),
    }));
  }

  function agregarImpresora() {
    setDispo((prev) => ({
      ...prev,
      impresoras: [...prev.impresoras, { nombre: "", puerto: "USB", papel_mm: 80 }],
    }));
  }

  function quitarImpresora(id) {
    setDispo((prev) => ({
      ...prev,
      impresoras: prev.impresoras.filter((_, i) => i !== id),
    }));
  }

  async function orgPost(url, body, resetFn) {
    setError("");
    try {
      await api(url, { method: "POST", body: JSON.stringify(body) });
      resetFn();
      loadOrganizacion();
    } catch (err) {
      setError(err.message);
    }
  }

  async function crearEmpresa(e) {
    e.preventDefault();
    const body = { ...empForm };
    Object.keys(body).forEach((k) => body[k] === "" && delete body[k]);
    await orgPost("/organizacion/empresas", body, () => setEmpForm({ nombre: "", nit: "", tipo_negocio: "general", razon_social: "", direccion: "", telefono: "", email: "", regimen: "" }));
  }

  async function crearSucursal(e) {
    e.preventDefault();
    if (!sucForm.empresa_id) { setError("Selecciona la empresa"); return; }
    await orgPost("/organizacion/sucursales", { ...sucForm, empresa_id: Number(sucForm.empresa_id) }, () => setSucForm({ empresa_id: "", nombre: "", codigo: "", direccion: "", telefono: "", ciudad: "" }));
  }

  async function crearPunto(e) {
    e.preventDefault();
    if (!pvForm.sucursal_id) { setError("Selecciona la sucursal"); return; }
    await orgPost("/organizacion/puntos-venta", { ...pvForm, sucursal_id: Number(pvForm.sucursal_id) }, () => setPvForm({ sucursal_id: "", nombre: "", tipo: "" }));
  }

  async function crearCaja(e) {
    e.preventDefault();
    if (!cajaForm.punto_venta_id) { setError("Selecciona el punto de venta"); return; }
    const body = { punto_venta_id: Number(cajaForm.punto_venta_id), nombre: cajaForm.nombre, codigo: cajaForm.codigo || null, saldo_inicial: Number(cajaForm.saldo_inicial) || 0, es_principal: cajaForm.es_principal };
    await orgPost("/organizacion/cajas", body, () => setCajaForm({ punto_venta_id: "", nombre: "", codigo: "", saldo_inicial: 0, es_principal: false }));
  }

  async function guardarConexion(e) {
    e.preventDefault();
    setError("");
    setOk("");
    try {
      const res = await api("/configuracion/conexion", {
        method: "PUT",
        body: JSON.stringify({ ...conForm, puerto: Number(conForm.puerto) || 1433, host: (conForm.host || "").trim(), base: (conForm.base || "").trim() }),
      });
      setConexion(res);
      setOk("Conexión probada y aplicada correctamente");
    } catch (err) {
      setError(err.message);
    }
  }

  async function marcarPrincipal(caja) {
    setError("");
    try {
      await api(`/organizacion/cajas/${caja.id}`, { method: "PUT", body: JSON.stringify({ es_principal: true }) });
      loadOrganizacion();
    } catch (err) {
      setError(err.message);
    }
  }

  async function guardarEditEmp(e) {
    e.preventDefault();
    setError("");
    try {
      const body = { ...editEmp };
      delete body.id;
      Object.keys(body).forEach((k) => body[k] === "" && delete body[k]);
      await api(`/organizacion/empresas/${editEmp.id}`, { method: "PUT", body: JSON.stringify(body) });
      setEditEmp(null);
      loadOrganizacion();
    } catch (err) {
      setError(err.message);
    }
  }

  async function guardarEditSuc(e) {
    e.preventDefault();
    setError("");
    try {
      const body = { ...editSuc };
      delete body.id;
      delete body.empresa_id;
      Object.keys(body).forEach((k) => body[k] === "" && delete body[k]);
      await api(`/organizacion/sucursales/${editSuc.id}`, { method: "PUT", body: JSON.stringify(body) });
      setEditSuc(null);
      loadOrganizacion();
    } catch (err) {
      setError(err.message);
    }
  }

  async function guardarLicencia(e) {
    e.preventDefault();
    setError("");
    setOk("");
    try {
      await api("/configuracion/licencia", { method: "PUT", body: JSON.stringify(licForm) });
      await recargar();
      setOk("Licencia actualizada");
      setTimeout(() => setOk(""), 2500);
    } catch (err) {
      setError(err.message);
    }
  }

  useEffect(() => {
    if (plan && tab === "plan") {
      setLicForm({
        cliente: plan.cliente || "",
        vence: plan.vence || "",
        modulos_extra: plan.modulos_extra || [],
        modulos_ocultos: plan.modulos_ocultos || [],
      });
    }
  }, [plan, tab]);

  const toggleLista = (campo, mod) => {
    setLicForm((prev) => {
      const lista = prev[campo];
      return {
        ...prev,
        [campo]: lista.includes(mod) ? lista.filter((m) => m !== mod) : [...lista, mod],
      };
    });
  };

  const EmpForm = ({ d, cambio, onSubmit, extra }) => (
    <form onSubmit={onSubmit} className="card" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(170px,1fr))", gap: 10, padding: 16, marginBottom: 24 }}>
      {extra}
      <div><Label>Nombre *</Label><input required value={d.nombre || ""} onChange={(e) => cambio("nombre", e.target.value)} /></div>
      <div><Label>NIT *</Label><input required value={d.nit || ""} onChange={(e) => cambio("nit", e.target.value)} /></div>
      <div><Label>Tipo de negocio</Label>
        <select value={d.tipo_negocio || "general"} onChange={(e) => cambio("tipo_negocio", e.target.value)}>
          {TIPOS.map((t) => <option key={t.id} value={t.id}>{t.label}</option>)}
        </select>
      </div>
      <div><Label>Razón social</Label><input value={d.razon_social || ""} onChange={(e) => cambio("razon_social", e.target.value)} /></div>
      <div><Label>Dirección</Label><input value={d.direccion || ""} onChange={(e) => cambio("direccion", e.target.value)} /></div>
      <div><Label>Teléfono</Label><input value={d.telefono || ""} onChange={(e) => cambio("telefono", e.target.value)} /></div>
      <div><Label>Email</Label><input type="email" value={d.email || ""} onChange={(e) => cambio("email", e.target.value)} /></div>
      <div><Label>Régimen</Label><input value={d.regimen || ""} onChange={(e) => cambio("regimen", e.target.value)} /></div>
      <div style={{ display: "flex", alignItems: "flex-end" }}><button className="btn" type="submit">Guardar</button></div>
    </form>
  );

  return (
    <div className="page">
      <div className="page-header">
        <h1>Configuración</h1>
        <div className="tabs">
          {["general", "dispositivos", "organizacion", "plan"].map((t) => (
            <button key={t} className={`btn ${tab === t ? "btn-primary" : ""}`} onClick={() => setTab(t)}>
              {t === "general" ? "General" : t === "dispositivos" ? "Dispositivos POS" : t === "organizacion" ? "Organización" : "Plan / Licencia"}
            </button>
          ))}
        </div>
      </div>

      {error && <div className="error">{error}</div>}
      {ok && <div className="chip" style={{ display: "inline-block", background: "rgba(5,150,105,.12)", color: "#059669", marginBottom: 12 }}>{ok}</div>}

      {tab === "general" && (
        <>
          <div className="card" style={{ marginBottom: 24 }}>
            <h2 style={{ fontSize: 16, marginBottom: 12 }}>Direccionamiento a la base de datos</h2>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center", marginBottom: 12 }}>
              {conexion ? (
                <>
                  <span className={`badge ${conexion.razon === "ok" ? "badge-success" : "badge-danger"}`}>
                    {conexion.razon === "ok" ? "Conectado" : "Error"}
                  </span>
                  <span className="chip">{conexion.dialecto}</span>
                  <span className="chip">{conexion.host}:{conexion.puerto || "—"}</span>
                  <span className="chip">BD: {conexion.base}</span>
                  {conexion.origen === "archivo" && <span className="chip">Configurado desde la app</span>}
                  {conexion.error && <span className="muted" style={{ fontSize: 12 }}>{conexion.error}</span>}
                </>
              ) : (
                <p className="muted" style={{ fontSize: 13 }}>Cargando conexión…</p>
              )}
            </div>
            {esAdmin ? (
              <form onSubmit={guardarConexion} style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(160px,1fr))", gap: 10 }}>
                <div>
                  <Label>Motor</Label>
                  <select value={conForm.dialecto || "mssql"} onChange={(e) => setConForm({ ...conForm, dialecto: e.target.value })}>
                    <option value="mssql">SQL Server</option>
                  </select>
                </div>
                <Campo etiqueta="Host / Servidor" valor={conForm.host} onChange={(v) => setConForm({ ...conForm, host: v })} />
                <Campo etiqueta="Puerto" tipo="number" valor={conForm.puerto} onChange={(v) => setConForm({ ...conForm, puerto: v })} />
                <Campo etiqueta="Base de datos" valor={conForm.base} onChange={(v) => setConForm({ ...conForm, base: v })} />
                <div style={{ gridColumn: "1 / -1", textAlign: "right" }}>
                  <button className="btn" type="submit">Probar y guardar</button>
                </div>
              </form>
            ) : (
              <p className="muted" style={{ fontSize: 13 }}>Solo un administrador puede ver o modificar la dirección de la base de datos.</p>
            )}
            <p className="muted" style={{ fontSize: 12, marginTop: 8 }}>
              La conexión se prueba antes de aplicarse y queda guardada en el servidor principal. Debe apuntar a una base ya creada con el esquema del sistema; las cajas secundarias usan la misma dirección al abrir el aplicativo en el navegador.
            </p>
          </div>

          <div className="card" style={{ marginBottom: 24 }}>
            <h2 style={{ fontSize: 16, marginBottom: 12 }}>Establecimiento / negocio (NIT)</h2>
            <div style={{ display: "flex", gap: 8, alignItems: "flex-end", marginBottom: 12 }}>
              <div style={{ flex: 1 }}>
                <Label>NIT</Label>
                <input
                  value={nitBusqueda}
                  onChange={(e) => setNitBusqueda(e.target.value)}
                  placeholder="Ingresa el NIT para cargar sus datos"
                />
              </div>
              <button className="btn btn-secondary" onClick={cargarEstablecimiento}>Cargar</button>
            </div>
            {establecimiento && (
              <form onSubmit={guardarEstablecimiento} style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(170px,1fr))", gap: 10 }}>
                <Campo etiqueta="Nombre del establecimiento" valor={estForm.nombre} onChange={(v) => setEstForm({ ...estForm, nombre: v })} />
                <Campo etiqueta="Razón social" valor={estForm.razon_social} onChange={(v) => setEstForm({ ...estForm, razon_social: v })} />
                <div>
                  <Label>Tipo de negocio</Label>
                  <select
                    value={estForm.modelo_negocio_id ?? ""}
                    onChange={(e) => {
                      const num = e.target.value === "" ? null : Number(e.target.value);
                      const m = modelos.find((x) => x.id === num);
                      const tipo = !m || (m.nombre || "").toLowerCase().includes("general")
                        ? "general"
                        : (m.nombre || "").toLowerCase().includes("ferreter")
                          ? "ferreteria"
                          : (m.nombre || "").toLowerCase().includes("restaurant") || (m.nombre || "").toLowerCase().includes("bar")
                            ? "restaurante"
                            : "minimarket";
                      setEstForm((p) => ({ ...p, modelo_negocio_id: num, tipo_negocio: tipo }));
                    }}
                  >
                    <option value="">Seleccionar…</option>
                    {(modelos.length ? modelos : [1, 2, 3, 4, 5, 6].map((n) => ({ id: n, nombre: "" }))).map((m) => (
                      <option key={m.id} value={m.id}>{m.id}</option>
                    ))}
                  </select>
                </div>
                <Campo etiqueta="Régimen" valor={estForm.regimen} onChange={(v) => setEstForm({ ...estForm, regimen: v })} />
                <Campo etiqueta="Actividad económica" valor={estForm.actividad_economica} onChange={(v) => setEstForm({ ...estForm, actividad_economica: v })} />
                <Campo etiqueta="Dirección" valor={estForm.direccion} onChange={(v) => setEstForm({ ...estForm, direccion: v })} />
                <Campo etiqueta="Ciudad" valor={estForm.ciudad} onChange={(v) => setEstForm({ ...estForm, ciudad: v })} />
                <Campo etiqueta="Departamento" valor={estForm.departamento} onChange={(v) => setEstForm({ ...estForm, departamento: v })} />
                <Campo etiqueta="Teléfono" valor={estForm.telefono} onChange={(v) => setEstForm({ ...estForm, telefono: v })} />
                <Campo etiqueta="Email" tipo="email" valor={estForm.email} onChange={(v) => setEstForm({ ...estForm, email: v })} />
                <div style={{ gridColumn: "1 / -1", textAlign: "right" }}>
                  <button className="btn" type="submit">Guardar</button>
                </div>
              </form>
            )}
            <p className="muted" style={{ fontSize: 12, marginTop: 8 }}>
              Al escribir el NIT se cargan los datos del establecimiento. Si ya existe una empresa con ese NIT, se precargan sus datos y se vinculan. El "Tipo de negocio" es el número del modelo que habilita sus módulos: 1 Restaurante, 2 Ferretería, 3 Minimarket / Tienda, 4 Bar / Restobar, 5 Distribuidora, 6 General.
            </p>
          </div>

          <div className="card" style={{ marginBottom: 24 }}>
            <h2 style={{ fontSize: 16, marginBottom: 4 }}>WhatsApp y pagos digitales</h2>
            <p className="muted" style={{ fontSize: 12, marginBottom: 12 }}>
              Recibos y resumen diario por WhatsApp, alertas automáticas, menú público QR por mesa y cobro con Nequi / Daviplata.
            </p>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: 12 }}>
              {[
                ["pos.telefono_notificaciones", "Teléfono WhatsApp (reportes y alertas)", "573123456789", "number"],
                ["pos.recibo_whatsapp", "Recibo automático al cliente (si/no)", "si", "text"],
                ["pos.reporte_diario", "Resumen diario (si/no)", "si", "text"],
                ["pos.hora_resumen", "Hora del resumen (HH:MM)", "21:00", "text"],
                ["pos.alertas_whatsapp", "Alertas de stock / ventas (si/no)", "si", "text"],
                ["publico.llave", "Llave de pedidos públicos", "publico", "text"],
                ["pos.url_publica", "URL pública del menú / kiosko", "https://ejemplo.com", "url"],
                ["pagos.qr_nequi", "Número Nequi (QR de cobro)", "3000000000", "number"],
                ["pagos.qr_daviplata", "Número Daviplata (QR de cobro)", "3000000000", "number"],
              ].map(([clave, etiqueta, ph, tipo]) => (
                <div key={clave}>
                  <label>{etiqueta}</label>
                  <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                    <input
                      type={tipo}
                      value={nuevoValor[clave] ?? (config.find((c) => c.clave === clave)?.valor ?? "")}
                      onChange={(e) => setNuevoValor({ ...nuevoValor, [clave]: e.target.value })}
                      placeholder={ph}
                      style={{ flex: 1 }}
                    />
                    <button
                      className="btn btn-secondary"
                      onClick={() => guardarConfig(clave, etiqueta)}
                      disabled={nuevoValor[clave] === undefined}
                    >
                      Guardar
                    </button>
                  </div>
                </div>
              ))}
            </div>
            <p className="muted" style={{ fontSize: 12, marginTop: 10 }}>
              💡 El <b>QR de cobro</b> (Nequi/Daviplata) se arma automáticamente con el número guardado y aparece en el Punto de Venta al elegir ese método. El <b>menú QR por mesa</b> usa la URL pública para que el cliente pida desde su celular.
            </p>
          </div>

          <div className="card" style={{ marginBottom: 24 }}>
            <h2 style={{ fontSize: 16, marginBottom: 12 }}>Configuración general</h2>
            <table className="table">
              <thead><tr><th>Clave</th><th>Descripción</th><th>Valor</th><th></th></tr></thead>
              <tbody>
                {config.map((c) => (
                  <tr key={c.clave}>
                    <td><code>{c.clave}</code></td>
                    <td className="muted">{c.descripcion || "—"}</td>
                    <td style={{ width: 220 }}>
                      <input
                        value={nuevoValor[c.clave] ?? c.valor ?? ""}
                        onChange={(e) => setNuevoValor({ ...nuevoValor, [c.clave]: e.target.value })}
                        placeholder={c.valor || ""}
                      />
                    </td>
                    <td><button className="btn btn-secondary" onClick={() => guardarConfig(c.clave, c.descripcion)}>Guardar</button></td>
                  </tr>
                ))}
                {config.length === 0 && <tr><td colSpan={4} className="muted" style={{ textAlign: "center", padding: 20 }}>Sin configuraciones</td></tr>}
              </tbody>
            </table>
          </div>

          <div className="card">
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
              <h2 style={{ fontSize: 16 }}>Impuestos</h2>
            </div>

            <form onSubmit={crearImpuesto} style={{ display: "flex", gap: 12, marginBottom: 16, flexWrap: "wrap" }}>
              <div style={{ flex: 1, minWidth: 180 }}>
                <label>Nombre</label>
                <input required value={impForm.nombre} onChange={(e) => setImpForm({ ...impForm, nombre: e.target.value })} placeholder="IVA 19%" />
              </div>
              <div>
                <label>Tasa (%)</label>
                <input required type="number" step="0.01" value={impForm.tasa} onChange={(e) => setImpForm({ ...impForm, tasa: e.target.value })} />
              </div>
              <div style={{ display: "flex", alignItems: "flex-end", gap: 8 }}>
                <button className="btn" type="submit">{editing ? "Actualizar" : "+ Crear impuesto"}</button>
                {editing && <button type="button" className="btn btn-secondary" onClick={() => { setEditing(null); setImpForm({ nombre: "", tasa: 0 }); }}>Cancelar</button>}
              </div>
            </form>

            <table className="table">
              <thead><tr><th>Nombre</th><th>Tasa</th><th>Estado</th><th>Acciones</th></tr></thead>
              <tbody>
                {impuestos.map((i) => (
                  <tr key={i.id}>
                    <td>{i.nombre}</td>
                    <td>{i.tasa}%</td>
                    <td><span className={`badge ${i.activo ? "badge-success" : "badge-danger"}`}>{i.activo ? "Activo" : "Inactivo"}</span></td>
                    <td>
                      <button className="btn btn-secondary" onClick={() => { setEditing(i.id); setImpForm({ nombre: i.nombre, tasa: i.tasa }); }}>Editar</button>
                    </td>
                  </tr>
                ))}
                {impuestos.length === 0 && <tr><td colSpan={4} className="muted" style={{ textAlign: "center", padding: 20 }}>Sin impuestos</td></tr>}
              </tbody>
            </table>
          </div>
        </>
      )}

      {tab === "dispositivos" && dispo && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(330px, 1fr))", gap: 18 }}>
          <Tarjeta titulo="Formato de factura / ticket" icono="🧾" descripcion="Aplica al ticket térmico de ventas y facturación." onGuardar={() => guardarDispo("factura", dispo.factura)}>
            <Campo etiqueta="Ancho del papel (mm)" tipo="number" valor={dispo.factura.ancho_mm} onChange={(v) => setFactura({ ancho_mm: Number(v) })} />
            <Campo etiqueta="Copias" tipo="number" valor={dispo.factura.copias} onChange={(v) => setFactura({ copias: Number(v) })} />
            <Campo etiqueta="Leyenda al pie" valor={dispo.factura.leyenda_pie} onChange={(v) => setFactura({ leyenda_pie: v })} />
          </Tarjeta>

          <Tarjeta titulo="Impresoras térmicas" icono="🖨️" descripcion="Equipos disponibles para tickets y etiquetas." onGuardar={() => guardarDispo("impresoras", dispo.impresoras)}>
            {dispo.impresoras.map((imp, i) => (
              <div key={i} style={{ display: "grid", gridTemplateColumns: "1fr 1fr 70px 28px", gap: 6 }}>
                <input value={imp.nombre} onChange={(e) => setImpresora(i, { nombre: e.target.value })} placeholder="Nombre" />
                <input value={imp.puerto} onChange={(e) => setImpresora(i, { puerto: e.target.value })} placeholder="Puerto (USB/IP)" />
                <input type="number" value={imp.papel_mm} onChange={(e) => setImpresora(i, { papel_mm: Number(e.target.value) })} title="Papel (mm)" />
                <button className="btn btn-danger" style={{ padding: "3px 6px", background: "transparent", color: "#dc2626" }} onClick={() => quitarImpresora(i)} title="Quitar">✕</button>
              </div>
            ))}
            <button className="btn btn-secondary" onClick={agregarImpresora}>+ Agregar impresora</button>
          </Tarjeta>

          <Tarjeta titulo="Lector de código de barras" icono="🔳" descripcion="Configuración del escáner conectado al POS." onGuardar={() => guardarDispo("lector", dispo.lector)}>
            <Campo etiqueta="Lector habilitado" tipo="checkbox" valor={dispo.lector.habilitado} onChange={(v) => setLector({ habilitado: v })} />
            <Campo etiqueta="Marca / modelo" valor={dispo.lector.marca} onChange={(v) => setLector({ marca: v })} />
            <Campo etiqueta="Sufijo al escanear" valor={dispo.lector.sufijo} onChange={(v) => setLector({ sufijo: v })} />
          </Tarjeta>

          <Tarjeta titulo="Terminal POS" icono="🖥️" descripcion="Identificación del terminal de venta." onGuardar={() => guardarDispo("terminal", dispo.terminal)}>
            <Campo etiqueta="Terminal habilitado" tipo="checkbox" valor={dispo.terminal.habilitado} onChange={(v) => setTerminal({ habilitado: v })} />
            <Campo etiqueta="Nombre del terminal" valor={dispo.terminal.nombre} onChange={(v) => setTerminal({ nombre: v })} />
            <Campo etiqueta="Número de serie" valor={dispo.terminal.serie} onChange={(v) => setTerminal({ serie: v })} />
          </Tarjeta>

          <Tarjeta titulo="Cajón monedero" icono="💰" descripcion="Apertura del cajón conectado a la impresora." onGuardar={() => guardarDispo("cajon", dispo.cajon)}>
            <Campo etiqueta="Cajón habilitado" tipo="checkbox" valor={dispo.cajon.habilitado} onChange={(v) => setCajon({ habilitado: v })} />
            <Campo etiqueta="Puerto / conexión" valor={dispo.cajon.puerto} onChange={(v) => setCajon({ puerto: v })} />
          </Tarjeta>

          <Tarjeta titulo="Correo (envío de facturas)" icono="📧" descripcion="SMTP usado para el envío de documentos por correo." onGuardar={() => guardarDispo("correo", dispo.correo)}>
            <Campo etiqueta="Servidor SMTP" valor={dispo.correo.servidor} onChange={(v) => setCorreo({ servidor: v })} />
            <Campo etiqueta="Puerto" tipo="number" valor={dispo.correo.puerto} onChange={(v) => setCorreo({ puerto: Number(v) }) } />
            <Campo etiqueta="Usuario" valor={dispo.correo.usuario} onChange={(v) => setCorreo({ usuario: v })} />
            <Campo etiqueta="Correo remitente" valor={dispo.correo.desde} onChange={(v) => setCorreo({ desde: v })} />
            <Campo etiqueta="Conexión segura (TLS)" tipo="checkbox" valor={dispo.correo.tls} onChange={(v) => setCorreo({ tls: v })} />
          </Tarjeta>
        </div>
      )}

      {tab === "organizacion" && (
        <>
          <h2 style={{ fontSize: 17, marginBottom: 10 }}>Empresas</h2>
          <EmpForm d={empForm} cambio={(k, v) => setEmpForm({ ...empForm, [k]: v })} onSubmit={crearEmpresa} />
          <table className="table" style={{ marginBottom: 28 }}>
            <thead><tr><th>Nombre</th><th>NIT</th><th>Tipo</th><th>Razón social</th><th>Régimen</th><th>Estado</th><th></th></tr></thead>
            <tbody>
              {org.empresas.map((e) => (
                <tr key={e.id}>
                  <td><b>{e.nombre}</b></td>
                  <td>{e.nit}</td>
                  <td><span className="badge">{TIPO_LABELS[e.tipo_negocio] || e.tipo_negocio || "General"}</span></td>
                  <td className="muted">{e.razon_social || "—"}</td>
                  <td className="muted">{e.regimen || "—"}</td>
                  <td><span className={`badge ${e.activa ? "badge-success" : "badge-danger"}`}>{e.activa ? "Activa" : "Inactiva"}</span></td>
                  <td><button className="btn btn-secondary" onClick={() => setEditEmp({ ...e })}>Editar</button></td>
                </tr>
              ))}
              {org.empresas.length === 0 && <tr><td colSpan={7} className="muted" style={{ textAlign: "center", padding: 20 }}>Sin empresas</td></tr>}
            </tbody>
          </table>

          <h2 style={{ fontSize: 17, marginBottom: 10 }}>Sucursales</h2>
          <form onSubmit={crearSucursal} className="card" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(170px,1fr))", gap: 10, padding: 16, marginBottom: 24 }}>
            <div><Label>Empresa *</Label><select required value={sucForm.empresa_id} onChange={(e) => setSucForm({ ...sucForm, empresa_id: e.target.value })}>
              <option value="">Seleccionar...</option>
              {org.empresas.map((e) => <option key={e.id} value={e.id}>{e.nombre}</option>)}
            </select></div>
            <div><Label>Nombre *</Label><input required value={sucForm.nombre} onChange={(e) => setSucForm({ ...sucForm, nombre: e.target.value })} /></div>
            <div><Label>Código</Label><input value={sucForm.codigo} onChange={(e) => setSucForm({ ...sucForm, codigo: e.target.value })} /></div>
            <div><Label>Dirección</Label><input value={sucForm.direccion} onChange={(e) => setSucForm({ ...sucForm, direccion: e.target.value })} /></div>
            <div><Label>Teléfono</Label><input value={sucForm.telefono} onChange={(e) => setSucForm({ ...sucForm, telefono: e.target.value })} /></div>
            <div><Label>Ciudad</Label><input value={sucForm.ciudad} onChange={(e) => setSucForm({ ...sucForm, ciudad: e.target.value })} /></div>
            <div style={{ display: "flex", alignItems: "flex-end" }}><button className="btn" type="submit">Crear</button></div>
          </form>
          <table className="table" style={{ marginBottom: 28 }}>
            <thead><tr><th>Nombre</th><th>Empresa</th><th>Código</th><th>Ciudad</th><th>Estado</th><th></th></tr></thead>
            <tbody>
              {org.sucursales.map((s) => (
                <tr key={s.id}>
                  <td><b>{s.nombre}</b></td>
                  <td>{org.empresas.find((e) => e.id === s.empresa_id)?.nombre || `#${s.empresa_id}`}</td>
                  <td className="muted">{s.codigo || "—"}</td>
                  <td className="muted">{s.ciudad || "—"}</td>
                  <td><span className={`badge ${s.activa ? "badge-success" : "badge-danger"}`}>{s.activa ? "Activa" : "Inactiva"}</span></td>
                  <td><button className="btn btn-secondary" onClick={() => setEditSuc({ ...s })}>Editar</button></td>
                </tr>
              ))}
              {org.sucursales.length === 0 && <tr><td colSpan={6} className="muted" style={{ textAlign: "center", padding: 20 }}>Sin sucursales</td></tr>}
            </tbody>
          </table>

          <h2 style={{ fontSize: 17, marginBottom: 10 }}>Puntos de venta</h2>
          <form onSubmit={crearPunto} className="card" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(170px,1fr))", gap: 10, padding: 16, marginBottom: 24 }}>
            <div><Label>Sucursal *</Label><select required value={pvForm.sucursal_id} onChange={(e) => setPvForm({ ...pvForm, sucursal_id: e.target.value })}>
              <option value="">Seleccionar...</option>
              {org.sucursales.map((s) => <option key={s.id} value={s.id}>{s.nombre}</option>)}
            </select></div>
            <div><Label>Nombre *</Label><input required value={pvForm.nombre} onChange={(e) => setPvForm({ ...pvForm, nombre: e.target.value })} /></div>
            <div><Label>Tipo</Label><input placeholder="Ej: Principal, Caja rápida" value={pvForm.tipo} onChange={(e) => setPvForm({ ...pvForm, tipo: e.target.value })} /></div>
            <div style={{ display: "flex", alignItems: "flex-end" }}><button className="btn" type="submit">Crear</button></div>
          </form>
          <table className="table" style={{ marginBottom: 28 }}>
            <thead><tr><th>Nombre</th><th>Sucursal</th><th>Tipo</th><th>Estado</th></tr></thead>
            <tbody>
              {org.puntos.map((p) => (
                <tr key={p.id}>
                  <td><b>{p.nombre}</b></td>
                  <td>{org.sucursales.find((s) => s.id === p.sucursal_id)?.nombre || `#${p.sucursal_id}`}</td>
                  <td className="muted">{p.tipo || "—"}</td>
                  <td><span className={`badge ${p.activo ? "badge-success" : "badge-danger"}`}>{p.activo ? "Activo" : "Inactivo"}</span></td>
                </tr>
              ))}
              {org.puntos.length === 0 && <tr><td colSpan={4} className="muted" style={{ textAlign: "center", padding: 20 }}>Sin puntos de venta</td></tr>}
            </tbody>
          </table>

          <h2 style={{ fontSize: 17, marginBottom: 10 }}>Cajas</h2>
          <form onSubmit={crearCaja} className="card" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(170px,1fr))", gap: 10, padding: 16, marginBottom: 24 }}>
            <div><Label>Punto de venta *</Label><select required value={cajaForm.punto_venta_id} onChange={(e) => setCajaForm({ ...cajaForm, punto_venta_id: e.target.value })}>
              <option value="">Seleccionar...</option>
              {org.puntos.map((p) => <option key={p.id} value={p.id}>{p.nombre}</option>)}
            </select></div>
            <div><Label>Nombre *</Label><input required value={cajaForm.nombre} onChange={(e) => setCajaForm({ ...cajaForm, nombre: e.target.value })} /></div>
            <div><Label>Código</Label><input value={cajaForm.codigo} onChange={(e) => setCajaForm({ ...cajaForm, codigo: e.target.value })} /></div>
            <div><Label>Saldo inicial ($)</Label><input type="number" value={cajaForm.saldo_inicial} onChange={(e) => setCajaForm({ ...cajaForm, saldo_inicial: e.target.value })} /></div>
            <div style={{ display: "flex", alignItems: "flex-end" }}>
              <label style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <input type="checkbox" checked={cajaForm.es_principal} onChange={(e) => setCajaForm({ ...cajaForm, es_principal: e.target.checked })} />
                Caja principal
              </label>
            </div>
            <div style={{ display: "flex", alignItems: "flex-end" }}><button className="btn" type="submit">Crear</button></div>
          </form>
          <table className="table">
            <thead><tr><th>Nombre</th><th>Punto de venta</th><th>Código</th><th>Saldo inicial</th><th>Tipo</th><th>Estado</th></tr></thead>
            <tbody>
              {org.cajas.map((c) => (
                <tr key={c.id}>
                  <td><b>{c.nombre}</b></td>
                  <td>{org.puntos.find((p) => p.id === c.punto_venta_id)?.nombre || `#${c.punto_venta_id}`}</td>
                  <td className="muted">{c.codigo || "—"}</td>
                  <td>${(c.saldo_inicial || 0).toLocaleString("es-CO")}</td>
                  <td>
                    {c.es_principal ? (
                      <span className="badge badge-success">⭐ Principal</span>
                    ) : (
                      <button className="btn btn-secondary btn-sm" onClick={() => marcarPrincipal(c)}>Marcar principal</button>
                    )}
                  </td>
                  <td><span className={`badge ${c.activa ? "badge-success" : "badge-danger"}`}>{c.activa ? "Activa" : "Inactiva"}</span></td>
                </tr>
              ))}
              {org.cajas.length === 0 && <tr><td colSpan={6} className="muted" style={{ textAlign: "center", padding: 20 }}>Sin cajas</td></tr>}
            </tbody>
          </table>

          {editEmp && (
            <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,.45)", display: "grid", placeItems: "center", zIndex: 1100, padding: 20 }}>
              <div style={{ width: "min(680px, 100%)" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
                  <h2 style={{ fontSize: 17 }}>Editar empresa · #{editEmp.id}</h2>
                  <button className="btn btn-ghost" onClick={() => setEditEmp(null)}>✕</button>
                </div>
                <EmpForm d={editEmp} cambio={(k, v) => setEditEmp({ ...editEmp, [k]: v })}
                  onSubmit={guardarEditEmp}
                  extra={<div style={{ display: "flex", alignItems: "flex-end" }}><label><input type="checkbox" checked={!!editEmp.activa} onChange={(e) => setEditEmp({ ...editEmp, activa: e.target.checked })} /> Activa</label></div>} />
              </div>
            </div>
          )}

          {editSuc && (
            <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,.45)", display: "grid", placeItems: "center", zIndex: 1100, padding: 20 }}>
              <div style={{ width: "min(680px, 100%)" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
                  <h2 style={{ fontSize: 17 }}>Editar sucursal · #{editSuc.id}</h2>
                  <button className="btn btn-ghost" onClick={() => setEditSuc(null)}>✕</button>
                </div>
                <form onSubmit={guardarEditSuc} className="card" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(170px,1fr))", gap: 10, padding: 16 }}>
                  <div><Label>Nombre *</Label><input required value={editSuc.nombre || ""} onChange={(e) => setEditSuc({ ...editSuc, nombre: e.target.value })} /></div>
                  <div><Label>Código</Label><input value={editSuc.codigo || ""} onChange={(e) => setEditSuc({ ...editSuc, codigo: e.target.value })} /></div>
                  <div><Label>Dirección</Label><input value={editSuc.direccion || ""} onChange={(e) => setEditSuc({ ...editSuc, direccion: e.target.value })} /></div>
                  <div><Label>Teléfono</Label><input value={editSuc.telefono || ""} onChange={(e) => setEditSuc({ ...editSuc, telefono: e.target.value })} /></div>
                  <div><Label>Ciudad</Label><input value={editSuc.ciudad || ""} onChange={(e) => setEditSuc({ ...editSuc, ciudad: e.target.value })} /></div>
                  <div style={{ display: "flex", alignItems: "flex-end" }}><label><input type="checkbox" checked={!!editSuc.activa} onChange={(e) => setEditSuc({ ...editSuc, activa: e.target.checked })} /> Activa</label></div>
                  <div style={{ display: "flex", alignItems: "flex-end", justifyContent: "flex-end", gridColumn: "1 / -1" }}>
                    <button type="button" className="btn btn-secondary" onClick={() => setEditSuc(null)} style={{ marginRight: 8 }}>Cancelar</button>
                    <button className="btn" type="submit">Guardar</button>
                  </div>
                </form>
              </div>
            </div>
          )}
        </>
      )}

      {tab === "plan" && (
        <>
          <div className="card" style={{ marginBottom: 24 }}>
            <h2 style={{ fontSize: 16, marginBottom: 12 }}>Plan activo · NIT {plan?.nit}</h2>
            <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginBottom: 12 }}>
              <span className="badge">{plan?.modelo != null ? `Modelo ${plan.modelo}` : TIPO_LABELS[plan?.tipo_negocio] || plan?.tipo_negocio || "General"}</span>
              {plan?.cliente && <span className="badge">Cliente: {plan.cliente}</span>}
              {plan?.vence && <span className="badge">Vence: {plan.vence}</span>}
            </div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
              {(plan?.modulos || []).map((m) => (
                <span key={m} className="chip" style={{ textTransform: "capitalize" }}>{m}</span>
              ))}
            </div>
          </div>

          {esAdmin && plan && (
            <form onSubmit={guardarLicencia} className="card" style={{ display: "grid", gap: 12, padding: 16 }}>
              <h2 style={{ fontSize: 16 }}>Licencia (configurable solo por el proveedor)</h2>
              <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
                <div style={{ flex: 1, minWidth: 200 }}>
                  <Label>Cliente</Label>
                  <input value={licForm.cliente} onChange={(e) => setLicForm({ ...licForm, cliente: e.target.value })} placeholder="Nombre del cliente" />
                </div>
                <div style={{ flex: 1, minWidth: 160 }}>
                  <Label>Vence (aaaa-mm-dd, opcional)</Label>
                  <input value={licForm.vence} onChange={(e) => setLicForm({ ...licForm, vence: e.target.value })} placeholder="2026-12-31" />
                </div>
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                <div>
                  <Label>Módulos extra (sumar al tipo)</Label>
                  <div style={{ display: "flex", flexDirection: "column", gap: 4, maxHeight: 220, overflowY: "auto" }}>
                    {PLAN_MODULOS.map((m) => (
                      <label key={m} style={{ display: "flex", gap: 6, alignItems: "center" }}>
                        <input type="checkbox" checked={licForm.modulos_extra.includes(m)} onChange={() => toggleLista("modulos_extra", m)} disabled={!plan.modulos.includes(m)} />
                        <span style={{ textTransform: "capitalize" }}>{m}</span>
                      </label>
                    ))}
                  </div>
                </div>
                <div>
                  <Label>Módulos ocultos (quitar del tipo)</Label>
                  <div style={{ display: "flex", flexDirection: "column", gap: 4, maxHeight: 220, overflowY: "auto" }}>
                    {PLAN_MODULOS.map((m) => (
                      <label key={m} style={{ display: "flex", gap: 6, alignItems: "center" }}>
                        <input type="checkbox" checked={licForm.modulos_ocultos.includes(m)} onChange={() => toggleLista("modulos_ocultos", m)} disabled={!plan.modulos.includes(m)} />
                        <span style={{ textTransform: "capitalize" }}>{m}</span>
                      </label>
                    ))}
                  </div>
                </div>
              </div>
              <div style={{ textAlign: "right" }}>
                <button className="btn" type="submit">Guardar licencia</button>
              </div>
            </form>
          )}
        </>
      )}
    </div>
  );
}