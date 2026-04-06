// PAGE: NationalVisualsPage
// ROUTE: /app/national-visuals
// ROLE: all
// DATA SOURCE: leaderboardService (DUMMY)
// STATUS: Scaffold

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

  const aggregateDummyTimeseries = useMemo(
    () => [
      { year: 2019, vt_score: 4600 },
      { year: 2020, vt_score: 4750 },
      { year: 2021, vt_score: 4920 },
      { year: 2022, vt_score: 5030 },
      { year: 2023, vt_score: 5200 },
      { year: 2024, vt_score: 5410 },
    ],
    [],
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
  <section className="space-y-5">
    <VTTimeseriesChart data={aggregateDummyTimeseries} title="All-India VT Trend" />

    
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
    <div className="bg-green-100 text-green-900 p-3 rounded shadow">Avg VT: {avgVT.toFixed(2)}</div>
    <div className="bg-blue-100 text-blue-900 p-3 rounded shadow">Highest: {highestVT}</div>
    <div className="bg-red-100 text-red-900 p-3 rounded shadow">Lowest: {lowestVT}</div>
    <div className="bg-yellow-100 text-yellow-900 p-3 rounded shadow">Deficit: {deficitStates}</div>
  </div>

    <select
      value={filter}
      onChange={(e) => setFilter(e.target.value)}
      className="border p-2 rounded bg-slate-900 text-slate-300"
    >
      <option value="all">All States</option>
      <option value="top">Top 10</option>
      <option value="bottom">Bottom 10</option>
    </select>

    <StateBarChart data={filteredStates} title="State-by-State VT Ranking" />
    <CarbonFlowMap />
  </section>
);
}
