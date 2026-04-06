import { useEffect, useMemo, useState } from "react";
import CarbonFlowMap from "../../components/charts/CarbonFlowMap";
import StateBarChart from "../../components/charts/StateBarChart";
import VTTimeseriesChart from "../../components/charts/VTTimeseriesChart";
import { getAllStates } from "../../services/leaderboardService";

export default function NationalVisualsPage() {
  const [states, setStates] = useState([]);

  useEffect(() => {
    getAllStates().then(setStates);
  }, []);

  const data = useMemo(
    () => [
      { year: 2019, vt_score: 4600 },
      { year: 2020, vt_score: 4750 },
      { year: 2021, vt_score: 4920 },
      { year: 2022, vt_score: 5030 },
      { year: 2023, vt_score: 5200 },
      { year: 2024, vt_score: 5410 },
    ],
    []
  );

  return (
    <div className="text-white max-w-6xl mx-auto px-4 space-y-10">

      {/* TOP CHART */}
      <div className="bg-slate-800/60 p-5 rounded-xl border border-white/10 overflow-hidden">
        <div className="w-full h-[320px]">
          <VTTimeseriesChart data={data} />
        </div>
      </div>

      {/* GRID */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">

        <div className="bg-slate-800/60 p-5 rounded-xl border border-white/10 overflow-hidden">
          <div className="w-full h-[350px]">
            <StateBarChart data={states} />
          </div>
        </div>

        <div className="bg-slate-800/60 p-5 rounded-xl border border-white/10 overflow-hidden">
          <div className="w-full h-[350px]">
            <CarbonFlowMap />
          </div>
        </div>

      </div>

    </div>
  );
}