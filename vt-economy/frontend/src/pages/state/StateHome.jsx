// PAGE: StateHome
// ROUTE: /app/home (role=state)
// ROLE: state
// DATA SOURCE: stateService.getStateByName(profile.state_name) (DUMMY)
// STATUS: Scaffold

import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import AlertBanner from "../../components/common/AlertBanner";
import useAuth from "../../hooks/useAuth";
import { getStateByName } from "../../services/stateService";

export default function StateHome() {
  const { profile } = useAuth();
  const [stateData, setStateData] = useState(null);

  useEffect(() => {
    if (profile?.state_name) {
      getStateByName(profile.state_name).then(setStateData);
    }
  }, [profile]);

  const withAlerts = useMemo(() => {
    if (!stateData) return null;

    const alerts = [
      { type: "warning", message: "Industrial corridor emissions up 8% in Q3 2024" },
      { type: "info", message: "Western Ghats generating passive VT - net carbon sink" },
    ];

    return { ...stateData, alerts };
  }, [stateData]);

  if (!withAlerts) {
    return <p className="text-slate-400">Loading state profile...</p>;
  }

  const deltaPositive = Number(withAlerts.yoy_delta) >= 0;

  return (
    <section className="grid gap-4 xl:grid-cols-[220px_1fr_220px]">
      <aside className="rounded-xl shadow-md p-4 bg-slate-800 border border-slate-700">
        <p className="text-sm text-slate-400">Your VT Balance</p>
        <h2 className="text-3xl font-bold mt-2">{Number(withAlerts.vt_balance).toLocaleString()}</h2>
        <p className={`mt-3 text-sm ${deltaPositive ? "text-emerald-400" : "text-red-400"}`}>
          {deltaPositive ? "+" : ""}
          {withAlerts.yoy_delta} VT from last year
        </p>
        <Link to="/app/state/timeseries" className="mt-4 inline-block text-sm text-emerald-400">
          View History →
        </Link>
      </aside>

      <main className="rounded-xl shadow-md p-5 bg-slate-800 border border-slate-700">
        <h1 className="text-2xl font-bold">{withAlerts.name}</h1>
        <p className="mt-2 inline-flex rounded-full bg-emerald-600/20 text-emerald-300 px-3 py-1 text-xs">
          {withAlerts.archetype}
        </p>

        <div className="mt-4 space-y-2 text-slate-300">
          <p>🌿 Ecosystem: {withAlerts.ecosystem}</p>
          <p>📐 Area: {Number(withAlerts.area_km2).toLocaleString()} km²</p>
        </div>

        <div className="mt-5 space-y-3">
          {withAlerts.alerts.map((alert) => (
            <AlertBanner key={alert.message} alert={alert} />
          ))}
        </div>

        <Link to="/app/state/relations" className="mt-5 inline-block bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg px-4 py-2">
          View Relations →
        </Link>
      </main>

      <aside className="rounded-xl shadow-md p-4 bg-slate-800 border border-slate-700 opacity-80 h-fit">
        <h3 className="font-semibold">State-Level Tools</h3>
        <p className="mt-2 inline-block rounded-full bg-slate-700 px-2 py-1 text-xs text-slate-300">Coming Soon</p>
        {/* FUTURE SCOPE */}
      </aside>
    </section>
  );
}
