// src/api/client.ts
import axios from "axios";

const api = axios.create({ baseURL: "http://localhost:8000/api/v1" });

const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

api.interceptors.request.use(cfg => {
  const p = (cfg.params ??= {});
  // Если по ошибке положили UUID в source_ext_id → переложим в source_id
  if (typeof p.source_ext_id === "string" && UUID_RE.test(p.source_ext_id.trim())) {
    p.source_id = p.source_ext_id.trim();
    delete p.source_ext_id;
  }
  // Не шлём оба параметра одновременно
  if (p.source_id && p.source_ext_id) delete p.source_ext_id;
  return cfg;
});

export default api;
