import { createContext, useContext, useEffect, useState } from "react";
import api from "../api.js";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem("user"));
    } catch {
      return null;
    }
  });
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (token && !user) {
      setLoading(true);
      api("/auth/me")
        .then((me) => {
          setUser(me);
          localStorage.setItem("user", JSON.stringify(me));
          localStorage.setItem("debe_cambiar_password", me.debe_cambiar_password ? "1" : "0");
        })
        .catch(() => {
          localStorage.removeItem("token");
          localStorage.removeItem("user");
          localStorage.removeItem("debe_cambiar_password");
          setUser(null);
        })
        .finally(() => setLoading(false));
    }
  }, []);

  async function login(username, password) {
    const data = await api("/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    });
    localStorage.setItem("token", data.access_token);
    localStorage.setItem("debe_cambiar_password", data.debe_cambiar_password ? "1" : "0");
    const me = await api("/auth/me");
    setUser(me);
    localStorage.setItem("user", JSON.stringify(me));
    return me;
  }

  function logout() {
    localStorage.removeItem("token");
    localStorage.removeItem("user");
    localStorage.removeItem("debe_cambiar_password");
    setUser(null);
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}