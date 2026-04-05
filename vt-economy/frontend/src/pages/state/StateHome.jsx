// PAGE: StateHome

import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import AlertBanner from "../../components/common/AlertBanner";
import useAuth from "../../hooks/useAuth";
import { getStateByName } from "../../services/stateService";

// ✅ Animated Number
function AnimatedNumber({ value }) {
  const safeValue = Number(value) || 0;
  const [display, setDisplay] = useState(0);

  useEffect(() => {
    setDisplay(0);

    let start = 0;
    const duration = 1000;
    const stepTime = 20;
    const steps = duration / stepTime;
    const increment = safeValue / steps;

    const timer = setInterval(() => {
      start += increment;

      if (Math.abs(start) >= Math.abs(safeValue)) {
        setDisplay(safeValue);
        clearInterval(timer);
      } else {
        setDisplay(Math.floor(start));
      }
    }, stepTime);

    return () => clearInterval(timer);
  }, [safeValue]);

  return <span>{display.toLocaleString()}</span>;
}

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
      { type: "warning", message: "Industrial emissions increased this quarter" },
      { type: "info", message: "Forest zones acting as carbon sinks" },
      { type: "success", message: "Renewable energy adoption improved" },
    ];

    return { ...stateData, alerts };
  }, [stateData]);

  if (!withAlerts) {
    return <p className="text-slate-400">Loading state profile...</p>;
  }

  const delta = Number(withAlerts.yoy_delta) || 0;
  const deltaPositive = delta >= 0;

  return (
    <section className="grid gap-4 xl:grid-cols-[220px_1fr_220px]">

      {/* LEFT PANEL */}
      <aside className="rounded-xl shadow-md p-4 bg-slate-800 border border-slate-700">
        <p className="text-sm text-slate-400">Your VT Balance</p>

        {/* ✅ Count animation */}
        <h2 className="text-3xl font-bold mt-2">
          <AnimatedNumber
            key={withAlerts.vt_balance}
            value={withAlerts.vt_balance}
          />
        </h2>

        {/* ✅ Delta badge */}
        <div className="mt-3">
          <span
            className={`px-3 py-1 rounded-full text-sm font-medium
            ${
              deltaPositive
                ? "bg-emerald-500/20 text-emerald-400"
                : "bg-red-500/20 text-red-400 animate-pulse"
            }`}
          >
            {deltaPositive ? "+" : ""}
            {delta} VT
          </span>
        </div>

        <Link
          to="/app/state/timeseries"
          className="mt-4 inline-block text-sm text-emerald-400"
        >
          View History →
        </Link>
      </aside>

      {/* MAIN PANEL */}
      <main className="rounded-xl shadow-md p-5 bg-slate-800 border border-slate-700">
        <h1 className="text-2xl font-bold">{withAlerts.name}</h1>

        <p className="mt-2 inline-flex rounded-full bg-emerald-600/20 text-emerald-300 px-3 py-1 text-xs">
          {withAlerts.archetype}
        </p>

        <div className="mt-4 space-y-2 text-slate-300">
          <p>🌿 Ecosystem: {withAlerts.ecosystem}</p>
          <p>📐 Area: {Number(withAlerts.area_km2).toLocaleString()} km²</p>
        </div>

        {/* ✅ Alerts */}
        <div className="mt-5 space-y-3">
          {withAlerts.alerts.map((alert) => (
            <AlertBanner
              key={alert.message}
              type={alert.type}
              message={alert.message}
            />
          ))}
        </div>

        <Link
          to="/app/state/relations"
          className="mt-5 inline-block bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg px-4 py-2"
        >
          View Relations →
        </Link>
      </main>

      {/* RIGHT PANEL */}
      <aside className="rounded-xl shadow-md p-4 bg-slate-800 border border-slate-700 opacity-80 h-fit">
        <h3 className="font-semibold">State-Level Tools</h3>
        <p className="mt-2 inline-block rounded-full bg-slate-700 px-2 py-1 text-xs text-slate-300">
          Coming Soon
        </p>
      </aside>

    </section>
  );
}