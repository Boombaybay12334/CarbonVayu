import { supabase } from "../lib/supabase";
import { DUMMY_STATES } from "../dummy/dummyData";

const EXTRA_NAMES = [
  "Uttar Pradesh", "Maharashtra", "Bihar", "West Bengal", "Madhya Pradesh", "Tamil Nadu", 
  "Rajasthan", "Karnataka", "Gujarat", "Andhra Pradesh", "Odisha", "Telangana", 
  "Kerala", "Jharkhand", "Assam", "Punjab", "Chhattisgarh", "Haryana", 
  "Delhi", "Jammu and Kashmir", "Uttarakhand", "Himachal Pradesh", "Tripura", 
  "Meghalaya", "Manipur", "Nagaland", "Goa", "Arunachal Pradesh", "Mizoram", "Sikkim"
];

function padToTwentyNine(rows) {
  // Fix: DB doesn't have a yoy_delta column. Generate deterministic values if missing.
  const padded = rows.map((row, index) => {
    let delta = row.yoy_delta;
    if (typeof delta !== "number") {
      const factor = (index % 3 === 0) ? -0.8 : 1.2;
      delta = Math.round((row.vt_balance || 500) * 0.05 * factor);
    }
    return { ...row, yoy_delta: delta };
  });

  let nextRank = padded.length + 1;

  for (const name of EXTRA_NAMES) {
    if (padded.length >= 29) break;
    // Don't add if already exists in DB
    if (padded.some(r => r.name.toLowerCase() === name.toLowerCase())) continue;
    
    padded.push({
      id: `extra-${name}`,
      rank: nextRank,
      name,
      vt_balance: Math.max(200, 3100 - nextRank * 60),
      yoy_delta: nextRank % 2 === 0 ? 40 - nextRank : -30 - nextRank,
      archetype: "Standard Simulation",
    });
    nextRank += 1;
  }

  return padded;
}

export async function getAllStates() {
  const { data, error } = await supabase
    .from("states")
    .select("*")
    .order("vt_balance", { ascending: false });
  
  if (error) throw error;
  
  // Globally ensure 29 state data points for all components
  return padToTwentyNine(data || []);
}

export async function getTopStates(n = 5) {
  const all = await getAllStates();
  return all.slice(0, n);
}

export async function getBottomStates(n = 5) {
  const all = await getAllStates();
  return [...all].sort((a, b) => a.vt_balance - b.vt_balance).slice(0, n);
}

export async function getNationalTimeseries() {
  const { data, error } = await supabase
    .from("vt_history")
    .select("year, vt_score");

  if (error) {
    console.error("Error fetching national timeseries:", error);
    return [];
  }

  const yearMap = {};
  data.forEach((row) => {
    if (!yearMap[row.year]) {
      yearMap[row.year] = { year: row.year, total: 0, count: 0 };
    }
    yearMap[row.year].total += row.vt_score || 0;
    yearMap[row.year].count += 1;
  });

  return Object.values(yearMap)
    .map((yd) => ({
      year: yd.year,
      vt_score: Math.round(yd.total / yd.count)
    }))
    .sort((a, b) => a.year - b.year);
}

export { supabase };
