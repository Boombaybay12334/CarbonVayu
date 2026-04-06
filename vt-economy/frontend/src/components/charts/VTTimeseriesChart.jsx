import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

const strokeByColor = {
  emerald: "#10b981",
  amber: "#f59e0b",
  red: "#ef4444",
  sky: "#0ea5e9",
};

export default function VTTimeseriesChart({ data, title = "VT Timeseries", color = "emerald" }) {
  if (!data || data.length === 0) {
    return (
      <section className="rounded-xl shadow-md p-4 bg-slate-800 border border-slate-700">
        <h3 className="text-slate-100 font-semibold mb-4">{title}</h3>
        <div className="h-64 rounded-lg bg-slate-700/60 grid place-items-center text-slate-400">
          No data yet
        </div>
      </section>
    );
  }

  return (
    <section className="rounded-xl shadow-md p-4 bg-slate-800 border border-slate-700">
      <h3 className="text-slate-100 font-semibold mb-4">{title}</h3>
      <div className="h-72 min-w-0">
        <ResponsiveContainer width="100%" height="100%" minWidth={280} minHeight={220}>
          <LineChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
            <XAxis dataKey="year" stroke="#94a3b8" />
            <YAxis stroke="#94a3b8" />
            <Tooltip contentStyle={{ backgroundColor: "#0f172a", borderColor: "#334155" }} />
            <Line
              type="monotone"
              dataKey="vt_score"
              stroke={strokeByColor[color] ?? strokeByColor.emerald}
              strokeWidth={3}
              dot={{ r: 4 }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}
