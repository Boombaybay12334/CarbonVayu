import { useEffect, useMemo, useState } from "react";
import CarbonFlowMap from "../../components/charts/CarbonFlowMap";
import IndiaMapFlowChart from "../../components/charts/IndiaMapFlowChart";
import StateBarChart from "../../components/charts/StateBarChart";
import { getAllStates } from "../../services/leaderboardService";

export default function NationalVisualsPage() {
  const [states, setStates] = useState([]);
  const [filter, setFilter] = useState("all");
  
  useEffect(() => {
    getAllStates().then(setStates);
  }, []);

  const filteredStates = useMemo(() => {
    if (!states || states.length === 0) return [];
    const sorted = [...states].sort((a, b) => b.vt_balance - a.vt_balance);
    if (filter === "top") return sorted.slice(0, 10);
    if (filter === "bottom") return sorted.slice(-10);
    return sorted;
  }, [states, filter]);

  const avgVT = states.length
    ? (states.reduce((sum, s) => sum + (s.vt_balance || 0), 0) / states.length).toFixed(0)
    : 0;

  const highestVT = states.length ? Math.max(...states.map((s) => s.vt_balance || 0)) : 0;
  const lowestVT = states.length ? Math.min(...states.map((s) => s.vt_balance || 0)) : 0;
  const deficitStates = states.filter((s) => (Number(s.vt_balance) || 0) < 500).length;

  return (
    <div className="text-white max-w-7xl mx-auto px-4 pb-12 space-y-10">

      {/* Header */}
      <div className="relative mb-10 pt-4 flex flex-col md:flex-row justify-between items-end gap-6 z-10">
        <div className="absolute -top-10 -left-10 w-64 h-64 bg-primary/20 rounded-full blur-[80px] -z-10"></div>
        <div>
          <h1 className="text-4xl md:text-5xl font-display font-bold bg-gradient-to-r from-emerald-400 to-cyan-400 bg-clip-text text-transparent animate-slide-up">
            National Overview
          </h1>
          <p className="text-slate-400 mt-2 text-lg max-w-2xl animate-slide-up" style={{ animationDelay: '0.1s' }}>
            Macro view of India's climate economy. Analyze high performing states, carbon flow mapping, and national statistics.
          </p>
        </div>
      </div>

      {/* Top Level Metric Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 animate-slide-up" style={{ animationDelay: '0.2s' }}>
        <div className="glass-card p-5 relative overflow-hidden group">
          <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity"><span className="text-4xl">📊</span></div>
          <p className="text-slate-400 text-sm font-medium mb-1">Average VT Score</p>
          <p className="text-3xl font-display font-bold text-white">{avgVT}</p>
        </div>
        
        <div className="glass-card p-5 relative overflow-hidden group">
          <div className="absolute top-0 right-0 p-4 opacity-10 text-primary group-hover:opacity-20 transition-opacity"><span className="text-4xl">🏆</span></div>
          <p className="text-slate-400 text-sm font-medium mb-1">Highest VT</p>
          <p className="text-3xl font-display font-bold text-primary">{highestVT}</p>
        </div>

        <div className="glass-card p-5 relative overflow-hidden group">
          <div className="absolute top-0 right-0 p-4 opacity-10 text-amber-500 group-hover:opacity-20 transition-opacity"><span className="text-4xl">⚠️</span></div>
          <p className="text-slate-400 text-sm font-medium mb-1">Lowest VT</p>
          <p className="text-3xl font-display font-bold text-amber-400">{lowestVT}</p>
        </div>

        <div className="glass-card p-5 relative overflow-hidden group">
          <div className="absolute top-0 right-0 p-4 opacity-10 text-red-500 group-hover:opacity-20 transition-opacity"><span className="text-4xl">🚨</span></div>
          <p className="text-slate-400 text-sm font-medium mb-1">Deficit States</p>
          <p className="text-3xl font-display font-bold text-red-400">{deficitStates}</p>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 animate-slide-up" style={{ animationDelay: '0.3s' }}>
        {/* State Bar Chart - Spans Full Column now */}
        <div className="glass-panel p-6 rounded-2xl relative overflow-hidden flex flex-col">
          <div className="flex justify-between items-center mb-6">
            <h3 className="text-xl font-display font-semibold text-white flex items-center gap-2">
              <span className="w-2 h-6 rounded-full bg-secondary inline-block"></span>
              State Performance Leaderboard
            </h3>
          </div>
          <div className="w-full flex-1">
            <StateBarChart data={states} />
          </div>
        </div>
      </div>

      {/* Carbon Flow Map - Full Width */}
      <div className="glass-panel p-6 rounded-2xl animate-slide-up relative overflow-hidden" style={{ animationDelay: '0.4s' }}>
        <div className="absolute top-0 right-1/4 w-96 h-96 bg-cyan-500/10 rounded-full blur-[80px] -z-10 pointer-events-none"></div>
        <div className="flex justify-between items-center mb-6">
          <h3 className="text-2xl font-display font-semibold text-white flex items-center gap-2">
            <span className="w-3 h-8 rounded-full bg-gradient-to-b from-primary to-cyan-500 inline-block"></span>
            Cross-Border Carbon Flow Dynamics
          </h3>
        </div>
        <div className="w-full h-[680px] rounded-xl overflow-hidden border border-white/5 bg-slate-900/50 backdrop-blur-sm">
          <CarbonFlowMap />
        </div>
      </div>

      {/* India Geographic Carbon Flow Map */}
      <div className="glass-panel p-6 rounded-2xl animate-slide-up relative overflow-hidden" style={{ animationDelay: '0.5s' }}>
        <div className="absolute bottom-0 left-1/4 w-96 h-96 bg-emerald-500/10 rounded-full blur-[80px] -z-10 pointer-events-none"></div>
        <div className="flex justify-between items-center mb-6">
          <div>
            <h3 className="text-2xl font-display font-semibold text-white flex items-center gap-2">
              <span className="w-3 h-8 rounded-full bg-gradient-to-b from-emerald-400 to-teal-600 inline-block"></span>
              Geographic Carbon Flow Map
            </h3>
            <p className="text-slate-400 text-sm mt-1 ml-5">
              Real India map — state VT balance as colour heatmap with animated cross-border carbon flows.
            </p>
          </div>
        </div>
        <IndiaMapFlowChart />
      </div>

    </div>
  );
}