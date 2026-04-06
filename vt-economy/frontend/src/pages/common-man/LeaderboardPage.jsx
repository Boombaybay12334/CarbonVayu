import { useMemo, useState, useEffect } from "react";
import { getAllStates } from "../../services/leaderboardService";

export default function LeaderboardPage() {
  const [states, setStates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [sortBy, setSortBy] = useState("rank");
  const [sortDir, setSortDir] = useState("asc");

  useEffect(() => {
    getAllStates()
      .then((rows) => setStates(rows))
      .finally(() => setLoading(false));
  }, []);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    let rows = states;

    if (q) {
      rows = rows.filter((row) =>
        row.name.toLowerCase().includes(q)
      );
    }

    const factor = sortDir === "asc" ? 1 : -1;

    return [...rows].sort((a, b) => {
      const av = a[sortBy];
      const bv = b[sortBy];
      if (typeof av === "number" && typeof bv === "number") return (av - bv) * factor;
      return String(av).localeCompare(String(bv)) * factor;
    });
  }, [search, sortBy, sortDir, states]);

  function toggleSort(column) {
    if (sortBy === column) {
      setSortDir((dir) => (dir === "asc" ? "desc" : "asc"));
      return;
    }
    setSortBy(column);
    setSortDir("asc");
  }

  return (
    <div className="max-w-7xl mx-auto px-4 pb-12 space-y-8 text-white">
      {/* Header */}
      <div className="relative pt-4 flex flex-col md:flex-row justify-between items-end gap-6 z-10 animate-slide-up">
        <div className="absolute -top-10 -left-10 w-64 h-64 bg-primary/20 rounded-full blur-[80px] -z-10"></div>
        <div>
          <h1 className="text-4xl md:text-5xl font-display font-bold bg-gradient-to-r from-emerald-400 to-cyan-400 bg-clip-text text-transparent">
            National VT Leaderboard
          </h1>
          <p className="text-slate-400 mt-2 text-lg max-w-2xl">
            Rankings based on state-level climate contributions, carbon sink management, and cumulative Vaayu Token balances.
          </p>
        </div>
      </div>

      <section className="glass-panel rounded-2xl p-6 relative overflow-hidden animate-slide-up" style={{ animationDelay: '0.1s' }}>
        <div className="absolute top-0 right-0 w-64 h-64 bg-secondary/5 rounded-full blur-[60px] -z-10 pointer-events-none"></div>
        
        {/* Search & Actions */}
        <div className="mb-6 flex flex-col sm:flex-row gap-4 justify-between items-center relative z-10">
          <div className="relative w-full sm:w-96 group">
            <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-400 group-focus-within:text-primary transition-colors">
              <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M8 4a4 4 0 100 8 4 4 0 000-8zM2 8a6 6 0 1110.89 3.476l4.817 4.817a1 1 0 01-1.414 1.414l-4.816-4.816A6 6 0 012 8z" clipRule="evenodd" />
              </svg>
            </div>
            <input
              type="text"
              placeholder="Search states..."
              className="w-full rounded-xl border border-white/10 bg-slate-900/50 pl-10 pr-4 py-3 text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary/50 transition-all shadow-inner"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
        </div>

        {/* Table */}
        <div className="max-h-[500px] overflow-y-auto overflow-x-auto custom-scrollbar rounded-xl border border-white/5 bg-slate-900/30 backdrop-blur-sm relative z-10">
          {loading ? (
            <div className="flex justify-center items-center h-64">
               <div className="w-8 h-8 flex gap-1">
                  <span className="w-2 h-full bg-primary/80 animate-bounce rounded-full"></span>
                  <span className="w-2 h-full bg-primary/80 animate-bounce rounded-full" style={{animationDelay: '0.1s'}}></span>
                  <span className="w-2 h-full bg-primary/80 animate-bounce rounded-full" style={{animationDelay: '0.2s'}}></span>
                </div>
            </div>
          ) : (
            <table className="w-full text-left min-w-[700px]">
              <thead className="bg-slate-800/80 backdrop-blur-md sticky top-0 z-20">
                <tr className="text-slate-300 border-b border-white/10 uppercase text-xs tracking-wider font-semibold">
                  <th className="p-4 cursor-pointer hover:text-white transition-colors group" onClick={() => toggleSort("rank")}>
                    Rank {sortBy === "rank" && <span className="text-primary">{sortDir === "asc" ? "▲" : "▼"}</span>}
                  </th>
                  <th className="p-4 cursor-pointer hover:text-white transition-colors group" onClick={() => toggleSort("name")}>
                    State {sortBy === "name" && <span className="text-primary">{sortDir === "asc" ? "▲" : "▼"}</span>}
                  </th>
                  <th className="p-4 cursor-pointer hover:text-white transition-colors group" onClick={() => toggleSort("vt_balance")}>
                    VT Score {sortBy === "vt_balance" && <span className="text-primary">{sortDir === "asc" ? "▲" : "▼"}</span>}
                  </th>
                  <th className="p-4 cursor-pointer hover:text-white transition-colors group" onClick={() => toggleSort("yoy_delta")}>
                    YoY Change {sortBy === "yoy_delta" && <span className="text-primary">{sortDir === "asc" ? "▲" : "▼"}</span>}
                  </th>
                  <th className="p-4 cursor-pointer hover:text-white transition-colors group" onClick={() => toggleSort("archetype")}>
                    Archetype {sortBy === "archetype" && <span className="text-primary">{sortDir === "asc" ? "▲" : "▼"}</span>}
                  </th>
                </tr>
              </thead>

              <tbody className="divide-y divide-white/5">
                {filtered.map((row) => (
                  <tr key={row.id} className="hover:bg-white/5 transition-colors group">
                    <td className="p-4 font-display font-semibold">
                      <span className="inline-flex items-center justify-center w-8 h-8 rounded-full bg-slate-800 border border-white/10 group-hover:border-primary/50 group-hover:text-primary transition-colors">
                        {row.rank}
                      </span>
                    </td>
                    <td className="p-4 font-medium text-slate-200">{row.name}</td>
                    <td className="p-4 font-display text-lg tracking-tight">{(Number(row.vt_balance) || 0).toLocaleString()}</td>
                    <td className={`p-4 font-medium flex items-center gap-1 ${row.yoy_delta >= 0 ? "text-emerald-400" : "text-amber-400"}`}>
                      {row.yoy_delta >= 0 ? (
                         <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6"></path></svg>
                      ) : (
                         <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 17h8m0 0v-8m0 8l-8-8-4 4-6-6"></path></svg>
                      )}
                      <span>{row.yoy_delta >= 0 ? "+" : ""}{(row.yoy_delta || 0).toLocaleString()}</span>
                    </td>
                    <td className="p-4">
                      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-slate-800 text-slate-300 border border-slate-700">
                        {row.archetype || "Standard"}
                      </span>
                    </td>
                  </tr>
                ))}
                {filtered.length === 0 && (
                  <tr>
                    <td colSpan="5" className="p-8 text-center text-slate-500">No states found matching your search.</td>
                  </tr>
                )}
              </tbody>
            </table>
          )}
        </div>
      </section>
    </div>
  );
}