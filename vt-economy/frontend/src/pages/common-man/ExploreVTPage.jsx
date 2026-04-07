import { useNavigate } from "react-router-dom";

export default function ExploreVTPage() {
  const navigate = useNavigate();

  return (
    <div className="text-white space-y-12 max-w-6xl mx-auto pb-16 px-4">

      {/* HERO */}
      <section className="text-center max-w-3xl mx-auto pt-10 animate-slide-up">
        <h1 className="text-4xl md:text-5xl font-display font-bold bg-gradient-to-r from-emerald-400 to-cyan-400 bg-clip-text text-transparent">
          Understanding Vaayu Token 🌍
        </h1>
        <p className="text-slate-400 mt-4 text-lg">
          A complete breakdown of how carbon accountability is measured,
          distributed, and enforced across Indian states.
        </p>
      </section>

      {/* PROBLEM */}
      <section className="glass-panel p-8 rounded-2xl border-l-4 border-l-red-500 animate-slide-up" style={{ animationDelay: '0.1s' }}>
        <h2 className="text-2xl font-display font-bold flex items-center gap-2 text-white">
          <span className="text-red-400">🚨</span> The Problem
        </h2>

        <p className="mt-4 text-slate-300 leading-relaxed text-lg">
          Traditional environmental systems treat states independently.
          However, pollution does not stay within borders — it travels
          across regions through wind and atmospheric movement.
        </p>

        <ul className="mt-4 text-slate-400 space-y-2">
          <li className="flex items-start gap-2"><span className="text-red-500 mt-1">•</span> States get unfair credit or blame for imported emissions</li>
          <li className="flex items-start gap-2"><span className="text-red-500 mt-1">•</span> Policies ignore massive cross-state pollution shifts</li>
          <li className="flex items-start gap-2"><span className="text-red-500 mt-1">•</span> No accountability for transported industrial exhaust</li>
        </ul>
      </section>

      {/* SOLUTION */}
      <section className="glass-panel p-10 rounded-2xl relative overflow-hidden animate-slide-up" style={{ animationDelay: '0.2s' }}>
        <div className="absolute -top-32 -right-32 w-64 h-64 bg-primary/20 rounded-full blur-[80px] -z-10 pointer-events-none"></div>

        <h2 className="text-3xl font-display font-bold text-transparent bg-clip-text bg-gradient-to-r from-emerald-400 to-emerald-200 text-center mb-8">
          ✅ The Solution: Vaayu Token (VT)
        </h2>

        <p className="text-slate-300 leading-relaxed max-w-4xl mx-auto text-lg text-center mb-8">
          Vaayu Token (VT) is a unified climate accountability score that evaluates
          environmental performance across states in a fair and interconnected way.
          It integrates emissions, carbon absorption, pollution transfer, and governance
          effort into a single measurable metric.
        </p>

        {/* FORMULA */}
        <div className="text-emerald-400 text-xl md:text-2xl font-display font-semibold bg-slate-900/80 py-6 rounded-xl border border-emerald-500/30 text-center shadow-[0_0_25px_rgba(16,185,129,0.15)] mb-10">
          VT = Carbon Balance × Effort × Normalisation
        </div>

        <div className="grid md:grid-cols-2 gap-8">
          {/* STEP 1 */}
          <div className="glass-card p-6 border-white/5">
            <h3 className="text-xl font-display font-semibold text-emerald-400 mb-2">1. Carbon Balance</h3>
            <p className="text-slate-400">
              Measures how much carbon a state produces versus how much it absorbs,
              ensuring accurate foundational environmental evaluation.
            </p>
          </div>

          {/* STEP 2 */}
          <div className="glass-card p-6 border-white/5">
            <h3 className="text-xl font-display font-semibold text-cyan-400 mb-2">2. Carbon Flow (M2)</h3>
            <p className="text-slate-400 mb-3">
              Pollution travels via wind. Modeled using transport matrices to capture real interactions.
            </p>
            <ul className="text-slate-500 text-sm space-y-1">
              <li>• Identifies pollution origins</li>
              <li>• Compensates pollution receivers</li>
            </ul>
          </div>

          {/* STEP 3 */}
          <div className="glass-card p-6 border-white/5">
            <h3 className="text-xl font-display font-semibold text-amber-400 mb-2">3. Effort Score (M3)</h3>
            <p className="text-slate-400">
              Measures sustainability improvements across renewable energy adoption,
              forest cover expansion, and operational efficiency gradients.
            </p>
          </div>

          {/* STEP 4 */}
          <div className="glass-card p-6 border-white/5">
            <h3 className="text-xl font-display font-semibold text-blue-400 mb-2">4. Normalisation</h3>
            <p className="text-slate-400">
              Mathematical bounding to assure scaling fairness regardless of a state's geographic size, baseline climate, and economic capacity.
            </p>
          </div>
        </div>

        {/* INCENTIVES TABLE */}
        <div className="mt-12 border-t border-white/10 pt-8">
          <h3 className="text-2xl font-display font-semibold text-white text-center mb-8">Incentives & Penalties Framework</h3>
          
          <div className="overflow-x-auto rounded-xl border border-white/10 bg-slate-900/60 backdrop-blur-md shadow-2xl">
            <table className="w-full text-left min-w-[700px]">
              <thead className="bg-[#103E34] text-emerald-50">
                <tr className="uppercase text-xs tracking-wider font-semibold">
                  <th className="p-4 rounded-tl-xl">VT Range</th>
                  <th className="p-4">Zone</th>
                  <th className="p-4">Central Fund Freeze / Allotment</th>
                  <th className="p-4 rounded-tr-xl">Loan Interest Rate Change</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {[
                  { range: "480–499", zone: "Mild penalty", fund: "5% frozen", loan: "+0.25%", color: "text-red-300", bg: "hover:bg-red-500/10" },
                  { range: "440–479", zone: "Moderate penalty", fund: "10% frozen", loan: "+0.75%", color: "text-red-400", bg: "hover:bg-red-500/10" },
                  { range: "400–439", zone: "Severe penalty", fund: "15% frozen", loan: "+1.50%", color: "text-red-400 font-semibold", bg: "hover:bg-red-500/10" },
                  { range: "300–399", zone: "Critical penalty", fund: "20% frozen", loan: "+3.00%", color: "text-red-500 font-bold", bg: "hover:bg-red-500/10" },
                  { range: "500", zone: "Maintenance", fund: "No freeze", loan: "No change", color: "text-slate-300", bg: "bg-slate-800/50 hover:bg-slate-800" },
                  { range: "501–550", zone: "Mild incentive", fund: "+3% of base allotment", loan: "Standard", color: "text-emerald-300", bg: "hover:bg-emerald-500/10" },
                  { range: "551–600", zone: "Moderate incentive", fund: "+6% of base allotment", loan: "-0.25%", color: "text-emerald-400", bg: "hover:bg-emerald-500/10" },
                  { range: "601–650", zone: "Strong incentive", fund: "+8% of base allotment", loan: "-0.50%", color: "text-emerald-400 font-semibold", bg: "hover:bg-emerald-500/10" },
                  { range: "651–700", zone: "Maximum incentive", fund: "+10% of base allotment", loan: "-0.75%", color: "text-emerald-500 font-bold", bg: "hover:bg-emerald-500/10" },
                ].map((row, i) => (
                  <tr key={i} className={`transition-colors ${row.bg}`}>
                    <td className={`p-4 font-mono font-medium ${row.color}`}>{row.range}</td>
                    <td className={`p-4 ${row.color}`}>{row.zone}</td>
                    <td className="p-4 text-slate-300">{row.fund}</td>
                    <td className="p-4 text-slate-300 font-mono">{row.loan}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>


      {/* CTA */}
      <div className="flex justify-center pt-6 animate-slide-up" style={{ animationDelay: '0.4s' }}>
        <button
          onClick={() => navigate("/app/national-visuals")}
          className="group relative inline-flex items-center gap-2 overflow-hidden rounded-full bg-gradient-to-r from-primary to-cyan-500 px-8 py-4 text-white font-semibold transition-all hover:scale-105 shadow-[0_0_20px_rgba(16,185,129,0.2)] hover:shadow-[0_0_30px_rgba(16,185,129,0.4)]"
        >
          <span className="relative z-10 text-lg">View National Real-Time Insights</span>
          <svg className="w-5 h-5 relative z-10 transition-transform group-hover:translate-x-1" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M14 5l7 7m0 0l-7 7m7-7H3"></path></svg>
          <div className="absolute inset-0 bg-white/20 transform -skew-x-12 -translate-x-full group-hover:animate-[shimmer_1.5s_infinite]"></div>
        </button>
      </div>

    </div>
  );
}