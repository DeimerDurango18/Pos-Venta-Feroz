import { useEffect, useMemo, useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import api from "../api.js";

const fmt = (n) => `$${Number(n || 0).toLocaleString("es-CO")}`;

export default function MenuPublico() {
  const params = useParams();
  const [searchParams] = useSearchParams();

  // Mesa ID can come from route params (:mesaId) or query param (?mesa=...)
  const initialMesaId = params.mesaId || searchParams.get("mesa") || "";

  const [mesaId, setMesaId] = useState(initialMesaId);
  const [mesas, setMesas] = useState([]);
  const [negocio, setNegocio] = useState({ nombre: "Restaurante", direccion: "", telefono: "" });
  const [categorias, setCategorias] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState("");
  const [busqueda, setBusqueda] = useState("");
  const [catActiva, setCatActiva] = useState("__todas");

  // Carrito de pedidos
  const [carrito, setCarrito] = useState([]);
  const [itemModal, setItemModal] = useState(null);
  const [itemCant, setItemCant] = useState(1);
  const [itemPrep, setItemPrep] = useState("");

  // Drawer y confirmación
  const [drawerAbierto, setDrawerAbierto] = useState(false);
  const [clienteNombre, setClienteNombre] = useState("");
  const [clienteTel, setClienteTel] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [pedidoExitoso, setPedidoExitoso] = useState(null);

  // Cargar datos del menú público
  useEffect(() => {
    setCargando(true);
    api("/publico/carta/datos")
      .then((data) => {
        if (data.negocio) setNegocio(data.negocio);
        if (Array.isArray(data.categorias)) setCategorias(data.categorias);
        if (Array.isArray(data.mesas)) setMesas(data.mesas);
      })
      .catch((err) => {
        if (mesaId) {
          api(`/publico/menu/${mesaId}/datos`)
            .then((d) => {
              if (d.negocio) setNegocio(d.negocio);
              if (Array.isArray(d.categorias)) setCategorias(d.categorias);
            })
            .catch((e) => setError(e.message));
        } else {
          setError(err.message);
        }
      })
      .finally(() => setCargando(false));
  }, [mesaId]);

  // Lista aplanada de productos filtrados
  const categoriasFiltradas = useMemo(() => {
    const term = busqueda.trim().toLowerCase();
    return categorias
      .map((cat) => {
        const prods = (cat.productos || []).filter((p) => {
          const coincideBusqueda =
            !term ||
            p.nombre.toLowerCase().includes(term) ||
            (p.descripcion && p.descripcion.toLowerCase().includes(term));
          return coincideBusqueda;
        });
        return { ...cat, productos: prods };
      })
      .filter((cat) => cat.productos.length > 0);
  }, [categorias, busqueda]);

  // Totales del pedido
  const totalPedido = useMemo(() => {
    return carrito.reduce((acc, l) => acc + l.precio * l.cantidad, 0);
  }, [carrito]);

  const totalItems = useMemo(() => {
    return carrito.reduce((acc, l) => acc + l.cantidad, 0);
  }, [carrito]);

  // Abrir modal de personalización
  function abrirPersonalizar(producto) {
    setItemModal(producto);
    setItemCant(1);
    setItemPrep("");
  }

  // Agregar al carrito con notas
  function agregarAlCarrito() {
    if (!itemModal) return;
    setCarrito((prev) => {
      const idx = prev.findIndex(
        (l) => l.producto_id === itemModal.id && (l.preparacion || "") === itemPrep.trim()
      );
      if (idx >= 0) {
        const copia = [...prev];
        copia[idx].cantidad += itemCant;
        return copia;
      }
      return [
        ...prev,
        {
          producto_id: itemModal.id,
          nombre: itemModal.nombre,
          precio: Number(itemModal.precio || itemModal.precio_final || 0),
          cantidad: itemCant,
          preparacion: itemPrep.trim(),
          imagen: itemModal.imagen,
        },
      ];
    });
    setItemModal(null);
  }

  // Modificar cantidad en carrito
  function cambiarCantidad(index, delta) {
    setCarrito((prev) => {
      const copia = [...prev];
      const nueva = copia[index].cantidad + delta;
      if (nueva <= 0) {
        return copia.filter((_, i) => i !== index);
      }
      copia[index].cantidad = nueva;
      return copia;
    });
  }

  // Enviar comanda/pedido a cocina
  async function enviarPedido(e) {
    if (e) e.preventDefault();
    if (!mesaId) {
      alert("Por favor selecciona tu número de mesa para llevar el pedido.");
      return;
    }
    if (carrito.length === 0) {
      alert("El carrito está vacío.");
      return;
    }

    setEnviando(true);
    setError("");

    try {
      const payload = {
        llave: "publico",
        mesa_id: Number(mesaId),
        cliente: clienteNombre.trim(),
        telefono: clienteTel.trim(),
        items: carrito.map((c) => ({
          producto_id: c.producto_id,
          cantidad: c.cantidad,
          preparacion: c.preparacion || null,
        })),
      };

      const res = await api("/publico/pedido", {
        method: "POST",
        body: JSON.stringify(payload),
      });

      setPedidoExitoso({
        comanda: res.numero,
        mesa: res.mesa || `Mesa #${mesaId}`,
        total: res.total || totalPedido,
        itemsCount: totalItems,
      });

      setCarrito([]);
      setDrawerAbierto(false);
    } catch (err) {
      setError("No se pudo enviar el pedido: " + err.message);
    } finally {
      setEnviando(false);
    }
  }

  const mesaActualObj = mesas.find((m) => String(m.id) === String(mesaId));

  return (
    <div className="carta-publica">
      <style>{`
        .carta-publica {
          min-height: 100vh;
          background: #090d16;
          color: #f1f5f9;
          font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
          padding-bottom: 110px;
        }
        .carta-header {
          position: sticky;
          top: 0;
          z-index: 40;
          background: rgba(9, 13, 22, 0.94);
          backdrop-filter: blur(12px);
          border-bottom: 1px solid rgba(255, 255, 255, 0.08);
          padding: 12px 18px;
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 12px;
        }
        .carta-brand {
          display: flex;
          align-items: center;
          gap: 10px;
        }
        .carta-logo {
          width: 38px;
          height: 38px;
          border-radius: 10px;
          background: linear-gradient(135deg, #e11d48, #f43f5e);
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 20px;
          box-shadow: 0 4px 14px rgba(225, 29, 72, 0.35);
        }
        .carta-title h1 {
          font-size: 16px;
          font-weight: 800;
          margin: 0;
          letter-spacing: -0.2px;
          color: #fff;
        }
        .carta-title p {
          margin: 0;
          font-size: 11.5px;
          color: #94a3b8;
        }
        .carta-mesa-tag {
          background: rgba(225, 29, 72, 0.15);
          border: 1px solid rgba(225, 29, 72, 0.35);
          color: #f43f5e;
          padding: 6px 12px;
          border-radius: 20px;
          font-size: 12px;
          font-weight: 700;
          cursor: pointer;
          display: flex;
          align-items: center;
          gap: 6px;
        }
        .carta-search-wrap {
          padding: 14px 18px 6px;
        }
        .carta-search {
          width: 100%;
          background: #131b2e;
          border: 1px solid rgba(255, 255, 255, 0.1);
          color: #fff;
          border-radius: 12px;
          padding: 12px 16px;
          font-size: 14px;
          outline: none;
          transition: border-color 0.2s;
        }
        .carta-search:focus {
          border-color: #f43f5e;
        }
        .carta-tabs {
          display: flex;
          gap: 8px;
          overflow-x: auto;
          padding: 8px 18px 14px;
          scrollbar-width: none;
        }
        .carta-tabs::-webkit-scrollbar {
          display: none;
        }
        .carta-tab {
          white-space: nowrap;
          background: #131b2e;
          border: 1px solid rgba(255, 255, 255, 0.08);
          color: #cbd5e1;
          padding: 8px 15px;
          border-radius: 20px;
          font-size: 13px;
          font-weight: 600;
          cursor: pointer;
          transition: all 0.2s;
        }
        .carta-tab.activa {
          background: #e11d48;
          color: #fff;
          border-color: #e11d48;
          box-shadow: 0 4px 12px rgba(225, 29, 72, 0.3);
        }
        .carta-section {
          padding: 0 18px 24px;
        }
        .carta-section-title {
          font-size: 17px;
          font-weight: 800;
          color: #f8fafc;
          margin-bottom: 14px;
          display: flex;
          align-items: center;
          gap: 8px;
        }
        .carta-grid {
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
          gap: 14px;
        }
        .dish-card {
          background: #131b2e;
          border: 1px solid rgba(255, 255, 255, 0.07);
          border-radius: 16px;
          padding: 14px;
          display: flex;
          gap: 14px;
          cursor: pointer;
          transition: transform 0.15s, border-color 0.15s;
          position: relative;
        }
        .dish-card:hover {
          border-color: rgba(225, 29, 72, 0.4);
          transform: translateY(-2px);
        }
        .dish-info {
          flex: 1;
          display: flex;
          flex-direction: column;
        }
        .dish-name {
          font-size: 15px;
          font-weight: 700;
          color: #fff;
          margin-bottom: 4px;
        }
        .dish-desc {
          font-size: 12.5px;
          color: #94a3b8;
          line-height: 1.4;
          margin-bottom: 8px;
          display: -webkit-box;
          -webkit-line-clamp: 2;
          -webkit-box-orient: vertical;
          overflow: hidden;
        }
        .dish-footer {
          margin-top: auto;
          display: flex;
          align-items: center;
          justify-content: space-between;
        }
        .dish-price {
          font-size: 15px;
          font-weight: 800;
          color: #f43f5e;
        }
        .dish-add-btn {
          background: rgba(225, 29, 72, 0.15);
          color: #f43f5e;
          border: 1px solid rgba(225, 29, 72, 0.35);
          padding: 6px 14px;
          border-radius: 10px;
          font-size: 12.5px;
          font-weight: 700;
          cursor: pointer;
          transition: all 0.2s;
        }
        .dish-add-btn:hover {
          background: #e11d48;
          color: #fff;
        }
        .dish-img {
          width: 82px;
          height: 82px;
          border-radius: 12px;
          background: #0b1120;
          object-fit: cover;
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 32px;
          flex-shrink: 0;
        }
        .carta-floating-bar {
          position: fixed;
          bottom: 20px;
          left: 18px;
          right: 18px;
          max-width: 500px;
          margin: 0 auto;
          z-index: 50;
          background: linear-gradient(135deg, #e11d48, #be123c);
          color: #fff;
          border-radius: 16px;
          padding: 14px 20px;
          display: flex;
          align-items: center;
          justify-content: space-between;
          box-shadow: 0 10px 25px rgba(225, 29, 72, 0.45);
          cursor: pointer;
          animation: slideUp 0.3s ease;
        }
        @keyframes slideUp {
          from { transform: translateY(100%); opacity: 0; }
          to { transform: translateY(0); opacity: 1; }
        }
        .floating-count {
          background: rgba(0, 0, 0, 0.25);
          padding: 4px 10px;
          border-radius: 20px;
          font-size: 13px;
          font-weight: 800;
        }
        .floating-action {
          font-weight: 800;
          font-size: 15px;
          display: flex;
          align-items: center;
          gap: 6px;
        }
        .modal-overlay {
          position: fixed;
          inset: 0;
          z-index: 100;
          background: rgba(0, 0, 0, 0.75);
          backdrop-filter: blur(5px);
          display: flex;
          align-items: flex-end;
          justify-content: center;
        }
        @media (min-width: 600px) {
          .modal-overlay {
            align-items: center;
            padding: 20px;
          }
        }
        .modal-card {
          width: 100%;
          max-width: 480px;
          background: #111a2e;
          border-radius: 24px 24px 0 0;
          padding: 24px;
          border: 1px solid rgba(255, 255, 255, 0.1);
          max-height: 90vh;
          overflow-y: auto;
        }
        @media (min-width: 600px) {
          .modal-card {
            border-radius: 20px;
          }
        }
        .prep-tag {
          background: #1b263e;
          border: 1px solid rgba(255, 255, 255, 0.1);
          color: #cbd5e1;
          padding: 6px 12px;
          border-radius: 12px;
          font-size: 12px;
          cursor: pointer;
          margin-right: 6px;
          margin-bottom: 6px;
          display: inline-block;
        }
        .prep-tag:hover {
          border-color: #f43f5e;
          color: #fff;
        }
        .qty-control {
          display: flex;
          align-items: center;
          gap: 14px;
          background: #0b1120;
          padding: 6px 14px;
          border-radius: 12px;
        }
        .qty-btn {
          width: 32px;
          height: 32px;
          border-radius: 8px;
          background: #1e293b;
          border: none;
          color: #fff;
          font-size: 18px;
          font-weight: 700;
          cursor: pointer;
        }
      `}</style>

      {/* Cabecera del Menú */}
      <header className="carta-header">
        <div className="carta-brand">
          <div className="carta-logo">🍽️</div>
          <div className="carta-title">
            <h1>{negocio.nombre || "Carta Digital"}</h1>
            <p>{negocio.direccion || "Pide directo a cocina desde tu mesa"}</p>
          </div>
        </div>

        {/* Selector de Mesa */}
        <div>
          {mesaActualObj ? (
            <div className="carta-mesa-tag" onClick={() => setMesaId("")}>
              <span>📍 {mesaActualObj.nombre}</span>
              <span style={{ fontSize: 10, opacity: 0.7 }}>Cambiar</span>
            </div>
          ) : (
            <select
              value={mesaId}
              onChange={(e) => setMesaId(e.target.value)}
              style={{
                background: "#1e293b",
                color: "#fff",
                border: "1px solid #334155",
                borderRadius: 10,
                padding: "6px 10px",
                fontSize: 12,
              }}
            >
              <option value="">Selecciona mesa…</option>
              {mesas.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.nombre} ({m.salon || "General"})
                </option>
              ))}
            </select>
          )}
        </div>
      </header>

      {/* Buscador */}
      <div className="carta-search-wrap">
        <input
          type="text"
          className="carta-search"
          placeholder="🔍 Buscar plato, bebida o postre…"
          value={busqueda}
          onChange={(e) => setBusqueda(e.target.value)}
        />
      </div>

      {/* Categorías en chips */}
      <div className="carta-tabs">
        <button
          className={`carta-tab ${catActiva === "__todas" ? "activa" : ""}`}
          onClick={() => setCatActiva("__todas")}
        >
          🌟 Todos
        </button>
        {categorias.map((c) => (
          <button
            key={c.id}
            className={`carta-tab ${catActiva === String(c.id) ? "activa" : ""}`}
            onClick={() => setCatActiva(String(c.id))}
          >
            {c.nombre} ({c.productos ? c.productos.length : 0})
          </button>
        ))}
      </div>

      {/* Mensaje de error si ocurre */}
      {error && (
        <div style={{ margin: "10px 18px", padding: 12, background: "rgba(225,29,72,0.2)", border: "1px solid #e11d48", borderRadius: 12, color: "#fecdd3", fontSize: 13 }}>
          {error}
        </div>
      )}

      {/* Catálogo de Productos por Categoría */}
      {cargando ? (
        <div style={{ padding: 40, textAlign: "center", color: "#94a3b8" }}>
          <div className="spinner" style={{ margin: "0 auto 12px" }} />
          Cargando la carta del restaurante…
        </div>
      ) : (
        categoriasFiltradas
          .filter((cat) => catActiva === "__todas" || String(cat.id) === catActiva)
          .map((cat) => (
            <section key={cat.id} className="carta-section">
              <div className="carta-section-title">
                <span>{cat.nombre}</span>
              </div>
              <div className="carta-grid">
                {cat.productos.map((prod) => (
                  <div
                    key={prod.id}
                    className="dish-card"
                    onClick={() => abrirPersonalizar(prod)}
                  >
                    <div className="dish-info">
                      <div className="dish-name">{prod.nombre}</div>
                      <div className="dish-desc">{prod.descripcion || "Plato fresco elaborado al momento."}</div>
                      <div className="dish-footer">
                        <div className="dish-price">{fmt(prod.precio || prod.precio_final)}</div>
                        <button
                          className="dish-add-btn"
                          onClick={(e) => {
                            e.stopPropagation();
                            abrirPersonalizar(prod);
                          }}
                        >
                          + Agregar
                        </button>
                      </div>
                    </div>
                    {prod.imagen ? (
                      <img src={prod.imagen} alt={prod.nombre} className="dish-img" />
                    ) : (
                      <div className="dish-img">🍲</div>
                    )}
                  </div>
                ))}
              </div>
            </section>
          ))
      )}

      {/* Barra flotante del Carrito */}
      {carrito.length > 0 && !drawerAbierto && (
        <div className="carta-floating-bar" onClick={() => setDrawerAbierto(true)}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <span className="floating-count">{totalItems}</span>
            <div>
              <div style={{ fontSize: 12, opacity: 0.9 }}>Total a pedir</div>
              <div style={{ fontWeight: 800, fontSize: 16 }}>{fmt(totalPedido)}</div>
            </div>
          </div>
          <div className="floating-action">
            <span>Ver pedido</span>
            <span>➔</span>
          </div>
        </div>
      )}

      {/* Modal para Personalizar Producto / Notas de Cocina */}
      {itemModal && (
        <div className="modal-overlay" onClick={() => setItemModal(null)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 14 }}>
              <div>
                <h3 style={{ margin: 0, fontSize: 18, color: "#fff" }}>{itemModal.nombre}</h3>
                <div style={{ color: "#f43f5e", fontWeight: 700, fontSize: 16, marginTop: 4 }}>
                  {fmt(itemModal.precio || itemModal.precio_final)}
                </div>
              </div>
              <button
                style={{ background: "none", border: "none", color: "#94a3b8", fontSize: 22, cursor: "pointer" }}
                onClick={() => setItemModal(null)}
              >
                ✕
              </button>
            </div>

            <p style={{ color: "#94a3b8", fontSize: 13, marginBottom: 16 }}>
              {itemModal.descripcion || "Agrega notas especiales de preparación para la cocina."}
            </p>

            <div style={{ marginBottom: 16 }}>
              <label style={{ display: "block", fontSize: 12, fontWeight: 700, color: "#cbd5e1", marginBottom: 8 }}>
                Notas de preparación para Cocina
              </label>
              <div>
                {["Sin cebolla", "Término medio", "Bien cocido", "Salsa aparte", "Poco picante", "Sin sal"].map((tag) => (
                  <span
                    key={tag}
                    className="prep-tag"
                    onClick={() => setItemPrep((p) => (p ? `${p}, ${tag}` : tag))}
                  >
                    + {tag}
                  </span>
                ))}
              </div>
              <input
                type="text"
                value={itemPrep}
                onChange={(e) => setItemPrep(e.target.value)}
                placeholder="Ej. Término 3/4, ensalada sin aderezo..."
                style={{
                  width: "100%",
                  background: "#0b1120",
                  border: "1px solid rgba(255,255,255,0.1)",
                  color: "#fff",
                  borderRadius: 10,
                  padding: "10px 14px",
                  fontSize: 13,
                  marginTop: 8,
                }}
              />
            </div>

            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginTop: 20 }}>
              <div className="qty-control">
                <button className="qty-btn" onClick={() => setItemCant((c) => Math.max(1, c - 1))}>-</button>
                <span style={{ fontWeight: 800, fontSize: 16, minWidth: 24, textAlign: "center" }}>{itemCant}</span>
                <button className="qty-btn" onClick={() => setItemCant((c) => c + 1)}>+</button>
              </div>
              <button
                style={{
                  flex: 1,
                  marginLeft: 14,
                  background: "#e11d48",
                  color: "#fff",
                  border: "none",
                  borderRadius: 12,
                  padding: "13px 18px",
                  fontWeight: 800,
                  fontSize: 14,
                  cursor: "pointer",
                }}
                onClick={agregarAlCarrito}
              >
                Agregar · {fmt((itemModal.precio || itemModal.precio_final) * itemCant)}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Drawer / Modal del Carrito Completo */}
      {drawerAbierto && (
        <div className="modal-overlay" onClick={() => setDrawerAbierto(false)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
              <h2 style={{ margin: 0, fontSize: 18, color: "#fff" }}>Tu Pedido</h2>
              <button
                style={{ background: "none", border: "none", color: "#94a3b8", fontSize: 22, cursor: "pointer" }}
                onClick={() => setDrawerAbierto(false)}
              >
                ✕
              </button>
            </div>

            {/* Selector de Mesa obligatorio */}
            <div style={{ background: "#0b1120", borderRadius: 12, padding: 12, marginBottom: 16, border: "1px solid rgba(255,255,255,0.08)" }}>
              <label style={{ display: "block", fontSize: 12, color: "#94a3b8", marginBottom: 6 }}>
                📍 ¿En qué mesa te encuentras? *
              </label>
              <select
                required
                value={mesaId}
                onChange={(e) => setMesaId(e.target.value)}
                style={{
                  width: "100%",
                  background: "#131b2e",
                  color: "#fff",
                  border: "1px solid #334155",
                  borderRadius: 8,
                  padding: "10px 12px",
                  fontSize: 14,
                }}
              >
                <option value="">Selecciona tu mesa…</option>
                {mesas.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.nombre} ({m.salon || "General"})
                  </option>
                ))}
              </select>
            </div>

            {/* Líneas de productos */}
            <div style={{ maxHeight: "40vh", overflowY: "auto", marginBottom: 16 }}>
              {carrito.map((linea, idx) => (
                <div
                  key={idx}
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    padding: "10px 0",
                    borderBottom: "1px solid rgba(255,255,255,0.08)",
                  }}
                >
                  <div style={{ flex: 1, paddingRight: 10 }}>
                    <div style={{ fontWeight: 700, fontSize: 14, color: "#fff" }}>{linea.nombre}</div>
                    {linea.preparacion && (
                      <div style={{ fontSize: 12, color: "#f43f5e", marginTop: 2 }}>
                        ✍️ {linea.preparacion}
                      </div>
                    )}
                    <div style={{ fontSize: 13, color: "#94a3b8", marginTop: 2 }}>
                      {fmt(linea.precio)}
                    </div>
                  </div>
                  <div className="qty-control" style={{ padding: "4px 8px" }}>
                    <button className="qty-btn" style={{ width: 26, height: 26, fontSize: 14 }} onClick={() => cambiarCantidad(idx, -1)}>-</button>
                    <span style={{ fontWeight: 700, fontSize: 14 }}>{linea.cantidad}</span>
                    <button className="qty-btn" style={{ width: 26, height: 26, fontSize: 14 }} onClick={() => cambiarCantidad(idx, 1)}>+</button>
                  </div>
                </div>
              ))}
            </div>

            {/* Datos opcionales del comensal */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginBottom: 16 }}>
              <div>
                <label style={{ fontSize: 11, color: "#94a3b8" }}>Nombre (opcional)</label>
                <input
                  type="text"
                  placeholder="Tu nombre"
                  value={clienteNombre}
                  onChange={(e) => setClienteNombre(e.target.value)}
                  style={{ width: "100%", background: "#0b1120", border: "1px solid #334155", color: "#fff", borderRadius: 8, padding: 8, fontSize: 13 }}
                />
              </div>
              <div>
                <label style={{ fontSize: 11, color: "#94a3b8" }}>Teléfono (opcional)</label>
                <input
                  type="tel"
                  placeholder="WhatsApp recibo"
                  value={clienteTel}
                  onChange={(e) => setClienteTel(e.target.value)}
                  style={{ width: "100%", background: "#0b1120", border: "1px solid #334155", color: "#fff", borderRadius: 8, padding: 8, fontSize: 13 }}
                />
              </div>
            </div>

            {/* Resumen y Botón de Enviar */}
            <div style={{ borderTop: "1px solid rgba(255,255,255,0.1)", paddingTop: 14 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
                <span style={{ fontSize: 15, color: "#94a3b8" }}>Total a pagar en caja</span>
                <span style={{ fontSize: 20, fontWeight: 900, color: "#f43f5e" }}>{fmt(totalPedido)}</span>
              </div>
              <button
                disabled={enviando || !mesaId}
                onClick={enviarPedido}
                style={{
                  width: "100%",
                  background: !mesaId ? "#475569" : "linear-gradient(135deg, #e11d48, #f43f5e)",
                  color: "#fff",
                  border: "none",
                  borderRadius: 14,
                  padding: "16px",
                  fontSize: 16,
                  fontWeight: 800,
                  cursor: !mesaId ? "not-allowed" : "pointer",
                  boxShadow: "0 6px 20px rgba(225,29,72,0.4)",
                }}
              >
                {enviando ? "Enviando a cocina…" : `🚀 Enviar Pedido a Cocina (${totalItems})`}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Pantalla de Confirmación de Pedido Exitoso */}
      {pedidoExitoso && (
        <div className="modal-overlay">
          <div className="modal-card" style={{ textAlign: "center", padding: "32px 24px" }}>
            <div style={{ fontSize: 50, marginBottom: 12 }}>👨‍🍳🎉</div>
            <h2 style={{ fontSize: 22, color: "#fff", marginBottom: 6 }}>¡Pedido Recibido!</h2>
            <p style={{ color: "#94a3b8", fontSize: 14, marginBottom: 18 }}>
              Tu orden fue enviada a la cocina y ya se está preparando.
            </p>

            <div style={{ background: "#0b1120", borderRadius: 16, padding: 18, border: "1px solid rgba(255,255,255,0.08)", marginBottom: 20 }}>
              <div style={{ fontSize: 13, color: "#94a3b8" }}>Número de comanda</div>
              <div style={{ fontSize: 24, fontWeight: 900, color: "#38bdf8", margin: "4px 0 10px" }}>
                {pedidoExitoso.comanda}
              </div>
              <div style={{ fontSize: 14, color: "#e2e8f0" }}>
                Ubicación: <strong>{pedidoExitoso.mesa}</strong>
              </div>
              <div style={{ fontSize: 14, color: "#f43f5e", fontWeight: 700, marginTop: 4 }}>
                Total: {fmt(pedidoExitoso.total)} ({pedidoExitoso.itemsCount} platos)
              </div>
            </div>

            <div style={{ display: "flex", gap: 8, justifyContent: "center", fontSize: 12, color: "#10b981", marginBottom: 24 }}>
              <span>✓ Enviado a cocina</span>
              <span>•</span>
              <span>🔥 En preparación</span>
            </div>

            <button
              style={{
                width: "100%",
                background: "#1e293b",
                color: "#fff",
                border: "1px solid #334155",
                borderRadius: 12,
                padding: "14px",
                fontWeight: 700,
                fontSize: 14,
                cursor: "pointer",
              }}
              onClick={() => setPedidoExitoso(null)}
            >
              Pedir algo más para esta mesa
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
