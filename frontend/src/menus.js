export const ITEMS = {
  dashboard: { to: "/", label: "Dashboard", icon: "🏠", end: true, modulo: "dashboard" },
  pos: { to: "/pos", label: "Punto de Venta", icon: "🛒", modulo: "pos" },
  ventas: { to: "/ventas", label: "Ventas", icon: "💳", modulo: "ventas" },
  caja: { to: "/caja", label: "Caja", icon: "💰", modulo: "caja" },
  restaurante: { to: "/restaurante", label: "Mesas", icon: "🍽️", modulo: "restaurante" },
  cocina: { to: "/cocina", label: "Pantalla Cocina", icon: "👨‍🍳", modulo: "restaurante" },
  menuCarta: { to: "/menu", label: "Menú (Carta)", icon: "📋", modulo: "restaurante" },
  domicilios: { to: "/pedidos", label: "Pedidos & Domicilios", icon: "🛵", modulo: "domicilios" },
  productos: { to: "/productos", label: "Productos", icon: "📦", modulo: "productos" },
  inventario: { to: "/inventario", label: "Inventario", icon: "📚", modulo: "inventario" },
  compras: { to: "/compras", label: "Compras", icon: "🧺", modulo: "compras" },
  proveedores: { to: "/proveedores", label: "Proveedores", icon: "🏭", modulo: "proveedores" },
  promociones: { to: "/promociones", label: "Promociones", icon: "🎁", modulo: "promociones" },
  clientes: { to: "/clientes", label: "Clientes", icon: "👥", modulo: "clientes" },
  cartera: { to: "/cartera", label: "Cartera", icon: "📑", modulo: "cartera" },
  vendedores: { to: "/vendedores", label: "Vendedores", icon: "🎯", modulo: "vendedores" },
  fidelizacion: { to: "/fidelizacion", label: "Fidelización", icon: "⭐", modulo: "fidelizacion" },
  apartados: { to: "/apartados", label: "Apartados", icon: "🔒", modulo: "apartados" },
  facturacion: { to: "/facturacion", label: "Facturación DIAN", icon: "🧾", modulo: "facturacion" },
  reportes: { to: "/reportes", label: "Reportes", icon: "📈", modulo: "reportes" },
  seguridad: { to: "/seguridad", label: "Seguridad", icon: "🛡️", modulo: "seguridad" },
  integraciones: { to: "/integraciones", label: "Integraciones", icon: "🔌", modulo: "integraciones" },
  offline: { to: "/offline", label: "Offline", icon: "📴", modulo: "offline" },
  configuracion: { to: "/configuracion", label: "Configuración", icon: "⚙️", modulo: "configuracion" },
  sistema: { to: "/sistema", label: "Sistema", icon: "🐞", modulo: "sistema" },
};

const MENUS = {
  restaurante: {
    titulo: "Restaurante",
    secciones: [
      { titulo: "Operación", items: ["dashboard", "restaurante", "cocina", "domicilios"] },
      { titulo: "Punto de venta", items: ["pos", "menuCarta", "productos", "promociones"] },
      { titulo: "Comercial", items: ["ventas", "clientes", "fidelizacion", "vendedores"] },
      { titulo: "Soporte", items: ["caja", "inventario", "reportes", "facturacion", "seguridad", "integraciones", "configuracion", "sistema"] },
    ],
  },
  bar: {
    titulo: "Bar / Restobar",
    secciones: [
      { titulo: "Operación", items: ["dashboard", "restaurante", "cocina", "domicilios"] },
      { titulo: "Barra", items: ["pos", "menuCarta", "productos", "promociones"] },
      { titulo: "Comercial", items: ["ventas", "clientes", "fidelizacion", "vendedores"] },
      { titulo: "Soporte", items: ["caja", "inventario", "reportes", "facturacion", "seguridad", "integraciones", "configuracion", "sistema"] },
    ],
  },
  ferreteria: {
    titulo: "Ferretería",
    secciones: [
      { titulo: "Operación", items: ["dashboard", "pos", "ventas", "caja"] },
      { titulo: "Almacén", items: ["productos", "inventario", "compras", "proveedores"] },
      { titulo: "Comercial", items: ["clientes", "cartera", "vendedores", "promociones"] },
      { titulo: "Soporte", items: ["facturacion", "reportes", "seguridad", "integraciones", "configuracion", "sistema"] },
    ],
  },
  distribuidora: {
    titulo: "Distribuidora / Mayorista",
    secciones: [
      { titulo: "Operación", items: ["dashboard", "pos", "ventas", "caja"] },
      { titulo: "Almacén", items: ["productos", "inventario", "compras", "proveedores"] },
      { titulo: "Comercial", items: ["clientes", "cartera", "apartados", "vendedores", "promociones"] },
      { titulo: "Soporte", items: ["facturacion", "reportes", "seguridad", "integraciones", "configuracion", "sistema"] },
    ],
  },
  minimarket: {
    titulo: "Minimarket / Tienda",
    secciones: [
      { titulo: "Operación", items: ["dashboard", "pos", "caja"] },
      { titulo: "Tienda", items: ["productos", "inventario", "promociones", "compras"] },
      { titulo: "Comercial", items: ["clientes", "ventas", "cartera", "fidelizacion", "vendedores"] },
      { titulo: "Soporte", items: ["facturacion", "reportes", "seguridad", "integraciones", "configuracion", "sistema"] },
    ],
  },
  general: {
    titulo: "Negocio",
    secciones: [
      { titulo: "Operación", items: ["dashboard", "pos", "ventas", "caja", "restaurante", "cocina", "menuCarta", "domicilios"] },
      { titulo: "Catálogo", items: ["productos", "inventario", "compras", "proveedores", "promociones"] },
      { titulo: "Comercial", items: ["clientes", "cartera", "vendedores", "fidelizacion", "apartados"] },
      { titulo: "Empresa", items: ["facturacion", "reportes", "seguridad", "integraciones", "offline", "configuracion", "sistema"] },
    ],
  },
};

const POR_MODELO = {
  1: "restaurante",
  2: "ferreteria",
  3: "minimarket",
  4: "bar",
  5: "distribuidora",
  6: "general",
};

export function tipoMenu(plan) {
  if (!plan) return "general";
  if (plan.modelo && POR_MODELO[plan.modelo]) return POR_MODELO[plan.modelo];
  const t = String(plan.tipo_negocio || "").toLowerCase();
  return MENUS[t] ? t : "general";
}

export function menuDePlan(plan) {
  return MENUS[tipoMenu(plan)] || MENUS.general;
}

export function menusOrdenados() {
  return MENUS;
}