import { useEffect, useState } from "react";
import api, { downloadCsv } from "../api.js";
import { formatMoney } from "../components/ui.jsx";
import ImportarCsv from "../components/ImportarCsv.jsx";

export default function Inventario() {
  const [tab, setTab] = useState("inventario");
  const [movimientos, setMovimientos] = useState([]);
  const [stock, setStock] = useState([]);
  const [productos, setProductos] = useState([]);
  const [error, setError] = useState("");
  const [form, setForm] = useState({
    producto_id: "",
    sucursal_id: 1,
    tipo: "entrada",
    cantidad: "",
    motivo: "",
  });
  const [merma, setMerma] = useState({ producto_id: "", cantidad: "", motivo: "" });
  const [conteo, setConteo] = useState({ observacion: "" });
  const [conteoProvisional, setConteoProvisional] = useState({ producto_id: "", contado: "" });
  const [conteoItems, setConteoItems] = useState([]);
  const [conteos, setConteos] = useState([]);
  const [produccion, setProduccion] = useState([]);
  const [resumen, setResumen] = useState(null);
  const [orden, setOrden] = useState({ producto_id: "", cantidad: "1" });
  const [cargando, setCargando] = useState(false);

  // bodegas
  const [bodegas, setBodegas] = useState([]);
  const [ubicaciones, setUbicaciones] = useState({});
  const [bodegaForm, setBodegaForm] = useState({ nombre: "", codigo: "", direccion: "" });
  const [ubicForm, setUbicForm] = useState({ bodega_id: "", nombre: "", codigo: "" });
  const [distBodega, setDistBodega] = useState([]);
  const [distUbic, setDistUbic] = useState([]);
  const [filtroBodega, setFiltroBodega] = useState("");
  const [stkForm, setStkForm] = useState({ producto_id: "", bodega_id: "", ubicacion_id: "", tipo: "entrada", cantidad: "", motivo: "" });
  const [trfForm, setTrfForm] = useState({ producto_id: "", cantidad: "", origen_bodega_id: "", destino_bodega_id: "", motivo: "" });
  const [transito, setTransito] = useState([]);

  // lotes
  const [lotes, setLotes] = useState([]);
  const [porLote, setPorLote] = useState([]);
  const [loteForm, setLoteForm] = useState({ producto_id: "", codigo: "", vencimiento: "", cantidad: "" });
  const [lotMot, setLotMot] = useState({ tipo: "stock", lote_id: "", cantidad: "", motivo: "" });

  // reposicion
  const [sugeridos, setSugeridos] = useState([]);

  // ajustes y transferencias entre sucursales
  const [sucursales, setSucursales] = useState([]);
  const [ajustForm, setAjustForm] = useState({ producto_id: "", sucursal_id: 1, existencias: "", motivo: "" });
  const [trfSucForm, setTrfSucForm] = useState({ producto_id: "", origen_sucursal_id: 1, destino_sucursal_id: 2, cantidad: "", motivo: "" });
  const [stkDet, setStkDet] = useState(null);

  useEffect(() => {
    api("/inventario/stock").then(setStock).catch((e) => setError(e.message));
    api("/inventario/movimientos").then(setMovimientos).catch(() => {});
    api("/inventario/conteos").then(setConteos).catch(() => {});
    api("/productos").then(setProductos).catch(() => {});
    api("/inventario/bodegas").then(setBodegas).catch(() => {});
    api("/inventario/por-bodega").then(setDistBodega).catch(() => {});
    api("/inventario/por-ubicacion").then(setDistUbic).catch(() => {});
    api("/inventario/transito").then(setTransito).catch(() => {});
    api("/inventario/lotes").then(setLotes).catch(() => {});
    api("/inventario/por-lote").then(setPorLote).catch(() => {});
    api("/organizacion/sucursales").then(setSucursales).catch(() => {});
  }, []);

  useEffect(() => {
    if (tab !== "produccion") return;
    api("/produccion").then(setProduccion).catch(() => {});
    api("/produccion/resumen").then(setResumen).catch(() => {});
  }, [tab]);

  useEffect(() => {
    if (tab !== "reposicion") return;
    api("/inventario/sugerir-reposicion?sucursal_id=1")
      .then((r) => setSugeridos(Array.isArray(r) ? r : (r?.sugerencias || [])))
      .catch(() => {});
  }, [tab]);

  async function handleMerma(e) {
    e.preventDefault();
    setError("");
    try {
      await api(`/inventario/mermas?producto_id=${merma.producto_id}&cantidad=${merma.cantidad}&sucursal_id=1&motivo=${encodeURIComponent(merma.motivo)}`, { method: "POST" });
      setMerma({ producto_id: "", cantidad: "", motivo: "" });
      api("/inventario/stock").then(setStock);
      api("/inventario/movimientos").then(setMovimientos);
    } catch (err) {
      setError(err.message);
    }
  }

  function agregarAConteo() {
    if (!conteoProvisional.producto_id || !conteoProvisional.contado) return;
    setConteoItems((prev) => [...prev, { producto_id: Number(conteoProvisional.producto_id), contado: Number(conteoProvisional.contado) }]);
    setConteoProvisional({ producto_id: "", contado: "" });
  }

  async function abrirConteo() {
    setError("");
    try {
      await api("/inventario/conteos", {
        method: "POST",
        body: JSON.stringify({ empresa_id: 1, sucursal_id: 1, observacion: conteo.observacion, detalle: conteoItems }),
      });
      setConteoItems([]);
      setConteo({ observacion: "" });
      api("/inventario/conteos").then(setConteos);
    } catch (err) {
      setError(err.message);
    }
  }

  async function liquidarConteo(id) {
    setError("");
    if (!window.confirm("¿Liquidar el conteo? Se aplicarán los ajustes al inventario.")) return;
    try {
      await api(`/inventario/conteos/${id}/liquidar`, { method: "POST" });
      api("/inventario/conteos").then(setConteos);
      api("/inventario/stock").then(setStock);
    } catch (err) {
      setError(err.message);
    }
  }

  async function cargarDetalle(producto_id) {
    setError("");
    try {
      const stockRow = await api(`/inventario/producto/${producto_id}?sucursal_id=1`);
      const prod = productos.find((p) => p.id === Number(producto_id));
      setStkDet({ ...stockRow, producto: prod?.nombre || `#${producto_id}` });
    } catch (err) {
      setError(err.message);
    }
  }

  async function ajustar(e) {
    e.preventDefault();
    setError("");
    try {
      await api("/inventario/ajustar", {
        method: "POST",
        body: JSON.stringify({
          producto_id: Number(ajustForm.producto_id),
          sucursal_id: Number(ajustForm.sucursal_id),
          existencias: Number(ajustForm.existencias),
          motivo: ajustForm.motivo || "Ajuste manual",
        }),
      });
      setAjustForm({ producto_id: "", sucursal_id: 1, existencias: "", motivo: "" });
      api("/inventario/stock").then(setStock);
      api("/inventario/movimientos").then(setMovimientos);
    } catch (err) {
      setError(err.message);
    }
  }

  async function transferirSuc(e) {
    e.preventDefault();
    setError("");
    if (Number(trfSucForm.origen_sucursal_id) === Number(trfSucForm.destino_sucursal_id)) {
      setError("La sucursal origen y destino deben ser diferentes");
      return;
    }
    try {
      await api("/inventario/transferir", {
        method: "POST",
        body: JSON.stringify({
          producto_id: Number(trfSucForm.producto_id),
          origen_sucursal_id: Number(trfSucForm.origen_sucursal_id),
          destino_sucursal_id: Number(trfSucForm.destino_sucursal_id),
          cantidad: Number(trfSucForm.cantidad),
          motivo: trfSucForm.motivo || null,
        }),
      });
      setTrfSucForm({ producto_id: "", origen_sucursal_id: 1, destino_sucursal_id: 2, cantidad: "", motivo: "" });
      api("/inventario/stock").then(setStock);
      api("/inventario/movimientos").then(setMovimientos);
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    try {
      await api("/inventario/movimientos", {
        method: "POST",
        body: JSON.stringify({
          ...form,
          producto_id: Number(form.producto_id),
          sucursal_id: Number(form.sucursal_id),
          cantidad: Number(form.cantidad),
        }),
      });
      setForm({ producto_id: "", sucursal_id: 1, tipo: "entrada", cantidad: "", motivo: "" });
      api("/inventario/stock").then(setStock);
      api("/inventario/movimientos").then(setMovimientos);
    } catch (err) {
      setError(err.message);
    }
  }

  async function crearOrden(e) {
    e.preventDefault();
    setError("");
    setCargando(true);
    try {
      const res = await api("/produccion", {
        method: "POST",
        body: JSON.stringify({ empresa_id: 1, sucursal_id: 1, producto_id: Number(orden.producto_id), cantidad: Number(orden.cantidad) }),
      });
      setOrden({ producto_id: "", cantidad: "1" });
      setProduccion((prev) => [res, ...prev]);
      api("/produccion/resumen").then(setResumen).catch(() => {});
    } catch (err) {
      setError(err.message);
    } finally {
      setCargando(false);
    }
  }

  // ---- bodegas ----
  async function crearBodega(e) {
    e.preventDefault();
    setError("");
    try {
      await api("/inventario/bodegas", {
        method: "POST",
        body: JSON.stringify({ empresa_id: 1, sucursal_id: 1, nombre: bodegaForm.nombre, codigo: bodegaForm.codigo || null, direccion: bodegaForm.direccion || null, activa: true }),
      });
      setBodegaForm({ nombre: "", codigo: "", direccion: "" });
      api("/inventario/bodegas").then(setBodegas);
    } catch (err) {
      setError(err.message);
    }
  }

  async function crearUbicacion(e) {
    e.preventDefault();
    setError("");
    if (!ubicForm.bodega_id) {
      setError("Selecciona una bodega.");
      return;
    }
    try {
      await api(`/inventario/bodegas/${ubicForm.bodega_id}/ubicaciones`, {
        method: "POST",
        body: JSON.stringify({ bodega_id: Number(ubicForm.bodega_id), nombre: ubicForm.nombre, codigo: ubicForm.codigo || null }),
      });
      setUbicForm({ bodega_id: "", nombre: "", codigo: "" });
    } catch (err) {
      setError(err.message);
    }
  }

  async function toggleActiva(b) {
    setError("");
    try {
      await api(`/inventario/bodegas/${b.id}`, {
        method: "PUT",
        body: JSON.stringify({ empresa_id: 1, sucursal_id: 1, nombre: b.nombre, codigo: b.codigo, direccion: b.direccion, activa: !b.activa }),
      });
      api("/inventario/bodegas").then(setBodegas);
    } catch (err) {
      setError(err.message);
    }
  }

  function cargarUbicaciones(bodegaId) {
    if (!bodegaId) return;
    api(`/inventario/bodegas/${bodegaId}/ubicaciones`)
      .then((r) => setUbicaciones((prev) => ({ ...prev, [bodegaId]: r })))
      .catch(() => {});
  }

  async function moverStockBodega(e) {
    e.preventDefault();
    setError("");
    try {
      await api("/inventario/stock-bodega", {
        method: "POST",
        body: JSON.stringify({
          producto_id: Number(stkForm.producto_id),
          bodega_id: Number(stkForm.bodega_id),
          ubicacion_id: stkForm.ubicacion_id ? Number(stkForm.ubicacion_id) : null,
          tipo: stkForm.tipo,
          cantidad: Number(stkForm.cantidad),
          motivo: stkForm.motivo || null,
        }),
      });
      setStkForm({ producto_id: "", bodega_id: "", ubicacion_id: "", tipo: "entrada", cantidad: "", motivo: "" });
      api("/inventario/por-bodega").then(setDistBodega);
      api("/inventario/por-ubicacion").then(setDistUbic).catch(() => {});
    } catch (err) {
      setError(err.message);
    }
  }

  async function transferir(e) {
    e.preventDefault();
    setError("");
    try {
      await api("/inventario/transferir-bodega", {
        method: "POST",
        body: JSON.stringify({
          producto_id: Number(trfForm.producto_id),
          cantidad: Number(trfForm.cantidad),
          origen_bodega_id: Number(trfForm.origen_bodega_id),
          destino_bodega_id: Number(trfForm.destino_bodega_id),
          motivo: trfForm.motivo || null,
        }),
      });
      setTrfForm({ producto_id: "", cantidad: "", origen_bodega_id: "", destino_bodega_id: "", motivo: "" });
      api("/inventario/transito").then(setTransito);
      api("/inventario/por-bodega").then(setDistBodega);
    } catch (err) {
      setError(err.message);
    }
  }

  async function transitoAction(id, accion) {
    setError("");
    try {
      await api(`/inventario/transito/${id}/${accion}`, { method: "POST" });
      api("/inventario/transito").then(setTransito);
      api("/inventario/por-bodega").then(setDistBodega);
    } catch (err) {
      setError(err.message);
    }
  }

  // ---- lotes ----
  async function crearLote(e) {
    e.preventDefault();
    setError("");
    try {
      await api("/inventario/lotes", {
        method: "POST",
        body: JSON.stringify({
          producto_id: Number(loteForm.producto_id),
          codigo: loteForm.codigo,
          vencimiento: loteForm.vencimiento || null,
          cantidad: Number(loteForm.cantidad || 0),
        }),
      });
      setLoteForm({ producto_id: "", codigo: "", vencimiento: "", cantidad: "" });
      api("/inventario/lotes").then(setLotes);
      api("/inventario/por-lote").then(setPorLote);
    } catch (err) {
      setError(err.message);
    }
  }

  async function movimientoLote(e) {
    e.preventDefault();
    setError("");
    if (!lotMot.lote_id || !lotMot.cantidad) return;
    try {
      await api(`/inventario/lotes/${lotMot.tipo}`, {
        method: "POST",
        body: JSON.stringify({ lote_id: Number(lotMot.lote_id), cantidad: Number(lotMot.cantidad), motivo: lotMot.motivo || null }),
      });
      setLotMot({ tipo: "stock", lote_id: "", cantidad: "", motivo: "" });
      api("/inventario/lotes").then(setLotes);
      api("/inventario/por-lote").then(setPorLote);
      api("/inventario/stock").then(setStock).catch(() => {});
    } catch (err) {
      setError(err.message);
    }
  }

  const compuestos = productos.filter((p) => p.es_compuesto);

  function estadoLote(v) {
    if (!v) return { txt: "Sin venc." };
    const exp = new Date(`${v}T23:59:59`);
    const hoy = new Date();
    if (exp < hoy) return { txt: "VENCIDO", danger: true };
    const diff = Math.ceil((exp - hoy) / 86400000);
    return { txt: diff <= 30 ? `OK (${diff}d)` : "Vigente" };
  }

  const distFiltrada = filtroBodega ? distBodega.filter((d) => String(d.bodega_id) === filtroBodega) : distBodega;

  return (
    <div className="page">
      <div className="page-header">
        <h1>Inventario</h1>
        <div className="tabs">
          {["inventario", "bodegas", "lotes", "ajustes", "reposicion", "produccion"].map((t) => (
            <button key={t} className={`btn ${tab === t ? "btn-primary" : ""}`} onClick={() => setTab(t)}>
              {t === "inventario" ? "Inventario" : t === "bodegas" ? "Bodegas" : t === "lotes" ? "Lotes / vencim." : t === "ajustes" ? "Ajustes / Transf." : t === "reposicion" ? "Reposición" : "Producción"}
            </button>
          ))}
        </div>
        <button className="btn btn-secondary" onClick={() => downloadCsv("/exportar/inventario", "inventario").catch((e) => setError(e.message))}>Exportar CSV</button>
        <ImportarCsv path="/importar/inventario" etiqueta="Importar CSV" onOk={() => api("/inventario/stock").then(setStock).catch(() => {})} />
      </div>

      {error && <div className="error">{error}</div>}

      {tab === "produccion" && (
        <>
          <form onSubmit={crearOrden} className="card" style={{ marginBottom: 20, display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))", gap: 12 }}>
            <div>
              <label>Producto a fabricar *</label>
              <select required value={orden.producto_id} onChange={(e) => setOrden({ ...orden, producto_id: e.target.value })}>
                <option value="">Seleccionar compuesto...</option>
                {compuestos.map((p) => (
                  <option key={p.id} value={p.id}>{p.nombre}</option>
                ))}
              </select>
              {compuestos.length === 0 && <small className="muted">No hay productos compuestos. Márcalos en Productos.</small>}
            </div>
            <div><label>Cantidad</label><input required type="number" min="1" value={orden.cantidad} onChange={(e) => setOrden({ ...orden, cantidad: e.target.value })} /></div>
            <div style={{ display: "flex", alignItems: "flex-end" }}>
              <button className="btn" type="submit" disabled={cargando || compuestos.length === 0}>{cargando ? "Procesando..." : "Producir"}</button>
            </div>
          </form>

          {resumen && (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: 18, marginBottom: 24 }}>
              <div className="card sec">
                <h3 className="card-title">Producido</h3>
                <table className="table">
                  <thead><tr><th>Producto</th><th>Cantidad</th><th>Costo</th></tr></thead>
                  <tbody>
                    {resumen.producido.map((r, i) => (
                      <tr key={i}><td>{r.producto}</td><td>{r.cantidad}</td><td>{formatMoney(r.costo)}</td></tr>
                    ))}
                    {!resumen.producido.length && <tr><td colSpan={3} className="muted" style={{ textAlign: "center", padding: 16 }}>Sin producción</td></tr>}
                  </tbody>
                </table>
              </div>
              <div className="card sec">
                <h3 className="card-title">Materias primas consumidas</h3>
                <table className="table">
                  <thead><tr><th>Materia prima</th><th>Cantidad</th></tr></thead>
                  <tbody>
                    {resumen.materias_primas.map((r, i) => (
                      <tr key={i}><td>{r.materia_prima}</td><td>{r.cantidad}</td></tr>
                    ))}
                    {!resumen.materias_primas.length && <tr><td colSpan={2} className="muted" style={{ textAlign: "center", padding: 16 }}>Sin consumo</td></tr>}
                  </tbody>
                </table>
              </div>
              <div className="card sec">
                <h3 className="card-title">Desperdicios (mermas)</h3>
                <table className="table">
                  <thead><tr><th>Producto</th><th>Cantidad</th></tr></thead>
                  <tbody>
                    {resumen.desperdicios.map((r, i) => (
                      <tr key={i}><td>{r.producto}</td><td>{r.cantidad}</td></tr>
                    ))}
                    {!resumen.desperdicios.length && <tr><td colSpan={2} className="muted" style={{ textAlign: "center", padding: 16 }}>Sin desperdicios</td></tr>}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          <h2 style={{ fontSize: 18, marginBottom: 12 }}>Órdenes de producción</h2>
          <table className="table" style={{ marginBottom: 24 }}>
            <thead>
              <tr><th>N°</th><th>Fecha</th><th>Producto</th><th>Cantidad</th><th>Costo total</th><th>Estado</th></tr>
            </thead>
            <tbody>
              {produccion.map((o) => (
                <tr key={o.id}>
                  <td>{o.numero}</td>
                  <td>{o.created_at ? new Date(o.created_at).toLocaleString() : "—"}</td>
                  <td>{o.producto}</td>
                  <td>{o.cantidad}</td>
                  <td>{formatMoney(o.costo_total)}</td>
                  <td><span className={`badge ${o.estado === "procesada" ? "badge-success" : "badge-warning"}`}>{o.estado}</span></td>
                </tr>
              ))}
              {produccion.length === 0 && <tr><td colSpan={6} className="muted" style={{ textAlign: "center", padding: 20 }}>Sin órdenes de producción</td></tr>}
            </tbody>
          </table>
        </>
      )}

      {tab === "bodegas" && (
        <>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))", gap: 16, marginBottom: 24 }}>
            <form onSubmit={crearBodega} className="card" style={{ display: "grid", gap: 10 }}>
              <h2 style={{ fontSize: 16 }}>Nueva bodega</h2>
              <div><label>Nombre *</label><input required value={bodegaForm.nombre} onChange={(e) => setBodegaForm({ ...bodegaForm, nombre: e.target.value })} /></div>
              <div><label>Código</label><input value={bodegaForm.codigo} onChange={(e) => setBodegaForm({ ...bodegaForm, codigo: e.target.value })} /></div>
              <div><label>Dirección</label><input value={bodegaForm.direccion} onChange={(e) => setBodegaForm({ ...bodegaForm, direccion: e.target.value })} /></div>
              <button className="btn" type="submit">Crear bodega</button>
            </form>

            <form onSubmit={crearUbicacion} className="card" style={{ display: "grid", gap: 10 }}>
              <h2 style={{ fontSize: 16 }}>Ubicación dentro de bodega</h2>
              <div>
                <label>Bodega *</label>
                <select required value={ubicForm.bodega_id} onChange={(e) => { setUbicForm({ ...ubicForm, bodega_id: e.target.value }); cargarUbicaciones(e.target.value); }}>
                  <option value="">Seleccionar...</option>
                  {bodegas.map((b) => <option key={b.id} value={b.id}>{b.nombre}</option>)}
                </select>
              </div>
              <div><label>Nombre de la ubicación (estante, fila...) *</label><input required value={ubicForm.nombre} onChange={(e) => setUbicForm({ ...ubicForm, nombre: e.target.value })} /></div>
              <div><label>Código</label><input value={ubicForm.codigo} onChange={(e) => setUbicForm({ ...ubicForm, codigo: e.target.value })} /></div>
              <button className="btn" type="submit">Agregar ubicación</button>
              {ubicaciones[ubicForm.bodega_id]?.length > 0 && (
                <div className="muted" style={{ fontSize: 12.5 }}>
                  Ya existentes: {ubicaciones[ubicForm.bodega_id].map((u) => u.nombre).join(", ")}
                </div>
              )}
            </form>
          </div>

          <h2 style={{ fontSize: 18, marginBottom: 12 }}>Movimiento de existencias en bodega</h2>
          <form onSubmit={moverStockBodega} className="card" style={{ marginBottom: 24, display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(170px, 1fr))", gap: 12 }}>
            <div>
              <label>Producto *</label>
              <select required value={stkForm.producto_id} onChange={(e) => setStkForm({ ...stkForm, producto_id: e.target.value })}>
                <option value="">Seleccionar...</option>
                {productos.map((p) => <option key={p.id} value={p.id}>{p.nombre}</option>)}
              </select>
            </div>
            <div>
              <label>Bodega *</label>
              <select required value={stkForm.bodega_id} onChange={(e) => { setStkForm({ ...stkForm, bodega_id: e.target.value }); cargarUbicaciones(e.target.value); }}>
                <option value="">Seleccionar...</option>
                {bodegas.filter((b) => b.activa !== false).map((b) => <option key={b.id} value={b.id}>{b.nombre}</option>)}
              </select>
            </div>
            <div>
              <label>Ubicación</label>
              <select value={stkForm.ubicacion_id} onChange={(e) => setStkForm({ ...stkForm, ubicacion_id: e.target.value })}>
                <option value="">Sin ubicación</option>
                {(ubicaciones[stkForm.bodega_id] || []).map((u) => <option key={u.id} value={u.id}>{u.nombre}</option>)}
              </select>
            </div>
            <div>
              <label>Tipo</label>
              <select value={stkForm.tipo} onChange={(e) => setStkForm({ ...stkForm, tipo: e.target.value })}>
                <option value="entrada">Entrada</option>
                <option value="salida">Salida</option>
                <option value="ajuste">Ajuste</option>
                <option value="reubicar">Reubicar</option>
              </select>
            </div>
            <div><label>Cantidad</label><input required type="number" value={stkForm.cantidad} onChange={(e) => setStkForm({ ...stkForm, cantidad: e.target.value })} /></div>
            <div><label>Motivo</label><input value={stkForm.motivo} onChange={(e) => setStkForm({ ...stkForm, motivo: e.target.value })} /></div>
            <div style={{ display: "flex", alignItems: "flex-end" }}><button className="btn" type="submit">Registrar</button></div>
          </form>

          <h2 style={{ fontSize: 18, marginBottom: 12 }}>Transferencia entre bodegas (tránsito)</h2>
          <form onSubmit={transferir} className="card" style={{ marginBottom: 16, display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(170px, 1fr))", gap: 12 }}>
            <div>
              <label>Producto *</label>
              <select required value={trfForm.producto_id} onChange={(e) => setTrfForm({ ...trfForm, producto_id: e.target.value })}>
                <option value="">Seleccionar...</option>
                {productos.map((p) => <option key={p.id} value={p.id}>{p.nombre}</option>)}
              </select>
            </div>
            <div>
              <label>Origen *</label>
              <select required value={trfForm.origen_bodega_id} onChange={(e) => setTrfForm({ ...trfForm, origen_bodega_id: e.target.value })}>
                <option value="">Origen...</option>
                {bodegas.filter((b) => b.activa !== false).map((b) => <option key={b.id} value={b.id}>{b.nombre}</option>)}
              </select>
            </div>
            <div>
              <label>Destino *</label>
              <select required value={trfForm.destino_bodega_id} onChange={(e) => setTrfForm({ ...trfForm, destino_bodega_id: e.target.value })}>
                <option value="">Destino...</option>
                {bodegas.filter((b) => b.activa !== false && b.id !== Number(trfForm.origen_bodega_id)).map((b) => <option key={b.id} value={b.id}>{b.nombre}</option>)}
              </select>
            </div>
            <div><label>Cantidad *</label><input required type="number" value={trfForm.cantidad} onChange={(e) => setTrfForm({ ...trfForm, cantidad: e.target.value })} /></div>
            <div><label>Motivo</label><input value={trfForm.motivo} onChange={(e) => setTrfForm({ ...trfForm, motivo: e.target.value })} /></div>
            <div style={{ display: "flex", alignItems: "flex-end" }}><button className="btn" type="submit">Iniciar tránsito</button></div>
          </form>

          <h2 style={{ fontSize: 16, marginBottom: 8 }}>Tránsito (pendientes de recibir)</h2>
          <table className="table" style={{ marginBottom: 24 }}>
            <thead><tr><th>Fecha</th><th>Producto</th><th>Origen</th><th>Destino</th><th>Cantidad</th><th>Estado</th><th></th></tr></thead>
            <tbody>
              {transito.map((t) => (
                <tr key={t.id}>
                  <td>{t.created_at ? new Date(t.created_at).toLocaleString() : "—"}</td>
                  <td>{t.producto}</td>
                  <td>{t.origen_bodega ?? t.bodega_origen}</td>
                  <td>{t.destino_bodega ?? t.bodega_destino}</td>
                  <td>{t.cantidad}</td>
                  <td><span className={`badge ${t.estado === "completada" ? "badge-success" : t.estado === "cancelada" ? "badge-danger" : "badge-warning"}`}>{t.estado}</span></td>
                  <td>
                    {t.estado === "en_transito" && (
                      <span>
                        <button className="btn btn-sm" onClick={() => transitoAction(t.id, "recibir")}>Recibir</button>{" "}
                        <button className="btn btn-sm btn-danger" onClick={() => transitoAction(t.id, "cancelar")}>Cancelar</button>
                      </span>
                    )}
                  </td>
                </tr>
              ))}
              {transito.length === 0 && <tr><td colSpan={7} className="muted" style={{ textAlign: "center", padding: 16 }}>Sin tránsitos</td></tr>}
            </tbody>
          </table>

          <h2 style={{ fontSize: 18, marginBottom: 12 }}>Bodegas</h2>
          <table className="table" style={{ marginBottom: 16 }}>
            <thead><tr><th>Nombre</th><th>Código</th><th>Ubicaciones</th><th>Estado</th><th></th></tr></thead>
            <tbody>
              {bodegas.map((b) => (
                <tr key={b.id}>
                  <td>{b.nombre}</td>
                  <td>{b.codigo || "—"}</td>
                  <td>{(ubicaciones[b.id] || []).length}</td>
                  <td><span className={`badge ${b.activa ? "badge-success" : "badge-danger"}`}>{b.activa ? "Activa" : "Inactiva"}</span></td>
                  <td>
                    <button className="btn btn-ghost" onClick={() => { cargarUbicaciones(b.id); setTab("bodegas"); }} title={`Ver ubicaciones (${(ubicaciones[b.id] || []).length})`}>📍</button>
                    <button className="btn btn-sm" onClick={() => toggleActiva(b)}>{b.activa ? "Desactivar" : "Activar"}</button>
                  </td>
                </tr>
              ))}
              {bodegas.length === 0 && <tr><td colSpan={5} className="muted" style={{ textAlign: "center", padding: 16 }}>No hay bodegas</td></tr>}
            </tbody>
          </table>

          <h2 style={{ fontSize: 18, marginBottom: 12 }}>Existencias por bodega</h2>
          <div style={{ marginBottom: 10, maxWidth: 300 }}>
            <select value={filtroBodega} onChange={(e) => setFiltroBodega(e.target.value)}>
              <option value="">Todas las bodegas</option>
              {bodegas.map((b) => <option key={b.id} value={b.id}>{b.nombre}</option>)}
            </select>
          </div>
          <table className="table">
            <thead><tr><th>Producto</th><th>Bodega</th><th>Existencias</th></tr></thead>
            <tbody>
              {distFiltrada.map((d, i) => (
                <tr key={i}>
                  <td>{d.producto}</td>
                  <td>{d.bodega}</td>
                  <td>{d.existencias}</td>
                </tr>
              ))}
              {distFiltrada.length === 0 && <tr><td colSpan={3} className="muted" style={{ textAlign: "center", padding: 16 }}>Sin resultados</td></tr>}
            </tbody>
          </table>
        </>
      )}

      {tab === "lotes" && (
        <>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: 16, marginBottom: 24 }}>
            <form onSubmit={crearLote} className="card" style={{ display: "grid", gap: 10 }}>
              <h2 style={{ fontSize: 16 }}>Registrar lote</h2>
              <div>
                <label>Producto *</label>
                <select required value={loteForm.producto_id} onChange={(e) => setLoteForm({ ...loteForm, producto_id: e.target.value })}>
                  <option value="">Seleccionar...</option>
                  {productos.map((p) => <option key={p.id} value={p.id}>{p.nombre}</option>)}
                </select>
              </div>
              <div><label>Código lote *</label><input required value={loteForm.codigo} onChange={(e) => setLoteForm({ ...loteForm, codigo: e.target.value })} placeholder="Ej: LOTE-2026-01" /></div>
              <div><label>Vencimiento</label><input type="date" value={loteForm.vencimiento} onChange={(e) => setLoteForm({ ...loteForm, vencimiento: e.target.value })} /></div>
              <div><label>Cantidad inicial</label><input type="number" value={loteForm.cantidad} onChange={(e) => setLoteForm({ ...loteForm, cantidad: e.target.value })} /></div>
              <button className="btn" type="submit">Guardar lote</button>
            </form>

            <form onSubmit={movimientoLote} className="card" style={{ display: "grid", gap: 10 }}>
              <h2 style={{ fontSize: 16 }}>Ingreso / salida por lote</h2>
              <div>
                <label>Lote *</label>
                <select required value={lotMot.lote_id} onChange={(e) => setLotMot({ ...lotMot, lote_id: e.target.value })}>
                  <option value="">Seleccionar lote...</option>
                  {lotes.map((l) => (
                    <option key={l.id} value={l.id}>{l.codigo}{l.vencimiento ? ` (vence ${l.vencimiento})` : ""}</option>
                  ))}
                </select>
              </div>
              <div>
                <label>Tipo movimiento</label>
                <select value={lotMot.tipo} onChange={(e) => setLotMot({ ...lotMot, tipo: e.target.value })}>
                  <option value="stock">Ingreso al lote</option>
                  <option value="salida">Salida del lote</option>
                </select>
              </div>
              <div><label>Cantidad *</label><input required type="number" value={lotMot.cantidad} onChange={(e) => setLotMot({ ...lotMot, cantidad: e.target.value })} /></div>
              <div><label>Motivo</label><input value={lotMot.motivo} onChange={(e) => setLotMot({ ...lotMot, motivo: e.target.value })} /></div>
              <button className="btn" type="submit">Aplicar</button>
            </form>
          </div>

          <h2 style={{ fontSize: 18, marginBottom: 12 }}>Stock por lote</h2>
          <table className="table">
            <thead><tr><th>Producto</th><th>Lote</th><th>Vencimiento</th><th>Cantidad</th><th>Estado</th></tr></thead>
            <tbody>
              {porLote.map((g, i) => {
                const est = estadoLote(g.vencimiento);
                return (
                  <tr key={i}>
                    <td>{g.producto}</td>
                    <td>{g.codigo}</td>
                    <td>{g.vencimiento || "—"}</td>
                    <td>{g.cantidad}</td>
                    <td><span className={`badge ${est.danger ? "badge-danger" : g.vencimiento ? "badge-success" : "badge"}`}>{est.txt}</span></td>
                  </tr>
                );
              })}
              {porLote.length === 0 && <tr><td colSpan={5} className="muted" style={{ textAlign: "center", padding: 16 }}>Sin lotes registrados</td></tr>}
            </tbody>
          </table>
        </>
      )}

      {tab === "ajustes" && (
        <>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(340px, 1fr))", gap: 18, marginBottom: 20 }}>
            <form onSubmit={ajustar} className="card sec" style={{ padding: 16, display: "grid", gap: 10 }}>
              <h3 className="card-title">Ajuste directo de existencias</h3>
              <p className="muted" style={{ fontSize: 12 }}>
                Fija el valor absoluto de existencias del producto en una sucursal (registra movimiento y auditoría, requiere autorización si está activada).
              </p>
              <div>
                <label>Producto *</label>
                <select required value={ajustForm.producto_id} onChange={(e) => setAjustForm({ ...ajustForm, producto_id: e.target.value })}>
                  <option value="">Seleccionar...</option>
                  {productos.map((p) => <option key={p.id} value={p.id}>{p.nombre}</option>)}
                </select>
              </div>
              <div>
                <label>Sucursal</label>
                <select value={ajustForm.sucursal_id} onChange={(e) => setAjustForm({ ...ajustForm, sucursal_id: e.target.value })}>
                  {sucursales.map((s) => <option key={s.id} value={s.id}>{s.nombre}</option>)}
                </select>
              </div>
              <div>
                <label>Nuevas existencias *</label>
                <input required type="number" min="0" step="any" value={ajustForm.existencias} onChange={(e) => setAjustForm({ ...ajustForm, existencias: e.target.value })} />
              </div>
              <div>
                <label>Motivo</label>
                <input value={ajustForm.motivo} onChange={(e) => setAjustForm({ ...ajustForm, motivo: e.target.value })} placeholder="Ajuste manual / corrección" />
              </div>
              <button className="btn btn-primary" type="submit">Aplicar ajuste</button>
            </form>

            <form onSubmit={transferirSuc} className="card sec" style={{ padding: 16, display: "grid", gap: 10 }}>
              <h3 className="card-title">Transferencia entre sucursales</h3>
              <p className="muted" style={{ fontSize: 12 }}>Mueve stock de una sucursal a otra (debita existencias en origen y suma en destino).</p>
              <div>
                <label>Producto *</label>
                <select required value={trfSucForm.producto_id} onChange={(e) => setTrfSucForm({ ...trfSucForm, producto_id: e.target.value })}>
                  <option value="">Seleccionar...</option>
                  {productos.map((p) => <option key={p.id} value={p.id}>{p.nombre}</option>)}
                </select>
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
                <div>
                  <label>Origen</label>
                  <select required value={trfSucForm.origen_sucursal_id} onChange={(e) => setTrfSucForm({ ...trfSucForm, origen_sucursal_id: e.target.value })}>
                    {sucursales.map((s) => <option key={s.id} value={s.id}>{s.nombre}</option>)}
                  </select>
                </div>
                <div>
                  <label>Destino</label>
                  <select required value={trfSucForm.destino_sucursal_id} onChange={(e) => setTrfSucForm({ ...trfSucForm, destino_sucursal_id: e.target.value })}>
                    {sucursales.map((s) => <option key={s.id} value={s.id}>{s.nombre}</option>)}
                  </select>
                </div>
              </div>
              <div>
                <label>Cantidad *</label>
                <input required type="number" min="0.001" step="any" value={trfSucForm.cantidad} onChange={(e) => setTrfSucForm({ ...trfSucForm, cantidad: e.target.value })} />
              </div>
              <div>
                <label>Motivo</label>
                <input value={trfSucForm.motivo} onChange={(e) => setTrfSucForm({ ...trfSucForm, motivo: e.target.value })} />
              </div>
              <button className="btn btn-primary" type="submit">Transferir</button>
            </form>
          </div>
        </>
      )}

      {tab === "reposicion" && (
        <>
          <div className="card sec" style={{ marginBottom: 16 }}>
            <h3 className="card-title">Sugerencia de reposición</h3>
            <p className="muted" style={{ fontSize: 13 }}>
              Productos por debajo del punto de reorden. La cantidad sugerida considera el stock máximo definido en el producto.
            </p>
          </div>
          <table className="table">
            <thead>
              <tr>
                <th>Producto</th>
                <th>Código</th>
                <th>Existencias</th>
                <th>Punto de reorden</th>
                <th>Stock máximo</th>
                <th>Recomendado comprar</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {sugeridos.map((s) => (
                <tr key={s.producto_id}>
                  <td>{s.producto}</td>
                  <td>{s.codigo || "—"}</td>
                  <td><span className={s.existencias <= s.punto_reorden ? "text-danger" : ""}>{s.existencias}</span></td>
                  <td>{s.punto_reorden}</td>
                  <td>{s.stock_maximo}</td>
                  <td><strong>{s.cantidad_sugerida}</strong></td>
                  <td>
                    <a className="btn btn-sm" href="/#/compras">Ir a compras →</a>
                  </td>
                </tr>
              ))}
              {sugeridos.length === 0 && <tr><td colSpan={7} className="muted" style={{ textAlign: "center", padding: 20 }}>Todo en niveles. Nada por reponer.</td></tr>}
            </tbody>
          </table>
        </>
      )}

      {tab === "inventario" && (
      <>
      <form onSubmit={handleSubmit} className="card" style={{ marginBottom: 20, display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(170px, 1fr))", gap: 12 }}>
        <div>
          <label>Producto</label>
          <select required value={form.producto_id} onChange={(e) => setForm({ ...form, producto_id: e.target.value })}>
            <option value="">Seleccionar...</option>
            {productos.map((p) => (
              <option key={p.id} value={p.id}>{p.nombre}</option>
            ))}
          </select>
        </div>
        <div>
          <label>Tipo</label>
          <select value={form.tipo} onChange={(e) => setForm({ ...form, tipo: e.target.value })}>
            <option value="entrada">Entrada</option>
            <option value="salida">Salida</option>
            <option value="ajuste">Ajuste</option>
          </select>
        </div>
        <div>
          <label>Cantidad</label>
          <input required type="number" value={form.cantidad} onChange={(e) => setForm({ ...form, cantidad: e.target.value })} />
        </div>
        <div>
          <label>Motivo</label>
          <input value={form.motivo} onChange={(e) => setForm({ ...form, motivo: e.target.value })} />
        </div>
        <div style={{ display: "flex", alignItems: "flex-end" }}>
          <button className="btn" type="submit">Registrar</button>
        </div>
      </form>

      <h2 style={{ fontSize: 18, marginBottom: 12 }}>Existencias</h2>
      <table className="table" style={{ marginBottom: 24 }}>
        <thead>
          <tr>
            <th>Producto</th>
            <th>Sucursal</th>
            <th>Existencias</th>
            <th>Disponible</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {stock.map((s) => (
            <tr key={s.id}>
              <td>{productos.find((p) => p.id === s.producto_id)?.nombre || s.producto_id}</td>
              <td>{s.sucursal_id}</td>
              <td>{s.existencias}</td>
              <td>{s.disponible}</td>
              <td><button className="btn btn-sm btn-ghost" onClick={() => cargarDetalle(s.producto_id)}>Detalle</button></td>
            </tr>
          ))}
          {stock.length === 0 && (
            <tr><td colSpan={5} className="muted" style={{ textAlign: "center", padding: 20 }}>Sin existencias</td></tr>
          )}
        </tbody>
      </table>

      <h2 style={{ fontSize: 18, marginBottom: 12 }}>Mermas / dañados / vencidos</h2>
      <form onSubmit={handleMerma} className="card" style={{ marginBottom: 24, display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(170px, 1fr))", gap: 12 }}>
        <div>
          <label>Producto</label>
          <select required value={merma.producto_id} onChange={(e) => setMerma({ ...merma, producto_id: e.target.value })}>
            <option value="">Seleccionar...</option>
            {productos.map((p) => <option key={p.id} value={p.id}>{p.nombre}</option>)}
          </select>
        </div>
        <div><label>Cantidad</label><input required type="number" min="1" value={merma.cantidad} onChange={(e) => setMerma({ ...merma, cantidad: e.target.value })} /></div>
        <div><label>Motivo</label><input required value={merma.motivo} onChange={(e) => setMerma({ ...merma, motivo: e.target.value })} placeholder="Dañado, vencido, robo..." /></div>
        <div style={{ display: "flex", alignItems: "flex-end" }}><button className="btn btn-danger" type="submit">Registrar merma</button></div>
      </form>

      <h2 style={{ fontSize: 18, marginBottom: 12 }}>Conteo físico</h2>
      <div className="card" style={{ marginBottom: 24 }}>
        <div style={{ display: "flex", gap: 10, alignItems: "flex-end", marginBottom: 12 }}>
          <div style={{ flex: "1 1 320px" }}>
            <label>Buscar y capturar existencias (producto + contado)</label>
            <div style={{ display: "flex", gap: 8 }}>
              <select style={{ flex: 1 }} value={conteoProvisional.producto_id} onChange={(e) => setConteoProvisional({ ...conteoProvisional, producto_id: e.target.value })}>
                <option value="">Producto...</option>
                {productos.map((p) => <option key={p.id} value={p.id}>{p.nombre}</option>)}
              </select>
              <input type="number" style={{ width: 100 }} placeholder="Contado" value={conteoProvisional.contado} onChange={(e) => setConteoProvisional({ ...conteoProvisional, contado: e.target.value })} />
              <button type="button" className="btn btn-secondary" onClick={agregarAConteo}>+ Agregar</button>
            </div>
          </div>
        </div>
        {conteoItems.length > 0 && (
          <div style={{ marginBottom: 12 }}>
            {conteoItems.map((it, i) => (
              <span key={i} className="badge badge-info" style={{ margin: "0 8px 8px 0", padding: "6px 10px" }}>
                {productos.find((p) => p.id === it.producto_id)?.nombre || it.producto_id} → {it.contado}
                <button className="btn btn-ghost" style={{ marginLeft: 6, padding: 0 }} onClick={() => setConteoItems(conteoItems.filter((_, x) => x !== i))}>×</button>
              </span>
            ))}
          </div>
        )}
        <div style={{ display: "flex", gap: 8, alignItems: "flex-end" }}>
          <div style={{ flex: 1 }}><label>Observación</label><input value={conteo.observacion} onChange={(e) => setConteo({ ...conteo, observacion: e.target.value })} placeholder="Conteo semanal..." /></div>
          <button className="btn" onClick={abrirConteo} disabled={conteoItems.length === 0}>Abrir conteo</button>
        </div>
      </div>

      <h2 style={{ fontSize: 18, marginBottom: 12 }}>Conteos abiertos</h2>
      <table className="table" style={{ marginBottom: 24 }}>
        <thead>
          <tr><th>Número</th><th>Fecha</th><th>Productos</th><th>Estado</th><th></th></tr>
        </thead>
        <tbody>
          {conteos.map((c) => (
            <tr key={c.id}>
              <td>{c.numero}</td>
              <td>{c.created_at ? new Date(c.created_at).toLocaleString() : "—"}</td>
              <td>{c.detalle?.length || 0}</td>
              <td><span className={`badge ${c.estado === "liquidado" ? "badge-success" : "badge-warning"}`}>{c.estado}</span></td>
              <td>
                {c.estado === "abierto" && (
                  <button className="btn" onClick={() => liquidarConteo(c.id)}>Liquidar</button>
                )}
              </td>
            </tr>
          ))}
          {conteos.length === 0 && <tr><td colSpan={5} className="muted" style={{ textAlign: "center", padding: 16 }}>Sin conteos</td></tr>}
        </tbody>
      </table>

      <h2 style={{ fontSize: 18, marginBottom: 12 }}>Movimientos recientes</h2>
      <table className="table">
        <thead>
          <tr>
            <th>Fecha</th>
            <th>Producto</th>
            <th>Tipo</th>
            <th>Cantidad</th>
            <th>Saldo</th>
            <th>Motivo</th>
          </tr>
        </thead>
        <tbody>
          {movimientos.map((m) => (
            <tr key={m.id}>
              <td>{m.created_at ? new Date(m.created_at).toLocaleString() : "—"}</td>
              <td>{productos.find((p) => p.id === m.producto_id)?.nombre || m.producto_id}</td>
              <td>
                <span className={`badge ${
                  m.tipo === "entrada" ? "badge-success" : m.tipo === "salida" ? "badge-danger" : "badge-warning"
                }`}>
                  {m.tipo}
                </span>
              </td>
              <td>{m.cantidad}</td>
              <td>{m.saldo}</td>
              <td>{m.motivo}</td>
            </tr>
          ))}
          {movimientos.length === 0 && (
            <tr><td colSpan={6} className="muted" style={{ textAlign: "center", padding: 20 }}>Sin movimientos</td></tr>
          )}
        </tbody>
      </table>
      </>
      )}

      {stkDet && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,.45)", display: "grid", placeItems: "center", zIndex: 1100, padding: 20 }}>
          <div className="card" style={{ width: "min(480px, 100%)" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
              <h3>{stkDet.producto}</h3>
              <button className="btn btn-ghost" onClick={() => setStkDet(null)}>✕</button>
            </div>
            <div style={{ display: "grid", gap: 8 }}>
              {[
                ["Producto", stkDet.producto_id],
                ["Sucursal", stkDet.sucursal_id],
                ["Existencias", stkDet.existencias],
                ["Disponible", stkDet.disponible],
                ["Reservado", stkDet.reservado ?? "—"],
                ["Punto de reorden", stkDet.punto_reorden ?? "—"],
                ["Stock máximo", stkDet.stock_maximo ?? "—"],
              ].map(([k, v]) => (
                <div key={k} style={{ display: "flex", justifyContent: "space-between", borderBottom: "1px solid var(--line)", padding: "6px 0" }}>
                  <span className="muted" style={{ fontSize: 13 }}>{k}</span>
                  <strong>{v ?? "—"}</strong>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}