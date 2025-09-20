export default function ExportButtons() {
  const go = (fmt: "csv" | "xlsx" | "xml") => {
    // через vite proxy: /api -> backend
    window.open(`/api/v1/analytics/export?format=${fmt}&limit=1000`, "_blank");
  };
  return (
    <div className="flex items-center gap-3">
      <button onClick={() => go("csv")}  className="bg-pink-600 hover:bg-pink-700 text-white px-3 py-2 rounded">CSV</button>
      <button onClick={() => go("xlsx")} className="bg-pink-600 hover:bg-pink-700 text-white px-3 py-2 rounded">XLSX</button>
      <button onClick={() => go("xml")}  className="bg-pink-600 hover:bg-pink-700 text-white px-3 py-2 rounded">XML</button>
    </div>
  );
}
