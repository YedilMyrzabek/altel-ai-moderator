import {type FC, useEffect, useState } from "react";
import api from "../api/client";
import { PieChart, Pie, Cell, Tooltip } from "recharts";

const COLORS = ["#E6007E", "#E5E5E5"];

interface AggregateRow {
  platform: string;
  source_ext_id: string;
  source_title: string;
  spam_rate: number;
  toxic_rate: number;
  total_cnt: number;
}

const Dashboard: FC = () => {
  const [rows, setRows] = useState<AggregateRow[]>([]);

  useEffect(() => {
    api.get("/analytics/aggregates").then((res: any) => setRows(res.data.rows));
  }, []);

  return (
    <div className="max-w-7xl mx-auto p-8">
      <h1 className="text-3xl font-bold text-altel-dark mb-10">
        📊 Панель аналитики
      </h1>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
        {rows.map((row, idx) => (
          <div
            key={idx}
            className="bg-white shadow-lg rounded-2xl p-6 border border-gray-100 hover:shadow-xl transition"
          >
            <h2 className="font-bold text-xl text-altel-pink mb-3">
              {row.source_title}
            </h2>
            <p className="text-sm text-gray-500 mb-6">
              Всего комментариев: {row.total_cnt}
            </p>

            <div className="flex justify-center">
              <PieChart width={250} height={200}>
                <Pie
                  data={[
                    { name: "Спам", value: row.spam_rate * 100 },
                    { name: "Чистые", value: 100 - row.spam_rate * 100 },
                  ]}
                  cx="50%"
                  cy="50%"
                  outerRadius={70}
                  dataKey="value"
                  label
                >
                  {COLORS.map((color, index) => (
                    <Cell key={`cell-${index}`} fill={color} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default Dashboard;
