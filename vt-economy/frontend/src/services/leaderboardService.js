import { supabase } from "../lib/supabase";
import { DUMMY_STATES } from "../dummy/dummyData";

export async function getAllStates() {
  // TODO: Replace with Supabase query when DB is seeded
  const { data, error } = await supabase
    .from("states")
    .select("*")
    .order("vt_balance", { ascending: false });
  if (error) throw error;
  return data;
  // return DUMMY_STATES; // DUMMY DATA - replace with Supabase query
}

export async function getTopStates(n = 5) {
  const all = await getAllStates();
  return all.slice(0, n);
}

export async function getBottomStates(n = 5) {
  const all = await getAllStates();
  return [...all].sort((a, b) => a.vt_balance - b.vt_balance).slice(0, n);
}

export { supabase };
