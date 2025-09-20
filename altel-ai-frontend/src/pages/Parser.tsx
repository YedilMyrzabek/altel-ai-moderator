import { useState } from "react";
import axios from "axios";

export default function ParserPage() {
  const [url, setUrl] = useState("");
  const [, setJobId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [comments, setComments] = useState<any[]>([]);
  const [status, setStatus] = useState("idle");

  async function startParsing() {
    setLoading(true);
    const res = await axios.post("http://localhost:8000/api/v1/parser/start", {
      url,
      max_comments: 500,
    });
    setJobId(res.data.job_id);
    pollStatus(res.data.job_id);
  }

  async function pollStatus(jobId: string) {
    const interval = setInterval(async () => {
      const res = await axios.get(
        `http://localhost:8000/api/v1/analytics/job-status?job_id=${jobId}`
      );
      if (res.data.status === "done") {
        clearInterval(interval);
        setStatus("done");
        loadComments(res.data.job_id);
      }
    }, 3000);
  }

  async function loadComments(jobId: string) {
    const res = await axios.get(
      `http://localhost:8000/api/v1/comments?source_ext_id=${jobId}&limit=100`
    );
    setComments(res.data.items);
    setLoading(false);
  }

  return (
    <div className="p-6">
      <h1 className="text-xl font-bold mb-4">🎥 Парсер YouTube</h1>

      <div className="flex gap-2 mb-6">
        <input
          type="text"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="Введите ссылку на видео"
          className="border p-2 rounded w-full"
        />
        <button
          onClick={startParsing}
          disabled={loading}
          className="bg-blue-600 text-white px-4 py-2 rounded"
        >
          🚀 Запустить
        </button>
      </div>

      {loading && <p className="text-gray-600">⏳ Парсинг комментариев...</p>}

      {status === "done" && (
        <div>
          <h2 className="text-lg font-semibold mb-4">✅ Комментарии</h2>
          <table className="w-full border">
            <thead>
              <tr className="bg-gray-100">
                <th className="p-2">Автор</th>
                <th className="p-2">Комментарий</th>
                <th className="p-2">Анализ</th>
                <th className="p-2">Ответ</th>
              </tr>
            </thead>
            <tbody>
              {comments.map((c) => (
                <tr key={c.comment_id} className="border-t">
                  <td className="p-2">{c.author_name}</td>
                  <td className="p-2">{c.comment_text}</td>
                  <td className="p-2">
                    {c.is_spam ? "🚫 Спам" : "✅ Чисто"} <br />
                    Sentiment: {c.sentiment}
                  </td>
                  <td className="p-2">{c.text_reply || "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
