// PAGE: StateRelationsPage
// ROUTE: /app/state/relations
// ROLE: state
// DATA SOURCE: stateService.getStateRelations() (DUMMY)
// STATUS: Scaffold

import { useEffect, useMemo, useState } from "react";
import useAuth from "../../hooks/useAuth";
import { getStateByName, getStateRelations } from "../../services/stateService";

function StatusBadge({ status }) {
  const classes =
    status === "fine_pending"
      ? "bg-red-500/20 text-red-300"
      : status === "gain"
        ? "bg-emerald-500/20 text-emerald-300"
        : "bg-slate-500/20 text-slate-300";

  return <span className={`rounded-full px-2 py-1 text-xs ${classes}`}>{status}</span>;
}

function RelationsTable({ rows }) {
  return (
    <div className="overflow-x-auto rounded-xl border border-slate-700">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-slate-700 text-slate-300">
            <th className="p-2">State</th>
            <th className="p-2">Relation Type</th>
            <th className="p-2">VT Impact</th>
            <th className="p-2">Status</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={`${row.state}-${row.type}`} className="border-b border-slate-700/50">
              <td className="p-2">{row.state}</td>
              <td className="p-2 text-slate-300">{row.type}</td>
              <td className={`p-2 ${row.vt_impact >= 0 ? "text-emerald-400" : "text-red-400"}`}>{row.vt_impact}</td>
              <td className="p-2"><StatusBadge status={row.status} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function StateRelationsPage() {
  const { profile } = useAuth();
  const [relations, setRelations] = useState({ affected_by: [], affecting: [] });

  useEffect(() => {
    async function load() {
      if (!profile?.state_name) return;
      const state = await getStateByName(profile.state_name);
      const rows = await getStateRelations(state?.id);
      setRelations(rows || { affected_by: [], affecting: [] });
    }

    load();
  }, [profile]);

  const summary = useMemo(() => {
    const fines = relations.affected_by.filter((row) => row.status === "fine_pending");
    const total = fines.reduce((acc, item) => acc + item.vt_impact, 0);
    return { count: fines.length, total };
  }, [relations]);

  return (
    <section className="space-y-5">
      <div className="rounded-xl border border-red-500/40 bg-red-500/10 p-4 text-red-200">
        You owe fines to {summary.count} states totalling {summary.total} VT this quarter
      </div>

      <section className="rounded-xl shadow-md p-4 bg-slate-800 border border-slate-700">
        <h2 className="font-semibold mb-3">States Affecting You</h2>
        <RelationsTable rows={relations.affected_by} />
      </section>

      <section className="rounded-xl shadow-md p-4 bg-slate-800 border border-slate-700">
        <h2 className="font-semibold mb-3">States You Are Affecting</h2>
        <RelationsTable rows={relations.affecting} />
      </section>
    </section>
  );
}
