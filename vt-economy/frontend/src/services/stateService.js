import { supabase } from "../lib/supabase";
import { DUMMY_STATES, DUMMY_TIMESERIES, DUMMY_RELATIONS } from "../dummy/dummyData";

export async function getStateByName(name) {
  // TODO: Replace with Supabase query
  // const { data, error } = await supabase
  //   .from("states")
  //   .select("*")
  //   .eq("name", name)
  //   .single();
  // if (error) throw error;
  // return data;
  return DUMMY_STATES.find((state) => state.name === name) || DUMMY_STATES[6]; // DUMMY DATA - replace with Supabase query
}

export async function getStateTimeseries(stateId, stateName) {
  // TODO: Replace with Supabase query
  // const { data, error } = await supabase
  //   .from("vt_history")
  //   .select("*")
  //   .eq("state_id", stateId)
  //   .order("year");
  // if (error) throw error;
  // return data;
  return DUMMY_TIMESERIES[stateName] || DUMMY_TIMESERIES.Karnataka; // DUMMY DATA - replace with Supabase query
}

export async function getStateRelations(stateId, stateName) {
  // TODO: Replace with Supabase query
  // const { data, error } = await supabase
  //   .from("carbon_relations")
  //   .select("*")
  //   .or(`source_state_id.eq.${stateId},target_state_id.eq.${stateId}`);
  // if (error) throw error;
  // return data;
  return DUMMY_RELATIONS[stateName] || DUMMY_RELATIONS.Karnataka; // DUMMY DATA - replace with Supabase query
}

export { supabase };
