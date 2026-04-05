import { supabase } from "../lib/supabase";
import { DUMMY_STATES, DUMMY_TIMESERIES, DUMMY_RELATIONS } from "../dummy/dummyData";

export async function getStateByName(name) {
  // TODO: Replace with Supabase query
  const { data, error } = await supabase
    .from("states")
    .select("*")
    .eq("name", name)
    .single();
  if (error) throw error;
  return data;
  //return DUMMY_STATES.find((state) => state.name === name) || DUMMY_STATES[6]; // DUMMY DATA - replace with Supabase query
}

export async function getStateTimeseries(stateId, stateName) {
   const { data, error } = await supabase
     .from("vt_history")
     .select("*")
     .eq("state_id", stateId)
     .order("year");
   if (error) throw error;
   return data;
  // return DUMMY_TIMESERIES[stateName] || DUMMY_TIMESERIES.Karnataka; // DUMMY DATA - replace with Supabase query
}

export async function getStateRelations(stateId) {
  const { data, error } = await supabase
    .from("carbon_relations")
    .select(`
      *,
      source_state:states!source_state_id(name),
      target_state:states!target_state_id(name)
    `)
    .or(`source_state_id.eq.${stateId},target_state_id.eq.${stateId}`);

  if (error) throw error;

  const affected_by = data
    .filter((rel) => rel.target_state_id === stateId)
    .map((rel) => ({
      state: rel.source_state?.name || "Unknown",
      type: rel.relation_type || "Unknown relation",
      vt_impact: rel.vt_impact || 0,
      status: rel.status || "neutral",
    }));

  const affecting = data
    .filter((rel) => rel.source_state_id === stateId)
    .map((rel) => ({
      state: rel.target_state?.name || "Unknown",
      type: rel.relation_type || "Unknown relation",
      vt_impact: rel.vt_impact || 0,
      status: rel.status || "neutral",
    }));

  return { affected_by, affecting };
}

export { supabase };
