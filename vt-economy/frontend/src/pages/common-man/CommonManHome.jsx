import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import VTBadge from "../../components/common/VTBadge";
import { getBottomStates, getTopStates } from "../../services/leaderboardService";

function StateRow({ state, danger = false, index }) {
  return (
    <div 
      className="flex items-center justify-between gap-3 rounded-xl border border-white/5 p-4 bg-surface/40 hover:bg-surface/80 transition-all duration-300 hover:scale-[1.02] cursor-default animate-slide-up"
      style={{ animationDelay: `${index * 0.1}s` }}
    >
      <div className="flex items-center gap-3 min-w-0">
        <div
          className={`h-8 w-8 rounded-full text-sm font-bold flex items-center justify-center border shadow-sm
          ${danger ? "bg-red-500/10 text-red-400 border-red-500/30 shadow-red-500/20" : "bg-primary/10 text-primary border-primary/30 shadow-primary/20"}`}
        >
          {state.rank}
        </div>

        <span className="truncate text-base font-semibold text-slate-200">
          {state.name}
        </span>
      </div>

      <VTBadge score={state.vt_balance} size="md" forceColor={!danger ? "bg-emerald-500" : undefined} />
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
    <div className="space-y-12 max-w-6xl mx-auto pb-10">

      {/* 🔥 HERO */}
      <section className="text-center flex flex-col items-center py-12 relative">
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-full max-w-2xl h-64 bg-primary/10 rounded-full blur-[80px] -z-10 pointer-events-none"></div>
        <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-surfaceLight/50 border border-primary/20 text-primary text-sm font-medium mb-6 animate-fade-in shadow-[0_0_15px_rgba(16,185,129,0.15)]">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2 w-2 bg-primary"></span>
          </span>
          Live Climate Governance
        </div>
        <h1 className="text-5xl md:text-6xl font-display font-bold tracking-tight bg-gradient-to-r from-white via-slate-200 to-slate-400 bg-clip-text text-transparent mb-6 animate-slide-up">
          VT Economy 🌍
        </h1>

        <p className="text-lg text-slate-400 max-w-2xl animate-slide-up" style={{ animationDelay: '0.1s' }}>
          Track carbon accountability, cross-state pollution flow, and climate governance across India in real-time.
        </p>
      </section>

      {/* WHY SECTION */}
      <section className="glass-panel rounded-2xl p-8 animate-slide-up relative overflow-hidden group" style={{ animationDelay: '0.2s' }}>
        <div className="absolute -top-24 -right-24 w-48 h-48 bg-primary/10 rounded-full blur-[50px] group-hover:bg-primary/20 transition-all duration-700"></div>
        
        <h2 className="text-3xl font-display font-bold text-white mb-4">Why Vaayu Token?</h2>

        <p className="text-slate-300 leading-relaxed text-lg max-w-4xl">
          Vaayu Token (VT) is a climate accountability score ranging from <span className="text-red-400 font-semibold">300</span> to <span className="text-primary font-semibold">700</span>.
          It integrates emissions, carbon absorption, atmospheric transport, and governance effort
          into a single measurable indicator.
        </p>

        {/* 🔥 CARDS */}
        <div className="mt-8 grid gap-6 md:grid-cols-3">
          
          <div className="glass-card p-6">
            <div className="w-12 h-12 rounded-xl bg-emerald-500/20 text-emerald-400 flex items-center justify-center text-2xl mb-4 border border-emerald-500/30">🌳</div>
            <h3 className="text-xl font-display font-semibold text-white mb-2">Carbon Accountability</h3>
            <p className="text-slate-400 leading-relaxed">
              Tracks emissions, absorption, and cross-state carbon movement using advanced atmospheric transport modeling.
            </p>
          </div>

          <div className="glass-card p-6">
            <div className="w-12 h-12 rounded-xl bg-amber-500/20 text-amber-500 flex items-center justify-center text-2xl mb-4 border border-amber-500/30">⚖️</div>
            <h3 className="text-xl font-display font-semibold text-white mb-2">State Incentives</h3>
            <p className="text-slate-400 leading-relaxed">
              States are rewarded or penalized financially based on their VT score relative to national benchmarks and historical data.
            </p>
          </div>

          <div className="glass-card p-6">
            <div className="w-12 h-12 rounded-xl bg-cyan-500/20 text-cyan-400 flex items-center justify-center text-2xl mb-4 border border-cyan-500/30">🌊</div>
            <h3 className="text-xl font-display font-semibold text-white mb-2">Ecosystem Health</h3>
            <p className="text-slate-400 leading-relaxed">
              Visualizes how carbon flows seamlessly across state borders using wind patterns and diffusion-based models.
            </p>
          </div>

        </div>

        {/* 🔥 BUTTON BELOW SECTION */}
        <div className="mt-10 flex justify-center">
          <button
            onClick={() => navigate("/app/explore")}
            className="group relative inline-flex items-center gap-2 overflow-hidden rounded-full bg-gradient-to-r from-primary to-emerald-500 px-8 py-3.5 text-white font-semibold transition-all hover:scale-105 shadow-[0_0_20px_rgba(16,185,129,0.3)] hover:shadow-[0_0_30px_rgba(16,185,129,0.5)]"
          >
            <span className="relative z-10">Explore the Economy</span>
            <svg className="w-5 h-5 relative z-10 transition-transform group-hover:translate-x-1" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M14 5l7 7m0 0l-7 7m7-7H3"></path></svg>
            <div className="absolute inset-0 bg-white/20 transform -skew-x-12 -translate-x-full group-hover:animate-[shimmer_1.5s_infinite]"></div>
          </button>
        </div>

      </section>

      {/* TOP + WORST */}
      <section className="grid md:grid-cols-2 gap-8 animate-slide-up" style={{ animationDelay: '0.4s' }}>
        
        {/* TOP */}
        <div className="glass-panel rounded-2xl p-6 relative overflow-hidden">
          <div className="absolute top-0 right-0 w-32 h-32 bg-primary/5 rounded-full blur-[40px]"></div>
          <div className="flex items-center gap-3 mb-6">
            <div className="p-2 rounded-lg bg-primary/20 border border-primary/30">
              <span className="text-xl">🌿</span>
            </div>
            <h3 className="text-2xl font-display font-semibold text-white">Top Performers</h3>
          </div>

          {loading ? (
            <div className="flex justify-center py-12">
              <div className="w-8 h-8 flex gap-1">
                <span className="w-2 h-full bg-primary/80 animate-bounce rounded-full"></span>
                <span className="w-2 h-full bg-primary/80 animate-bounce rounded-full" style={{animationDelay: '0.1s'}}></span>
                <span className="w-2 h-full bg-primary/80 animate-bounce rounded-full" style={{animationDelay: '0.2s'}}></span>
              </div>
            </div>
          ) : (
            <div className="space-y-3">
              {top.map((state, i) => (
                <StateRow key={state.id} state={state} index={i} />
              ))}
            </div>
          )}
        </div>

        {/* WORST */}
        <div className="glass-panel rounded-2xl p-6 relative overflow-hidden">
          <div className="absolute top-0 right-0 w-32 h-32 bg-red-500/5 rounded-full blur-[40px]"></div>
          <div className="flex items-center gap-3 mb-6">
            <div className="p-2 rounded-lg bg-red-500/20 border border-red-500/30">
              <span className="text-xl">⚠️</span>
            </div>
            <h3 className="text-2xl font-display font-semibold text-white">Needs Improvement</h3>
          </div>

          {loading ? (
            <div className="flex justify-center py-12">
              <div className="w-8 h-8 flex gap-1">
                <span className="w-2 h-full bg-red-400/80 animate-bounce rounded-full"></span>
                <span className="w-2 h-full bg-red-400/80 animate-bounce rounded-full" style={{animationDelay: '0.1s'}}></span>
                <span className="w-2 h-full bg-red-400/80 animate-bounce rounded-full" style={{animationDelay: '0.2s'}}></span>
              </div>
            </div>
          ) : (
            <div className="space-y-3">
              {bottom.map((state, i) => (
                <StateRow key={state.id} state={state} danger index={i} />
              ))}
            </div>
          )}
        </div>

      </section>

      {/* UPDATES */}
      <section className="glass-panel rounded-2xl p-6 animate-slide-up flex items-center justify-between" style={{ animationDelay: '0.6s' }}>
        <div>
          <div className="flex items-center gap-3 mb-2">
            <span className="relative flex h-3 w-3">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-secondary opacity-75"></span>
              <span className="relative inline-flex rounded-full h-3 w-3 bg-secondary"></span>
            </span>
            <h3 className="text-xl font-display font-semibold text-white">Live Policy Updates</h3>
          </div>
          <p className="text-slate-400 pl-6">
            National policy updates and regional climate insights will appear here shortly.
          </p>
        </div>
        <div className="hidden sm:block text-4xl opacity-20">📰</div>
      </section>
      
      {/* Footer minimal info */}
      <div className="text-center text-slate-500 text-sm py-4 animate-fade-in" style={{ animationDelay: '0.8s' }}>
        © 2026 VT Economy Project. Data modeled for demonstration.
      </div>

    </div>
  );
}