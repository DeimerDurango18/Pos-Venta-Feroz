import { lazy, Suspense } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import { useAuth } from "./contexts/AuthContext.jsx";
import { PlanProvider, usePlan } from "./contexts/PlanContext.jsx";
import Login from "./pages/Login.jsx";
import CambiarPassword from "./pages/CambiarPassword.jsx";
import Layout from "./components/Layout.jsx";
const Setup = lazy(() => import("./pages/Setup.jsx"));

// Carga diferida de módulos: separa el bundle inicial por página.
const Dashboard = lazy(() => import("./pages/Dashboard.jsx"));
const Productos = lazy(() => import("./pages/Productos.jsx"));
const Inventario = lazy(() => import("./pages/Inventario.jsx"));
const Ventas = lazy(() => import("./pages/Ventas.jsx"));
const PuntoVenta = lazy(() => import("./pages/PuntoVenta.jsx"));
const Caja = lazy(() => import("./pages/Caja.jsx"));
const Clientes = lazy(() => import("./pages/Clientes.jsx"));
const Proveedores = lazy(() => import("./pages/Proveedores.jsx"));
const Compras = lazy(() => import("./pages/Compras.jsx"));
const Cartera = lazy(() => import("./pages/Cartera.jsx"));
const Configuracion = lazy(() => import("./pages/Configuracion.jsx"));
const Reportes = lazy(() => import("./pages/Reportes.jsx"));
const Promociones = lazy(() => import("./pages/Promociones.jsx"));
const Facturacion = lazy(() => import("./pages/Facturacion.jsx"));
const Fidelizacion = lazy(() => import("./pages/Fidelizacion.jsx"));
const Apartados = lazy(() => import("./pages/Apartados.jsx"));
const Cotizaciones = lazy(() => import("./pages/Cotizaciones.jsx"));
const LinksPago = lazy(() => import("./pages/LinksPago.jsx"));
const Pedidos = lazy(() => import("./pages/Pedidos.jsx"));
const Restaurante = lazy(() => import("./pages/Restaurante.jsx"));
const Cocina = lazy(() => import("./pages/Cocina.jsx"));
const Menu = lazy(() => import("./pages/Menu.jsx"));
const MenuPublico = lazy(() => import("./pages/MenuPublico.jsx"));
const Seguridad = lazy(() => import("./pages/Seguridad.jsx"));
const Vendedores = lazy(() => import("./pages/Vendedores.jsx"));
const Sistema = lazy(() => import("./pages/Sistema.jsx"));
const Integraciones = lazy(() => import("./pages/Integraciones.jsx"));
const Offline = lazy(() => import("./pages/Offline.jsx"));

function Protected({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="spinner" />;
  if (!user) return <Navigate to="/login" replace />;
  if (localStorage.getItem("debe_cambiar_password") === "1") return <Navigate to="/cambiar" replace />;
  return children;
}

function CambiarPasswordGuard() {
  const { user, loading } = useAuth();
  if (loading) return <div className="spinner" />;
  if (!user) return <Navigate to="/login" replace />;
  if (localStorage.getItem("debe_cambiar_password") !== "1") return <Navigate to="/" replace />;
  return <CambiarPassword />;
}

function ModuloGuard({ modulo, children }) {
  const { plan, enabled } = usePlan();
  if (!plan) return <div className="spinner" />;
  if (!enabled(modulo)) return <Navigate to="/" replace />;
  return children;
}

function CargandoRuta() {
  return <div className="page"><div className="spinner" /></div>;
}

export default function App() {
  return (
    <PlanProvider>
      <Suspense fallback={<CargandoRuta />}>
        <Routes>
          <Route
            path="/cocina"
            element={
              <Protected>
                <Cocina />
              </Protected>
            }
          />
          <Route path="/login" element={<Login />} />
          <Route path="/setup" element={<Setup />} />
          <Route path="/cambiar" element={<CambiarPasswordGuard />} />
          <Route path="/carta" element={<MenuPublico />} />
          <Route path="/carta/:mesaId" element={<MenuPublico />} />
          <Route path="/menu-digital" element={<MenuPublico />} />
          <Route path="/publico/menu/:mesaId" element={<MenuPublico />} />
          <Route
            path="/"
            element={
              <Protected>
                <Layout />
              </Protected>
            }
          >
            <Route index element={<Dashboard />} />
            <Route path="productos" element={<ModuloGuard modulo="productos"><Productos /></ModuloGuard>} />
            <Route path="inventario" element={<ModuloGuard modulo="inventario"><Inventario /></ModuloGuard>} />
            <Route path="ventas" element={<ModuloGuard modulo="ventas"><Ventas /></ModuloGuard>} />
            <Route path="cotizaciones" element={<ModuloGuard modulo="ventas"><Cotizaciones /></ModuloGuard>} />
            <Route path="links" element={<ModuloGuard modulo="ventas"><LinksPago /></ModuloGuard>} />
            <Route path="pos" element={<ModuloGuard modulo="pos"><PuntoVenta /></ModuloGuard>} />
            <Route path="caja" element={<ModuloGuard modulo="caja"><Caja /></ModuloGuard>} />
            <Route path="clientes" element={<ModuloGuard modulo="clientes"><Clientes /></ModuloGuard>} />
            <Route path="proveedores" element={<ModuloGuard modulo="proveedores"><Proveedores /></ModuloGuard>} />
            <Route path="compras" element={<ModuloGuard modulo="compras"><Compras /></ModuloGuard>} />
            <Route path="cartera" element={<ModuloGuard modulo="cartera"><Cartera /></ModuloGuard>} />
            <Route path="configuracion" element={<Configuracion />} />
            <Route path="reportes" element={<ModuloGuard modulo="reportes"><Reportes /></ModuloGuard>} />
            <Route path="promociones" element={<ModuloGuard modulo="promociones"><Promociones /></ModuloGuard>} />
            <Route path="facturacion" element={<ModuloGuard modulo="facturacion"><Facturacion /></ModuloGuard>} />
            <Route path="fidelizacion" element={<ModuloGuard modulo="fidelizacion"><Fidelizacion /></ModuloGuard>} />
            <Route path="apartados" element={<ModuloGuard modulo="apartados"><Apartados /></ModuloGuard>} />
            <Route path="pedidos" element={<ModuloGuard modulo="domicilios"><Pedidos /></ModuloGuard>} />
            <Route path="restaurante" element={<ModuloGuard modulo="restaurante"><Restaurante /></ModuloGuard>} />
            <Route path="menu" element={<ModuloGuard modulo="restaurante"><Menu /></ModuloGuard>} />
            <Route path="seguridad" element={<Seguridad />} />
            <Route path="vendedores" element={<ModuloGuard modulo="vendedores"><Vendedores /></ModuloGuard>} />
            <Route path="sistema" element={<Sistema />} />
            <Route path="integraciones" element={<ModuloGuard modulo="integraciones"><Integraciones /></ModuloGuard>} />
            <Route path="offline" element={<ModuloGuard modulo="offline"><Offline /></ModuloGuard>} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Suspense>
    </PlanProvider>
  );
}