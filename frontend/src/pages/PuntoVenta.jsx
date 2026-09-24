import { useEffect, useMemo, useRef, useState } from "react";
import api, { openWindow } from "../api.js";
import { WhatsAppButton } from "../components/ui.jsx";

function formatMoney(n) {
  return new Intl.NumberFormat("es-CO", {
    style: "currency",
    currency: "COP",
    maximumFractionDigits: 0,
  }).format(n || 0);
}

function formatDoc(d) {
  return d ? String(d).replace(/\B(?=(\d{3})+(?!\d))/g, ".") : "";
}

const DOC_LABEL = {
  CC: "C.C.",
  TI: "T.I.",
  CE: "C.E.",
  NIT: "NIT",
  PASAPORTE: "P.A.S.",
  "C.C": "C.C.",
  "T.I.": "T.I.",
};

function beep(ok = true) {
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    const o = ctx.createOscillator();
    const g = ctx.createGain();
    o.connect(g);
    g.connect(ctx.destination);
    o.frequency.value = ok ? 880 : 220;
    g.gain.setValueAtTime(0.05, ctx.currentTime);
    g.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + 0.12);
    o.start();
    o.stop(ctx.currentTime + 0.12);
  } catch {
    /* audio no disponible */
  }
}

function vibrar(ok = true) {
  try {
    if (navigator.vibrate) navigator.vibrate(ok ? [40, 30, 40] : 120);
  } catch {
    /* vibración no disponible */
  }
}

const MEDIOS = [
  { valor: "efectivo", icono: "💵", etiqueta: "Efectivo" },
  { valor: "tarjeta", icono: "💳", etiqueta: "Tarjeta" },
  { valor: "transferencia", icono: "🏦", etiqueta: "Transferencia" },
  { valor: "QR", icono: "📲", etiqueta: "QR" },
  { valor: "nequi", icono: "📱", etiqueta: "Nequi" },
  { valor: "daviplata", icono: "💸", etiqueta: "Daviplata" },
  { valor: "breb", icono: "🟩", etiqueta: "Bre-B" },
  { valor: "otro", icono: "🛒", etiqueta: "Otro" },
];

const TIPO_LABEL = {
  unidad: "Ud",
  peso: "kg",
  volumen: "L",
  longitud: "m",
  caja: "caja",
  paquete: "pqt",
};

