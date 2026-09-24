import { useEffect, useMemo, useState } from "react";
import api, { downloadFile, openWindow } from "../api.js";
import { formatMoney, WhatsAppButton } from "../components/ui.jsx";

const TIPOS = {
  factura: "Factura",
  nota_credito: "Nota Crédito",
  nota_debito: "Nota Débito",
  documento_equivalente: "Doc. Equivalente",
  documento_pos: "Doc. POS",
};

const ESTADOS = ["", "pendiente", "enviado", "aprobado", "rechazado", "anulado"];

const estadoBadge = (e) => {
  const cls = {
    aprobado: "badge-success",
    pendiente: "badge",
    enviado: "badge",
    rechazado: "badge-danger",
    anulado: "badge",
  };
  return <span className={cls[e] || "badge"}>{e || "-"}</span>;
};

function copiarTexto(txt) {
  if (navigator.clipboard?.writeText) return navigator.clipboard.writeText(txt);
  const ta = document.createElement("textarea");
  ta.value = txt;
  document.body.appendChild(ta);
  ta.select();
  document.execCommand("copy");
  document.body.removeChild(ta);
  return Promise.resolve();
}

async function copiarCufe(d, setMsg, setError) {
  if (!d.cufe) {
    setError("Este documento aún no tiene CUFE asignado.");
    return;
  }
  try {
    await copiarTexto(d.cufe);
    setMsg(`CUFE de ${d.numero} copiado al portapapeles.`);
  } catch {
    setError("No se pudo copiar el CUFE.");
  }
}

function verificarDian(d) {
  if (!d.cufe) return;
  window.open(
    `https://catalogo-vpfe.dian.gov.co/document/search?documentId=${encodeURIComponent(d.cufe)}`,
    "_blank",
    "noopener,noreferrer"
  );
}

