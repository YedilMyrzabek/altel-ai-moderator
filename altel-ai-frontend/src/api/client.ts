// src/api/client.ts
import axios from "axios";

const API_BASE =
  import.meta.env.VITE_API_URL || "http://localhost:8000"; // берём из env, иначе локалка

const api = axios.create({
  baseURL: `${API_BASE}/api/v1`,
  timeout: 15000,
});

const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

api.interceptors.request.use(cfg => {
  const p = (cfg.params ??= {});
  if (typeof p.source_ext_id === "string" && UUID_RE.test(p.source_ext_id.trim())) {
    p.source_id = p.source_ext_id.trim();
    delete p.source_ext_id;
  }
  if (p.source_id && p.source_ext_id) delete p.source_ext_id;
  return cfg;
});

console.log("[API] baseURL =", api.defaults.baseURL);

export default api;
