import { Routes, Route, Navigate } from "react-router-dom";
import { useAuth } from "./contexts/AuthContext.jsx";
import { PlanProvider, usePlan } from "./contexts/PlanContext.jsx";
import Login from "./pages/Login.jsx";
import CambiarPassword from "./pages/CambiarPassword.jsx";
import Layout from "./components/Layout.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import Productos from "./pages/Productos.jsx";
import Inventario from "./pages/Inventario.jsx";
import Ventas from "./pages/Ventas.jsx";
import PuntoVenta from "./pages/PuntoVenta.jsx";
import Caja from "./pages/Caja.jsx";
import Clientes from "./pages/Clientes.jsx";
import Proveedores from "./pages/Proveedores.jsx";
import Compras from "./pages/Compras.jsx";
import Cartera from "./pages/Cartera.jsx";
import Configuracion from "./pages/Configuracion.jsx";
import Reportes from "./pages/Reportes.jsx";
import Promociones from "./pages/Promociones.jsx";
import Facturacion from "./pages/Facturacion.jsx";
import Fidelizacion from "./pages/Fidelizacion.jsx";
import Apartados from "./pages/Apartados.jsx";
import Pedidos from "./pages/Pedidos.jsx";
import Restaurante from "./pages/Restaurante.jsx";
import Cocina from "./pages/Cocina.jsx";
import Menu from "./pages/Menu.jsx";
import Seguridad from "./pages/Seguridad.jsx";
import Vendedores from "./pages/Vendedores.jsx";
import Sistema from "./pages/Sistema.jsx";
import Integraciones from "./pages/Integraciones.jsx";
import Offline from "./pages/Offline.jsx";

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

export default function App() {
  return (
    <PlanProvider>
      <Routes>
        <Route
          path="/cocina"
          element={
            <Protected>
              <Cocina />
            </Protected>
          }
        />
        <Route
          path="/login"
          element={<Login />}
        />
        <Route
          path="/cambiar"
          element={
            <CambiarPasswordGuard />
          }
        />
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
    </PlanProvider>
  );
}