export default function Facturacion() {
  const [tab, setTab] = useState("docs");
  const [docs, setDocs] = useState([]);
  const [resoluciones, setResoluciones] = useState([]);
  const [sinFacturar, setSinFacturar] = useState([]);
  const [resumen, setResumen] = useState(null);
  const [integracion, setIntegracion] = useState(null);
  const [modoDian, setModoDian] = useState("sandbox");
  const [estado, setEstado] = useState("");
  const [tipo, setTipo] = useState("");
  const [error, setError] = useState("");
  const [msg, setMsg] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [docDetalle, setDocDetalle] = useState(null);
  const [form, setForm] = useState({
    resolucion: "",
    prefijo: "",
    tipo_documento: "factura",
    rango_inicial: 1,
    rango_final: 100000,
    fecha_inicio: "",
    fecha_vencimiento: "",
  });

  async function load() {
    api("/facturacion/documentos").then(setDocs).catch((e) => setError(e.message));
    api("/facturacion/resoluciones").then(setResoluciones).catch(() => {});
    api("/facturacion/resumen").then(setResumen).catch(() => {});
    api("/facturacion/integracion/estado").then((r) => {
      setIntegracion(r);
      if (r.modo) setModoDian(r.modo);
    }).catch(() => {});
    api("/facturacion/ventas-sin-facturar").then(setSinFacturar).catch(() => {});
  }

  useEffect(() => {
    load();
  }, []);

  useEffect(() => {
    api(
      `/facturacion/documentos${estado ? `?estado=${estado}` : ""}${tipo ? `${estado ? "&" : "?"}tipo_documento=${tipo}` : ""}`
    )
      .then(setDocs)
      .catch((e) => setError(e.message));
  }, [estado, tipo]);

  async function accion(id, accion, extra = null) {
    setError("");
    setMsg("");
    try {
      const query = extra ? `?${extra}` : "";
      const r = await api(`/facturacion/${id}/${accion}${query}`, { method: "POST" });
      setMsg(`OK: ${r.numero} -> ${r.estado_dian}`);
      load();
    } catch (e) {
      setError(e.message);
    }
  }

  const puedeTransmitir = Boolean(integracion?.puede_transmitir);

  async function generar(ventaId, tipoDoc, monto, concepto) {
    setError("");
    setMsg("");
    try {
      const r = await api(`/facturacion/generar/${ventaId}`, {
        method: "POST",
        body: JSON.stringify({ tipo_documento: tipoDoc, monto, concepto }),
      });
      setMsg(`Documento ${r.numero} generado`);
      load();
    } catch (e) {
      setError(e.message);
    }
  }

  async function crearResolucion(e) {
    e.preventDefault();
    setError("");
    if (form.rango_inicial > form.rango_final) {
      setError("El rango inicial no puede ser mayor que el rango final.");
      return;
    }
    if (form.fecha_vencimiento && form.fecha_inicio && form.fecha_vencimiento < form.fecha_inicio) {
      setError("La fecha de vencimiento no puede ser anterior a la fecha de inicio.");
      return;
    }
    try {
      await api("/facturacion/resoluciones", { method: "POST", body: JSON.stringify(form) });
      setShowForm(false);
      setForm({ resolucion: "", prefijo: "", tipo_documento: "factura", rango_inicial: 1, rango_final: 100000, fecha_inicio: "", fecha_vencimiento: "" });
      load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function toggleRes(id) {
    setMsg("");
    setError("");
    try {
      const r = await api(`/facturacion/resoluciones/${id}/toggle`, { method: "POST" });
      setMsg(`Resolución ${r.prefijo} ${r.activa ? "activada" : "desactivada"}`);
      load();
    } catch (e) {
      setError(e.message);
    }
  }

  async function verDoc(id) {
    setError("");
    setMsg("");
    try {
      const d = await api(`/facturacion/documentos/${id}`);
      setDocDetalle(d);
    } catch (e) {
      setError(e.message);
    }
  }

  async function rechazarDoc(d) {
    setError("");
    setMsg("");
    const motivo = window.prompt("Motivo del rechazo (simulación DIAN):", "Validación fallida");
    if (motivo === null) return;
    try {
      const r = await api(`/facturacion/${d.id}/rechazar?motivo=${encodeURIComponent(motivo)}`, { method: "POST" });
      setMsg(`Documento ${r.numero} marcado como rechazado (se puede reintentar).`);
      load();
    } catch (e) {
      setError(e.message);
    }
  }

  async function guardarModoDian() {
    setError("");
    setMsg("");
    try {
      await api(`/configuracion/general/dian.modo?valor=${encodeURIComponent(modoDian)}`, { method: "PUT" });
      setMsg(`DIAN configurado en modo ${modoDian === "produccion" ? "PRODUCCIÓN" : "SANDBOX (simulado)"}.`);
      load();
    } catch (e) {
      setError(e.message);
    }
  }

  const colorDoc = { factura: "#cbe6ff", nota_credito: "#d1fadf", nota_debito: "#ffe0c2" };
  const resMap = useMemo(
    () => Object.fromEntries(resoluciones.map((r) => [r.id, r.resolucion])),
    [resoluciones]
  );

  return (
    <div className="page">
      <div className="page-header">
        <h1>Facturación electrónica (DIAN)</h1>
        <div className="tabs">
          {[
            ["docs", "Documentos"],
            ["resoluciones", "Resoluciones"],
            ["porfacturar", "Ventas por facturar"],
          ].map(([k, l]) => (
            <button key={k} className={`btn ${tab === k ? "btn-primary" : ""}`} onClick={() => setTab(k)}>
              {l}
            </button>
          ))}
        </div>
      </div>

      {resumen && (
        <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginBottom: 16 }}>
          {[
            ["Total", resumen.total, ""],
            ["Aprobados", resumen.por_estado.aprobado, "#16a34a"],
            ["Pendientes", resumen.por_estado.pendiente, "#d97706"],
            ["Enviados", resumen.por_estado.enviado, "#0284c7"],
            ["Rechazados", resumen.por_estado.rechazado, "#dc2626"],
            ["Anulados", resumen.por_estado.anulado, "#6b7280"],
            ["Valor facturado", `$${resumen.valor_facturado.toLocaleString("es-CO")}`, ""],
          ].map(([lab, val, col]) => (
            <div key={lab} className="card" style={{ minWidth: 120, padding: "10px 14px" }}>
              <div style={{ fontSize: 11, color: "#6b7280" }}>{lab}</div>
              <div style={{ fontSize: 18, fontWeight: 700, color: col }}>{val}</div>
            </div>
          ))}
        </div>
      )}

      {integracion && (
        <div className={`card ${integracion.puede_generar_ubl ? "" : "error"}`} style={{ marginBottom: 16, padding: "12px 14px" }}>
          <div style={{ display: "flex", gap: 16, flexWrap: "wrap", alignItems: "center" }}>
            <strong>DIAN: {integracion.ambiente === "no_configurado" ? "Sin habilitar" : integracion.ambiente}</strong>
            {integracion.modo === "produccion" ? (
              <span className="badge" style={{ background: "#fee2e2", color: "#991b1b" }}>PRODUCCIÓN (transmisión real requerida)</span>
            ) : (
              <span className="badge" style={{ background: "#fef3c7", color: "#92400e" }}>SANDBOX · Modo simulación</span>
            )}
            {integracion.puede_generar_ubl && <span className="badge-success">UBL 2.1 ✓</span>}
          </div>
          <div style={{ fontSize: 13, marginTop: 4 }}>{integracion.mensaje}</div>
          {integracion.faltantes?.length > 0 && (
            <div style={{ fontSize: 12, marginTop: 6, color: "#92400e" }}>Faltantes: {integracion.faltantes.join(" · ")}</div>
          )}
          <div style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 10, flexWrap: "wrap" }}>
            <label style={{ fontSize: 12, color: "#6b7280" }}>Modo por cliente:</label>
            <select value={modoDian} onChange={(e) => setModoDian(e.target.value)} style={{ width: "auto" }}>
              <option value="sandbox">Sandbox (simulado, sin transmitir)</option>
              <option value="produccion">Producción (transmisión real, requiere conector)</option>
            </select>
            <button className="btn btn-secondary btn-sm" onClick={guardarModoDian} disabled={!integracion}>
              Guardar modo
            </button>
          </div>
        </div>
      )}

      {msg && <div className="badge-success" style={{ display: "inline-block", marginBottom: 8, padding: "6px 10px", borderRadius: 6 }}>{msg}</div>}
      {error && <div className="error">{error}</div>}

      {(() => {
        const act = resoluciones.find((r) => r.activa);
        return (
          <div className="card" style={{ marginBottom: 16, padding: "12px 14px", border: act ? "1px solid #16a34a" : "1px solid #fca5a5" }}>
            <div style={{ display: "flex", gap: 16, flexWrap: "wrap", alignItems: "center" }}>
              <strong>Resolución autorizada por la DIAN</strong>
              {act ? (
                <span className="badge-success" style={{ display: "inline-block", padding: "4px 10px", borderRadius: 6 }}>Aprobada ✓</span>
              ) : (
                <span className="badge" style={{ background: "#fee2e2", color: "#991b1b", display: "inline-block", padding: "4px 10px", borderRadius: 6 }}>Sin resolución activa</span>
              )}
            </div>
            {act ? (
              <div style={{ fontSize: 13, marginTop: 6 }}>
                <b>No. {act.resolucion}</b> · Prefijo <b>{act.prefijo}</b> · {TIPOS[act.tipo_documento] || act.tipo_documento} ·
                Rango {act.rango_inicial}–{act.rango_final} · Consecutivo actual {act.numero_actual} ·
                Vigencia {act.fecha_inicio || "…"} al {act.fecha_vencimiento || "…"}
              </div>
            ) : (
              <div style={{ fontSize: 13, marginTop: 6 }}>
                Active una resolución en la pestaña «{resoluciones.length > 0 ? "Resoluciones" : "Resoluciones"}» para habilitar la numeración autorizada.
              </div>
            )}
          </div>
        );
      })()}

      {tab === "docs" && (
        <>
          <div style={{ display: "flex", gap: 10, marginBottom: 10, flexWrap: "wrap" }}>
            <select value={estado} onChange={(e) => setEstado(e.target.value)} className="btn">
              {ESTADOS.map((e) => (
                <option key={e || "todos"} value={e}>
                  {e === "" ? "Todos los estados" : e}
                </option>
              ))}
            </select>
            <select value={tipo} onChange={(e) => setTipo(e.target.value)} className="btn">
              <option value="">Todos los tipos</option>
              {Object.entries(TIPOS).map(([k, l]) => (
                <option key={k} value={k}>
                  {l}
                </option>
              ))}
            </select>
          </div>
          <table className="table">
            <thead>
              <tr>
                <th>Número</th>
                <th>Resolución</th>
                <th>Tipo</th>
                <th>Cliente</th>
                <th>Fecha</th>
                <th>Monto</th>
                <th>Estado DIAN</th>
                <th>CUFE</th>
                <th>Acciones</th>
              </tr>
            </thead>
            <tbody>
              {docs.length === 0 && (
                <tr>
                  <td colSpan={9}>Sin documentos.</td>
                </tr>
              )}
              {docs.map((d) => (
                <tr key={d.id}>
                  <td>
                    <b>{d.numero}</b>
                  </td>
                  <td style={{ fontSize: 12 }}>{d.resolucion_id ? resMap[d.resolucion_id] || `#${d.resolucion_id}` : "-"}</td>
                  <td>
                    <span style={{ background: colorDoc[d.tipo_documento] || "#eee", padding: "2px 8px", borderRadius: 6, fontSize: 12 }}>
                      {TIPOS[d.tipo_documento] || d.tipo_documento}
                    </span>
                  </td>
                  <td>{d.cliente || "-"}</td>
                  <td style={{ fontSize: 12 }}>{d.fecha_emision || "-"}</td>
                  <td>{d.monto ? d.monto.toLocaleString("es-CO") : "-"}</td>
                  <td>{estadoBadge(d.estado_dian)}</td>
                  <td style={{ fontSize: 10, fontFamily: "monospace" }}>
                    {d.cufe ? (
                      <span style={{ display: "inline-flex", gap: 6, alignItems: "center", flexWrap: "wrap" }}>
                        <span title={d.cufe}>{d.cufe.slice(0, 12)}…</span>
                        <span style={{ whiteSpace: "nowrap" }}>
                          <button className="btn btn-sm" title="Copiar CUFE completo" onClick={() => copiarCufe(d, setMsg, setError)}>📋</button>
                          <button className="btn btn-sm" title="Verificar validez en el portal de la DIAN" onClick={() => verificarDian(d)}>🔎</button>
                        </span>
                      </span>
                    ) : (
                      "-"
                    )}
                  </td>
                  <td>
                    <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                      <button className="btn btn-sm" disabled={d.anulado || !puedeTransmitir} title={puedeTransmitir ? "Enviar a DIAN" : "Complete la configuración DIAN para habilitar el envío"} onClick={() => accion(d.id, "enviar")}>Enviar a DIAN</button>
                      <button className="btn btn-sm" disabled={d.anulado || !puedeTransmitir} title={puedeTransmitir ? "Consultar DIAN" : "Complete la configuración DIAN para habilitar la consulta"} onClick={() => accion(d.id, "consultar")}>Consultar DIAN</button>
                      {d.estado_dian === "rechazado" && (
                        <button className="btn btn-sm" onClick={() => accion(d.id, "reintentar")}>Reintentar</button>
                      )}
                      <button className="btn btn-sm" disabled={d.anulado} onClick={() => accion(d.id, "anular", "motivo=Anulaci%C3%B3n+desde+POS")}>Anular</button>
                      <button className="btn btn-sm" onClick={() => downloadFile(`/facturacion/${d.id}/pdf`, `${d.numero}.pdf`).catch((e) => setError(e.message))}>PDF</button>
                      <button className="btn btn-sm" onClick={() => downloadFile(`/facturacion/${d.id}/xml`, `${d.numero}.xml`).catch((e) => setError(e.message))}>XML</button>
                      <button className="btn btn-sm" onClick={() => openWindow(`/facturacion/${d.id}/ticket`).catch((e) => setError(e.message))}>Imprimir</button>
                      <button className="btn btn-sm" onClick={() => openWindow(`/facturacion/${d.id}/html`).catch((e) => setError(e.message))}>Ver</button>
                      <button className="btn btn-sm" onClick={() => accion(d.id, "correo")}>Correo</button>
                      <WhatsAppButton
                          telefono={d.telefono_cliente}
                          mensaje={`Hola ${d.cliente || ""}, su ${TIPOS[d.tipo_documento] || "documento"} ${d.numero} (${d.monto ? d.monto.toLocaleString("es-CO") : ""}) ya está listo.`}
                          label="WhatsApp"
                        />
                      <button className="btn btn-sm" onClick={() => verDoc(d.id)}>Detalle</button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}

      {tab === "resoluciones" && (
        <>
          <button className="btn" style={{ marginBottom: 12 }} onClick={() => setShowForm(!showForm)}>
            {showForm ? "Cerrar" : "+ Nueva resolución"}
          </button>
          {showForm && (
            <form onSubmit={crearResolucion} className="card" style={{ padding: 16, marginBottom: 16, display: "grid", gap: 10, maxWidth: 720 }}>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px,1fr))", gap: 10 }}>
                <input required placeholder="Nº resolución DIAN" value={form.resolucion} onChange={(e) => setForm({ ...form, resolucion: e.target.value })} />
                <input required placeholder="Prefijo (FV, NC, ND…)" value={form.prefijo} onChange={(e) => setForm({ ...form, prefijo: e.target.value })} />
                <select value={form.tipo_documento} onChange={(e) => setForm({ ...form, tipo_documento: e.target.value })}>
                  {Object.entries(TIPOS).map(([k, l]) => (
                    <option key={k} value={k}>{l}</option>
                  ))}
                </select>
                <input required type="number" min={1} placeholder="Rango inicial" value={form.rango_inicial} onChange={(e) => setForm({ ...form, rango_inicial: Number(e.target.value) })} />
                <input required type="number" min={1} placeholder="Rango final" value={form.rango_final} onChange={(e) => setForm({ ...form, rango_final: Number(e.target.value) })} />
                <input type="date" value={form.fecha_inicio} onChange={(e) => setForm({ ...form, fecha_inicio: e.target.value })} />
                <input type="date" value={form.fecha_vencimiento} onChange={(e) => setForm({ ...form, fecha_vencimiento: e.target.value })} />
              </div>
              <button className="btn btn-primary" style={{ justifySelf: "start" }}>Crear resolución</button>
            </form>
          )}
          <table className="table">
            <thead>
              <tr>
                <th>Prefijo</th>
                <th>Tipo</th>
                <th>Resolución</th>
                <th>Rango</th>
                <th>Consecutivo actual</th>
                <th>Vigencia</th>
                <th>Estado</th>
              </tr>
            </thead>
            <tbody>
              {resoluciones.map((r) => (
                <tr key={r.id}>
                  <td><b>{r.prefijo}</b></td>
                  <td>{TIPOS[r.tipo_documento] || r.tipo_documento}</td>
                  <td>{r.resolucion}</td>
                  <td>{r.rango_inicial} – {r.rango_final}</td>
                  <td>{r.numero_actual}</td>
                  <td style={{ fontSize: 12 }}>
                    {r.fecha_inicio || "…"} al {r.fecha_vencimiento || "…"}
                  </td>
                  <td>
                    <button className={`btn btn-sm ${r.activa ? "badge-success" : ""}`} title="La resolución activa es la autorizada por la DIAN para numerar" onClick={() => toggleRes(r.id)}>
                      {r.activa ? "Activa ✓" : "Inactiva"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}

      {tab === "porfacturar" && (
        <table className="table">
          <thead>
            <tr>
              <th>Venta</th>
              <th>Fecha</th>
              <th>Cliente</th>
              <th>Total</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {sinFacturar.length === 0 && (
              <tr>
                <td colSpan={5}>Todas las ventas completadas tienen factura electrónica.</td>
              </tr>
            )}
            {sinFacturar.map((v) => (
              <tr key={v.id}>
                <td><b>{v.numero}</b></td>
                <td style={{ fontSize: 12 }}>{v.created_at}</td>
                <td>{v.cliente}</td>
                <td>{v.total.toLocaleString("es-CO")}</td>
                <td>
                  <div style={{ display: "flex", gap: 6 }}>
                    <button className="btn btn-sm btn-primary" onClick={() => generar(v.id, "factura", null, null)}>Generar factura</button>
                    <button className="btn btn-sm" onClick={() => generar(v.id, "nota_credito", v.total, "Nota crédito manual")}>NC</button>
                    <button className="btn btn-sm" onClick={() => generar(v.id, "nota_debito", null, "Nota débito manual")}>ND</button>
                    <button className="btn btn-sm" onClick={() => generar(v.id, "documento_equivalente", null, null)}>Doc. equiv.</button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {docDetalle && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,.45)", display: "grid", placeItems: "center", zIndex: 1100, padding: 20 }}>
          <div className="card" style={{ width: "min(640px, 100%)", maxHeight: "86vh", overflow: "auto" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
              <h2 style={{ fontSize: 18 }}>{docDetalle.numero} <span className="muted" style={{ fontSize: 13 }}>#{docDetalle.id}</span></h2>
              <button className="btn btn-ghost" onClick={() => setDocDetalle(null)}>✕</button>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, fontSize: 14, marginBottom: 12 }}>
              <div><span className="muted">Tipo: </span>{TIPOS[docDetalle.tipo_documento] || docDetalle.tipo_documento}</div>
              <div><span className="muted">Prefijo: </span>{docDetalle.prefijo}</div>
              <div><span className="muted">Cliente: </span>{docDetalle.cliente || "—"}</div>
              <div><span className="muted">Venta: </span>{docDetalle.venta_id ? `#${docDetalle.venta_id}` : "—"}</div>
              <div><span className="muted">Fecha: </span>{docDetalle.fecha_emision || "—"}</div>
              <div><span className="muted">Monto: </span><strong>{docDetalle.monto != null ? `$${Number(docDetalle.monto).toLocaleString("es-CO")}` : "—"}</strong></div>
              <div><span className="muted">Estado DIAN: </span>{estadoBadge(docDetalle.estado_dian)}</div>
              <div><span className="muted">Anulado: </span>{docDetalle.anulado ? "Sí" : "No"}</div>
            </div>
            {docDetalle.cufe && (
              <div className="card sec" style={{ padding: 10, marginBottom: 10 }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 4 }}>
                  <span className="muted" style={{ fontSize: 12 }}>CUFE</span>
                  <span style={{ display: "flex", gap: 6 }}>
                    <button className="btn btn-sm" onClick={() => copiarCufe(docDetalle, setMsg, setError)}>📋 Copiar</button>
                    <button className="btn btn-sm" onClick={() => verificarDian(docDetalle)}>🔎 Verificar en DIAN</button>
                  </span>
                </div>
                <div style={{ fontSize: 12, fontFamily: "monospace", wordBreak: "break-all" }}>{docDetalle.cufe}</div>
              </div>
            )}
            {docDetalle.motivo_rechazo && (
              <div className="card sec" style={{ padding: 10, marginBottom: 10 }}>
                <div className="muted" style={{ fontSize: 12, marginBottom: 4 }}>Motivo de rechazo</div>
                <div style={{ fontSize: 13 }}>{docDetalle.motivo_rechazo}</div>
              </div>
            )}
            {docDetalle.respuesta_dian && (
              <div className="card sec" style={{ padding: 10 }}>
                <div className="muted" style={{ fontSize: 12, marginBottom: 4 }}>Respuesta DIAN</div>
                <div style={{ fontSize: 13, whiteSpace: "pre-wrap" }}>{docDetalle.respuesta_dian}</div>
              </div>
            )}
            <div style={{ display: "flex", gap: 6, marginTop: 14, flexWrap: "wrap" }}>
              <button className="btn btn-sm" onClick={() => downloadFile(`/facturacion/${docDetalle.id}/pdf`, `${docDetalle.numero}.pdf`).catch((e) => setError(e.message))}>PDF</button>
              <button className="btn btn-sm" onClick={() => downloadFile(`/facturacion/${docDetalle.id}/xml`, `${docDetalle.numero}.xml`).catch((e) => setError(e.message))}>XML</button>
              <button className="btn btn-sm" onClick={() => openWindow(`/facturacion/${docDetalle.id}/ticket`).catch((e) => setError(e.message))}>Imprimir ticket</button>
              <button className="btn btn-sm" disabled={!puedeTransmitir} title={puedeTransmitir ? "Consultar DIAN" : "Complete la configuración DIAN para habilitar la consulta"} onClick={() => accion(docDetalle.id, "consultar")}>Consultar DIAN</button>
              {docDetalle.estado_dian === "rechazado" && !docDetalle.anulado && (
                <button className="btn btn-sm" onClick={() => accion(docDetalle.id, "reintentar")}>Reintentar</button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
