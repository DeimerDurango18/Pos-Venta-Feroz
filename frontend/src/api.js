const BASE = "/api";

export async function api(path, options = {}) {
  const token = localStorage.getItem("token");
  const headers = {
    "Content-Type": "application/json",
    ...(options.headers || {}),
  };
  if (token) headers.Authorization = `Bearer ${token}`;

  const res = await fetch(`${BASE}${path}`, { ...options, headers });

  if (res.status === 401 && !path.startsWith("/auth/login") && !path.startsWith("/publico") && !options.public) {
    localStorage.removeItem("token");
    localStorage.removeItem("user");
    localStorage.removeItem("debe_cambiar_password");
    window.location.href = "/login";
    throw new Error("Sesión expirada");
  }

  const text = await res.text();
  let data = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = text;
  }

  if (!res.ok) {
    if (res.status === 403 && data?.detail === "Debe cambiar la contraseña") {
      localStorage.setItem("debe_cambiar_password", "1");
      window.location.href = "/cambiar";
    }
    throw new Error(data?.detail || `Error ${res.status}`);
  }
  return data;
}

export async function downloadCsv(path, nombre) {
  await downloadFile(path, `${nombre}.csv`);
}

export async function downloadFile(path, filename) {
  const token = localStorage.getItem("token");
  const headers = {};
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(`${BASE}${path}`, { headers });
  if (!res.ok) throw new Error(`Error ${res.status}`);
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export async function openWindow(path) {
  const token = localStorage.getItem("token");
  const headers = {};
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(`${BASE}${path}`, { headers });
  if (!res.ok) throw new Error(`Error ${res.status}`);
  const blob = await res.blob();
  const url = URL.createObjectURL(new Blob([blob], { type: "text/html" }));
  window.open(url, "_blank");
}

export default api;