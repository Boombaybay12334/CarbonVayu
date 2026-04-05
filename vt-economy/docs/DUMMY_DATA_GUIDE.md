# Dummy Data Guide

All dummy records are centralized in `frontend/src/dummy/dummyData.js`.

## Locations with DUMMY DATA markers

1. `frontend/src/dummy/dummyData.js`
- Purpose: source of fake records for states, timeseries, relations, and projects.
- Replace with: seeded Supabase records in `states`, `vt_history`, `carbon_relations`, `projects`.

2. `frontend/src/services/leaderboardService.js`
- Function: `getAllStates()`
- Current return: `DUMMY_STATES`
- Replace with:
  ```js
  const { data, error } = await supabase
    .from("states")
    .select("*")
    .order("vt_balance", { ascending: false });
  ```

3. `frontend/src/services/stateService.js`
- Function: `getStateByName(name)` returns matching record from `DUMMY_STATES`.
- Replace with:
  ```js
  await supabase.from("states").select("*").eq("name", name).single();
  ```
- Function: `getStateTimeseries(stateId, stateName)` returns `DUMMY_TIMESERIES[stateName]`.
- Replace with:
  ```js
  await supabase.from("vt_history").select("*").eq("state_id", stateId).order("year");
  ```
- Function: `getStateRelations(stateId, stateName)` returns `DUMMY_RELATIONS[stateName]`.
- Replace with:
  ```js
  await supabase
    .from("carbon_relations")
    .select("*")
    .or(`source_state_id.eq.${stateId},target_state_id.eq.${stateId}`);
  ```

4. `frontend/src/services/projectsService.js`
- Function: `getProjects()` returns `DUMMY_PROJECTS`.
- Replace with:
  ```js
  await supabase
    .from("projects")
    .select("*, states(name)")
    .order("created_at", { ascending: false });
  ```
- Function: `createProject(project)` logs and returns fake success.
- Replace with:
  ```js
  await supabase.from("projects").insert(project);
  ```

5. `frontend/src/pages/state/StateHome.jsx`
- Adds hardcoded alerts in component.
- Replace by adding `state_alerts` table or deriving from analytics pipeline.

6. `frontend/src/pages/common-man/NationalVisualsPage.jsx`
- Uses aggregate trend placeholder (`aggregateDummyTimeseries`).
- Replace with grouped yearly aggregate query from `vt_history`.

## Replacement workflow
1. Seed Supabase with matching data.
2. Replace one service function at a time.
3. Keep output shape identical for UI stability.
4. Remove `// DUMMY DATA - replace with Supabase query` comments only after verification.
