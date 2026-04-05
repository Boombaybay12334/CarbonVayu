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

export default function LeaderboardPage() {
  const [states, setStates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [sortBy, setSortBy] = useState("rank");
  const [sortDir, setSortDir] = useState("asc");

  useEffect(() => {
    getAllStates().then((rows) => setStates(padToThirtySix(rows)));
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
            {filtered.map((row) => (
              <tr key={row.id} className="border-b border-slate-700/60">
                <td className="p-2">{row.rank}</td>
                <td className="p-2">{row.name}</td>
                <td className="p-2">{Number(row.vt_balance).toLocaleString()}</td>
                <td className={`p-2 ${row.yoy_delta >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                  {row.yoy_delta >= 0 ? "↑" : "↓"} {row.yoy_delta >= 0 ? "+" : ""}
                  {row.yoy_delta}
                </td>
                <td className="p-2 text-slate-300">{row.archetype}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}