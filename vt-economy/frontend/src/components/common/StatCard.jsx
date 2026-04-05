export default function StatCard({ title, value, delta = 0, unit = "" }) {
  const isPositive = Number(delta) >= 0;

  return (
    <article className="rounded-xl shadow-md p-4 bg-slate-800 border border-slate-700">
      <p className="text-slate-400 text-sm">{title}</p>
      <h3 className="text-2xl font-bold text-slate-100 mt-2">
        {value}
        {unit ? <span className="text-base font-medium text-slate-400 ml-2">{unit}</span> : null}
      </h3>
      <p className={`mt-2 text-sm ${isPositive ? "text-emerald-400" : "text-red-400"}`}>
        {isPositive ? "↑" : "↓"} {delta}
      </p>
    </article>
  );
}
