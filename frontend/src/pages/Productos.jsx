import { useEffect, useState } from "react";
import api, { downloadCsv, openWindow } from "../api.js";
import ImportarCsv from "../components/ImportarCsv.jsx";

function formatMoney(n) {
  return new Intl.NumberFormat("es-CO", {
    style: "currency",
    currency: "COP",
    maximumFractionDigits: 0,
  }).format(n || 0);
}

const FORM_BASE = {
  empresa_id: 1,
  nombre: "",
  codigo_barras: "",
  sku: "",
  categoria_id: "",
  marca_id: "",
  tipo: "unidad",
  precio_compra: "",
  precio_venta: "",
  precio_mayorista: "",
  precio_minorista: "",
  precio_institucional: "",
  costo: "",
  impuesto: "",
  margen_minimo: "",
  stock_minimo: "",
  stock_maximo: "",
  punto_reorden: "",
  es_servicio: false,
  maneja_lotes: false,
  maneja_serie: false,
  con_vencimiento: false,
  ficha_tecnica: "",
};

const TIPOS = ["unidad", "peso", "volumen", "longitud", "caja", "paquete"];

export default function Productos() {
  const [productos, setProductos] = useState([]);
  const [categorias, setCategorias] = useState([]);
  const [marcas, setMarcas] = useState([]);
  const [presentaciones, setPresentaciones] = useState([]);
  const [q, setQ] = useState("");
  const [error, setError] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(FORM_BASE);
  const [editando, setEditando] = useState(null);
  const [detalle, setDetalle] = useState(null);
  const [historial, setHistorial] = useState([]);
  const [competencia, setCompetencia] = useState([]);
  const [comp, setComp] = useState({ competidor: "", precio: "", notas: "" });
  const [showTipos, setShowTipos] = useState(false);
  const [tipoNuevo, setTipoNuevo] = useState({ categoria: "", marca: "", pres: { nombre: "", unidad_medida: "", cantidad: 1 } });
  const [recetaFor, setRecetaFor] = useState(null);
  const [recetaInfo, setRecetaInfo] = useState(null);
  const [recIngs, setRecIngs] = useState([]);
  const [recMsg, setRecMsg] = useState("");

  useEffect(() => {
    load();
    loadTipos();
  }, []);

  useEffect(() => {
    const t = setTimeout(() => load(), 300);
    return () => clearTimeout(t);
  }, [q]);

  function load() {
    api(`/productos${q ? `?q=${encodeURIComponent(q)}` : ""}`)
      .then(setProductos)
      .catch((e) => setError(e.message));
  }

  function loadTipos() {
    api("/productos/categorias").then(setCategorias).catch(() => {});
    api("/productos/marcas").then(setMarcas).catch(() => {});
    api("/productos/presentaciones").then(setPresentaciones).catch(() => {});
  }

  function num(f) {
    const n = Number(f);
    return Number.isFinite(n) ? n : 0;
  }

  function bodyProducto(f) {
    return {
      ...f,
      categoria_id: f.categoria_id ? Number(f.categoria_id) : null,
      marca_id: f.marca_id ? Number(f.marca_id) : null,
      precio_compra: num(f.precio_compra),
      precio_venta: num(f.precio_venta),
      precio_mayorista: num(f.precio_mayorista),
      precio_minorista: num(f.precio_minorista),
      precio_institucional: num(f.precio_institucional),
      costo: num(f.costo),
      impuesto: num(f.impuesto),
      margen_minimo: num(f.margen_minimo),
      stock_minimo: num(f.stock_minimo),
      stock_maximo: num(f.stock_maximo),
      punto_reorden: num(f.punto_reorden),
    };
  }

  async function handleCreate(e) {
    e.preventDefault();
    setError("");
    try {
      await api("/productos", { method: "POST", body: JSON.stringify(bodyProducto(form)) });
      setShowForm(false);
      setForm(FORM_BASE);
      load();
    } catch (err) {
      setError(err.message);
    }
  }

  function abrirEdicion(p) {
    setEditando(p);
    setError("");
  }

  async function guardarEdicion(e) {
    e.preventDefault();
    if (!editando) return;
    setError("");
    try {
      await api(`/productos/${editando.id}`, {
        method: "PUT",
        body: JSON.stringify(bodyProducto(editando)),
      });
      setEditando(null);
      load();
      if (detalle?.id === editando.id) abrirDetalle(editando);
    } catch (err) {
      setError(err.message);
    }
  }

  function setEditandoCampo(key, val) {
    setEditando((prev) => ({ ...prev, [key]: val }));
  }

  async function abrirDetalle(p) {
    setError("");
    try {
      const [prod, hist, comps] = await Promise.all([
        api(`/productos/${p.id}`),
        api(`/productos/${p.id}/precios`),
        api(`/productos/${p.id}/precios-competencia`),
      ]);
      setDetalle(prod);
      setHistorial(hist);
      setCompetencia(comps);
      setComp({ competidor: "", precio: "", notas: "" });
    } catch (err) {
      setError(err.message);
    }
  }

  async function agregarCompetencia() {
    if (!comp.competidor || !comp.precio) {
      setError("Indica competidor y precio.");
      return;
    }
    setError("");
    try {
      const nuevo = await api(`/productos/${detalle.id}/precios-competencia`, {
        method: "POST",
        body: JSON.stringify({ competidor: comp.competidor, precio: num(comp.precio), notas: comp.notas }),
      });
      setCompetencia((prev) => [nuevo, ...prev]);
      setComp({ competidor: "", precio: "", notas: "" });
    } catch (err) {
      setError(err.message);
    }
  }

  async function eliminarCompetencia(id) {
    if (!window.confirm("¿Eliminar este precio de competencia?")) return;
    setError("");
    try {
      await api(`/productos/precios-competencia/${id}`, { method: "DELETE" });
      setCompetencia((prev) => prev.filter((x) => x.id !== id));
    } catch (err) {
      setError(err.message);
    }
  }

  async function crearCategoria() {
    if (!tipoNuevo.categoria) return;
    setError("");
    try {
      await api("/productos/categorias", { method: "POST", body: JSON.stringify({ nombre: tipoNuevo.categoria }) });
      setTipoNuevo({ ...tipoNuevo, categoria: "" });
      loadTipos();
    } catch (err) {
      setError(err.message);
    }
  }

  async function crearMarca() {
    if (!tipoNuevo.marca) return;
    setError("");
    try {
      await api("/productos/marcas", { method: "POST", body: JSON.stringify({ nombre: tipoNuevo.marca }) });
      setTipoNuevo({ ...tipoNuevo, marca: "" });
      loadTipos();
    } catch (err) {
      setError(err.message);
    }
  }

  async function crearPresentacion() {
    if (!tipoNuevo.pres.nombre) return;
    setError("");
    try {
      await api("/productos/presentaciones", {
        method: "POST",
        body: JSON.stringify({
          nombre: tipoNuevo.pres.nombre,
          unidad_medida: tipoNuevo.pres.unidad_medida || null,
          cantidad: num(tipoNuevo.pres.cantidad),
        }),
      });
      setTipoNuevo({ ...tipoNuevo, pres: { nombre: "", unidad_medida: "", cantidad: 1 } });
      loadTipos();
    } catch (err) {
      setError(err.message);
    }
  }

  function abrirEtiquetas(ids, gondola = false) {
    if (!ids.length) return;
    setError("");
    openWindow(`/etiquetas/${gondola ? "gondola" : "productos"}?ids=${ids.join(",")}`).catch((e) => setError(e.message));
  }

  async function abrirReceta(p) {
    setError("");
    setRecMsg("");
    try {
      const r = await api(`/productos/${p.id}/receta`);
      setRecetaFor(p);
      setRecetaInfo(r);
      setRecIngs((r.ingredientes || []).map((i) => ({ componente_id: i.componente_id, cantidad: i.cantidad })));
    } catch (err) {
      setError(err.message);
    }
  }

  function setRecIng(i, patch) {
    setRecIngs((prev) => prev.map((row, idx) => (idx === i ? { ...row, ...patch } : row)));
  }

  function addRecIng() {
    setRecIngs((prev) => [...prev, { componente_id: "", cantidad: 1 }]);
  }

  function quitarRecIng(i) {
    setRecIngs((prev) => prev.filter((_, idx) => idx !== i));
  }

  async function guardarReceta() {
    setError("");
    setRecMsg("");
    const val = recIngs
      .filter((r) => r.componente_id)
      .map((r) => ({ componente_id: Number(r.componente_id), cantidad: Number(r.cantidad) || 1 }));
    try {
      await api(`/productos/${recetaFor.id}/receta`, { method: "PUT", body: JSON.stringify({ ingredientes: val }) });
      setRecetaFor(null);
      setRecetaInfo(null);
      load();
    } catch (err) {
      setError(err.message);
    }
  }

  function costoReceta() {
    let total = 0;
    for (const r of recIngs) {
      if (!r.componente_id) continue;
      const prod = productos.find((p) => p.id === Number(r.componente_id));
      total += (Number(prod?.costo) || 0) * (Number(r.cantidad) || 1);
    }
    return total;
  }

  async function costearProducto() {
    setError("");
    setRecMsg("");
    try {
      const r = await api(`/productos/${recetaFor.id}/costear`, { method: "POST" });
      setRecMsg(`✔ Costo aplicado: ${formatMoney(r.costo_calculado)}${r.margen_pct != null ? ` · margen ${r.margen_pct}%` : ""}`);
      const info = await api(`/productos/${recetaFor.id}/receta`);
      setRecetaInfo(info);
      load();
    } catch (err) {
      setError(err.message);
    }
  }

  const campoForm = (key) => (e) => setForm((prev) => ({ ...prev, [key]: e.target.value }));

  return (
    <div className="page">
      <div className="page-header">
        <h1>Productos</h1>
        <button className="btn btn-secondary" onClick={() => setShowTipos(!showTipos)}>{showTipos ? "Cerrar tipologías" : "Tipologías"}</button>
        <button className="btn btn-secondary" onClick={() => downloadCsv("/exportar/productos", "productos").catch((e) => setError(e.message))}>Exportar CSV</button>
        <ImportarCsv path="/importar/productos" etiqueta="Importar CSV" onOk={() => api("/productos").then(setProductos).catch(() => {})} />
        <button className="btn btn-secondary" onClick={() => abrirEtiquetas(productos.map((p) => p.id) || [])}>Etiquetas</button>
        <button className="btn btn-secondary" onClick={() => abrirEtiquetas(productos.map((p) => p.id) || [], true)}>Góndola</button>
        <button className="btn" onClick={() => setShowForm(!showForm)}>
          {showForm ? "Cerrar" : "+ Nuevo producto"}
        </button>
      </div>

      {error && <div className="error">{error}</div>}

      {showTipos && (
        <div className="card" style={{ marginBottom: 20, display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: 16 }}>
          <div>
            <h3 className="card-title">Categorías</h3>
            <div className="muted" style={{ fontSize: 12.5, marginBottom: 8 }}>
              {categorias.map((c) => c.nombre).join(", ") || "Sin categorías"}
            </div>
            <div style={{ display: "flex", gap: 8 }}>
              <input placeholder="Nueva categoría" value={tipoNuevo.categoria} onChange={(e) => setTipoNuevo({ ...tipoNuevo, categoria: e.target.value })} />
              <button className="btn" onClick={crearCategoria}>Crear</button>
            </div>
          </div>
          <div>
            <h3 className="card-title">Marcas</h3>
            <div className="muted" style={{ fontSize: 12.5, marginBottom: 8 }}>
              {marcas.map((m) => m.nombre).join(", ") || "Sin marcas"}
            </div>
            <div style={{ display: "flex", gap: 8 }}>
              <input placeholder="Nueva marca" value={tipoNuevo.marca} onChange={(e) => setTipoNuevo({ ...tipoNuevo, marca: e.target.value })} />
              <button className="btn" onClick={crearMarca}>Crear</button>
            </div>
          </div>
          <div>
            <h3 className="card-title">Presentaciones</h3>
            <div className="muted" style={{ fontSize: 12.5, marginBottom: 8 }}>
              {presentaciones.map((p) => `${p.nombre}${p.unidad_medida ? ` (${p.unidad_medida})` : ""}`).join(", ") || "Sin presentaciones"}
            </div>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              <input placeholder="Nombre" value={tipoNuevo.pres.nombre} onChange={(e) => setTipoNuevo({ ...tipoNuevo, pres: { ...tipoNuevo.pres, nombre: e.target.value } })} />
              <input style={{ width: 90 }} placeholder="Unidad" value={tipoNuevo.pres.unidad_medida} onChange={(e) => setTipoNuevo({ ...tipoNuevo, pres: { ...tipoNuevo.pres, unidad_medida: e.target.value } })} />
              <input style={{ width: 80 }} type="number" placeholder="Cant." value={tipoNuevo.pres.cantidad} onChange={(e) => setTipoNuevo({ ...tipoNuevo, pres: { ...tipoNuevo.pres, cantidad: e.target.value } })} />
              <button className="btn" onClick={crearPresentacion}>Crear</button>
            </div>
          </div>
        </div>
      )}

      {showForm && (
        <form onSubmit={handleCreate} className="card" style={{ marginBottom: 20, display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(180px, 1fr))", gap: 12 }}>
          <div>
            <label>Nombre *</label>
            <input required value={form.nombre} onChange={campoForm("nombre")} />
          </div>
          <div>
            <label>Código de barras</label>
            <input value={form.codigo_barras} onChange={campoForm("codigo_barras")} />
          </div>
          <div>
            <label>SKU</label>
            <input value={form.sku} onChange={campoForm("sku")} />
          </div>
          <div>
            <label>Categoría</label>
            <select value={form.categoria_id} onChange={campoForm("categoria_id")}>
              <option value="">Sin categoría</option>
              {categorias.map((c) => (
                <option key={c.id} value={c.id}>{c.nombre}</option>
              ))}
            </select>
          </div>
          <div>
            <label>Marca</label>
            <select value={form.marca_id} onChange={campoForm("marca_id")}>
              <option value="">Sin marca</option>
              {marcas.map((m) => (
                <option key={m.id} value={m.id}>{m.nombre}</option>
              ))}
            </select>
          </div>
          <div>
            <label>Tipo</label>
            <select value={form.tipo} onChange={campoForm("tipo")}>
              {TIPOS.map((t) => (
                <option key={t} value={t}>{t}</option>
              ))}
            </select>
          </div>
          <div>
            <label>Precio compra</label>
            <input type="number" value={form.precio_compra} onChange={campoForm("precio_compra")} />
          </div>
          <div>
            <label>Precio venta *</label>
            <input required type="number" value={form.precio_venta} onChange={campoForm("precio_venta")} />
          </div>
          <div>
            <label>Mayorista</label>
            <input type="number" value={form.precio_mayorista} onChange={campoForm("precio_mayorista")} />
          </div>
          <div>
            <label>Minorista</label>
            <input type="number" value={form.precio_minorista} onChange={campoForm("precio_minorista")} />
          </div>
          <div>
            <label>Institucional</label>
            <input type="number" value={form.precio_institucional} onChange={campoForm("precio_institucional")} />
          </div>
          <div>
            <label>Costo</label>
            <input type="number" value={form.costo} onChange={campoForm("costo")} />
          </div>
          <div>
            <label>IVA %</label>
            <input type="number" value={form.impuesto} onChange={campoForm("impuesto")} />
          </div>
          <div>
            <label>Margen mín. %</label>
            <input type="number" value={form.margen_minimo} onChange={campoForm("margen_minimo")} />
          </div>
          <div>
            <label>Punto de reorden</label>
            <input type="number" value={form.punto_reorden} onChange={campoForm("punto_reorden")} />
          </div>
          <div>
            <label>Stock mín.</label>
            <input type="number" value={form.stock_minimo} onChange={campoForm("stock_minimo")} />
          </div>
          <div>
            <label>Stock máx.</label>
            <input type="number" value={form.stock_maximo} onChange={campoForm("stock_maximo")} />
          </div>
          <div style={{ display: "flex", gap: 14, flexWrap: "wrap" }}>
            <label className="muted" style={{ fontSize: 12.5 }}><input type="checkbox" checked={form.es_servicio} onChange={(e) => setForm({ ...form, es_servicio: e.target.checked })} /> Servicio</label>
            <label className="muted" style={{ fontSize: 12.5 }}><input type="checkbox" checked={form.maneja_lotes} onChange={(e) => setForm({ ...form, maneja_lotes: e.target.checked })} /> Lotes</label>
            <label className="muted" style={{ fontSize: 12.5 }}><input type="checkbox" checked={form.maneja_serie} onChange={(e) => setForm({ ...form, maneja_serie: e.target.checked })} /> N° serie</label>
            <label className="muted" style={{ fontSize: 12.5 }}><input type="checkbox" checked={form.con_vencimiento} onChange={(e) => setForm({ ...form, con_vencimiento: e.target.checked })} /> Vencimiento</label>
          </div>
          <div style={{ gridColumn: "1 / -1" }}>
            <label>Ficha técnica</label>
            <textarea rows={2} value={form.ficha_tecnica} onChange={campoForm("ficha_tecnica")} placeholder="Especificaciones, materiales, uso..." />
          </div>
          <div style={{ display: "flex", alignItems: "flex-end" }}>
            <button className="btn" type="submit">Guardar</button>
          </div>
        </form>
      )}

      <input
        placeholder="Buscar por nombre, código, SKU..."
        value={q}
        onChange={(e) => setQ(e.target.value)}
        style={{ maxWidth: 400, marginBottom: 16 }}
      />

      <table className="table">
        <thead>
          <tr>
            <th>Código</th>
            <th>Nombre</th>
            <th>Precio venta</th>
            <th>Costo</th>
            <th>Stock mín.</th>
            <th>Estado</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {productos.map((p) => (
            <tr key={p.id}>
              <td>{p.codigo_barras || p.sku || "—"}</td>
              <td>
                {p.es_compuesto && <span className="badge" title="Combo / kit (producto compuesto)">🧩 Combo</span>}{" "}
                {p.tipo !== "unidad" && <span className="badge">{p.tipo}</span>}{" "}
                {p.maneja_serie && <span className="badge badge-info" title="Controla números de serie">#</span>}{" "}
                {p.nombre}
              </td>
              <td>{formatMoney(p.precio_venta)}</td>
              <td>{formatMoney(p.costo)}</td>
              <td>{p.stock_minimo}</td>
              <td>
                <span className={`badge ${p.activo ? "badge-success" : "badge-danger"}`}>
                  {p.activo ? "Activo" : "Inactivo"}
                </span>
              </td>
              <td>
                <button className="btn btn-ghost" onClick={() => abrirDetalle(p)} title="Detalle / precios / competencia">👁</button>
                <button className="btn btn-ghost" onClick={() => abrirEdicion(p)} title="Editar">✏️</button>
                <button className="btn btn-ghost" onClick={() => openWindow(`/productos/${p.id}/codigo-barras`).catch((e) => setError(e.message))} title="Código de barras">▓▓</button>
                <button className="btn btn-ghost" onClick={() => abrirReceta(p)} title="Receta / ingredientes">🧩</button>
                <button className="btn btn-ghost" onClick={() => abrirEtiquetas([p.id])} title="Imprimir etiqueta">🏷️</button>
              </td>
            </tr>
          ))}
          {productos.length === 0 && (
            <tr><td colSpan={7} className="muted" style={{ textAlign: "center", padding: 20 }}>Sin productos</td></tr>
          )}
        </tbody>
      </table>

      {editando && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,.45)", display: "grid", placeItems: "center", zIndex: 1100, padding: 20 }}>
          <form onSubmit={guardarEdicion} className="card" style={{ width: "min(760px, 100%)", maxHeight: "86vh", overflow: "auto", display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(170px, 1fr))", gap: 12 }}>
            <div style={{ gridColumn: "1 / -1", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <h2 style={{ fontSize: 17 }}>Editar · #{editando.id} {editando.nombre}</h2>
              <button type="button" className="btn btn-ghost" onClick={() => setEditando(null)}>✕</button>
            </div>
            <div><label>Nombre</label><input value={editando.nombre} onChange={(e) => setEditandoCampo("nombre", e.target.value)} /></div>
            <div><label>Código de barras</label><input value={editando.codigo_barras || ""} onChange={(e) => setEditandoCampo("codigo_barras", e.target.value)} /></div>
            <div><label>SKU</label><input value={editando.sku || ""} onChange={(e) => setEditandoCampo("sku", e.target.value)} /></div>
            <div>
              <label>Categoría</label>
              <select value={editando.categoria_id || ""} onChange={(e) => setEditandoCampo("categoria_id", e.target.value)}>
                <option value="">Sin categoría</option>
                {categorias.map((c) => <option key={c.id} value={c.id}>{c.nombre}</option>)}
              </select>
            </div>
            <div>
              <label>Tipo</label>
              <select value={editando.tipo} onChange={(e) => setEditandoCampo("tipo", e.target.value)}>
                {TIPOS.map((t) => <option key={t} value={t}>{t}</option>)}
              </select>
            </div>
            <div><label>Precio venta</label><input type="number" value={editando.precio_venta} onChange={(e) => setEditandoCampo("precio_venta", e.target.value)} /></div>
            <div><label>Precio mayorista</label><input type="number" value={editando.precio_mayorista || ""} onChange={(e) => setEditandoCampo("precio_mayorista", e.target.value)} /></div>
            <div><label>Precio minorista</label><input type="number" value={editando.precio_minorista || ""} onChange={(e) => setEditandoCampo("precio_minorista", e.target.value)} /></div>
            <div><label>Precio institucional</label><input type="number" value={editando.precio_institucional || ""} onChange={(e) => setEditandoCampo("precio_institucional", e.target.value)} /></div>
            <div><label>Costo</label><input type="number" value={editando.costo || ""} onChange={(e) => setEditandoCampo("costo", e.target.value)} /></div>
            <div><label>IVA %</label><input type="number" value={editando.impuesto || ""} onChange={(e) => setEditandoCampo("impuesto", e.target.value)} /></div>
            <div><label>Margen mín. %</label><input type="number" value={editando.margen_minimo || ""} onChange={(e) => setEditandoCampo("margen_minimo", e.target.value)} /></div>
            <div><label>Punto reorden</label><input type="number" value={editando.punto_reorden || ""} onChange={(e) => setEditandoCampo("punto_reorden", e.target.value)} /></div>
            <div><label>Stock mín.</label><input type="number" value={editando.stock_minimo || ""} onChange={(e) => setEditandoCampo("stock_minimo", e.target.value)} /></div>
            <div><label>Stock máx.</label><input type="number" value={editando.stock_maximo || ""} onChange={(e) => setEditandoCampo("stock_maximo", e.target.value)} /></div>
            <div style={{ display: "flex", gap: 14, flexWrap: "wrap" }}>
              <label className="muted" style={{ fontSize: 12.5 }}><input type="checkbox" checked={!!editando.es_servicio} onChange={(e) => setEditandoCampo("es_servicio", e.target.checked)} /> Servicio</label>
              <label className="muted" style={{ fontSize: 12.5 }}><input type="checkbox" checked={!!editando.maneja_lotes} onChange={(e) => setEditandoCampo("maneja_lotes", e.target.checked)} /> Lotes</label>
              <label className="muted" style={{ fontSize: 12.5 }}><input type="checkbox" checked={!!editando.maneja_serie} onChange={(e) => setEditandoCampo("maneja_serie", e.target.checked)} /> N° serie</label>
              <label className="muted" style={{ fontSize: 12.5 }}><input type="checkbox" checked={!!editando.con_vencimiento} onChange={(e) => setEditandoCampo("con_vencimiento", e.target.checked)} /> Vencimiento</label>
              <label className="muted" style={{ fontSize: 12.5 }}><input type="checkbox" checked={!!editando.activo} onChange={(e) => setEditandoCampo("activo", e.target.checked)} /> Activo</label>
            </div>
            <div style={{ gridColumn: "1 / -1" }}>
              <label>Ficha técnica</label>
              <textarea rows={2} value={editando.ficha_tecnica || ""} onChange={(e) => setEditandoCampo("ficha_tecnica", e.target.value)} />
            </div>
            <div style={{ gridColumn: "1 / -1", display: "flex", gap: 8, justifyContent: "flex-end" }}>
              <button type="button" className="btn btn-secondary" onClick={() => setEditando(null)}>Cancelar</button>
              <button type="submit" className="btn">Guardar cambios</button>
            </div>
          </form>
        </div>
      )}

      {detalle && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,.45)", display: "grid", placeItems: "center", zIndex: 1150, padding: 20 }}>
          <div className="card" style={{ width: "min(860px, 100%)", maxHeight: "88vh", overflow: "auto" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
              <h2 style={{ fontSize: 18 }}>{detalle.nombre} <span className="muted" style={{ fontSize: 13 }}>#{detalle.id}</span></h2>
              <button className="btn btn-ghost" onClick={() => setDetalle(null)}>✕</button>
            </div>
            <div className="muted" style={{ fontSize: 13, marginBottom: 14 }}>
              {detalle.tipo} · SKU {detalle.sku || "—"} · Código {detalle.codigo_barras || "—"} ·{" "}
              {detalle.maneja_serie ? "N° de serie: sí" : "N° de serie: no"} · {detalle.maneja_lotes ? "Maneja lotes" : ""} {detalle.con_vencimiento ? "· con vencimiento" : ""}
            </div>
            {detalle.ficha_tecnica && (
              <div className="card sec" style={{ marginBottom: 14, padding: 12 }}>
                <h3 className="card-title">Ficha técnica</h3>
                <p style={{ whiteSpace: "pre-wrap" }}>{detalle.ficha_tecnica}</p>
              </div>
            )}

            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(170px, 1fr))", gap: 12, marginBottom: 18 }}>
              <div className="card sec"><b>Precio venta</b><div>{formatMoney(detalle.precio_venta)}</div></div>
              <div className="card sec"><b>Mayorista</b><div>{formatMoney(detalle.precio_mayorista)}</div></div>
              <div className="card sec"><b>Minorista</b><div>{formatMoney(detalle.precio_minorista)}</div></div>
              <div className="card sec"><b>Institucional</b><div>{formatMoney(detalle.precio_institucional)}</div></div>
              <div className="card sec"><b>Costo</b><div>{formatMoney(detalle.costo)}</div></div>
              <div className="card sec"><b>IVA</b><div>{detalle.impuesto || 0}%</div></div>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 18 }}>
              <div>
                <h3 className="card-title">Precios de competencia</h3>
                <div style={{ display: "flex", gap: 8, marginBottom: 10 }}>
                  <input style={{ flex: 1 }} placeholder="Competidor" value={comp.competidor} onChange={(e) => setComp({ ...comp, competidor: e.target.value })} />
                  <input style={{ width: 90 }} type="number" placeholder="Precio" value={comp.precio} onChange={(e) => setComp({ ...comp, precio: e.target.value })} />
                  <button className="btn" onClick={agregarCompetencia}>+</button>
                </div>
                {competencia.length === 0 && <p className="muted" style={{ fontSize: 13 }}>Sin registros.</p>}
                <table className="table">
                  <tbody>
                    {competencia.map((c) => (
                      <tr key={c.id}>
                        <td><strong>{c.competidor}</strong><div className="muted" style={{ fontSize: 12 }}>{c.fecha}</div></td>
                        <td style={{ textAlign: "right" }}>{formatMoney(c.precio)}</td>
                        <td><button className="btn btn-ghost" style={{ color: "#dc2626" }} onClick={() => eliminarCompetencia(c.id)}>✕</button></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div>
                <h3 className="card-title">Historial de precios</h3>
                {historial.length === 0 && <p className="muted" style={{ fontSize: 13 }}>Sin cambios registrados.</p>}
                <table className="table">
                  <thead><tr><th>Campo</th><th>Anterior</th><th>Nuevo</th></tr></thead>
                  <tbody>
                    {historial.map((h) => (
                      <tr key={h.id}>
                        <td className="muted">{h.campo}</td>
                        <td>{formatMoney(h.valor_anterior)}</td>
                        <td><strong>{formatMoney(h.valor_nuevo)}</strong></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </div>
      )}

      {recetaFor && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,.45)", display: "grid", placeItems: "center", zIndex: 1200, padding: 20 }}>
          <div className="card" style={{ width: "min(680px, 100%)", maxHeight: "86vh", overflow: "auto" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
              <h2 style={{ fontSize: 17 }}>Receta · {recetaFor.nombre}</h2>
              <button className="btn btn-ghost" onClick={() => setRecetaFor(null)}>✕</button>
            </div>
            <p className="muted" style={{ fontSize: 13, marginBottom: 14 }}>
              Ingredientes del combo/kit. El costo del producto se calcula automáticamente (Σ costo × cantidad).
              {recetaInfo?.costo_calculado > 0 && recetaInfo?.costo !== recetaInfo?.costo_calculado && (
                <> Costo actual <b>{formatMoney(recetaInfo.costo)}</b>, costeo pendiente: <b>{formatMoney(recetaInfo.costo_calculado)}</b>.</>
              )}
            </p>

            <div style={{ display: "grid", gap: 8, marginBottom: 12 }}>
              {recIngs.map((r, i) => (
                <div key={i} style={{ display: "grid", gridTemplateColumns: "1fr 90px 32px", gap: 8 }}>
                  <select value={r.componente_id} onChange={(e) => setRecIng(i, { componente_id: e.target.value })}>
                    <option value="">Seleccionar ingrediente...</option>
                    {productos
                      .filter((p) => p.id !== recetaFor.id)
                      .map((p) => (
                        <option key={p.id} value={p.id}>{p.nombre} ({formatMoney(p.costo)})</option>
                      ))}
                  </select>
                  <input type="number" min="0.01" step="any" value={r.cantidad} onChange={(e) => setRecIng(i, { cantidad: e.target.value })} title="Cantidad de la receta" />
                  <button className="btn btn-ghost" style={{ color: "#dc2626" }} onClick={() => quitarRecIng(i)}>✕</button>
                </div>
              ))}
              {recIngs.length === 0 && <p className="muted" style={{ fontSize: 13 }}>Sin ingredientes: el producto quedará como venta normal.</p>}
            </div>

            <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
              <button className="btn btn-secondary" onClick={addRecIng}>+ Agregar ingrediente</button>
              {recIngs.some((r) => r.componente_id) && (
                <span className="chip">Costo calculado: <b>{formatMoney(costoReceta())}</b></span>
              )}
              <div style={{ marginLeft: "auto", display: "flex", gap: 8 }}>
                <button className="btn btn-secondary" onClick={() => setRecetaFor(null)}>Cancelar</button>
                <button className="btn btn-secondary" onClick={costearProducto}>Costear ahora</button>
                <button className="btn" onClick={guardarReceta}>Guardar receta</button>
              </div>
            </div>
            {recMsg && <div className="chip" style={{ marginTop: 10 }}>{recMsg}</div>}
          </div>
        </div>
      )}
    </div>
  );
}