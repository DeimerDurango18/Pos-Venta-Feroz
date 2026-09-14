import { useEffect, useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext.jsx";
import { usePlan } from "../contexts/PlanContext.jsx";
import { ITEMS, menuDePlan } from "../menus.js";

function useIsMobile() {
  const [mobile, setMobile] = useState(window.innerWidth <= 768);
  useEffect(() => {
    const onResize = () => setMobile(window.innerWidth <= 768);
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);
  return mobile;
}

export default function Layout() {
  const { user, logout } = useAuth();
  const { enabled, plan } = usePlan();
  const navigate = useNavigate();
  const [dark, setDark] = useState(document.documentElement.getAttribute("data-theme") === "dark");
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const isMobile = useIsMobile();

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", dark ? "dark" : "light");
    localStorage.setItem("tema", dark ? "oscuro" : "claro");
  }, [dark]);

  useEffect(() => {
    if (isMobile) setSidebarOpen(false);
  }, [isMobile]);

  const closeSidebar = () => setSidebarOpen(false);

  const iniciales = (user?.nombre || "U")
    .split(" ")
    .slice(0, 2)
    .map((s) => s[0])
    .join("")
    .toUpperCase();
  const hoy = new Date().toLocaleDateString("es-CO", {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
  });

  const sidebarVisible = !isMobile || sidebarOpen;
  const menu = menuDePlan(plan);

  return (
    <div style={{ display: "flex", minHeight: "100vh" }}>
      {isMobile && (
        <div
          className={`sidebar-overlay${sidebarOpen ? " visible" : ""}`}
          onClick={closeSidebar}
        />
      )}

      <aside
        className="sidebar"
        style={{
          width: 248,
          color: "var(--sidebar-ink)",
          background: "var(--sidebar-bg)",
          display: "flex",
          flexDirection: "column",
          padding: "18px 12px 14px",
          position: "sticky",
          top: 0,
          height: "100vh",
          transition: "background 0.25s ease, transform 0.25s ease, visibility 0.25s",
          zIndex: 150,
          ...(isMobile
            ? {
                position: "fixed",
                left: 0,
                top: 0,
                transform: sidebarOpen ? "translateX(0)" : "translateX(-100%)",
                visibility: sidebarOpen ? "visible" : "hidden",
                boxShadow: sidebarOpen ? "8px 0 30px rgba(0,0,0,0.3)" : "none",
              }
            : {}),
        }}
      >
        <div className="sidebar-brand">
          <div className="sidebar-logo">🛒</div>
          <div>
            <div className="sidebar-title">
              POS <span style={{ color: "var(--brand1)" }}>Feroz</span>
            </div>
            <div className="sidebar-sub">{menu.titulo}</div>
          </div>
        </div>

        <nav style={{ flex: 1, display: "flex", flexDirection: "column", gap: 3, overflowY: "auto" }}>
          {menu.secciones.map((sec) => {
            const visibles = sec.items.filter((key) => enabled(ITEMS[key]?.modulo));
            if (visibles.length === 0) return null;
            return (
              <div key={sec.titulo}>
                <div className="nav-sec">{sec.titulo}</div>
                {visibles.map((key) => {
                  const item = ITEMS[key];
                  return (
                    <NavLink
                      key={key}
                      to={item.to}
                      end={item.end}
                      className="nav-link"
                      onClick={closeSidebar}
                      style={({ isActive }) => ({
                        display: "flex",
                        alignItems: "center",
                        gap: 11,
                        padding: "9px 12px",
                        color: isActive ? "#fff" : "var(--nav-idle)",
                        background: isActive ? "var(--nav-active)" : "transparent",
                        fontWeight: isActive ? 700 : 500,
                        boxShadow: isActive ? "0 8px 18px -8px var(--nav-active-shadow)" : "none",
                      })}
                    >
                      <span style={{ fontSize: 16, width: 20, textAlign: "center" }}>{item.icon}</span>
                      {item.label}
                    </NavLink>
                  );
                })}
              </div>
            );
          })}
        </nav>

        <div className="sidebar-user">
          <div className="avatar">{iniciales}</div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 13.5, fontWeight: 700, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", color: "var(--sidebar-ink)" }}>
              {user?.nombre}
            </div>
            <div style={{ fontSize: 11.5, color: "var(--sidebar-muted)" }}>{user?.rol?.nombre || ""}</div>
          </div>
          <button
            className="btn btn-sm"
            style={{ background: "rgba(244,63,94,.16)", color: "#e11d48", boxShadow: "none", borderRadius: 10 }}
            onClick={() => {
              logout();
              navigate("/login");
            }}
            title="Cerrar sesión"
          >
            ⎋
          </button>
        </div>
      </aside>

      <main style={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0, maxHeight: "100vh", overflow: "auto" }}>
        <div className="topbar">
          <div style={{ display: "flex", alignItems: "center", gap: 8, minWidth: 0 }}>
            {isMobile && (
              <button
                onClick={() => setSidebarOpen(!sidebarOpen)}
                style={{
                  width: 36,
                  height: 36,
                  display: "grid",
                  placeItems: "center",
                  border: "1px solid var(--line)",
                  borderRadius: 10,
                  background: "var(--card)",
                  color: "var(--ink)",
                  fontSize: 18,
                  flexShrink: 0,
                }}
              >
                {sidebarOpen ? "✕" : "☰"}
              </button>
            )}
            <span className="chip" style={{ textTransform: "capitalize", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
              🏪 {plan ? `${plan.modelo ?? plan.tipo_negocio ?? "—"} · NIT ${plan.nit}` : "Cargando plan..."}
            </span>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 8, flexShrink: 0 }}>
            {!isMobile && <span className="chip">📅 {hoy}</span>}
            <button className="theme-toggle" onClick={() => setDark(!dark)} title={dark ? "Modo claro" : "Modo oscuro"}>
              {dark ? "☀️" : "🌙"}
            </button>
          </div>
        </div>
        <Outlet />
      </main>
    </div>
  );
}
