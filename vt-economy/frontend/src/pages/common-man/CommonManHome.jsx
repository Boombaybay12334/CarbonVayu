// PAGE: CommonManHome
// ROUTE: /app/home (role=common_man)
// STATUS: T3.1 Completed (clean + polished, no over-engineering)

import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import VTBadge from "../../components/common/VTBadge";
import { getBottomStates, getTopStates } from "../../services/leaderboardService";

function StateRow({ state, danger = false }) {
  return (
    <div
      className="flex items-center justify-between gap-3 rounded-lg border border-slate-700 p-2
      transition-all duration-300 hover:shadow-md hover:-translate-y-0.5"
    >
      <div className="flex items-center gap-2 min-w-0">
        <span
          className={`h-6 w-6 rounded-full text-xs grid place-items-center
          ${danger ? "bg-red-500/20 text-red-300" : "bg-emerald-500/20 text-emerald-300"}`}
        >
          {state.rank}
        </span>

        <span className="truncate text-sm font-medium">
          {state.name}
        </span>
      </div>

      <VTBadge score={state.vt_balance} size="sm" />
    </div>
  );
}

export default function CommonManHome() {
  const [top, setTop] = useState([]);
  const [bottom, setBottom] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([getTopStates(5), getBottomStates(5)])
      .then(([topData, bottomData]) => {
        setTop(topData);
        setBottom(bottomData);
      })
      .finally(() => setLoading(false));
  }, []);

  return (
    <section className="grid gap-4 p-3 md:p-4 grid-cols-1 lg:grid-cols-[220px_1fr_200px]">
      
      {/* LEFT SIDEBAR */}
      <aside className="rounded-xl shadow-md p-4 bg-slate-800 border border-slate-700">
        
        <h2 className="font-semibold">Top Performers 🌿</h2>

        <div className="mt-3 min-h-[140px] flex items-center justify-center">
          {loading ? (
            <div className="w-5 h-5 border-2 border-slate-600 border-t-emerald-400 rounded-full animate-spin"></div>
          ) : (
            <div className="w-full space-y-2">
              {top.map((state) => (
                <StateRow key={state.id} state={state} />
              ))}
            </div>
          )}
        </div>

        <hr className="my-4 border-slate-700" />

        <h2 className="font-semibold">Worst Performers ⚠️</h2>

        <div className="mt-3 min-h-[140px] flex items-center justify-center">
          {loading ? (
            <div className="w-5 h-5 border-2 border-slate-600 border-t-red-400 rounded-full animate-spin"></div>
          ) : (
            <div className="w-full space-y-2">
              {bottom.map((state) => (
                <StateRow key={state.id} state={state} danger />
              ))}
            </div>
          )}
        </div>

        <Link
          to="/app/leaderboard"
          className="mt-4 inline-block text-sm text-emerald-400 hover:text-emerald-300 transition"
        >
          Full Leaderboard →
        </Link>
      </aside>

      {/* MAIN CONTENT */}
      <main className="rounded-xl shadow-md p-5 bg-slate-800 border border-slate-700">
        
        <h1 className="text-3xl font-bold">Why Vaayu Token?</h1>

        <p className="mt-4 text-slate-300 leading-relaxed">
          Vaayu Token (VT) is a carbon-accountability score for every Indian state. States that protect ecosystems,
          reduce emissions, and act as carbon sinks earn VT. States that pollute or damage neighbouring ecosystems
          lose VT and face fines.
        </p>

        <div className="mt-6 grid gap-4 md:grid-cols-3">
          
          <article className="rounded-xl shadow-md p-4 bg-slate-900 border border-slate-700 transition hover:shadow-lg">
            <h3 className="font-semibold">🌳 Carbon Accountability</h3>
            <p className="text-sm text-slate-400 mt-2">
              Every state's footprint is tracked in real time
            </p>
          </article>

          <article className="rounded-xl shadow-md p-4 bg-slate-900 border border-slate-700 transition hover:shadow-lg">
            <h3 className="font-semibold">⚖️ State Incentives</h3>
            <p className="text-sm text-slate-400 mt-2">
              High VT states receive economic benefits
            </p>
          </article>

          <article className="rounded-xl shadow-md p-4 bg-slate-900 border border-slate-700 transition hover:shadow-lg">
            <h3 className="font-semibold">🌊 Ecosystem Health</h3>
            <p className="text-sm text-slate-400 mt-2">
              Cross-state carbon flows are mapped and priced
            </p>
          </article>

        </div>

        <Link
          to="/app/explore"
          className="mt-6 inline-block bg-emerald-600 hover:bg-emerald-500 
          text-white rounded-lg px-4 py-2 transition"
        >
          Explore the Economy →
        </Link>
      </main>

      {/* RIGHT SIDEBAR */}
      <aside className="rounded-xl shadow-md p-4 bg-slate-800 border border-slate-700 h-fit">
        
        <h3 className="font-semibold">🔔 Updates</h3>

        <p className="text-sm text-slate-400 mt-3">
          National policy update feed will be shown here.
        </p>
      </aside>

    </section>
  );
}