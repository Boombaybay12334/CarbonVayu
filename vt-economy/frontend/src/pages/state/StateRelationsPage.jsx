import { useEffect, useMemo, useState } from "react";
import useAuth from "../../hooks/useAuth";
import { getStateByName, getStateRelations } from "../../services/stateService";
import { AlertTriangle, MapPin, Zap } from "lucide-react";

function StatusBadge({ status }) {
  const isPending = status === "fine_pending";
  const isGain = status === "gain";
  
  const classes = isPending
    ? "bg-red-500/10 border-red-500/30 text-red-400"
    : isGain
      ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-400"
      : "bg-slate-500/10 border-slate-500/30 text-slate-300";

  return <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold border ${classes}`}>{status.replace("_", " ")}</span>;
}

function RelationsTable({ rows, isLiability = false }) {
  if (!rows || rows.length === 0) {
     return <div className="p-8 text-center text-slate-500 italic">No significant atmospheric relations recorded in this category.</div>;
  }

  return (
    <div className="overflow-x-auto rounded-xl border border-white/5 bg-slate-900/40 backdrop-blur-sm">
      <table className="w-full text-left text-sm">
        <thead className="bg-white/5 backdrop-blur-md">
          <tr className="border-b border-white/10 text-slate-300 uppercase text-xs tracking-wider font-semibold">
            <th className="p-4">Neighboring State</th>
            <th className="p-4">Atmospheric Type</th>
            <th className="p-4">Impact</th>
            <th className="p-4">Ledger Status</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-white/5">
          {rows.map((row) => {
            const isFine = row.type === "fine" || row.status === "fine_pending";
            const isPenalty = isLiability && isFine;
            const impactVal = Math.abs(Number(row.vt_impact) || 0);
            const unit = row.type === "transport" ? "µg/m³" : "VT";

            return (
              <tr key={`${row.state}-${row.type}-${row.period || ""}`} className="hover:bg-white/5 transition-colors">
                <td className="p-4 font-medium text-white flex items-center gap-2">
                   <MapPin className="w-4 h-4 text-primary" />
                   {row.state}
                </td>
                <td className="p-4 text-slate-300 capitalize">{row.type.replace("_", " ")}</td>
                <td className={`p-4 font-mono font-medium ${isPenalty ? "text-amber-400" : "text-emerald-400"}`}>
                   {isPenalty ? "-" : "+"}{impactVal.toLocaleString(undefined, { maximumFractionDigits: 4 })} {unit}
                </td>
                <td className="p-4"><StatusBadge status={row.status} /></td>
              </tr>
            );
          })}
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
      if (state) {
        const rows = await getStateRelations(state.id, "2023-v5");
        setRelations(rows || { affected_by: [], affecting: [] });
      }
    }
    load();
  }, [profile]);

  // Fines we owe to states we are actively polluting (Liability)
  const summary = useMemo(() => {
    const fines = relations.affecting.filter((row) => row.status === "fine_pending" && row.type === "fine");
    const total = fines.reduce((acc, item) => acc + Math.abs(Number(item.vt_impact) || 0), 0);
    return { count: fines.length, total: Math.round(total * 100) / 100 };
  }, [relations]);

  return (
    <div className="text-white space-y-8 max-w-6xl mx-auto pb-16 pt-4 animate-fade-in">

      <div className="relative">
        <div className="absolute top-0 right-20 w-80 h-80 bg-cyan-500/10 rounded-full blur-[100px] -z-10 pointer-events-none"></div>
        <h1 className="text-4xl font-display font-bold text-white tracking-tight flex items-center gap-3">
          <Zap className="w-8 h-8 text-cyan-400" /> State Relations Ledger
        </h1>
        <p className="text-slate-400 mt-2 text-lg">Cross-border atmospheric PM2.5 transport flows and active Vaayu Token liability claims (Period: 2023-v5).</p>
      </div>

      {summary.count > 0 && (
        <div className="glass-panel border-l-4 border-l-red-500 bg-red-500/5 p-6 animate-slide-up flex items-start gap-4">
          <AlertTriangle className="w-8 h-8 text-red-500 flex-shrink-0" />
          <div>
            <h3 className="text-red-400 text-lg font-bold font-display">Active Penalties Detected</h3>
            <p className="text-red-200/80 mt-1">
              You owe fines to {summary.count} states totalling <span className="font-mono font-bold text-red-300">{summary.total} VT</span> this period, derived directly from states you are actively affecting via validated atmospheric PM2.5 transport.
            </p>
          </div>
        </div>
      )}

      <div className="grid lg:grid-cols-2 gap-8">
         <section className="glass-panel p-6 rounded-2xl animate-slide-up bg-gradient-to-br from-slate-900/80 to-slate-800/50" style={{ animationDelay: '0.1s' }}>
           <h2 className="font-display font-semibold text-xl mb-6 text-white flex items-center gap-2">
             <span className="w-2 h-6 rounded-full bg-amber-500 inline-block"></span>
             States You Are Affecting
           </h2>
           <p className="text-sm text-slate-400 mb-4">Emissions generated by your state migrating and polluting neighboring zones (Liability & Fines).</p>
           <RelationsTable rows={relations.affecting} isLiability={true} />
         </section>

         <section className="glass-panel p-6 rounded-2xl animate-slide-up bg-gradient-to-br from-slate-900/80 to-slate-800/50" style={{ animationDelay: '0.2s' }}>
           <h2 className="font-display font-semibold text-xl mb-6 text-white flex items-center gap-2">
             <span className="w-2 h-6 rounded-full bg-emerald-500 inline-block"></span>
             States Affecting You
           </h2>
           <p className="text-sm text-slate-400 mb-4">Emissions generated by neighboring states drifting into your atmospheric borders (Incoming PM2.5 Impact).</p>
           <RelationsTable rows={relations.affected_by} isLiability={false} />
         </section>
      </div>

    </div>
  );
}
