export default function CarbonFlowMap() {
  return (
    <section className="relative rounded-xl shadow-md p-6 bg-slate-800 border border-slate-700 h-72 flex items-center justify-center">

      {/* ✅ faint background */}
      <div className="absolute inset-0 flex items-center justify-center opacity-10 text-7xl">
        🇮🇳
      </div>

      {/* ✅ overlay content */}
      <div className="z-10 text-center">
        <p className="text-xl font-semibold text-slate-200">
          Carbon Flow Map
        </p>

        <p className="text-slate-400 mt-2">
          Visualizing cross-state carbon exchange
        </p>

        <p className="mt-4 inline-block bg-slate-700 text-slate-300 px-3 py-1 rounded-full text-xs">
          Coming Soon
        </p>
      </div>
    </section>
  );
}