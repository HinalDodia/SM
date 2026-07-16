import React, { useState } from "react";
import {
  Chart as ChartJS,
  LineElement,
  CategoryScale,
  LinearScale,
  PointElement,
  Tooltip,
  Legend,
  Filler,
} from "chart.js";
import { API_URL } from "./config";
import { Line } from "react-chartjs-2";
import { motion } from "framer-motion";
import { BarChart3, Activity, Cpu } from "lucide-react";

ChartJS.register(LineElement, CategoryScale, LinearScale, PointElement, Tooltip, Legend, Filler);

export default function StockPrediction() {
  const [symbol, setSymbol] = useState("");
  const [hasResult, setHasResult] = useState(false);
  const [logs, setLogs] = useState("");
  const [predData, setPredData] = useState(null);
  const [maData, setMaData] = useState(null);
  const [ma100Data, setMa100Data] = useState(null);

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { labels: { color: "#cbd5e1", boxWidth: 14 } }, tooltip: { intersect: false, mode: "index" } },
    elements: { point: { radius: 0 } },
    scales: {
      x: { type: "category", grid: { color: "rgba(148,163,184,0.2)" }, ticks: { color: "#94a3b8", maxRotation: 0 } },
      y: { type: "linear", grid: { color: "rgba(148,163,184,0.2)" }, ticks: { color: "#94a3b8" } },
    },
  };

  const handlePredict = async () => {
    if (!symbol) return;
    try {
      const res = await fetch(`${API_URL}/predict-stock/${symbol.toUpperCase()}`);
      const data = await res.json();

      if (!res.ok) {
        setLogs(data?.error || "Prediction failed with server error.");
        setHasResult(true);
        return;
      }

     setPredData({
  labels: data.dates,
  datasets: [
    { 
      label: "Predicted Stock Price", 
      data: data.predictions, 
      borderColor: "#ef4444", 
      borderDash: [6, 6], 
      borderWidth: 2,
      tension: 0.25,
      spanGaps: true, // Connects history to the prediction
      order: 2 // Draws this first
    },
    { 
      label: "Actual Stock Price", 
      data: data.actual, 
      borderColor: "#60a5fa", 
      borderWidth: 3, // Slightly thicker
      tension: 0.25,
      spanGaps: false, // Stops the blue line at today
      order: 1 // Draws this on top of the red line
    },
  ],
});

      setMaData({
        labels: data.dates,
        datasets: [
          { label: "Actual Price", data: data.actual, borderColor: "#60a5fa", tension: 0.25 },
          { label: "100-Day MA", data: data.ma100, borderColor: "#f59e0b", tension: 0.25 },
          { label: "200-Day MA", data: data.ma200, borderColor: "#22c55e", tension: 0.25 },
        ],
      });

      setMa100Data({
        labels: data.dates,
        datasets: [
          { label: "Actual Price", data: data.actual, borderColor: "#60a5fa", tension: 0.25 },
          { label: "100-Day MA", data: data.ma100, borderColor: "#f59e0b", tension: 0.25 },
        ],
      });

      setLogs(data.logs || "Prediction completed successfully.");
      setHasResult(true);
    } catch (err) {
      console.error(err);
      setLogs("Failed to fetch prediction. Check console.");
      setHasResult(true);
    }
  };

  const Card = ({ title, icon, children }) => (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
      className="bg-[#1e293b] p-6 rounded-2xl shadow-lg hover:shadow-xl transition"
    >
      <div className="flex items-center gap-3 mb-4 border-b border-slate-700 pb-2">
        {icon}
        <h2 className="text-base font-semibold text-slate-200">{title}</h2>
      </div>
      {children}
    </motion.div>
  );

  return (
    <div className="min-h-screen text-white p-8 bg-gradient-to-b from-[#05080a] to-[#0b0f12]">
      <motion.h1
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6 }}
        className="text-4xl font-extrabold text-cyan-400 text-center mb-2"
      >
        Stock Price Predictor
      </motion.h1>
      <p className="text-center text-slate-400 mb-10 text-lg">
        AI-powered stock analysis & prediction dashboard
      </p>

      <div className="flex justify-center mb-12">
        <input
          type="text"
          placeholder="Enter stock symbol (e.g. AAPL)"
          value={symbol}
          onChange={(e) => setSymbol(e.target.value)}
          className="w-full max-w-md px-4 py-3 rounded-l-xl bg-[#1e293b] text-white border border-slate-600 focus:ring-2 focus:ring-cyan-500 focus:outline-none"
        />
        <button
          onClick={handlePredict}
          className="px-6 py-3 bg-cyan-500 hover:bg-cyan-600 rounded-r-xl font-semibold transition"
        >
          Predict
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-8 mb-12">
        <Card title={`${symbol.toUpperCase()} Price Prediction`} icon={<BarChart3 size={20} className="text-cyan-400" />}>
          <div className="h-72 flex items-center justify-center text-slate-500">
            {hasResult && predData ? <Line data={predData} options={options} /> : "No data yet"}
          </div>
        </Card>
        <Card title={`${symbol.toUpperCase()} 100 & 200 Day MAs`} icon={<Activity size={20} className="text-yellow-400" />}>
          <div className="h-72 flex items-center justify-center text-slate-500">
            {hasResult && maData ? <Line data={maData} options={options} /> : "No data yet"}
          </div>
        </Card>
        <Card title={`${symbol.toUpperCase()} 100 Day MA`} icon={<Cpu size={20} className="text-green-400" />}>
          <div className="h-72 flex items-center justify-center text-slate-500">
            {hasResult && ma100Data ? <Line data={ma100Data} options={options} /> : "No data yet"}
          </div>
        </Card>
      </div>

      <Card title="Model Output Console" icon={<Cpu size={20} className="text-cyan-300" />}>
        <div className="bg-black text-green-400 font-mono p-5 rounded-lg h-80 overflow-y-auto text-sm whitespace-pre-wrap">
          {logs || "Logs will appear here after prediction..."}
        </div>
      </Card>
      

    </div>
    
  );
}
