import type {FC} from "react";

const Reports: FC = () => {
  const handleExport = (fmt: string) => {
    window.open(`/api/v1/analytics/export?format=${fmt}`, "_blank");
  };

  return (
    <div className="max-w-3xl mx-auto p-8">
      <h1 className="text-2xl font-bold text-altel-dark mb-6">📑 Экспорт отчётов</h1>
      <div className="grid grid-cols-3 gap-4">
        {["CSV", "XLSX", "XML"].map((fmt) => (
          <button
            key={fmt}
            className="bg-altel-pink hover:bg-pink-700 text-white py-3 rounded-xl font-semibold shadow-md transition"
            onClick={() => handleExport(fmt.toLowerCase())}
          >
            {fmt}
          </button>
        ))}
      </div>
    </div>
  );
};

export default Reports;
