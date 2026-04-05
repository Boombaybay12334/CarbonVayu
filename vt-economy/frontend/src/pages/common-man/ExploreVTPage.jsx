// PAGE: ExploreVTPage
// ROUTE: /app/explore (also linked from sidebar "How We Calculate VT")
// ROLE: all
// DATA SOURCE: static content
// STATUS: Scaffold - content is placeholder

import CarbonFlowMap from "../../components/charts/CarbonFlowMap";
import StateBarChart from "../../components/charts/StateBarChart";
import { DUMMY_STATES } from "../../dummy/dummyData";

export default function ExploreVTPage() {
  return (
    <section className="space-y-5">
      <section className="rounded-xl shadow-md p-5 bg-slate-800 border border-slate-700">
        <h1 className="text-2xl font-bold">What is Vaayu Token?</h1>
        <p className="mt-3 text-slate-300 leading-relaxed">
          {/* TODO: content */}
          Vaayu Token is a policy-facing carbon accountability instrument designed to compare and reward state-level
          ecosystem stewardship across India.
        </p>
        <p className="mt-2 text-slate-300 leading-relaxed">
          {/* TODO: content */}
          It combines sinks, emissions, and cross-state externalities into a single economic signal that can support
          fiscal incentives and penalties.
        </p>
      </section>

      <section className="rounded-xl shadow-md p-5 bg-slate-800 border border-slate-700">
        <h2 className="text-xl font-semibold">How is it calculated?</h2>
        <p className="mt-3 text-slate-300">Placeholder explanation of weighted ecosystem and emissions factors.</p>
        <div className="mt-4">
          <CarbonFlowMap />
        </div>
      </section>

      <section className="rounded-xl shadow-md p-5 bg-slate-800 border border-slate-700">
        <h2 className="text-xl font-semibold">Why trust the model?</h2>
        <p className="mt-3 text-slate-300">
          Placeholder section for model validation, audit trail, and inter-state review transparency.
        </p>
      </section>

      <section className="rounded-xl shadow-md p-5 bg-slate-800 border border-slate-700">
        <h2 className="text-xl font-semibold">Impact on Indian states</h2>
        <div className="mt-4">
          <StateBarChart data={DUMMY_STATES} title="Dummy VT Balances" />
        </div>
      </section>
    </section>
  );
}
