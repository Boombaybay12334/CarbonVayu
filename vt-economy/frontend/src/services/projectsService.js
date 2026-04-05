import { supabase } from "../lib/supabase";
import { DUMMY_PROJECTS } from "../dummy/dummyData";

export async function getProjects() {
  // TODO: Replace with Supabase query
  // const { data, error } = await supabase
  //   .from("projects")
  //   .select("*, states(name)")
  //   .order("created_at", { ascending: false });
  // if (error) throw error;
  // return data;
  return DUMMY_PROJECTS; // DUMMY DATA - replace with Supabase query
}

export async function createProject(project) {
  // TODO: Replace with Supabase insert
  // const { data, error } = await supabase.from("projects").insert(project).select().single();
  // if (error) throw error;
  // return data;
  console.log("DUMMY: would create project", project); // DUMMY DATA - replace with Supabase query
  return { success: true };
}

export { supabase };
