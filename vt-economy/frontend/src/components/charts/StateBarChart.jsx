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

function getBarColor(score) {
  if (score >= 500) return "#10b981"; // emerald-500
  if (score >= 200) return "#f59e0b"; // amber-500
  return "#ef4444"; // red-500
}

export default function StateBarChart({ data = [], title = "" }) {
  // Render up to 29 states
  const chartData = data.slice(0, 29);
  
  // Calculate a dynamic height so the chart stretches properly and is cleanly scrollable
  const rowHeight = 34; // px per state row
  const innerHeight = Math.max(chartData.length * rowHeight, 300); // at least 300px

  return (
    <div className="w-full h-full flex flex-col">
      {title && <h3 className="text-slate-100 font-semibold mb-4">{title}</h3>}
      {/* Scrollable Container */}
      <div style={{ maxHeight: 320 }} className="overflow-y-auto pr-2 custom-scrollbar">
        {/* inner chart height sized by number of states; outer container stays small and scrollable */}
        <div style={{ height: `${innerHeight}px` }}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData} layout="vertical" margin={{ left: 32, right: 16 }}>
              <XAxis type="number" stroke="#94a3b8" />
              <YAxis type="category" dataKey="name" width={120} stroke="#94a3b8" interval={0} tick={{ fontSize: 13 }} />
              <Tooltip 
                contentStyle={{ backgroundColor: "#0f172a", borderColor: "#334155" }} 
                itemStyle={{ color: "#3b82f6" }} // Force blue color on hover
                cursor={{ fill: "rgba(255,255,255,0.05)" }}
              />
              <Bar dataKey="vt_balance" radius={[0, 6, 6, 0]} barSize={24}>
                {chartData.map((entry) => (
                  <Cell key={entry.id ?? entry.name} fill={getBarColor(entry.vt_balance)} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}