import { useState } from "react";
import api from "../api/client";

export default function ParserForm() {
  const [url, setUrl] = useState("");
  const [max, setMax] = useState(200);
  const [job, setJob] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  const start = async () => {
    if (!url.trim()) { alert("Введите YouTube URL"); return; }
    setLoading(true);
    try {
      const res = await api.post("/parser/start", { url, max_comments: max });
      setJob(res.data);
    } catch (e: any) {
      console.error(e);
      alert("Ошибка запуска парсинга");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-white rounded-xl shadow p-6">
      <h2 className="text-xl font-semibold mb-4">Запуск парсинга YouTube</h2>

      <div className="space-y-3">
        <input
          className="border rounded w-full p-2"
          placeholder="https://www.youtube.com/watch?v=..."
          value={url}
          onChange={e => setUrl(e.target.value)}
        />

        <div className="flex items-center gap-3">
          <label className="text-sm text-gray-600">Max comments</label>
          <input
            type="number"
            min={1}
            className="border rounded p-2 w-24"
            value={max}
            onChange={e => setMax(parseInt(e.target.value || "0", 10))}
          />

          <button
            onClick={start}
            disabled={loading}
            className="bg-pink-600 hover:bg-pink-700 text-white px-4 py-2 rounded"
          >
            {loading ? "Запускаю..." : "Старт"}
          </button>
        </div>

        {job && (
          <div className="text-sm text-gray-700">
            <div><b>Job:</b> {job.job_id}</div>
            <div><b>Status:</b> {job.status}</div>
          </div>
        )}
      </div>
    </div>
  );
}
