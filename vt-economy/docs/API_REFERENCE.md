# API Reference (Supabase Service Layer)

## leaderboardService.js

### `getAllStates()`
- Purpose: Fetch all states sorted by VT balance.
- Query pattern (commented in code):
  ```js
  supabase.from("states").select("*").order("vt_balance", { ascending: false })
  ```
- Return shape:
  ```js
  [{ id, name, vt_balance, yoy_delta, rank, archetype, ecosystem, area_km2 }]
  ```

### `getTopStates(n = 5)`
- Purpose: Top N states from `getAllStates()`.
- Return shape: same as `getAllStates()` but sliced.

### `getBottomStates(n = 5)`
- Purpose: Bottom N states by VT balance.
- Return shape: same as `getAllStates()` but sorted ascending and sliced.

## stateService.js

### `getStateByName(name)`
- Purpose: Fetch one state by name.
- Query pattern:
  ```js
  supabase.from("states").select("*").eq("name", name).single()
  ```
- Return shape:
  ```js
  { id, name, vt_balance, yoy_delta, rank, archetype, ecosystem, area_km2 }
  ```

### `getStateTimeseries(stateId, stateName)`
- Purpose: VT score history for a state.
- Query pattern:
  ```js
  supabase.from("vt_history").select("*").eq("state_id", stateId).order("year")
  ```
- Return shape:
  ```js
  [{ year, vt_score, note }]
  ```

### `getStateRelations(stateId, stateName)`
- Purpose: Inbound/outbound carbon relation impacts.
- Query pattern:
  ```js
  supabase
    .from("carbon_relations")
    .select("*")
    .or(`source_state_id.eq.${stateId},target_state_id.eq.${stateId}`)
  ```
- Return shape:
  ```js
  {
    affected_by: [{ state, type, vt_impact, status }],
    affecting: [{ state, type, vt_impact, status }]
  }
  ```

## projectsService.js

### `getProjects()`
- Purpose: List projects with newest first.
- Query pattern:
  ```js
  supabase
    .from("projects")
    .select("*, states(name)")
    .order("created_at", { ascending: false })
  ```
- Return shape:
  ```js
  [{ id, state_name, title, description, vt_gain_estimate, funds_needed, funds_raised }]
  ```

### `createProject(project)`
- Purpose: Submit a new project.
- Query pattern:
  ```js
  supabase.from("projects").insert(project)
  ```
- Input shape:
  ```js
  { title, description, vt_gain_estimate, funds_needed, funds_raised?, state_id? }
  ```
- Return shape (scaffold):
  ```js
  { success: true }
  ```

## Component usage example

```js
useEffect(() => {
  getAllStates().then(setStates);
}, []);
```
