import { useEffect, useMemo, useState } from "react";
import api from "../api.js";

const fmt = (n) => `$${Number(n || 0).toLocaleString("es-CO")}`;

export default function Menu() {
  const [productos, setProductos] = useState([]);
  const [categoriasRaw, setCategoriasRaw] = useState([]);
  const [mesas, setMesas] = useState([]);
  const [carrito, setCarrito] = useState([]);
  const [mesaId, setMesaId] = useState("");
  const [error, setError] = useState("");
  const [msg, setMsg] = useState("");
  const [busqueda, setBusqueda] = useState("");
  const [catActiva, setCatActiva] = useState("__todas");

  useEffect(() => {
    api("/productos?limite=500").then(setProductos).catch((e) => setError(e.message));
    api("/productos/categorias").then(setCategoriasRaw).catch(() => {});
    api("/restaurante/mesas").then(setMesas).catch(() => {});
  }, []);

  const nombreCat = (id) => (id ? categoriasRaw.find((c) => c.id === id)?.nombre : null);

  const categorias = useMemo(() => {
    const map = new Map();
    productos
      .filter((p) => p.activo !== false)
      .forEach((p) => {
        const cat = nombreCat(p.categoria_id) || "Otros";
        if (!map.has(cat)) map.set(cat, []);
        map.get(cat).push(p);
      });
    return Array.from(map.entries()).sort((a, b) => a[0].localeCompare(b[0]));
  }, [productos, categoriasRaw]);

  const filtrados = useMemo(() => {
    const res = [];
    categorias.forEach(([cat, items]) => {
      if (catActiva !== "__todas" && cat !== catActiva) return;
      const f = busqueda
        ? items.filter(
            (p) =>
              p.nombre.toLowerCase().includes(busqueda.toLowerCase()) ||
              String(p.id).includes(busqueda)
          )
        : items;
      if (f.length > 0) res.push([cat, f]);
    });
    return res;
  }, [categorias, busqueda, catActiva]);

  const total = carrito.reduce((s, l) => s + Number(l.precio || 0) * l.cantidad, 0);
  const contar = carrito.reduce((s, l) => s + l.cantidad, 0);

  function agregar(p) {
    setError("");
    setCarrito((prev) => {
      const ex = prev.find((l) => l.producto_id === p.id);
      if (ex) return prev.map((l) => (l.producto_id === p.id ? { ...l, cantidad: l.cantidad + 1 } : l));
      return [...prev, { producto_id: p.id, nombre: p.nombre, precio: Number(p.precio_venta || 0), cantidad: 1, preparacion: "" }];
    });
  }

  function cambiar(idx, campo, valor) {
    setCarrito((prev) => prev.map((l, i) => (i === idx ? { ...l, [campo]: campo === "cantidad" ? Math.max(0, Number(valor)) : valor } : l)));
  }

  function quitar(idx) {
    setCarrito((prev) => prev.filter((_, i) => i !== idx));
  }

  async function enviarComanda(e) {
    e.preventDefault();
    setError("");
    setMsg("");
    if (!mesaId) {
      setError("Seleccione la mesa");
      return;
    }
    if (carrito.length === 0) {
      setError("La comanda está vacía");
      return;
    }
    try {
      const detalle = carrito
        .filter((l) => l.cantidad > 0)
        .map((l) => ({
          producto_id: l.producto_id,
          cantidad: l.cantidad,
          precio: l.precio,
          preparacion: l.preparacion || null,
        }));
      const r = await api("/restaurante/comandas", {
        method: "POST",
        body: JSON.stringify({ mesa_id: Number(mesaId), detalle }),
      });
      setMsg(`Comanda ${r.numero} abierta en la mesa seleccionada · ${fmt(r.total || total)}`);
      setCarrito([]);
      setMesaId("");
    } catch (err) {
      setError(err.message);
    }
  }

  const mesasDisponibles = mesas.filter((m) => m.estado === "disponible" || m.estado === "ocupada");

  return (
    <div className="page">
      <div className="hero" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 16, flexWrap: "wrap" }}>
        <div>
          <h1>Menú (Carta)</h1>
          <p>Carta visual por categorías · las comandas se reflejan en Restaurante y Cocina.</p>
        </div>
        <form onSubmit={enviarComanda} style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
          <select required value={mesaId} onChange={(e) => setMesaId(e.target.value)} className="btn">
            <option value="">Mesa…</option>
            {mesasDisponibles.map((m) => (
              <option key={m.id} value={m.id}>
                {m.nombre} ({m.estado})
              </option>
            ))}
          </select>
          <button className="btn btn-primary" style={{ fontWeight: 800 }}>
            🧾 Abrir comanda ({contar}) · {fmt(total)}
          </button>
        </form>
      </div>

      <div style={{ display: "flex", gap: 10, marginBottom: 14, alignItems: "center", flexWrap: "wrap" }}>
        <input
          placeholder="Buscar producto…"
          value={busqueda}
          onChange={(e) => setBusqueda(e.target.value)}
          style={{ flex: 1, minWidth: 200 }}
        />
        <button className={`btn ${catActiva === "__todas" ? "btn-primary" : ""}`} onClick={() => setCatActiva("__todas")}>
          Todas
        </button>
        {categorias.map(([cat, items]) => (
          <button key={cat} className={`btn ${catActiva === cat ? "btn-primary" : ""}`} onClick={() => setCatActiva(cat)}>
            {cat} ({items.length})
          </button>
        ))}
      </div>

      {msg && <div className="badge-success" style={{ display: "inline-block", marginBottom: 8, padding: "6px 10px", borderRadius: 6 }}>{msg}</div>}
      {error && <div className="error">{error}</div>}

      {filtrados.length === 0 && (
        <div className="card" style={{ padding: 30, textAlign: "center", color: "var(--muted)" }}>Sin productos que coincidan.</div>
      )}

      {filtrados.map(([cat, items]) => (
        <section key={cat} style={{ marginBottom: 22 }}>
          <h2 style={{ fontSize: 17, marginBottom: 8, paddingBottom: 6, borderBottom: "2px solid var(--brand1)" }}>{cat}</h2>
          <div style={{ display: "grid", gap: 12, gridTemplateColumns: "repeat(auto-fill,minmax(170px,1fr))" }}>
            {items.map((p) => (
              <button
                key={p.id}
                className="card"
                onClick={() => agregar(p)}
                style={{
                  cursor: "pointer",
                  textAlign: "left",
                  display: "flex",
                  flexDirection: "column",
                  gap: 6,
                  padding: 14,
                  border: carrito.some((l) => l.producto_id === p.id) ? "2px solid var(--brand1)" : "1px solid var(--line)",
                }}
              >
                <div
                  style={{
                    height: 74,
                    borderRadius: 8,
                    background: "linear-gradient(135deg, var(--surface,#f5f7fa), var(--card))",
                    display: "grid",
                    placeItems: "center",
                    fontSize: 22,
                  }}
                >
                  🍽️
                </div>
                <div style={{ fontWeight: 700, fontSize: 13.5, lineHeight: 1.25, minHeight: 34 }}>{p.nombre}</div>
                <div style={{ fontSize: 13, color: "var(--muted)" }}>#{p.id}</div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <b style={{ color: "var(--brand1)", fontSize: 15 }}>{fmt(p.precio_venta)}</b>
                  {carrito.some((l) => l.producto_id === p.id) && <span className="badge-success">✓</span>}
                </div>
              </button>
            ))}
          </div>
        </section>
      ))}

      {carrito.length > 0 && (
        <div className="card" style={{ padding: 16, marginTop: 6 }}>
          <h3 style={{ fontSize: 16, marginBottom: 10 }}>
            Pedido actual · Mesa: {mesas.find((m) => String(m.id) === String(mesaId))?.nombre || (mesaId ? `#${mesaId}` : "sin seleccionar")}
          </h3>
          <table className="table">
            <thead>
              <tr>
                <th>Producto</th>
                <th>Cantidad</th>
                <th>P/U</th>
                <th>Preparación</th>
                <th>Subtotal</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {carrito.map((l, i) => (
                <tr key={l.producto_id}>
                  <td>
                    <b>{l.nombre}</b>
                    <div style={{ fontSize: 11, color: "var(--muted)" }}>#{l.producto_id}</div>
                  </td>
                  <td>
                    <button className="btn btn-sm" type="button" onClick={() => cambiar(i, "cantidad", l.cantidad - 1)}>−</button>
                    <span style={{ margin: "0 8px", fontWeight: 700 }}>{l.cantidad}</span>
                    <button className="btn btn-sm" type="button" onClick={() => cambiar(i, "cantidad", l.cantidad + 1)}>+</button>
                  </td>
                  <td>{fmt(l.precio)}</td>
                  <td>
                    <input
                      placeholder="crudo, sin sal…"
                      value={l.preparacion}
                      onChange={(e) => cambiar(i, "preparacion", e.target.value)}
                      style={{ width: 130 }}
                    />
                  </td>
                  <td>
                    <b>{fmt(l.precio * l.cantidad)}</b>
                  </td>
                  <td>
                    <button className="btn btn-sm" type="button" onClick={() => quitar(i)}>✕</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 12 }}>
            <b>Total: {fmt(total)}</b>
            <button className="btn btn-primary" onClick={enviarComanda}>
              Enviar a cocina ({contar} ítems)
            </button>
          </div>
        </div>
      )}
    </div>
  );
}