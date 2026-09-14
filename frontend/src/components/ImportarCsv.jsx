import { useRef, useState } from "react";
import api from "../api.js";

export default function ImportarCsv({ path, etiqueta = "Importar CSV", onOk }) {
  const input = useRef(null);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  async function handle(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    setMsg("");
    setErr("");
    const fd = new FormData();
    fd.append("archivo", file);
    try {
      const token = localStorage.getItem("token");
      const res = await fetch(`/api${path}`, { method: "POST", body: fd, headers: token ? { Authorization: `Bearer ${token}` } : {} });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data?.detail || `Error ${res.status}`);
      setMsg(`OK: ${data.creados ?? 0} creados, ${data.actualizados ?? 0} actualizados`);
      onOk?.();
    } catch (er) {
      setErr(er.message);
    } finally {
      e.target.value = "";
    }
  }

  return (
    <div style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
      <button className="btn btn-secondary" onClick={() => input.current?.click()}>{etiqueta}</button>
      <input ref={input} type="file" accept=".csv,text/csv" style={{ display: "none" }} onChange={handle} />
      {msg && <span className="badge-success" style={{ padding: "4px 8px", borderRadius: 6 }}>{msg}</span>}
      {err && <span style={{ color: "#dc2626", fontSize: 12 }}>{err}</span>}
    </div>
  );
}