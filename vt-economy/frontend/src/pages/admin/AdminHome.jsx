// PAGE: AdminHome
// ROUTE: /app/home (role=admin)
// ROLE: admin
// DATA SOURCE: TBD
// STATUS: Placeholder - build after economic model finalised

export default function AdminHome() {
  const cards = ["Economic Controls", "State Audits", "Model Parameters"];

  return (
    <section>
      <h1 className="text-2xl font-bold">Central Government Console</h1>
      <div className="mt-6 grid gap-4 md:grid-cols-3">
        {cards.map((card) => (
          <article key={card} className="rounded-xl shadow-md p-6 bg-slate-800 border border-slate-700 opacity-80">
            <h3 className="text-lg font-semibold">{card}</h3>
            <p className="mt-2 inline-block rounded-full bg-slate-700 px-3 py-1 text-xs text-slate-300">Coming Soon</p>
          </article>
        ))}
      </div>

      {/* TODO: Full admin dashboard - blocked on economic model finalisation */}
    </section>
  );
}
