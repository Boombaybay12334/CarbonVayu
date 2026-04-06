import { useEffect, useState } from "react";
import CarbonFlowMap from "../../components/charts/CarbonFlowMap";
import StateBarChart from "../../components/charts/StateBarChart";
import { getAllStates } from "../../services/leaderboardService";

export default function NationalVisualsPage() {
  const [states, setStates] = useState([]);

  useEffect(() => {
    getAllStates().then(setStates);
  }, []);

  return (
    <div className="text-white max-w-6xl mx-auto px-4 space-y-12">

      {/* 🔥 HEADER */}
      <div className="text-center space-y-2">
        <h1 className="text-4xl font-bold tracking-tight">
          National Carbon Insights 🌍
        </h1>
        <p className="text-slate-400 max-w-2xl mx-auto">
          Compare state performance and understand how carbon flows across India
        </p>
      </div>

      {/* 🔥 MAIN CHART (BIG) */}
      <div className="bg-slate-800/50 backdrop-blur-md p-6 rounded-2xl border border-white/10 shadow-lg">
        
        <h2 className="text-xl font-semibold mb-4 text-center">
          State Comparison
        </h2>

        <div className="w-full h-[450px]">
          <StateBarChart data={states} />
        </div>

      </div>

      {/* 🔥 MAP SECTION */}
      <div className="bg-slate-800/50 backdrop-blur-md p-6 rounded-2xl border border-white/10 shadow-lg">
        
        <h2 className="text-xl font-semibold mb-4 text-center">
          Carbon Flow Map
        </h2>

        <div className="w-full h-[450px]">
          <CarbonFlowMap />
        </div>

      </div>

    </div>
  );
}