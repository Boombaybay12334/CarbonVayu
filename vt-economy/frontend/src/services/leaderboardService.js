import { supabase } from "../lib/supabase";

export async function getAllStates() {
  const [statesRes, historyRes, bundleRes] = await Promise.allSettled([
    supabase
      .from("states")
      .select("*")
      .order("rank", { ascending: true }),
    supabase
      .from("vt_history")
      .select("state_id, year, vt_score, note")
      .in("year", [2022, 2023]),
    fetch("/v5/vt_v5_bundle.json").then((r) => (r.ok ? r.json() : null)),
  ]);

  if (statesRes.status === "rejected" || statesRes.value.error) {
    throw statesRes.value?.error || new Error("Failed to load states");
  }
  const states = statesRes.value.data || [];
  const history = historyRes.status === "fulfilled" && !historyRes.value.error ? historyRes.value.data || [] : [];
  const bundle = bundleRes.status === "fulfilled" ? bundleRes.value : null;

  const bundleMap = {};
  if (bundle?.leaderboard) {
    bundle.leaderboard.forEach((b) => {
      bundleMap[b.state.toLowerCase()] = b;
    });
  }

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
    const b = bundleMap[s.name?.toLowerCase()] || {};
    let yoy_delta = 0;
    if (h[2023] != null && h[2022] != null) {
      yoy_delta = Math.round((Number(h[2023]) - Number(h[2022])) * 100) / 100;
    } else {
      yoy_delta = 0;
    }

    const ci_low = h.ci_low ?? (b.vt_ci_low != null ? Number(b.vt_ci_low.toFixed(1)) : null);
    const ci_high = h.ci_high ?? (b.vt_ci_high != null ? Number(b.vt_ci_high.toFixed(1)) : null);
    const settledScore = b.vt_settled ?? s.vt_balance;

    return {
      ...s,
      vt_balance: settledScore != null ? Number(Number(settledScore).toFixed(2)) : s.vt_balance,
      yoy_delta,
      vt_ci_low: ci_low,
      vt_ci_high: ci_high,
      pillar_A_export: b.pillar_A_export ?? null,
      pillar_B_progress: b.pillar_B_progress ?? null,
      pillar_C_re: b.pillar_C_re ?? null,
      audit_flag: b.audit_flag ?? null,
      pm25_curr: b.pm25_curr ?? null,
      is_modeled: s.rank <= 22,
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
