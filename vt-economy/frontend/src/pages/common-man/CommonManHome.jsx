import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import VTBadge from "../../components/common/VTBadge";
import { getBottomStates, getTopStates } from "../../services/leaderboardService";

function StateRow({ state, danger = false }) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-lg border border-slate-700 p-3 bg-slate-900/60">
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

  const navigate = useNavigate();

  useEffect(() => {
    Promise.all([getTopStates(5), getBottomStates(5)])
      .then(([topData, bottomData]) => {
        setTop(topData);
        setBottom(bottomData);
      })
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="space-y-10 max-w-6xl mx-auto text-white">

      {/* 🔥 HERO */}
      <section className="text-center flex flex-col items-center">
        <h1 className="text-3xl font-bold flex items-center gap-2 justify-center">
          VT Economy 🌍
        </h1>

        <p className="text-slate-400 mt-2 max-w-2xl">
          Track carbon accountability, cross-state pollution flow, and climate governance across India.
        </p>
      </section>

      {/* WHY SECTION */}
      <section className="rounded-xl p-6 bg-slate-800/60 border border-white/10">
        <h2 className="text-2xl font-bold">Why Vaayu Token?</h2>

        <p className="mt-4 text-slate-300 leading-relaxed">
          Vaayu Token (VT) is a climate accountability score ranging from 300 to 700.
          It integrates emissions, carbon absorption, atmospheric transport, and governance effort
          into a single measurable indicator.
        </p>

        {/* 🔥 CARDS (UPGRADED) */}
        <div className="mt-6 grid gap-4 md:grid-cols-3">
          
          <div className="p-4 rounded-xl bg-slate-900 border border-slate-700">
            <h3 className="font-semibold">🌳 Carbon Accountability</h3>
            <p className="text-sm text-slate-400 mt-2">
              Tracks emissions, absorption, and cross-state carbon movement using atmospheric transport modeling.
            </p>
          </div>

          <div className="p-4 rounded-xl bg-slate-900 border border-slate-700">
            <h3 className="font-semibold">⚖️ State Incentives</h3>
            <p className="text-sm text-slate-400 mt-2">
              States are rewarded or penalized financially based on their VT score relative to national benchmarks.
            </p>
          </div>

          <div className="p-4 rounded-xl bg-slate-900 border border-slate-700">
            <h3 className="font-semibold">🌊 Ecosystem Health</h3>
            <p className="text-sm text-slate-400 mt-2">
              Visualizes how carbon flows across states using wind patterns and diffusion-based transport models.
            </p>
          </div>

        </div>

        {/* 🔥 BUTTON BELOW SECTION */}
        <div className="mt-6 flex justify-center">
          <button
            onClick={() => navigate("/app/explore")}
            className="bg-emerald-600 hover:bg-emerald-500 text-white px-6 py-2 rounded-lg font-medium transition"
          >
            Explore the Economy →
          </button>
        </div>

      </section>

      {/* TOP + WORST */}
      <section className="grid md:grid-cols-2 gap-6">
        
        {/* TOP */}
        <div className="rounded-xl p-4 bg-slate-800/60 border border-white/10">
          <h3 className="font-semibold mb-3">Top Performers 🌿</h3>

          {loading ? (
            <div className="flex justify-center py-6">
              <div className="w-5 h-5 border-2 border-slate-600 border-t-emerald-400 rounded-full animate-spin"></div>
            </div>
          ) : (
            <div className="space-y-2">
              {top.map((state) => (
                <StateRow key={state.id} state={state} />
              ))}
            </div>
          )}
        </div>

        {/* WORST */}
        <div className="rounded-xl p-4 bg-slate-800/60 border border-white/10">
          <h3 className="font-semibold mb-3">Worst Performers ⚠️</h3>

          {loading ? (
            <div className="flex justify-center py-6">
              <div className="w-5 h-5 border-2 border-slate-600 border-t-red-400 rounded-full animate-spin"></div>
            </div>
          ) : (
            <div className="space-y-2">
              {bottom.map((state) => (
                <StateRow key={state.id} state={state} danger />
              ))}
            </div>
          )}
        </div>

      </section>

      {/* UPDATES */}
      <section className="rounded-xl p-4 bg-slate-800/60 border border-white/10">
        <h3 className="font-semibold">🔔 Updates</h3>
        <p className="text-sm text-slate-400 mt-2">
          National policy updates and climate insights will appear here.
        </p>
      </section>

    </div>
  );
}