export default function PuntoVenta() {
  const searchRef = useRef(null);
  const codigoRef = useRef(null);
  const flashTimerRef = useRef(null);
  const actionsRef = useRef({});
  const [kiosko, setKiosko] = useState(false);
  const [flashId, setFlashId] = useState(null);
  const [productos, setProductos] = useState([]);
  const [stock, setStock] = useState({});
  const [clientes, setClientes] = useState([]);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [q, setQ] = useState("");
  const [codigo, setCodigo] = useState("");
  const [filtro, setFiltro] = useState("todos");
  const [carrito, setCarrito] = useState([]);
  const [cli, setCli] = useState(null);
  const [cliQuery, setCliQuery] = useState("");
  const [cliPicker, setCliPicker] = useState(false);
  const [creandoCli, setCreandoCli] = useState(false);
  const [cliNuevo, setCliNuevo] = useState({ nombre: "", documento: "", telefono: "" });
  const [deudaCli, setDeudaCli] = useState(null);
  const [tipoVenta, setTipoVenta] = useState("contado");
  const [pagoMedio, setPagoMedio] = useState("efectivo");
  const [recibido, setRecibido] = useState("");
  const [qrOk, setQrOk] = useState(false);
  const [qrErr, setQrErr] = useState(false);
  const [escaneando, setEscaneando] = useState(false);
  const [wamsg, setWamsg] = useState("");
  const [tarjetaAuth, setTarjetaAuth] = useState(null);
  const [descuento, setDescuento] = useState("");
  const [descTipo, setDescTipo] = useState("monto");
  const [propina, setPropina] = useState("");
  const [cuponCodigo, setCuponCodigo] = useState("");
  const [cuponDes, setCuponDes] = useState(0);
  const [cuponInfo, setCuponInfo] = useState("");
  const [ventaOk, setVentaOk] = useState(null);
  const [balanzas, setBalanzas] = useState([]);
  const [pesoModal, setPesoModal] = useState(null);
  const [pesoVal, setPesoVal] = useState("");
  const [pesando, setPesando] = useState(false);
  const [comandasModal, setComandasModal] = useState(false);
  const [comandasLista, setComandasLista] = useState([]);
  const [comandaActiva, setComandaActiva] = useState(null);
  const [mesasMapa, setMesasMapa] = useState({});
  const [favs, setFavs] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem("pos.favoritos") || "[]");
    } catch {
      return [];
    }
  });

  useEffect(() => {
    try {
      localStorage.setItem("pos.favoritos", JSON.stringify(favs));
    } catch {
      /* almacenamiento no disponible */
    }
  }, [favs]);

  function toggleFav(id) {
    setFavs((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));
  }

  useEffect(() => {
    api("/productos?activo=true").then(setProductos).catch(() => {});
    api("/clientes").then(setClientes).catch(() => {});
    api("/balanzas").then(setBalanzas).catch(() => {});
    api("/inventario/stock?sucursal_id=1")
      .then((rows) => {
        const m = {};
        (rows || []).forEach((r) => (m[r.producto_id] = r.disponible ?? r.existencias ?? 0));
        setStock(m);
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    const t = setTimeout(() => {
      api(`/productos${q ? `?q=${encodeURIComponent(q)}` : "?activo=true"}`)
        .then(setProductos)
        .catch(() => {});
    }, 300);
    return () => clearTimeout(t);
  }, [q]);

  useEffect(() => {
    const key = (e) => {
      if (e.key === "F2") {
        e.preventDefault();
        searchRef.current?.focus();
      } else if (e.key === "F4") {
        e.preventDefault();
        codigoRef.current?.focus();
      } else if (e.key === "F8") {
        e.preventDefault();
        if (actionsRef.current.puedeCobrar) actionsRef.current.cobrar();
        else beep(false);
      }
    };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, []);

  useEffect(() => {
    actionsRef.current = { cobrar, puedeCobrar };
  });

  useEffect(() => {
    const onFs = () => setKiosko(Boolean(document.fullscreenElement));
    document.addEventListener("fullscreenchange", onFs);
    const qs = new URLSearchParams(window.location.search);
    if (qs.get("kiosko") === "1") {
      document.documentElement.requestFullscreen().catch(() => {});
    }
    return () => document.removeEventListener("fullscreenchange", onFs);
  }, []);

  function toggleKiosko() {
    if (document.fullscreenElement) {
      document.exitFullscreen().catch(() => {});
    } else {
      document.documentElement
        .requestFullscreen()
        .catch(() => setError("Tu navegador no permite pantalla completa."));
    }
  }

  const subtotal = carrito.reduce((s, i) => s + i.precio * i.cantidad, 0);
  const impuesto = carrito.reduce((s, i) => s + (i.precio * i.cantidad * (Number(i.impuesto) || 0)) / 100, 0);
  const desc = descTipo === "porcentaje" ? Math.round((subtotal * (Number(descuento) || 0)) / 100) : Number(descuento) || 0;
  const tip = Number(propina) || 0;
  const total = Math.max(0, subtotal - desc - cuponDes + impuesto + tip);
  const rec = Number(recibido) || 0;
  const cambio = pagoMedio === "efectivo" && tipoVenta === "contado" ? Math.max(0, rec - total) : 0;

  const puedeCobrar =
    carrito.length > 0 &&
    !(pagoMedio === "efectivo" && tipoVenta === "contado" && rec < total) &&
    !((pagoMedio === "nequi" || pagoMedio === "daviplata" || pagoMedio === "breb") && !qrOk);

  useEffect(() => {
    const t = setTimeout(() => {
      api("/pantalla", {
        method: "POST",
        body: JSON.stringify({
          items: carrito.map((i) => ({ nombre: i.nombre, cantidad: i.cantidad, subtotal: i.precio * i.cantidad })),
          subtotal,
          descuento: desc,
          impuesto: Math.round(impuesto),
          propina: tip,
          total,
          mensaje: "Aguarde · Su ticket sale al finalizar",
        }),
      }).catch(() => {});
    }, 600);
    return () => clearTimeout(t);
  }, [carrito, desc, tip, total, subtotal]);

  const VOL_MIN_MAYORISTA = 3;

  function precioLinea(item, cantidad, cliente) {
    if (item.es_peso) return item.precio_base;
    const min = Number(item.precio_minorista) || 0;
    const may = Number(item.precio_mayorista) || 0;
    if (cliente && cliente.tipo === "mayorista" && may > 0) return may;
    if (!item.es_peso && cantidad >= VOL_MIN_MAYORISTA && may > 0) return may;
    if (cliente && min > 0) return min;
    return item.precio_base;
  }

  function lineaCarrito(p, cantidad) {
    const base = Number(p.precio_venta) || 0;
    return {
      producto_id: p.id,
      nombre: p.nombre,
      precio_base: base,
      precio_minorista: Number(p.precio_minorista) || 0,
      precio_mayorista: Number(p.precio_mayorista) || 0,
      cantidad,
      es_peso: (p.tipo || "unidad") === "peso",
      es_compuesto: !!p.es_compuesto,
      impuesto: Number(p.impuesto) || 0,
    };
  }

  const tiposPresentes = useMemo(() => {
    const set = new Set(productos.map((p) => p.tipo || "unidad"));
    return ["todos", ...Object.keys(TIPO_LABEL).filter((t) => set.has(t)), "favoritos"];
  }, [productos]);

  const listaVisible = useMemo(() => {
    if (filtro === "favoritos") return productos.filter((p) => favs.includes(p.id));
    if (filtro === "todos") return productos;
    return productos.filter((p) => (p.tipo || "unidad") === filtro);
  }, [productos, filtro, favs]);

  function agregarItem(p, cantidad = 1) {
    beep();
    vibrar(true);
    setFlashId(p.id);
    window.clearTimeout(flashTimerRef.current);
    flashTimerRef.current = setTimeout(() => setFlashId(null), 650);
    setCarrito((prev) => {
      const idx = prev.findIndex((i) => i.producto_id === p.id);
      if (idx >= 0) {
        const next = [...prev];
        const nueva = next[idx].cantidad + cantidad;
        next[idx] = { ...next[idx], cantidad: nueva, precio: precioLinea(next[idx], nueva, cli) };
        return next;
      }
      const linea = { ...lineaCarrito(p, cantidad), precio: 0 };
      linea.precio = precioLinea(linea, cantidad, cli);
      return [...prev, linea];
    });
  }

  function clickProducto(p) {
    if ((p.tipo || "unidad") === "peso") {
      setPesoVal("1");
      setPesoModal(p);
      return;
    }
    agregarItem(p);
  }

  function agregarPesoModal() {
    const kg = Math.max(0.001, Math.round((Number(pesoVal) || 0) * 1000) / 1000);
    if (!kg) return;
    agregarItem(pesoModal, kg);
    setPesoModal(null);
    setPesoVal("");
  }

  async function leerBalanza() {
    setError("");
    const bal = balanzas.find((b) => b.activa);
    if (!bal) {
      setError("No hay balanza activa. Configúrala en Integraciones → Balanzas.");
      return;
    }
    setPesando(true);
    try {
      const w = await api(`/balanzas/${bal.id}/pesar`, { method: "POST" });
      setPesoVal(String(Math.round(w.peso * 1000) / 1000));
      setSuccess(`Báscula «${bal.nombre}»: ${w.peso} kg`);
    } catch (err) {
      setError(err.message);
    } finally {
      setPesando(false);
    }
  }

  async function agregarCodigo() {
    const cod = codigo.trim();
    if (!cod) return;
    try {
      const res = await api(`/productos?q=${encodeURIComponent(cod)}`);
      const p = (Array.isArray(res) ? res : []).find(
        (x) => x.codigo_barras === cod || x.sku === cod || x.plu === cod
      ) || (Array.isArray(res) && res.length ? res[0] : null);
      if (p) {
        beep();
        clickProducto(p);
        setCodigo("");
        setError("");
      } else {
        beep(false);
        vibrar(false);
        setError(`No se encontró el código «${cod}»`);
      }
    } catch (err) {
      setError(err.message);
    }
  }

  function cambiarCantidad(id, delta) {
    setCarrito((prev) =>
      prev
        .map((i) => {
          if (i.producto_id !== id) return i;
          const nueva = Math.max(i.es_peso ? 0.001 : 1, i.cantidad + delta);
          return { ...i, cantidad: nueva, precio: precioLinea(i, nueva, cli) };
        })
        .filter((i) => i.cantidad > 0)
    );
  }

  function quitarItem(id) {
    setCarrito((prev) => prev.filter((i) => i.producto_id !== id));
  }

  const clientesFiltrados = useMemo(() => {
    const s = cliQuery.trim();
    if (!s) return [];
    if (/^\d+$/.test(s)) {
      return clientes.filter((c) => (c.documento || "").includes(s)).slice(0, 6);
    }
    return clientes.filter((c) => c.nombre.toLowerCase().includes(s.toLowerCase())).slice(0, 6);
  }, [clientes, cliQuery]);

  useEffect(() => {
    if (!cli || tipoVenta !== "credito") {
      setDeudaCli(null);
      return;
    }
    let on = true;
    api(`/cartera/estado-cuenta/${cli.id}`)
      .then((d) => {
        if (on) setDeudaCli(d?.saldo_total ?? null);
      })
      .catch(() => {});
    return () => {
      on = false;
    };
  }, [cli, tipoVenta]);

  function seleccionarCliente(c) {
    setCli(c);
    setCliQuery("");
    setCliPicker(false);
    setCreandoCli(false);
    setError("");
    setCuponDes(0);
    setCuponInfo("");
    setCarrito((prev) => prev.map((i) => ({ ...i, precio: precioLinea(i, i.cantidad, c) })));
  }

  function volverConsumidorFinal() {
    setCli(null);
    setCliPicker(false);
    setCreandoCli(false);
    setCliQuery("");
    setCuponDes(0);
    setCuponInfo("");
    setCarrito((prev) => prev.map((i) => ({ ...i, precio: precioLinea(i, i.cantidad, null) })));
  }

  async function crearCliente() {
    setError("");
    try {
      const nuevo = await api("/clientes?empresa_id=1", {
        method: "POST",
        body: JSON.stringify({
          nombre: cliNuevo.nombre.trim(),
          tipo_documento: "CC",
          documento: cliNuevo.documento.trim() || null,
          telefono: cliNuevo.telefono.trim() || null,
        }),
      });
      setClientes((prev) => [nuevo, ...prev]);
      seleccionarCliente(nuevo);
      setCliNuevo({ nombre: "", documento: "", telefono: "" });
      beep();
    } catch (err) {
      setError(err.message);
    }
  }

  function abrirPantallaCliente() {
    openWindow("/pantalla/vista").catch((err) => setError(err.message));
  }

  async function abrirSelectorComandas() {
    setError("");
    try {
      const [coms, mesasData] = await Promise.all([
        api("/restaurante/comandas?estado=abierta").catch(() => []),
        api("/restaurante/mesas").catch(() => []),
      ]);
      const mapa = {};
      (mesasData || []).forEach((m) => {
        mapa[m.id] = m.nombre;
      });
      setMesasMapa(mapa);
      setComandasLista(coms || []);
      setComandasModal(true);
    } catch (e) {
      setError("No se pudieron cargar las comandas: " + e.message);
    }
  }

  function cargarComandaEnPOS(com) {
    if (!com || !com.detalle) return;
    const itemsCargados = com.detalle.map((d) => {
      const p = productos.find((prod) => prod.id === d.producto_id);
      return {
        producto_id: d.producto_id,
        nombre: d.producto || (p ? p.nombre : `Producto #${d.producto_id}`),
        codigo: p ? (p.sku || p.codigo_barras) : "",
        precio: Number(d.precio || (p ? p.precio_venta : 0)),
        precio_base: Number(p ? p.precio_venta : d.precio),
        precio_mayorista: Number(p ? p.precio_mayorista : d.precio),
        cantidad: Number(d.cantidad || 1),
        impuesto: Number(p ? p.impuesto : 0),
        es_peso: p ? p.tipo_unidad === "peso" : false,
        es_compuesto: p ? p.es_compuesto : false,
        preparacion: d.preparacion,
      };
    });

    setCarrito(itemsCargados);
    setComandaActiva({
      id: com.id,
      numero: com.numero,
      mesa_id: com.mesa_id,
      mesa_nombre: mesasMapa[com.mesa_id] || `Mesa #${com.mesa_id}`,
    });

    if (com.cliente_id) {
      const c = clientes.find((cli) => cli.id === com.cliente_id);
      if (c) seleccionarCliente(c);
    }

    setComandasModal(false);
    setSuccess(`Comanda ${com.numero} (${mesasMapa[com.mesa_id] || 'Mesa'}) cargada al POS.`);
    setTimeout(() => setSuccess(""), 3500);
  }

  async function aplicarCupon() {
    setError("");
    setCuponInfo("");
    const cod = cuponCodigo.trim().toUpperCase();
    if (!cod) {
      setCuponDes(0);
      return;
    }
    if (!cli) {
      setError("Selecciona o crea el cliente antes de aplicar el cupón (muchos cupones aplican por cliente).");
      return;
    }
    try {
      const r = await api("/fidelizacion/cupones/validar", {
        method: "POST",
        body: JSON.stringify({ codigo: cod, subtotal, cliente_id: cli ? cli.id : null }),
      });
      if (!r.valido) {
        setCuponDes(0);
        setError(`El cupón «${cod}» no aplica en este checkout.`);
        return;
      }
      setCuponDes(Number(r.descuento) || 0);
      setCuponInfo(`Cupón ${cod} aplicado: -${formatMoney(r.descuento)}`);
      beep();
    } catch (e) {
      setCuponDes(0);
      setCuponInfo("");
      setError(e.message);
    }
  }

  async function autorizarTarjeta() {
    setError("");
    const monto = total;
    try {
      const tx = await api("/pagos/tarjeta/autorizar", {
        method: "POST",
        body: JSON.stringify({ monto, marca: "Visa", ultimos4: "4242" }),
      });
      if (tx.estado === "rechazada") {
        beep(false);
        setError(`Tarjeta rechazada: el monto ${formatMoney(monto)} supera el límite`);
        return null;
      }
      beep();
      setTarjetaAuth(tx);
      setSuccess(`Tarjeta aprobada ${tx.codigo_autorizacion} por ${formatMoney(tx.monto)} ✓`);
      return tx;
    } catch (err) {
      setError(err.message);
      return null;
    }
  }

  async function reversarTarjeta() {
    if (!tarjetaAuth) return;
    try {
      await api(`/pagos/tarjeta/${tarjetaAuth.id}/reversar`, { method: "POST" });
      setSuccess(`Transacción ${tarjetaAuth.codigo_autorizacion} reversada`);
      setTarjetaAuth(null);
    } catch (err) {
      setError(err.message);
    }
  }

  async function cobrar() {
    setError("");
    setSuccess("");
    setVentaOk(null);
    if (tipoVenta === "credito" && !cli) {
      setError("Selecciona un cliente para la venta a crédito.");
      return;
    }
    if (pagoMedio === "efectivo" && tipoVenta === "contado" && rec < total) {
      setError("El monto recibido es menor al total. Ajusta la cantidad recibida.");
      return;
    }
    if ((pagoMedio === "nequi" || pagoMedio === "daviplata" || pagoMedio === "breb") && !qrOk) {
      setError("Confirma que ya recibiste el pago por el QR antes de cobrar.");
      return;
    }
    try {
      let tx = tarjetaAuth;
      if (pagoMedio === "tarjeta" && !tx) {
        tx = await autorizarTarjeta();
        if (!tx) return;
      }
      const data = await api("/ventas", {
        method: "POST",
        body: JSON.stringify({
          empresa_id: 1,
          sucursal_id: 1,
          cliente_id: cli ? cli.id : null,
          tipo: tipoVenta,
          descuento_global: desc,
          propina: tip,
          cupon_codigo: cuponCodigo.trim().toUpperCase() || null,
          detalle: carrito.map((i) => ({ producto_id: i.producto_id, cantidad: i.cantidad, precio: i.precio })),
          pagos: [{ medio: pagoMedio, monto: pagoMedio === "efectivo" && tipoVenta === "contado" ? rec : total, referencia: tx?.codigo_autorizacion || null }],
        }),
      });
      if (tx) {
        api(`/pagos/tarjeta/${tx.id}/confirmar`, { method: "POST" }).catch(() => {});
        setTarjetaAuth(null);
      }
      const docs = await api(`/facturacion/documentos?venta_id=${data.id}`).catch(() => []);
      const fac = Array.isArray(docs) ? docs.find((d) => d.tipo_documento === "factura") : null;
      setVentaOk({
        id: data.id,
        numero: data.numero,
        total: data.total,
        recibido: pagoMedio === "efectivo" && tipoVenta === "contado" ? rec : 0,
        cambio: pagoMedio === "efectivo" && tipoVenta === "contado" ? cambio : 0,
        factura: fac || (Array.isArray(docs) ? docs[0] : null),
        cliente: cli ? { telefono: cli.telefono || null, nombre: cli.nombre || null } : null,
      });
      if (comandaActiva) {
        api(`/restaurante/comandas/${comandaActiva.id}/cerrar`, { method: "POST" }).catch(() => {});
        setComandaActiva(null);
      }
      setCarrito([]);
      setDescuento("");
      setPropina("");
      setRecibido("");
      setQrOk(false);
      setQrErr(false);
      setWamsg("");
      setCuponCodigo("");
      setCuponDes(0);
      setCuponInfo("");
      setCli(null);
      setCliQuery("");
      setCliPicker(false);
      setCreandoCli(false);
      beep();
      vibrar(true);
    } catch (err) {
      if (tarjetaAuth) {
        api(`/pagos/tarjeta/${tarjetaAuth.id}/reversar`, { method: "POST" }).catch(() => {});
        setTarjetaAuth(null);
      }
      beep(false);
      vibrar(false);
      setError(err.message);
    }
  }

  function imprimirFactura() {
    if (!ventaOk?.factura) return;
    openWindow(`/facturacion/${ventaOk.factura.id}/ticket`).catch((err) => setError(err.message));
  }

  function imprimirTirilla() {
    if (!ventaOk?.id) return;
    const q = `?recibido=${ventaOk.recibido ?? ""}&cambio=${ventaOk.cambio ?? ""}`;
    openWindow(`/ventas/${ventaOk.id}/tirilla${q}`).catch((err) => setError(err.message));
  }

  function nuevaVenta() {
    setVentaOk(null);
    setSuccess("");
    setTimeout(() => searchRef.current?.focus(), 50);
  }

  return (
    <div className="page" style={{ padding: 16 }}>
      <div className="page-header" style={{ marginBottom: 14 }}>
        <div>
          <h1 style={{ fontSize: 20 }}>Punto de Venta</h1>
          <div className="muted" style={{ marginTop: 2 }}>
            F2 buscar · F4 código · F8 cobrar · escanea y vende · ★ marca favoritos
          </div>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button className="btn btn-secondary" onClick={toggleKiosko} title={kiosko ? "Salir de pantalla completa" : "Modo kiosko (pantalla completa, ideal tablet)"}>
            {kiosko ? "⛶ Salir de kiosko" : "⛶ Kiosko"}
          </button>
          <button className="btn btn-secondary" onClick={abrirPantallaCliente}>
            🖥️ Pantalla de cliente
          </button>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: kiosko ? "1fr 360px" : "1fr 400px", gap: 16, alignItems: "start" }}>
        {/* ---------- Catálogo ---------- */}
        <div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 180px", gap: 10, marginBottom: 10 }}>
            <div style={{ position: "relative" }}>
              <span style={{ position: "absolute", left: 12, top: 9, opacity: 0.5, fontSize: 16 }}>🔎</span>
              <input
                ref={searchRef}
                placeholder="Buscar por nombre, código, SKU o PLU…"
                value={q}
                onChange={(e) => setQ(e.target.value)}
                style={{ paddingLeft: 38, height: 44, fontSize: 15, borderRadius: 12 }}
              />
            </div>
            <div style={{ position: "relative" }}>
              <span style={{ position: "absolute", left: 12, top: 9, opacity: 0.5, fontSize: 16 }}>⌛</span>
              <input
                ref={codigoRef}
                placeholder="Código / barras"
                value={codigo}
                onChange={(e) => setCodigo(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") agregarCodigo();
                }}
                style={{ paddingLeft: 38, paddingRight: 44, height: 44, fontSize: 15, borderRadius: 12 }}
              />
              <button
                title="Escanear código con la cámara"
                onClick={() => setEscaneando(true)}
                style={{
                  position: "absolute",
                  right: 6,
                  top: 5,
                  width: 34,
                  height: 34,
                  borderRadius: 9,
                  border: 0,
                  cursor: "pointer",
                  fontSize: 17,
                  background: "var(--brand1)",
                  color: "#fff",
                  opacity: escaneando ? 0.5 : 1,
                }}
              >
                📷
              </button>
            </div>
          </div>

          <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 12 }}>
            {tiposPresentes.map((t) => (
              <button
                key={t}
                type="button"
                onClick={() => setFiltro(t)}
                style={{
                  padding: "7px 15px",
                  borderRadius: 999,
                  border: "1px solid var(--line)",
                  background: filtro === t ? "linear-gradient(135deg,#0e9f74,#0b7a59)" : "var(--card)",
                  color: filtro === t ? "#fff" : "var(--ink)",
                  fontWeight: 700,
                  fontSize: 12.5,
                  cursor: "pointer",
                  transition: "transform .12s, box-shadow .12s",
                }}
              >
                {t === "todos" ? "Todos" : t === "favoritos" ? "★ Favoritos" : TIPO_LABEL[t]}
              </button>
            ))}
          </div>

          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fill, minmax(168px, 1fr))",
              gap: 12,
              maxHeight: "calc(100vh - 250px)",
              overflow: "auto",
              paddingBottom: 8,
            }}
          >
            {listaVisible.map((p) => {
              const disp = stock[p.id];
              const agotado = disp != null && disp <= 0;
              const bajo = !agotado && disp != null && disp < 5 && (p.tipo || "unidad") !== "peso";
              const enCarrito = carrito.reduce((s, i) => (i.producto_id === p.id ? i.cantidad : s), 0);
              return (
                <button
                  key={p.id}
                  type="button"
                  onClick={() => clickProducto(p)}
                  className="pos-card"
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    alignItems: "stretch",
                    textAlign: "left",
                    background: "var(--card)",
                    border: "1px solid var(--line)",
                    borderRadius: 14,
                    padding: "12px 13px",
                    cursor: "pointer",
                    position: "relative",
                    opacity: agotado ? 0.55 : 1,
                    boxShadow: "0 1px 2px rgba(0,0,0,.04)",
                  }}
                >
                  <span
                    role="button"
                    tabIndex={0}
                    title={favs.includes(p.id) ? "Quitar de favoritos" : "Agregar a favoritos"}
                    onClick={(e) => {
                      e.stopPropagation();
                      toggleFav(p.id);
                    }}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.stopPropagation();
                        e.preventDefault();
                        toggleFav(p.id);
                      }
                    }}
                    style={{
                      position: "absolute",
                      top: 6,
                      right: 8,
                      fontSize: 15,
                      cursor: "pointer",
                      zIndex: 2,
                      color: favs.includes(p.id) ? "#f59e0b" : "#cbd5e1",
                      userSelect: "none",
                    }}
                  >
                    ★
                  </span>
                  <div style={{ fontWeight: 700, fontSize: 13.5, lineHeight: 1.25, minHeight: 34, display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical", overflow: "hidden" }}>
                    {p.nombre}
                  </div>
                  <div style={{ fontSize: 16, fontWeight: 800, color: "var(--brand1)", marginTop: 6 }}>
                    {formatMoney(Math.round((Number(p.precio_venta) || 0) * (1 + (Number(p.impuesto) || 0) / 100)))}
                    <span style={{ fontSize: 10.5, fontWeight: 600, color: "var(--muted)", marginLeft: 4 }}>
                      {TIPO_LABEL[p.tipo || "unidad"] || "Ud"}
                    </span>
                    {Number(p.impuesto) > 0 && (
                      <span style={{ fontSize: 10, color: "#b45309", fontWeight: 700, marginLeft: 6 }}>IVA incl.</span>
                    )}
                  </div>
                  {Number(p.precio_mayorista) > 0 && Number(p.precio_mayorista) !== Number(p.precio_venta) && (
                    <div style={{ fontSize: 11.5, color: "var(--muted)", marginTop: 2 }}>
                      May: <b style={{ color: "#059669", fontWeight: 700 }}>{formatMoney(Math.round((Number(p.precio_mayorista) || 0) * (1 + (Number(p.impuesto) || 0) / 100)))}</b>
                    </div>
                  )}
                  <div style={{ display: "flex", gap: 6, alignItems: "center", marginTop: 8, flexWrap: "wrap" }}>
                    {agotado ? (
                      <span className="badge badge-danger" style={{ fontSize: 10 }}>Agotado</span>
                    ) : bajo ? (
                      <span className="badge badge-warning" style={{ fontSize: 10 }}>Quedan {disp}</span>
                    ) : disp != null ? (
                      <span className="badge badge-cyan" style={{ fontSize: 10 }}>{Math.round(disp)} disp</span>
                    ) : null}
                    {(p.tipo || "unidad") === "peso" && (
                      <span className="badge badge-purple" style={{ fontSize: 10 }}>⚖️ Pesa</span>
                    )}
                    {p.es_compuesto && (
                      <span className="badge" style={{ fontSize: 10, background: "#fef3c7", color: "#92400e" }}>🧩 Combo</span>
                    )}
                    {enCarrito > 0 && (
                      <span className="badge badge-success" style={{ fontSize: 10, marginLeft: "auto" }}>
                        x{enCarrito}
                      </span>
                    )}
                  </div>
                </button>
              );
            })}
            {listaVisible.length === 0 && (
              <div className="muted" style={{ gridColumn: "1/-1", padding: 26, textAlign: "center" }}>
                Sin resultados
              </div>
            )}
          </div>
        </div>

        {/* ---------- Carrito ---------- */}
        <div className="card" style={{ position: "sticky", top: 70 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
            <h2 style={{ fontSize: 16 }}>Venta actual</h2>
            <div style={{ display: "flex", gap: 4 }}>
              <button
                type="button"
                onClick={() => setTipoVenta("contado")}
                className="btn btn-sm"
                style={{
                  background: tipoVenta === "contado" ? "linear-gradient(135deg,#0e9f74,#0b7a59)" : "var(--card)",
                  color: tipoVenta === "contado" ? "#fff" : "var(--ink)",
                  border: "1px solid var(--line)",
                  boxShadow: tipoVenta === "contado" ? "0 6px 14px -8px rgba(13,148,136,.6)" : "none",
                }}
              >
                Contado
              </button>
              <button
                type="button"
                onClick={() => setTipoVenta("credito")}
                className="btn btn-sm"
                style={{
                  background: tipoVenta === "credito" ? "linear-gradient(135deg,#0e9f74,#0b7a59)" : "var(--card)",
                  color: tipoVenta === "credito" ? "#fff" : "var(--ink)",
                  border: "1px solid var(--line)",
                  boxShadow: tipoVenta === "credito" ? "0 6px 14px -8px rgba(13,148,136,.6)" : "none",
                }}
              >
                Crédito
              </button>
            </div>
          </div>

          {/* Cargar Comanda de Restaurante */}
          <div style={{ marginBottom: 10 }}>
            {comandaActiva ? (
              <div style={{ background: "rgba(225,29,72,0.12)", border: "1px solid rgba(225,29,72,0.35)", borderRadius: 10, padding: "8px 12px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <div>
                  <span style={{ fontWeight: 800, color: "#e11d48", fontSize: 13 }}>🍽️ {comandaActiva.mesa_nombre}</span>
                  <span style={{ fontSize: 11, color: "var(--muted)", marginLeft: 6 }}>({comandaActiva.numero})</span>
                </div>
                <button
                  type="button"
                  className="btn btn-ghost"
                  style={{ padding: "2px 6px", fontSize: 11, color: "#dc2626" }}
                  onClick={() => setComandaActiva(null)}
                  title="Desvincular mesa"
                >
                  ✕ Desvincular
                </button>
              </div>
            ) : (
              <button
                type="button"
                className="btn btn-sm"
                style={{ width: "100%", fontWeight: 700, background: "rgba(225,29,72,0.08)", color: "#e11d48", border: "1px solid rgba(225,29,72,0.25)" }}
                onClick={abrirSelectorComandas}
              >
                🍽️ Cargar Mesa / Comanda de Restaurante
              </button>
            )}
          </div>

          <div style={{ marginBottom: 12 }}>
            <label>Cliente de la venta</label>
            {cli ? (
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  padding: "9px 12px",
                  border: "1px solid rgba(13,148,136,.35)",
                  borderRadius: 11,
                  background: "var(--brand-soft)",
                }}
              >
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontWeight: 700, fontSize: 13.5, color: "var(--brand1)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    👤 {cli.nombre}
                  </div>
                  <div style={{ fontSize: 11.5, color: "var(--muted)" }}>
                    {cli.documento ? `${DOC_LABEL[cli.tipo_documento] || "C.C."} ${formatDoc(cli.documento)}` : "Sin documento"}
                    {cli.telefono ? ` · 📞 ${cli.telefono}` : ""}
                  </div>
                </div>
                <span className="badge badge-info" style={{ fontSize: 10 }}>
                  {cli.tipo === "mayorista" ? "Mayorista" : cli.tipo === "frecuente" ? "Frecuente" : "Ocasional"}
                </span>
                <button className="btn btn-ghost" style={{ padding: "3px 8px" }} onClick={volverConsumidorFinal} title="Volver a Consumidor final">
                  ✕
                </button>
              </div>
            ) : (
              <div>
                <button
                  type="button"
                  onClick={() => setCliPicker((v) => !v)}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    width: "100%",
                    padding: "9px 12px",
                    border: "1px solid var(--line)",
                    borderRadius: 11,
                    background: "var(--card)",
                    cursor: "pointer",
                    fontSize: 13.5,
                    fontWeight: 700,
                    color: "var(--ink)",
                  }}
                >
                  <span>🧾 Consumidor final</span>
                  <span style={{ fontSize: 12, color: "var(--brand1)", fontWeight: 700 }}>{cliPicker ? "Ocultar ▴" : "Cambiar ▾"}</span>
                </button>

                {cliPicker && (
                  <div style={{ marginTop: 8 }}>
                    <input
                      autoFocus
                      placeholder="Buscar por cédula o nombre…"
                      value={cliQuery}
                      onChange={(e) => {
                        setCliQuery(e.target.value);
                        setCreandoCli(false);
                      }}
                    />
                    <div style={{ border: "1px solid var(--line)", borderRadius: 11, marginTop: 6, overflow: "hidden", background: "var(--card)" }}>
                      {clientesFiltrados.map((c) => (
                        <button
                          key={c.id}
                          type="button"
                          onClick={() => seleccionarCliente(c)}
                          style={{
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "space-between",
                            gap: 8,
                            width: "100%",
                            textAlign: "left",
                            padding: "9px 12px",
                            border: "none",
                            borderBottom: "1px solid var(--line)",
                            background: "transparent",
                            cursor: "pointer",
                            fontSize: 13,
                          }}
                        >
                          <span style={{ minWidth: 0 }}>
                            <span style={{ display: "block", fontWeight: 600, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{c.nombre}</span>
                            <span style={{ display: "block", fontSize: 11.5, color: "var(--muted)" }}>
                              {c.documento ? `${DOC_LABEL[c.tipo_documento] || "C.C."} ${formatDoc(c.documento)}` : "Sin documento"}
                            </span>
                          </span>
                          {c.tipo === "mayorista" && <span className="badge badge-purple" style={{ fontSize: 9.5 }}>Mayorista</span>}
                        </button>
                      ))}
                      {cliQuery.trim() && clientesFiltrados.length === 0 && !creandoCli && (
                        <button
                          type="button"
                          onClick={() => setCreandoCli(true)}
                          style={{
                            display: "flex",
                            alignItems: "center",
                            gap: 8,
                            width: "100%",
                            padding: "10px 12px",
                            border: "none",
                            background: "rgba(13,148,136,.08)",
                            color: "var(--brand1)",
                            cursor: "pointer",
                            fontSize: 13,
                            fontWeight: 700,
                          }}
                        >
                          ➕ Registrar «{cliQuery.trim()}» como cliente nuevo
                        </button>
                      )}
                      {!cliQuery.trim() && <div className="muted" style={{ padding: 10, fontSize: 12 }}>Escribe cédula o nombre para buscar</div>}
                    </div>

                    {creandoCli && (
                      <div style={{ marginTop: 8, display: "grid", gap: 8 }}>
                        <input
                          placeholder="Nombre completo *"
                          value={cliNuevo.nombre}
                          onChange={(e) => setCliNuevo({ ...cliNuevo, nombre: e.target.value })}
                        />
                        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
                          <input
                            placeholder="Cédula"
                            value={cliNuevo.documento}
                            onChange={(e) => setCliNuevo({ ...cliNuevo, documento: e.target.value })}
                          />
                          <input
                            placeholder="Teléfono"
                            value={cliNuevo.telefono}
                            onChange={(e) => setCliNuevo({ ...cliNuevo, telefono: e.target.value })}
                          />
                        </div>
                        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
                          <button className="btn btn-secondary" onClick={() => setCreandoCli(false)}>
                            Cancelar
                          </button>
                          <button className="btn" onClick={crearCliente} disabled={!cliNuevo.nombre.trim()}>
                            Guardar cliente
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>

          <div style={{ maxHeight: 300, overflow: "auto", marginBottom: 12 }}>
            {carrito.map((i) => (
              <div
                key={i.producto_id}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  padding: "9px 2px",
                  borderBottom: "1px solid var(--line)",
                  borderRadius: 8,
                  background: i.producto_id === flashId ? "rgba(16,185,129,.16)" : "transparent",
                  transition: "background .3s ease",
                }}
              >
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 13, fontWeight: 600, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {i.es_compuesto && (
                      <span className="badge" style={{ fontSize: 9, background: "#fef3c7", color: "#92400e", marginRight: 5 }}>🧩 Combo</span>
                    )}
                    {i.nombre}
                  </div>
                  <div className="muted" style={{ fontSize: 11.5 }}>
                    {formatMoney(i.precio)} / {i.es_peso ? "kg" : "ud"}
                    {!i.es_peso && i.precio < i.precio_base && (
                      <span
                        className="badge badge-success"
                        style={{ fontSize: 9, marginLeft: 6 }}
                        title="Precio por lista aplicado"
                      >
                        {cli && cli.tipo === "mayorista"
                          ? "Mayorista"
                          : i.cantidad >= VOL_MIN_MAYORISTA
                          ? "Volumen"
                          : "Minorista"}
                      </span>
                    )}
                  </div>
                </div>
                <button className="btn btn-ghost" onClick={() => cambiarCantidad(i.producto_id, -1)} style={{ padding: "4px 9px", fontSize: 15 }}>
                  −
                </button>
                <span style={{ minWidth: 46, textAlign: "center", fontWeight: 700, fontSize: 13.5 }}>
                  {i.es_peso ? i.cantidad.toFixed(3).replace(/\.?0+$/, "") : i.cantidad}
                </span>
                <button className="btn btn-ghost" onClick={() => cambiarCantidad(i.producto_id, 1)} style={{ padding: "4px 9px", fontSize: 15 }}>
                  +
                </button>
                <div style={{ width: 78, textAlign: "right", fontWeight: 700, fontSize: 13.5 }}>
                  {formatMoney(i.precio * i.cantidad)}
                </div>
                <button className="btn btn-danger" onClick={() => quitarItem(i.producto_id)} style={{ padding: "3px 7px", background: "transparent", color: "#dc2626" }} title="Quitar">
                  ✕
                </button>
              </div>
            ))}
            {carrito.length === 0 && (
              <div className="muted" style={{ textAlign: "center", padding: 26 }}>
                Toca los productos para agregarlos
              </div>
            )}
          </div>

          <div style={{ display: "grid", gap: 6, marginBottom: 10, fontSize: 13.5 }}>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span className="muted">Subtotal</span>
              <span>{formatMoney(subtotal)}</span>
            </div>
            {impuesto > 0 && (
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span className="muted">IVA</span>
                <span>{formatMoney(impuesto)}</span>
              </div>
            )}
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span className="muted">Descuento</span>
              <div style={{ display: "flex", gap: 6 }}>
                <select
                  value={descTipo}
                  onChange={(e) => setDescTipo(e.target.value)}
                  style={{ width: 62, padding: "6px 6px", fontSize: 12.5 }}
                  title="Tipo de descuento"
                >
                  <option value="monto">$</option>
                  <option value="porcentaje">%</option>
                </select>
                <input type="number" value={descuento} onChange={(e) => setDescuento(e.target.value)} style={{ width: 92, padding: "6px 10px" }} placeholder="0" />
              </div>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span className="muted">Propina</span>
              <input type="number" value={propina} onChange={(e) => setPropina(e.target.value)} style={{ width: 92, padding: "6px 10px" }} placeholder="0" />
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 6 }}>
              <span className="muted">Cupón</span>
              <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                <input
                  value={cuponCodigo}
                  onChange={(e) => {
                    setCuponCodigo(e.target.value);
                    setCuponInfo("");
                  }}
                  style={{ width: 110, padding: "6px 10px", textTransform: "uppercase" }}
                  placeholder="CÓDIGO"
                  onKeyDown={(e) => e.key === "Enter" && aplicarCupon()}
                />
                <button className="btn btn-sm" onClick={aplicarCupon}>✓</button>
              </div>
            </div>
            {cuponInfo && (
              <div style={{ fontSize: 12, color: "#16a34a", fontWeight: 700, textAlign: "right" }}>{cuponInfo}</div>
            )}
            {cuponDes > 0 && (
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span className="muted">Dcto. cupón</span>
                <span>-{formatMoney(cuponDes)}</span>
              </div>
            )}
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                fontSize: 21,
                fontWeight: 800,
                paddingTop: 8,
                borderTop: "1px solid var(--line)",
              }}
            >
              <span>Total</span>
              <span style={{ color: "var(--brand1)" }}>{formatMoney(total)}</span>
            </div>
          </div>

          {tipoVenta === "contado" && (
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginBottom: 12 }}>
              <div>
                <label>Método de pago</label>
                <select
                  value={pagoMedio}
                  onChange={(e) => {
                    setPagoMedio(e.target.value);
                    setQrOk(false);
                    setQrErr(false);
                    if (e.target.value !== "tarjeta") setTarjetaAuth(null);
                  }}
                  style={{ padding: "9px 12px" }}
                >
                  {MEDIOS.map((m) => (
                    <option key={m.valor} value={m.valor}>
                      {m.icono} {m.etiqueta}
                    </option>
                  ))}
                </select>
              </div>
              {pagoMedio === "efectivo" ? (
                <div>
                  <label>Recibido</label>
                  <input
                    type="number"
                    value={recibido}
                    onChange={(e) => setRecibido(e.target.value)}
                    style={{ padding: "9px 12px" }}
                    placeholder="0"
                  />
                </div>
              ) : (
                <div />
              )}
            </div>
          )}

          {tipoVenta === "contado" && pagoMedio === "efectivo" && rec > 0 && (
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                padding: "11px 14px",
                borderRadius: 12,
                marginBottom: 12,
                background: cambio >= 0 ? "rgba(16,185,129,.12)" : "rgba(244,63,94,.1)",
                color: cambio >= 0 ? "#059669" : "#e11d48",
                fontWeight: 800,
                fontSize: 16,
              }}
            >
              <span style={{ fontWeight: 600, fontSize: 13 }}>💵 Cambio a entregar</span>
              <span>{formatMoney(cambio)}</span>
            </div>
          )}

          {(pagoMedio === "nequi" || pagoMedio === "daviplata" || pagoMedio === "breb") && (
            <div
              style={{
                border: "1px solid var(--line)",
                borderRadius: 12,
                padding: 12,
                marginBottom: 12,
                textAlign: "center",
                background: "var(--card)",
              }}
            >
              <label style={{ marginBottom: 8, display: "block" }}>
                {pagoMedio === "nequi" ? "📱 Nequi" : pagoMedio === "daviplata" ? "💸 Daviplata" : "🟩 Bre-B"} · muestra este QR al cliente
              </label>
              {qrErr ? (
                <p style={{ fontSize: 12.5, color: "#d97706", marginBottom: 8 }}>
                  Aún no configuraste el QR de {pagoMedio}. Ve a <b>Configuración → WhatsApp y Pagos</b>.
                </p>
              ) : (
                <div style={{ background: "#fff", borderRadius: 12, padding: 10, display: "inline-block", marginBottom: 10 }}>
                  <img
                    src={`/publico/qr-pago/${pagoMedio}`}
                    alt={`QR ${pagoMedio}`}
                    width={150}
                    height={150}
                    style={{ display: "block" }}
                    onLoad={() => setQrErr(false)}
                    onError={() => setQrErr(true)}
                  />
                </div>
              )}
              <button
                className={qrOk ? "btn btn-success" : "btn btn-secondary"}
                onClick={() => setQrOk(!qrOk)}
                style={{ width: "100%" }}
              >
                {qrOk ? "✓ Pago recibido" : "Ya recibí el pago"}
              </button>
            </div>
          )}

          {tipoVenta === "credito" && !cli && (
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 8,
                fontSize: 12,
                color: "#d97706",
                marginBottom: 10,
                fontWeight: 700,
                padding: "9px 12px",
                borderRadius: 10,
                background: "rgba(245,158,11,.1)",
                border: "1px solid rgba(245,158,11,.3)",
              }}
            >
              ⚠️ Para vender a crédito selecciona el cliente del fiado.
            </div>
          )}

          {tipoVenta === "credito" && cli && (
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                gap: 8,
                fontSize: 12,
                marginBottom: 10,
                padding: "9px 12px",
                borderRadius: 10,
                background: "var(--brand-soft)",
                border: "1px solid rgba(13,148,136,.3)",
              }}
            >
              <span style={{ fontWeight: 700, color: "var(--brand1)", whiteSpace: "nowrap" }}>
                🏷️ {cli.nombre.split(" ")[0]} va a fiado
                {cli.tipo === "mayorista" && (
                  <span className="badge badge-purple" style={{ fontSize: 9, marginLeft: 6, verticalAlign: "middle" }}>
                    🏢 Crédito empresarial
                  </span>
                )}
              </span>
              <span style={{ textAlign: "right", lineHeight: 1.35 }}>
                {deudaCli != null && (
                  <span style={{ display: "block", fontWeight: 800, color: deudaCli > 0 ? "#d97706" : "#059669" }}>
                    Debe {formatMoney(deudaCli)}
                  </span>
                )}
                {cli.limite_credito > 0 && (
                  <span style={{ display: "block", color: "var(--muted)" }}>
                    Límite {formatMoney(cli.limite_credito)}
                  </span>
                )}
              </span>
            </div>
          )}

          {pagoMedio === "tarjeta" && tipoVenta === "contado" && (
            <div style={{ marginBottom: 12 }}>
              {tarjetaAuth ? (
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 10,
                    flexWrap: "wrap",
                    padding: "10px 12px",
                    border: "1px solid rgba(16,185,129,.4)",
                    background: "rgba(16,185,129,.08)",
                    borderRadius: 12,
                  }}
                >
                  <span className="badge badge-success">
                    💳 Aprobada {tarjetaAuth.codigo_autorizacion} · {formatMoney(tarjetaAuth.monto)}
                  </span>
                  <button className="btn btn-danger" onClick={reversarTarjeta} style={{ marginLeft: "auto", padding: "6px 12px" }}>
                    Reversar
                  </button>
                </div>
              ) : (
                <button
                  className="btn btn-secondary"
                  style={{ width: "100%", padding: "10px 12px" }}
                  onClick={autorizarTarjeta}
                  disabled={carrito.length === 0}
                >
                  💳 Autorizar {formatMoney(total)}
                </button>
              )}
            </div>
          )}

          {error && <div className="error">{error}</div>}
          {success && !ventaOk && <div className="chip" style={{ marginBottom: 8, width: "100%", justifyContent: "center" }}>{success}</div>}

          {ventaOk ? (
            <div style={{ background: "rgba(16,185,129,.1)", border: "1px solid rgba(16,185,129,.4)", borderRadius: 14, padding: 16, textAlign: "center" }}>
              <div style={{ fontSize: 34 }}>🎉</div>
              <div style={{ fontWeight: 800, fontSize: 16, color: "#059669", margin: "4px 0" }}>
                Venta {ventaOk.numero} registrada
              </div>
              <div className="muted" style={{ marginBottom: 12 }}>
                {formatMoney(ventaOk.total)}
                {cambio > 0 && <div style={{ marginTop: 3 }}>Cambio: {formatMoney(cambio)}</div>}
              </div>
              <div style={{ display: "grid", gap: 8 }}>
                <button className="btn" onClick={imprimirTirilla} style={{ width: "100%", padding: 11 }}>
                  🖨️ Imprimir tirilla
                </button>
                {ventaOk.cliente && (
                  <WhatsAppButton
                    telefono={ventaOk.cliente.telefono}
                    mensaje={`Hola ${ventaOk.cliente.nombre || ""} 👋,\nGracias por tu compra en ${window.location.hostname}.\nTu recibo ${ventaOk.numero || ""} por ${formatMoney(ventaOk.total)} quedó registrado.`}
                    label={`📲 WhatsApp al cliente${ventaOk.cliente.nombre ? ` · ${ventaOk.cliente.nombre.split(" ")[0]}` : ""}`}
                    size=""
                    estilo={{ width: "100%", padding: 11 }}
                  />
                )}
                {wamsg && (
                  <div style={{ fontSize: 12.5, color: "#16a34a", fontWeight: 700 }}>{wamsg}</div>
                )}
                {ventaOk.factura && (
                  <button className="btn btn-secondary" onClick={imprimirFactura} style={{ width: "100%", padding: 11 }}>
                    🧾 Imprimir factura {ventaOk.factura.numero || ""}
                  </button>
                )}
                <button className="btn btn-secondary" onClick={nuevaVenta} style={{ width: "100%", padding: 11 }}>
                  ➕ Nueva venta
                </button>
              </div>
            </div>
          ) : (
            <button className="btn" onClick={cobrar} disabled={!puedeCobrar} style={{ width: "100%", padding: 14, fontSize: 17, borderRadius: 14 }}>
              {pagoMedio === "tarjeta" && tarjetaAuth ? "🛒 Cobrar con tarjeta" : "🛒 Cobrar"} · {formatMoney(total)}
            </button>
          )}

          <div style={{ display: "flex", gap: 8, marginTop: 10, fontSize: 11.5, color: "var(--muted)" }}>
            <span style={{ flex: 1, textAlign: "center" }}>F2 · Buscar</span>
            <span style={{ flex: 1, textAlign: "center" }}>F4 · Código</span>
            <span style={{ flex: 1, textAlign: "center" }}>F8 · Cobrar</span>
          </div>
        </div>
      </div>

      {/* ---------- Modal de peso ---------- */}
      {pesoModal && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(2,6,23,.45)",
            display: "grid",
            placeItems: "center",
            zIndex: 50,
            padding: 16,
          }}
          onClick={() => setPesoModal(null)}
        >
          <div
            className="card"
            style={{ width: 380, boxShadow: "0 40px 80px -30px rgba(2,6,23,.7)" }}
            onClick={(e) => e.stopPropagation()}
          >
            <h3 style={{ fontSize: 15, fontWeight: 800, marginBottom: 2 }}>{pesoModal.nombre}</h3>
            <div className="muted" style={{ marginBottom: 14 }}>
              {formatMoney(Math.round(pesoModal.precio_venta * (1 + (Number(pesoModal.impuesto) || 0) / 100)))} por kilogramo{Number(pesoModal.impuesto) > 0 ? " (IVA incl.)" : ""}
            </div>

            <div style={{ fontSize: 12.5, fontWeight: 700, color: "var(--muted)", marginBottom: 5 }}>Peso (kg)</div>
            <div style={{ display: "flex", gap: 8 }}>
              <input
                type="number"
                step="0.001"
                min="0.001"
                autoFocus
                value={pesoVal}
                onChange={(e) => setPesoVal(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") agregarPesoModal();
                }}
                style={{ fontSize: 26, fontWeight: 800, flex: 1, textAlign: "right" }}
              />
              <button className="btn btn-secondary" onClick={leerBalanza} disabled={pesando} style={{ whiteSpace: "nowrap" }}>
                {pesando ? "…" : "⚖️ Báscula"}
              </button>
            </div>

            {Number(pesoVal) > 0 && (
              <div
                style={{
                  marginTop: 12,
                  padding: "12px 14px",
                  borderRadius: 12,
                  background: "var(--brand-soft)",
                  color: "var(--brand1)",
                  fontWeight: 800,
                  fontSize: 18,
                  display: "flex",
                  justifyContent: "space-between",
                }}
              >
                <span style={{ fontWeight: 600, fontSize: 13 }}>{Number(pesoVal)} kg</span>
                <span>{formatMoney((Number(pesoVal) || 0) * (Number(pesoModal.precio_venta) || 0) * (1 + (Number(pesoModal.impuesto) || 0) / 100))}</span>
              </div>
            )}

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginTop: 14 }}>
              <button className="btn btn-secondary" onClick={() => setPesoModal(null)}>
                Cancelar
              </button>
              <button className="btn" onClick={agregarPesoModal} disabled={!(Number(pesoVal) > 0)}>
                Agregar
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ---------- Selector de Comandas / Mesas ---------- */}
      {comandasModal && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,.6)", display: "grid", placeItems: "center", zIndex: 1200, padding: 20 }}>
          <div className="card" style={{ width: "min(680px, 100%)", maxHeight: "85vh", overflow: "auto" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
              <div>
                <h3 style={{ margin: 0, fontSize: 18, color: "var(--ink)" }}>🍽️ Mesas con Comandas Abiertas</h3>
                <p className="muted" style={{ margin: "3px 0 0", fontSize: 12.5 }}>
                  Selecciona una mesa para cargar sus consumos a la caja y cobrar la cuenta.
                </p>
              </div>
              <button className="btn btn-ghost" onClick={() => setComandasModal(false)}>✕</button>
            </div>

            {comandasLista.length === 0 ? (
              <div style={{ textAlign: "center", padding: "36px 16px", color: "var(--muted)" }}>
                <div style={{ fontSize: 40, marginBottom: 8 }}>🪑</div>
                <p>No hay comandas abiertas en este momento.</p>
                <p style={{ fontSize: 12 }}>Los pedidos realizados desde la carta digital o desde Restaurante aparecerán aquí.</p>
              </div>
            ) : (
              <div style={{ display: "grid", gap: 12 }}>
                {comandasLista.map((com) => {
                  const nombreMesa = mesasMapa[com.mesa_id] || `Mesa #${com.mesa_id}`;
                  const cantItems = (com.detalle || []).reduce((s, l) => s + Number(l.cantidad || 1), 0);
                  const totalCom = (com.detalle || []).reduce((s, l) => s + Number(l.precio || 0) * Number(l.cantidad || 1), 0);

                  return (
                    <div
                      key={com.id}
                      style={{
                        border: "1px solid var(--line)",
                        borderRadius: 12,
                        padding: "14px 16px",
                        background: "var(--card)",
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        gap: 14,
                        flexWrap: "wrap",
                      }}
                    >
                      <div style={{ flex: 1, minWidth: 200 }}>
                        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                          <span style={{ fontWeight: 800, fontSize: 16, color: "var(--brand1)" }}>{nombreMesa}</span>
                          <span className="badge" style={{ fontSize: 11 }}>{com.numero}</span>
                          {com.cliente && <span className="badge badge-info" style={{ fontSize: 10 }}>👤 {com.cliente}</span>}
                        </div>
                        <div style={{ fontSize: 12.5, color: "var(--muted)", lineHeight: 1.4 }}>
                          {(com.detalle || []).slice(0, 4).map((d) => `${d.cantidad}x ${d.producto || d.producto_id}`).join(", ")}
                          {(com.detalle || []).length > 4 && ` y ${(com.detalle || []).length - 4} más…`}
                        </div>
                      </div>

                      <div style={{ textAlign: "right" }}>
                        <div style={{ fontSize: 12, color: "var(--muted)" }}>{cantItems} ítems</div>
                        <div style={{ fontSize: 17, fontWeight: 800, color: "var(--ink)", marginBottom: 6 }}>
                          {formatMoney(com.total || totalCom)}
                        </div>
                        <button
                          className="btn btn-sm btn-primary"
                          style={{ fontWeight: 700 }}
                          onClick={() => cargarComandaEnPOS(com)}
                        >
                          Cargar al Carrito ➔
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      )}

      {/* ---------- Escáner de cámara ---------- */}
      {escaneando && <CamaraScan onDetect={agregarCodigo} onClose={() => setEscaneando(false)} />}
    </div>
  );
}

function CamaraScan({ onDetect, onClose }) {
  const vidRef = useRef(null);
  const [msg, setMsg] = useState("");
  const [noSoporte, setNoSoporte] = useState(false);
  const [done, setDone] = useState(false);

  async function leer(valor) {
    if (done) return;
    setDone(true);
    try {
      onDetect(valor);
    } finally {
      setTimeout(onClose, 250);
    }
  }

  useEffect(() => {
    let stream = null;
    let raf = 0;
    let det = null;

    (async () => {
      const B = window.BarcodeDetector;
      if (!B) {
        setNoSoporte(true);
        return;
      }
      try {
        det = new B({ formats: ["ean_13", "ean_8", "upc_a", "upc_e", "code_128", "code_39", "qr_code"] });
      } catch {
        det = new B();
      }
      try {
        stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" }, audio: false });
        if (vidRef.current) {
          vidRef.current.srcObject = stream;
          await vidRef.current.play();
        }
      } catch {
        setMsg("No se pudo acceder a la cámara. Verifica permisos.");
        return;
      }
      const tick = async () => {
        if (done) return;
        if (!vidRef.current) return;
        try {
          const codes = await det.detect(vidRef.current);
          if (codes.length > 0 && codes[0].rawValue) leer(codes[0].rawValue);
        } catch {}
        if (!done) raf = requestAnimationFrame(tick);
      };
      raf = requestAnimationFrame(tick);
    })();

    return () => {
      cancelAnimationFrame(raf);
      stream?.getTracks?.().forEach((t) => t.stop());
    };
  }, []);

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(2,6,23,.9)",
        display: "grid",
        placeItems: "center",
        zIndex: 1200,
        padding: 20,
      }}
      onClick={onClose}
    >
      <div className="card" style={{ width: "min(520px, 100%)", textAlign: "center" }} onClick={(e) => e.stopPropagation()}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
          <h3 style={{ fontSize: 16 }}>📷 Escanear código</h3>
          <button className="btn btn-ghost" onClick={onClose}>✕</button>
        </div>
        {noSoporte ? (
          <div style={{ padding: "18px 6px" }}>
            <div style={{ fontSize: 34, marginBottom: 8 }}>😕</div>
            <p style={{ fontSize: 13.5 }}>
              Tu navegador no soporta escaneo con cámara (BarcodeDetector). Usa el campo de código con un lector de barras o tipea el código.
            </p>
          </div>
        ) : (
          <>
            <video
              ref={vidRef}
              playsInline
              muted
              autoPlay
              style={{ width: "100%", borderRadius: 12, background: "#000", minHeight: 220, objectFit: "cover" }}
            />
            <p style={{ fontSize: 13, color: "var(--muted)", marginTop: 10 }}>
              Apunta al código de barras o QR del producto · se agrega solo
            </p>
          </>
        )}
        {msg && <div className="error">{msg}</div>}
        <div style={{ marginTop: 12 }}>
          <button className="btn btn-secondary" onClick={onClose} style={{ width: "100%" }}>Cerrar</button>
        </div>
      </div>
    </div>
  );
}