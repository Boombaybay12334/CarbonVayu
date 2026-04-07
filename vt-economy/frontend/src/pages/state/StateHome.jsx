import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import useAuth from "../../hooks/useAuth";
import { getStateByName } from "../../services/stateService";
import { TrendingUp, TrendingDown, Map, Leaf, AlertTriangle, Info, CheckCircle2, ChevronRight, Activity, Zap } from "lucide-react";

// ✅ Animated VT number (smooth + guaranteed)
function AnimatedNumber({ value }) {
  const [display, setDisplay] = useState(0);

  useEffect(() => {
    const end = Number(value) || 0;
    let frame;

    const startTime = performance.now();
    const duration = 1000;

    function animate(time) {
      const progress = Math.min((time - startTime) / duration, 1);
      const current = Math.floor(progress * end);
      setDisplay(current);

      if (progress < 1) {
        frame = requestAnimationFrame(animate);
      }
    }

    frame = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(frame);
  }, [value]);

  return <span>{display.toLocaleString()}</span>;
}

export default function StateHome() {
  const { profile } = useAuth();
  const [stateData, setStateData] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    if (profile?.state_name) {
      getStateByName(profile.state_name).then(setStateData);
    }
  }, [profile]);

  const withAlerts = useMemo(() => {
    if (!stateData) return null;

    const alerts = [
      { type: "warning", message: "Industrial emissions increased by 4% this quarter" },
      { type: "success", message: "Forest zones successfully acting as major carbon sinks" },
      { type: "info", message: "Renewable energy adoption index updated" },
    ];

    // Ensure we have a delta even if missing from DB since dummy data generator was updated
    const factor = (stateData.rank || 1 % 3 === 0) ? -0.8 : 1.2;
    const fallbackDelta = Math.round((stateData.vt_balance || 500) * 0.05 * factor);

    return { ...stateData, alerts, yoy_delta: typeof stateData.yoy_delta === "number" ? stateData.yoy_delta : fallbackDelta };
  }, [stateData]);

  if (!withAlerts) {
    return (
      <div className="flex justify-center items-center h-[60vh]">
         <div className="w-8 h-8 flex gap-1">
            <span className="w-2 h-full bg-primary/80 animate-bounce rounded-full"></span>
            <span className="w-2 h-full bg-primary/80 animate-bounce rounded-full" style={{animationDelay: '0.1s'}}></span>
            <span className="w-2 h-full bg-primary/80 animate-bounce rounded-full" style={{animationDelay: '0.2s'}}></span>
          </div>
      </div>
    );
  }

  const delta = Number(withAlerts.yoy_delta) || 0;
  const deltaPositive = delta >= 0;

  return (
    <div className="text-white space-y-8 max-w-6xl mx-auto pb-16 pt-6">

      {/* HEADER HERO */}
      <div className="relative glass-panel rounded-3xl p-10 overflow-hidden animate-slide-up">
        {/* Glow Effects */}
        <div className="absolute -top-32 -right-32 w-80 h-80 bg-primary/20 rounded-full blur-[100px] pointer-events-none"></div>
        <div className="absolute -bottom-20 -left-20 w-64 h-64 bg-cyan-500/10 rounded-full blur-[80px] pointer-events-none"></div>
        
        <div className="relative z-10 flex flex-col md:flex-row md:justify-between md:items-end gap-6">
          <div>
            <div className="inline-flex rounded-full bg-emerald-500/20 border border-emerald-500/40 text-emerald-300 px-4 py-1.5 text-sm font-semibold tracking-wide uppercase mb-4 shadow-[0_0_15px_rgba(16,185,129,0.3)]">
              {withAlerts.archetype || "Standard State"}
            </div>
            <h1 className="text-5xl md:text-6xl font-display font-bold text-white tracking-tight">
              {withAlerts.name}
            </h1>
            <p className="text-slate-400 mt-3 text-lg md:text-xl max-w-xl">
              State-Level Climate Administration & Vaayu Token Performance.
            </p>
          </div>
          
          <div className="flex gap-4">
             <button 
                onClick={() => navigate('/app/state/relations')}
                className="bg-emerald-600 hover:bg-emerald-500 px-5 py-3 rounded-xl flex items-center gap-2 transition-all font-medium shadow-[0_0_15px_rgba(16,185,129,0.3)] hover:shadow-[0_0_25px_rgba(16,185,129,0.5)] hover:scale-105"
             >
                <Zap className="w-5 h-5" />
                Relations
             </button>
          </div>
        </div>
      </div>

      <div className="grid lg:grid-cols-3 gap-8">
        {/* MAIN VT BALANCE METRIC */}
        <div className="lg:col-span-1 border-y-0">
          <div className="glass-panel p-8 rounded-2xl h-full flex flex-col animate-slide-up" style={{ animationDelay: '0.1s' }}>
            <h2 className="text-slate-400 font-medium tracking-wide uppercase text-sm mb-2">Live VT Balance</h2>
            
            <div className="flex-1 flex flex-col justify-center my-8">
              <h3 className="text-6xl font-display font-bold text-white mb-4">
                <AnimatedNumber key={withAlerts.vt_balance} value={withAlerts.vt_balance} />
              </h3>
              
              <div className="inline-flex">
                <span className={`px-4 py-2 rounded-full text-sm font-bold flex items-center gap-2 max-w-fit shadow-lg ${
                  deltaPositive ? "bg-emerald-500/20 text-emerald-400 shadow-emerald-500/10" : "bg-red-500/20 text-red-400 shadow-red-500/10 animate-pulse"
                }`}>
                  {deltaPositive ? <TrendingUp className="w-4 h-4" /> : <TrendingDown className="w-4 h-4" />}
                  {deltaPositive ? "+" : ""}{delta.toLocaleString()} VT (YoY)
                </span>
              </div>
            </div>
            
            <p className="text-sm text-slate-500">Live updated score based on state carbon generation and atmospheric offsets.</p>
          </div>
        </div>

        {/* DETAILS & ALERTS */}
        <div className="lg:col-span-2 space-y-6">
          
          {/* STATS ROW */}
          <div className="grid sm:grid-cols-2 gap-6 animate-slide-up" style={{ animationDelay: '0.2s' }}>
            <div className="glass-card p-6 rounded-2xl flex items-start gap-4 hover:border-emerald-500/30 transition-colors group">
              <div className="p-3 bg-slate-900/50 rounded-xl group-hover:bg-emerald-500/20 transition-colors">
                <Leaf className="w-6 h-6 text-emerald-400" />
              </div>
              <div>
                <p className="text-slate-400 text-sm font-medium mb-1">Ecosystem Typology</p>
                <p className="text-xl font-display font-semibold text-white capitalize">{withAlerts.ecosystem || "Mixed Terrain"}</p>
              </div>
            </div>
            <div className="glass-card p-6 rounded-2xl flex items-start gap-4 hover:border-cyan-500/30 transition-colors group">
              <div className="p-3 bg-slate-900/50 rounded-xl group-hover:bg-cyan-500/20 transition-colors">
                <Map className="w-6 h-6 text-cyan-400" />
              </div>
              <div>
                <p className="text-slate-400 text-sm font-medium mb-1">Governed Area</p>
                <p className="text-xl font-display font-semibold text-white truncate">{Number(withAlerts.area_km2 || 0).toLocaleString()} km²</p>
              </div>
            </div>
          </div>

          {/* AI ALERTS */}
          <div className="glass-panel p-6 rounded-2xl animate-slide-up" style={{ animationDelay: '0.3s' }}>
            <h3 className="text-xl font-display font-semibold text-white mb-5 flex items-center gap-2">
              <span className="w-2 h-6 rounded-full bg-amber-500 inline-block"></span>
              State Priority Intelligence
            </h3>
            
            <div className="space-y-3">
              {withAlerts.alerts.map((alert, idx) => {
                const isWarn = alert.type === "warning";
                const isSuccess = alert.type === "success";
                
                return (
                  <div key={idx} className={`p-4 rounded-xl border flex items-start gap-3 transition-colors ${
                    isWarn ? "bg-amber-500/5 border-amber-500/20 text-amber-200 hover:bg-amber-500/10" : 
                    isSuccess ? "bg-emerald-500/5 border-emerald-500/20 text-emerald-200 hover:bg-emerald-500/10" : 
                    "bg-cyan-500/5 border-cyan-500/20 text-cyan-200 hover:bg-cyan-500/10"
                  }`}>
                    <div className="mt-0.5">
                      {isWarn ? <AlertTriangle className="w-5 h-5 text-amber-500" /> : 
                       isSuccess ? <CheckCircle2 className="w-5 h-5 text-emerald-500" /> : 
                       <Info className="w-5 h-5 text-cyan-500" />}
                    </div>
                    <p className="font-medium text-sm leading-relaxed">{alert.message}</p>
                  </div>
                );
              })}
            </div>
          </div>
          
        </div>
      </div>
      
    </div>
  );
}