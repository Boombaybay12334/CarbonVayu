import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Cell,
} from "recharts";

/* 🔥 CUSTOM TOOLTIP (robust) */
const CustomTooltip = ({ active, payload, label }) => {
  if (active && payload && payload.length) {
    const raw = payload[0]?.value;
    const value = typeof raw === "number" && !isNaN(raw) ? raw.toFixed(2) : raw ?? "—";
    return (
      <div className="bg-slate-950 border border-slate-700 px-4 py-2 rounded-lg shadow-lg">
        <p className="text-white font-medium">{label}</p>
        <p className="text-blue-400 text-sm mt-1 font-semibold">{value} VT</p>
      </div>
    );
  }
  return null;
};

export default function StateBarChart({ data }) {
  const sorted = [...(data || [])].sort(
    (a, b) => (b?.vt_balance ?? 0) - (a?.vt_balance ?? 0)
  );

  const getColor = (value) => {
    if (value >= 550) return "#22c55e"; // green
    if (value >= 500) return "#facc15"; // yellow
    return "#ef4444"; // red
  };

  return (
    <div className="h-[400px] overflow-y-auto pr-2">
      
      {/* Bigger inner height for 29 states */}
      <div className="h-[900px]">

        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={sorted}
            layout="vertical"
            margin={{ top: 10, right: 20, left: 10, bottom: 10 }}
          >
            <CartesianGrid strokeDasharray="3 3" opacity={0.1} />

            {/* Y Axis (State Names) */}
            <YAxis
              dataKey="name"
              type="category"
              width={120}
              tick={{ fill: "#cbd5f5", fontSize: 11 }}
            />

            {/* X Axis (Values) */}
            <XAxis
              type="number"
              tick={{ fill: "#94a3b8", fontSize: 11 }}
            />

            {/* 🔥 CUSTOM TOOLTIP */}
            <Tooltip content={<CustomTooltip />} />

            {/* Bars */}
            <Bar dataKey="vt_balance" radius={[6, 6, 6, 6]}>
              {sorted.map((entry, index) => (
                <Cell key={index} fill={getColor(entry.vt_balance)} />
              ))}
            </Bar>

          </BarChart>
        </ResponsiveContainer>

      </div>
    </div>
  );
}