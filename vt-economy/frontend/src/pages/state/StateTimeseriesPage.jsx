// PAGE: StateTimeseriesPage
// ROUTE: /app/state/timeseries
// ROLE: state
// DATA SOURCE: stateService.getStateTimeseries() (DUMMY)
// STATUS: Scaffold

import { useEffect, useMemo, useState } from "react";
import VTTimeseriesChart from "../../components/charts/VTTimeseriesChart";
import useAuth from "../../hooks/useAuth";
import { getStateByName, getStateTimeseries } from "../../services/stateService";

export default function StateTimeseriesPage() {
  const { profile } = useAuth();
  const [timeseries, setTimeseries] = useState([]);

  useEffect(() => {
    async function load() {
      if (!profile?.state_name) return;
      const state = await getStateByName(profile.state_name);
      const rows = await getStateTimeseries(state?.id, profile.state_name);
      setTimeseries(rows || []);
    }

    load();
  }, [profile]);

  const rowsWithDelta = useMemo(() => {
    return timeseries.map((item, idx) => {
      const prev = timeseries[idx - 1]?.vt_score;
      const delta = prev ? item.vt_score - prev : 0;
      return { ...item, delta };
    });
  }, [timeseries]);

  return (
    <section className="space-y-4">
      <h1 className="text-2xl font-bold">{profile?.state_name || "State"} - VT History</h1>
      <VTTimeseriesChart data={timeseries} title="State VT History" />

      <div className="rounded-xl shadow-md p-4 bg-slate-800 border border-slate-700 overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-slate-700 text-slate-300">
              <th className="p-2">Year</th>
              <th className="p-2">VT Score</th>
              <th className="p-2">Change</th>
              <th className="p-2">Note</th>
            </tr>
          </thead>
          <tbody>
            {rowsWithDelta.map((row) => (
              <tr key={row.year} className="border-b border-slate-700/60">
                <td className="p-2">{row.year}</td>
                <td className="p-2">{row.vt_score}</td>
                <td className={`p-2 ${row.delta >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                  {row.delta >= 0 ? "+" : ""}
                  {row.delta}
                </td>
                <td className="p-2 text-slate-300">{row.note}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
