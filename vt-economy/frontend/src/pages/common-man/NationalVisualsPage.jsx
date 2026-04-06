import { useEffect, useMemo, useState } from "react";
import CarbonFlowMap from "../../components/charts/CarbonFlowMap";
import StateBarChart from "../../components/charts/StateBarChart";
import VTTimeseriesChart from "../../components/charts/VTTimeseriesChart";
import { getAllStates } from "../../services/leaderboardService";

export default function NationalVisualsPage() {
  const [states, setStates] = useState([]);
  const [filter, setFilter] = useState("all");
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

  const filteredStates = useMemo(() => {
  if (!states || states.length === 0) return [];

  const sorted = [...states].sort((a, b) => b.vt_score - a.vt_score);

  if (filter === "top") return sorted.slice(0, 10);
  if (filter === "bottom") return sorted.slice(-10);

  return sorted;
}, [states, filter]);



  const avgVT =
  states.reduce((sum, s) => sum + (s.vt_score || 0), 0) /
  (states.length || 1);

  const highestVT = Math.max(...states.map((s) => s.vt_score || 0));
  const lowestVT = Math.min(...states.map((s) => s.vt_score || 0));
  const deficitStates = states.filter((s) => (s.vt_score || 0) < 0).length;

  return (
    <div className="text-white max-w-6xl mx-auto px-4 space-y-10">

      {/* TOP CHART */}
      <div className="bg-slate-800/60 p-5 rounded-xl border border-white/10 overflow-hidden">
        <div className="w-full h-[320px]">
          <VTTimeseriesChart data={data} />
        </div>
      </div>

      {/* CONTENT */}
      <div className="grid grid-cols-1 gap-6">

        <div className="bg-slate-800/60 p-5 rounded-xl border border-white/10 overflow-hidden">
          <div className="w-full h-[420px]">
            <StateBarChart data={states} />
          </div>
        </div>

        <div className="bg-slate-800/60 p-5 rounded-xl border border-white/10">
          <div className="w-full min-h-[680px]">
            <CarbonFlowMap />
          </div>
        </div>

      </div>

    </div>
  );
}
