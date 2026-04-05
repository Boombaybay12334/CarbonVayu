import { useMemo, useState, useEffect } from "react";
import { getAllStates } from "../../services/leaderboardService";

const EXTRA_NAMES = [
  "Maharashtra", "Gujarat", "Punjab", "Bihar", "Assam", "West Bengal", "Andhra Pradesh", "Telangana",
  "Tripura", "Manipur", "Nagaland", "Andaman and Nicobar Islands", "Chandigarh", "Jammu and Kashmir",
  "Ladakh", "Lakshadweep", "Puducherry", "Dadra and Nagar Haveli and Daman and Diu",
];

function padToThirtySix(rows) {
  const padded = [...rows];
  let nextRank = padded.length + 1;

  for (const name of EXTRA_NAMES) {
    if (padded.length >= 28) break;
    padded.push({
      id: `extra-${name}`,
      rank: nextRank,
      name,
      vt_balance: Math.max(500, 3600 - nextRank * 70),
      yoy_delta: nextRank % 2 === 0 ? 40 - nextRank : -30 - nextRank,
      archetype: "Placeholder Archetype",
    });
    nextRank += 1;
  }

  return padded;
}

// ✅ Animated number (safe, handles negatives, no NaN)
function AnimatedNumber({ value }) {
  const safeValue = Number(value) || 0;
  const [display, setDisplay] = useState(0);

  useEffect(() => {
    let start = 0;
    const duration = 800;
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

  return <span>{display}</span>;
}

export default function LeaderboardPage() {
  const [states, setStates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [sortBy, setSortBy] = useState("rank");
  const [sortDir, setSortDir] = useState("asc");

  // ✅ Slight delay so skeleton is visible (important for demo)
  useEffect(() => {
    setLoading(true);

    setTimeout(() => {
      getAllStates()
        .then((rows) => setStates(padToThirtySix(rows)))
        .finally(() => setLoading(false));
    }, 800);
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
      if (typeof av === "number" && typeof bv === "number") {
        return (av - bv) * factor;
      }
      return String(av).localeCompare(String(bv)) * factor;
    });
  }, [search, sortBy, sortDir, states]);

  function toggleSort(column) {
    if (sortBy === column) {
      setSortDir((dir) =>
        dir === "asc" ? "desc" : "asc"
      );
      return;
    }
    setSortBy(column);
    setSortDir("asc");
  }

  return (
    <section className="rounded-xl shadow-md p-4 bg-slate-800 border border-slate-700">
      <h1 className="text-2xl font-bold">
        National VT Leaderboard
      </h1>

      <input
        type="text"
        placeholder="Search by state"
        className="mt-4 w-full md:w-80 rounded-lg border border-slate-600 bg-slate-900 px-3 py-2"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
      />

      {/* ✅ Horizontal scroll */}
      <div className="mt-4 overflow-x-auto">
        <table className="w-full text-left text-sm min-w-[600px]">
          <thead>
            <tr className="text-slate-300 border-b border-slate-700">
              <th className="p-2 cursor-pointer" onClick={() => toggleSort("rank")}>Rank</th>
              <th className="p-2 cursor-pointer" onClick={() => toggleSort("name")}>State</th>
              <th className="p-2 cursor-pointer" onClick={() => toggleSort("vt_balance")}>VT Score</th>
              <th className="p-2 cursor-pointer" onClick={() => toggleSort("yoy_delta")}>YoY Change</th>
              <th className="p-2 cursor-pointer" onClick={() => toggleSort("archetype")}>Archetype</th>
            </tr>
          </thead>

          <tbody>
            {loading ? (
              // ✅ Skeleton loading rows
              [...Array(6)].map((_, i) => (
                <tr key={i} className="animate-pulse border-b border-slate-700/40">
                  <td className="p-2"><div className="h-4 bg-slate-700 rounded w-6"></div></td>
                  <td className="p-2"><div className="h-4 bg-slate-700 rounded w-24"></div></td>
                  <td className="p-2"><div className="h-4 bg-slate-700 rounded w-20"></div></td>
                  <td className="p-2"><div className="h-4 bg-slate-700 rounded w-16"></div></td>
                  <td className="p-2"><div className="h-4 bg-slate-700 rounded w-28"></div></td>
                </tr>
              ))
            ) : (
              filtered.map((row) => {
                const yoy = Number(row.yoy_delta) || 0;

                return (
                  <tr
                    key={row.id}
                    className="border-b border-slate-700/60 hover:bg-slate-700/40 transition"
                  >
                    <td className="p-2">{row.rank}</td>

                    <td className="p-2">{row.name}</td>

                    <td className="p-2">
                      {Number(row.vt_balance).toLocaleString()}
                    </td>

                    {/* ✅ Animated YoY */}
                    <td className={`p-2 ${yoy >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                      {yoy >= 0 ? "↑" : "↓"}{" "}
                      {yoy >= 0 ? "+" : ""}
                      <AnimatedNumber value={yoy} />
                    </td>

                    <td className="p-2 text-slate-300">
                      {row.archetype}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}