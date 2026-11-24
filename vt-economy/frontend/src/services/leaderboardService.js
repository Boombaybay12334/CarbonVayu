import { supabase } from "../lib/supabase";

export async function getAllStates() {
  const [statesRes, historyRes] = await Promise.all([
    supabase
      .from("states")
      .select("*")
      .order("rank", { ascending: true }),
    supabase
      .from("vt_history")
      .select("state_id, year, vt_score, note")
      .in("year", [2022, 2023]),
  ]);

  if (statesRes.error) throw statesRes.error;
  const states = statesRes.data || [];
  const history = historyRes.data || [];

  // Map history by state_id to calculate real YoY delta and parse 95% CIs
  const histMap = {};
  for (const h of history) {
    if (!histMap[h.state_id]) histMap[h.state_id] = {};
    histMap[h.state_id][h.year] = h.vt_score;
    if (h.year === 2023 && h.note) {
      // Note format contains: "...; 95% CI=[521.8, 545.7]"
      const match = h.note.match(/95% CI=\[([\d.]+),\s*([\d.]+)\]/);
      if (match) {
        histMap[h.state_id].ci_low = parseFloat(match[1]);
        histMap[h.state_id].ci_high = parseFloat(match[2]);
      }
    }
  }

  return states.map((s) => {
    const h = histMap[s.id] || {};
    let yoy_delta = 0;
    if (h[2023] != null && h[2022] != null) {
      yoy_delta = Math.round((Number(h[2023]) - Number(h[2022])) * 100) / 100;
    } else {
      yoy_delta = 0;
    }

    return {
      ...s,
      yoy_delta,
      vt_ci_low: h.ci_low ?? null,
      vt_ci_high: h.ci_high ?? null,
      is_modeled: (s.rank <= 22),
    };
  });
}

export async function getTopStates(n = 5) {
  const all = await getAllStates();
  return all.filter((s) => s.is_modeled).slice(0, n);
}

export async function getBottomStates(n = 5) {
  const all = await getAllStates();
  const modeled = all.filter((s) => s.is_modeled);
  return [...modeled].sort((a, b) => a.vt_balance - b.vt_balance).slice(0, n);
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
  (data || []).forEach((row) => {
    if (!row.year) return;
    if (!yearMap[row.year]) {
      yearMap[row.year] = { year: row.year, total: 0, count: 0 };
    }
    yearMap[row.year].total += Number(row.vt_score) || 0;
    yearMap[row.year].count += 1;
  });

  return Object.values(yearMap)
    .map((yd) => ({
      year: yd.year,
      vt_score: Math.round(yd.total / (yd.count || 1)),
    }))
    .sort((a, b) => a.year - b.year);
}

export { supabase };
