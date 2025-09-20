import { useEffect, useMemo, useState } from "react";
import api from "../api/client";

type Item = {
  id: string;
  author_name: string;
  text_raw: string;
  sentiment?: string;
  is_spam?: boolean;
  text_reply?: string;
};

type JobStatus = {
  job_id: string;
  status: "queued" | "running" | "done" | "error";
  // Под себя: добавь то, что реально отдаёт твой /analytics/job-status.
  // Главное — чтобы можно было достать source_id или ext_id видео.
  sources?: Array<{ id: string; ext_id?: string }>;
};

const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export default function CommentsTable() {
  const [input, setInput] = useState("");
  const [items, setItems] = useState<Item[]>([]);
  const [loading, setLoading] = useState(false);
  const [hint, setHint] = useState<"empty" | "ext" | "source_id" | "job_id">("empty");

  const detectKind = useMemo<"empty" | "uuid" | "ext">(() => {
    const v = input.trim();
    if (!v) return "empty";
    return UUID_RE.test(v) ? "uuid" : "ext";
  }, [input]);

  useEffect(() => {
    if (detectKind === "empty") setHint("empty");
    else if (detectKind === "ext") setHint("ext");
    else setHint("source_id"); // по умолчанию UUID считаем source_id; если не найдём — попробуем job_id
  }, [detectKind]);

  const load = async () => {
    setLoading(true);
    try {
      const v = input.trim();
      const base = { limit: 100 };

      // 1) Ничего не введено → без фильтра
      if (!v) {
        const res = await api.get("/comments", { params: base });
        setItems(res.data.items || res.data || []);
        return;
      }

      // 2) Внешний id (например, T2DemoVid02)
      if (detectKind === "ext") {
        setHint("ext");
        const res = await api.get("/comments", { params: { ...base, source_ext_id: v } });
        setItems(res.data.items || res.data || []);
        return;
      }

      // 3) UUID → сперва пробуем как source_id
      setHint("source_id");
      let res = await api.get("/comments", { params: { ...base, source_id: v } });
      let items: Item[] = res.data.items || res.data || [];

      // 3a) Если пусто, попробуем трактовать UUID как job_id и резолвим source
      if (!items.length) {
        setHint("job_id");
        // Получаем job-status (из него берём первый source)
        const j = await api.get("/analytics/job-status", { params: { job_id: v } });
        const job: JobStatus = j.data;

        const source = job?.sources?.[0];
        if (source?.id) {
          // Лучше фильтровать по source_id
          res = await api.get("/comments", { params: { ...base, source_id: source.id } });
          items = res.data.items || res.data || [];
        } else if (source?.ext_id) {
          // Либо по source_ext_id, если нет UUID
          res = await api.get("/comments", { params: { ...base, source_ext_id: source.ext_id } });
          items = res.data.items || res.data || [];
        }
      }

      setItems(items);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="bg-white rounded-xl shadow p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-semibold">Комментарии</h3>
        <div className="flex items-center gap-2">
          <input
            className="border rounded p-2"
            placeholder="Введите T2DemoVid02, source UUID или job UUID"
            value={input}
            onChange={(e) => setInput(e.target.value)}
          />
          <span className="text-xs text-gray-500">
            Отправлю:{" "}
            {hint === "ext"
              ? "source_ext_id"
              : hint === "source_id"
              ? "source_id"
              : hint === "job_id"
              ? "job_id → (auto-resolve) → source_id/source_ext_id"
              : "без фильтра"}
          </span>
          <button onClick={load} className="bg-gray-800 text-white px-3 py-2 rounded">
            Обновить
          </button>
        </div>
      </div>

      {loading ? (
        <div className="text-gray-500">Загружаю…</div>
      ) : (
        <table className="w-full text-sm border">
          <thead className="bg-gray-50">
            <tr>
              <th className="p-2 border text-left">Автор</th>
              <th className="p-2 border text-left">Текст</th>
              <th className="p-2 border">Spam</th>
              <th className="p-2 border">Sentiment</th>
              <th className="p-2 border text-left">Ответ</th>
            </tr>
          </thead>
          <tbody>
            {items.map((c) => (
              <tr key={c.id} className="align-top">
                <td className="p-2 border">{c.author_name}</td>
                <td className="p-2 border max-w-[520px]">{c.text_raw}</td>
                <td className="p-2 border">{c.is_spam ? "Да" : "—"}</td>
                <td className="p-2 border">{c.sentiment || "—"}</td>
                <td className="p-2 border max-w-[520px]">{c.text_reply || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
