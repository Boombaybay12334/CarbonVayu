import { Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

function getBarColor(score) {
  if (score > 7000) return "#10b981";
  if (score > 3000) return "#f59e0b";
  return "#ef4444";
}

export default function StateBarChart({ data = [], title = "State VT Balance" }) {
  const chartData = data.slice(0, 20);

  return (
    <section className="rounded-xl shadow-md p-4 bg-slate-800 border border-slate-700">
      <h3 className="text-slate-100 font-semibold mb-4">{title}</h3>
      <div className="h-[420px] min-w-0">
        <ResponsiveContainer width="100%" height="100%" minWidth={280} minHeight={260}>
          <BarChart data={chartData} layout="vertical" margin={{ left: 32, right: 16 }}>
            <XAxis type="number" stroke="#94a3b8" />
            <YAxis type="category" dataKey="name" width={120} stroke="#94a3b8" />
            <Tooltip contentStyle={{ backgroundColor: "#0f172a", borderColor: "#334155" }} />
            <Bar dataKey="vt_balance" radius={[0, 6, 6, 0]}>
              {chartData.map((entry) => (
                <Cell key={entry.id ?? entry.name} fill={getBarColor(entry.vt_balance)} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}
