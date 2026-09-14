import { createContext, useContext, useEffect, useState, useCallback } from "react";
import api from "../api.js";
import { useAuth } from "./AuthContext.jsx";

const PlanContext = createContext(null);

export function PlanProvider({ children }) {
  const { user } = useAuth();
  const [plan, setPlan] = useState(null);

  const recargar = useCallback(async () => {
    try {
      const p = await api("/configuracion/plan");
      setPlan(p);
    } catch {
      setPlan(null);
    }
  }, []);

  useEffect(() => {
    if (user) recargar();
    else setPlan(null);
  }, [user, recargar]);

  const enabled = (modulo) => !plan || (plan.modulos || []).includes(modulo);

  return (
    <PlanContext.Provider value={{ plan, recargar, enabled }}>
      {children}
    </PlanContext.Provider>
  );
}

export const usePlan = () => useContext(PlanContext);