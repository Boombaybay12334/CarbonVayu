# Component Map

| File | Route | Role Required | Data Source | Status |
|---|---|---|---|---|
| frontend/src/pages/auth/LoginPage.jsx | /login | public | Firebase Auth | Scaffold |
| frontend/src/pages/auth/SignupPage.jsx | /signup | public | Firebase Auth + Supabase user_profiles | Scaffold |
| frontend/src/pages/common-man/CommonManHome.jsx | /app/home | common_man | leaderboardService (dummy) | Scaffold |
| frontend/src/pages/common-man/LeaderboardPage.jsx | /app/leaderboard | all | leaderboardService.getAllStates (dummy) | Scaffold |
| frontend/src/pages/common-man/ExploreVTPage.jsx | /app/explore | all | static + DUMMY_STATES | Scaffold |
| frontend/src/pages/common-man/NationalVisualsPage.jsx | /app/national-visuals | all | dummy aggregate + DUMMY_STATES | Scaffold |
| frontend/src/pages/state/StateHome.jsx | /app/home | state | stateService.getStateByName (dummy) | Scaffold |
| frontend/src/pages/state/StateTimeseriesPage.jsx | /app/state/timeseries | state | stateService.getStateTimeseries (dummy) | Scaffold |
| frontend/src/pages/state/StateRelationsPage.jsx | /app/state/relations | state | stateService.getStateRelations (dummy) | Scaffold |
| frontend/src/pages/state/ProjectsPage.jsx | /app/projects | state | projectsService (dummy) | Scaffold |
| frontend/src/pages/admin/AdminHome.jsx | /app/home | admin | TBD | Placeholder |
| frontend/src/components/layout/Navbar.jsx | all /app/* | authenticated | AuthContext user/profile | Scaffold |
| frontend/src/components/layout/Sidebar.jsx | all /app/* | authenticated | AuthContext profile.role | Scaffold |
| frontend/src/components/layout/ProtectedRoute.jsx | all /app/* | authenticated | AuthContext loading/user | Scaffold |
| frontend/src/components/charts/VTTimeseriesChart.jsx | reusable | all | chart props | Scaffold |
| frontend/src/components/charts/StateBarChart.jsx | reusable | all | chart props | Scaffold |
| frontend/src/components/charts/CarbonFlowMap.jsx | reusable | all | placeholder | Placeholder |
| frontend/src/components/common/VTBadge.jsx | reusable | all | score prop | Scaffold |
| frontend/src/components/common/StatCard.jsx | reusable | all | values via props | Scaffold |
| frontend/src/components/common/AlertBanner.jsx | reusable | all | alert prop | Scaffold |
| frontend/src/components/common/LoadingSpinner.jsx | reusable | all | none | Scaffold |
| frontend/src/services/leaderboardService.js | service | all | Supabase TODO + dummy fallback | Scaffold |
| frontend/src/services/stateService.js | service | state | Supabase TODO + dummy fallback | Scaffold |
| frontend/src/services/projectsService.js | service | state | Supabase TODO + dummy fallback | Scaffold |
| frontend/src/context/AuthContext.jsx | provider | app-wide | Firebase onAuthStateChanged + Supabase profile | Scaffold |
