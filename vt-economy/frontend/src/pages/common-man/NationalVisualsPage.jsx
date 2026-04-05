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

  return (
    <section className="space-y-5">
      <VTTimeseriesChart data={aggregateDummyTimeseries} title="All-India VT Trend" />
      <StateBarChart data={states} title="State-by-State VT Ranking" />
      <CarbonFlowMap />
    </section>
  );
}
