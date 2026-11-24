import { supabase } from "../lib/supabase";

export async function getStateByName(name) {
  const { data, error } = await supabase
    .from("states")
    .select("*")
    .eq("name", name)
    .single();
  if (error) throw error;
  return data;
}

export async function getStateTimeseries(stateId) {
  const { data, error } = await supabase
    .from("vt_history")
    .select("*")
    .eq("state_id", stateId)
    .order("year", { ascending: true });
  if (error) throw error;
  return data;
}

export async function getStateRelations(stateId, period = "2023-v5") {
  let query = supabase
    .from("carbon_relations")
    .select(`
      *,
      source_state:states!source_state_id(name),
      target_state:states!target_state_id(name)
    `)
    .or(`source_state_id.eq.${stateId},target_state_id.eq.${stateId}`);

  if (period) {
    query = query.eq("period", period);
  }

  const { data, error } = await query;
  if (error) throw error;

  let rows = data || [];
  if (!rows.length && period === "2023-v5") {
    // Fallback to 2023-v3 if 2023-v5 has no relation records
    const fallbackRes = await supabase
      .from("carbon_relations")
      .select(`
        *,
        source_state:states!source_state_id(name),
        target_state:states!target_state_id(name)
      `)
      .or(`source_state_id.eq.${stateId},target_state_id.eq.${stateId}`)
      .eq("period", "2023-v3");
    if (!fallbackRes.error && fallbackRes.data?.length) {
      rows = fallbackRes.data;
    }
  }

  const affected_by = rows
    .filter((rel) => rel.target_state_id === stateId)
    .map((rel) => ({
      state: rel.source_state?.name || "Unknown",
      type: rel.relation_type || "transport",
      vt_impact: Number(rel.vt_impact) || 0,
      status: rel.status || "neutral",
      period: rel.period,
    }));

  const affecting = rows
    .filter((rel) => rel.source_state_id === stateId)
    .map((rel) => ({
      state: rel.target_state?.name || "Unknown",
      type: rel.relation_type || "transport",
      vt_impact: Number(rel.vt_impact) || 0,
      status: rel.status || "neutral",
      period: rel.period,
    }));

  return { affected_by, affecting };
}

export { supabase };
