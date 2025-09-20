import { useEffect, useState } from "react";
import type {AxiosResponse} from "axios";
import api from "../api/client";

type Row = {
  platform: string;
  source_ext_id: string;
  source_title: string;
  total_cnt: number;
  done_cnt: number;
  spam_rate: number;
  toxic_rate: number;
  avg_spam_score?: number | null;
  avg_tox_score?: number | null;
};

export default function AggregatesCard() {
  const [rows, setRows] = useState<Row[]>([]);
  const [loading, setLoading] = useState(true);

    useEffect(() => {
      api.get("/analytics/aggregates")
        .then((res: AxiosResponse<{ rows: Row[] }>) => {
          setRows(res.data.rows || []);
        })
        .finally(() => setLoading(false));
    }, []);

  if (loading) return <div className="text-gray-500">Загружаю агрегаты…</div>;
  if (!rows.length) return <div className="text-gray-500">Нет данных</div>;

  return (
    <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
      {rows.map((r) => (
        <div key={r.source_ext_id} className="bg-white rounded-xl shadow p-4">
          <div className="text-xs uppercase text-gray-500">{r.platform}</div>
          <div className="font-semibold">{r.source_title}</div>
          <div className="mt-2 text-sm text-gray-700 space-y-1">
            <div>Всего: {r.total_cnt} / Done: {r.done_cnt}</div>
            <div>Spam rate: {(r.spam_rate * 100).toFixed(1)}%</div>
            <div>Toxic rate: {(r.toxic_rate * 100).toFixed(1)}%</div>
            {r.avg_spam_score != null && <div>Avg spam: {r.avg_spam_score?.toFixed?.(3)}</div>}
            {r.avg_tox_score  != null && <div>Avg tox:  {r.avg_tox_score?.toFixed?.(3)}</div>}
          </div>
        </div>
      ))}
    </div>
  );
}
