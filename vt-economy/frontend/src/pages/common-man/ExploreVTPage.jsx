import { useNavigate } from "react-router-dom";

export default function ExploreVTPage() {
  const navigate = useNavigate();

  return (
    <div className="text-white space-y-12 max-w-6xl mx-auto">

      {/* HERO */}
      <section className="text-center max-w-3xl mx-auto">
        <h1 className="text-3xl font-bold">Understanding Vaayu Token 🌍</h1>
        <p className="text-slate-400 mt-2">
          A complete breakdown of how carbon accountability is measured,
          distributed, and enforced across Indian states.
        </p>
      </section>

      {/* PROBLEM */}
      <section className="bg-red-500/5 border border-red-400/20 p-6 rounded-xl">
        <h2 className="text-2xl font-bold text-center">🚨 The Problem</h2>

        <p className="mt-4 text-slate-300 leading-relaxed">
          Traditional environmental systems treat states independently.
          However, pollution does not stay within borders — it travels
          across regions through wind and atmospheric movement.
        </p>

        <ul className="mt-4 text-slate-400 space-y-1 text-sm">
          <li>• States get unfair credit or blame</li>
          <li>• Policies ignore cross-state pollution</li>
          <li>• No accountability for transported emissions</li>
        </ul>
      </section>

      {/* SOLUTION */}
      <section className="bg-green-500/10 border border-green-400/30 p-8 rounded-2xl space-y-8 shadow-[0_0_40px_rgba(34,197,94,0.15)]">

        {/* ONLY THIS CENTERED */}
        <h2 className="text-3xl font-bold text-green-300 text-center">
          ✅ The Solution: Vaayu Token (VT)
        </h2>

        {/* LEFT */}
        <p className="text-slate-200 leading-relaxed max-w-3xl">
          Vaayu Token (VT) is a unified climate accountability score that evaluates
          environmental performance across states in a fair and interconnected way.
          It integrates emissions, carbon absorption, pollution transfer, and governance
          effort into a single measurable metric.
        </p>

        {/* FORMULA CENTER LOOKS GOOD */}
        <div className="text-green-400 text-xl font-semibold bg-slate-900/60 py-4 rounded-lg border border-green-400/20 text-center">
          VT = Carbon Balance × Effort × Normalisation
        </div>

        {/* STEP 1 */}
        <div>
          <h3 className="text-lg font-semibold text-green-300">
            1. Carbon Balance
          </h3>
          <p className="text-slate-300 mt-2">
            Measures how much carbon a state produces versus how much it absorbs,
            ensuring accurate environmental evaluation.
          </p>
        </div>

        {/* STEP 2 */}
        <div>
          <h3 className="text-lg font-semibold text-green-300">
            2. Carbon Flow (M2 Matrix)
          </h3>
          <p className="text-slate-300 mt-2">
            Pollution travels across states through wind. This is modeled using
            transport matrices to capture real-world environmental interactions.
          </p>

          <ul className="mt-2 text-slate-400 text-sm space-y-1">
            <li>• Identifies which states pollute others</li>
            <li>• Identifies pollution receivers</li>
            <li>• Detects major pollution corridors</li>
          </ul>
        </div>

        {/* STEP 3 */}
        <div>
          <h3 className="text-lg font-semibold text-green-300">
            3. Effort Score (M3)
          </h3>
          <p className="text-slate-300 mt-2">
            Measures sustainability improvements across renewable energy,
            forest cover, air quality, and efficiency.
          </p>
        </div>

        {/* STEP 4 */}
        <div>
          <h3 className="text-lg font-semibold text-green-300">
            4. Normalisation
          </h3>
          <p className="text-slate-300 mt-2">
            Ensures fairness across states of different sizes and economic capacities.
          </p>
        </div>

        {/* STEP 5 */}
        <div>
          <h3 className="text-lg font-semibold text-green-300">
            5. Incentives & Penalties
          </h3>

          <div className="grid md:grid-cols-2 gap-4 mt-3">
            <div className="bg-green-500/10 p-4 rounded-lg border border-green-400/20">
              <p className="text-green-300 font-semibold">High VT (500+)</p>
              <p className="text-sm text-slate-400 mt-2">
                Increased funding and policy advantages.
              </p>
            </div>

            <div className="bg-red-500/10 p-4 rounded-lg border border-red-400/20">
              <p className="text-red-300 font-semibold">Low VT (&lt;500)</p>
              <p className="text-sm text-slate-400 mt-2">
                Financial penalties and stricter regulations.
              </p>
            </div>
          </div>
        </div>

      </section>

      {/* CTA */}
      <div className="flex justify-center">
        <button
          onClick={() => navigate("/app/national-visuals")}
          className="bg-emerald-600 hover:bg-emerald-500 px-6 py-2 rounded-lg"
        >
          View National Insights →
        </button>
      </div>

    </div>
  );
}