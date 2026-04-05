export default function ExploreVTPage() {
  return (
    <section className="space-y-6 p-4">

      {/* WHAT IS VT */}
      <div className="rounded-xl bg-slate-800 border border-slate-700 p-5">
        <h2 className="text-xl font-bold">🌍 What is Vaayu Token (VT)?</h2>
        <p className="mt-3 text-slate-300">
          Vaayu Token (VT) is a carbon accountability score for each state.
          It measures how much a state pollutes versus how much it helps absorb carbon.
        </p>
      </div>

      {/* HOW VT WORKS */}
      <div className="rounded-xl bg-slate-800 border border-slate-700 p-5">
        <h2 className="text-xl font-bold">⚙️ How VT Works</h2>

        <div className="mt-3 text-slate-400 space-y-2">
          <p>• Carbon absorbed (forests & ecosystems)</p>
          <p>• Carbon emitted (industry, transport)</p>
          <p>• Pollution affecting other states</p>
          <p>• Effort (renewables, AQI, forest growth)</p>
        </div>
      </div>

      {/* INFO CARDS */}
      <div className="grid gap-4 md:grid-cols-3">

        <div className="rounded-xl bg-slate-900 border border-slate-700 p-4">
          <h3 className="font-semibold text-emerald-300">🌿 Absorption</h3>
          <p className="text-sm text-slate-400 mt-2">
            Nature removes CO₂ through forests and ecosystems.
          </p>
        </div>

        <div className="rounded-xl bg-slate-900 border border-slate-700 p-4">
          <h3 className="font-semibold text-red-300">🏭 Emissions</h3>
          <p className="text-sm text-slate-400 mt-2">
            Human activities release carbon into the atmosphere.
          </p>
        </div>

        <div className="rounded-xl bg-slate-900 border border-slate-700 p-4">
          <h3 className="font-semibold text-blue-300">⚖️ Balance</h3>
          <p className="text-sm text-slate-400 mt-2">
            VT depends on the balance between emission and absorption.
          </p>
        </div>

      </div>

      {/* WHY IT MATTERS */}
      <div className="rounded-xl bg-slate-800 border border-slate-700 p-5">
        <h2 className="text-xl font-bold">💰 Why It Matters</h2>

        <div className="mt-3 text-slate-300 space-y-2">
          <p>• High VT → rewards</p>
          <p>• Low VT → penalties</p>
          <p>• Drives real climate action</p>
        </div>
      </div>

      {/* HOW TO IMPROVE */}
      <div className="rounded-xl bg-slate-800 border border-slate-700 p-5">
        <h2 className="text-xl font-bold">📈 How States Improve</h2>

        <div className="mt-3 text-slate-300 space-y-2">
          <p>• Increase renewable energy</p>
          <p>• Improve air quality</p>
          <p>• Expand forests</p>
          <p>• Reduce emissions</p>
        </div>
      </div>

    </section>
  );
}