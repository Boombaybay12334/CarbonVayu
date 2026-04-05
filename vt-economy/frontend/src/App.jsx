import { Navigate, Route, Routes } from "react-router-dom";

// IMPORTANT: Keep route definitions centralized in this file.
import LoadingSpinner from "./components/common/LoadingSpinner";
import ProtectedRoute from "./components/layout/ProtectedRoute";
import { useAuth } from "./context/AuthContext";
import AdminHome from "./pages/admin/AdminHome";
import LoginPage from "./pages/auth/LoginPage";
import SignupPage from "./pages/auth/SignupPage";
import CommonManHome from "./pages/common-man/CommonManHome";
import ExploreVTPage from "./pages/common-man/ExploreVTPage";
import LeaderboardPage from "./pages/common-man/LeaderboardPage";
import NationalVisualsPage from "./pages/common-man/NationalVisualsPage";
import NotFoundPage from "./pages/shared/NotFoundPage";
import ProjectsPage from "./pages/state/ProjectsPage";
import StateHome from "./pages/state/StateHome";
import StateRelationsPage from "./pages/state/StateRelationsPage";
import StateTimeseriesPage from "./pages/state/StateTimeseriesPage";

function RoleHome() {
  const { profile } = useAuth();

  if (!profile) return <LoadingSpinner />;
  if (profile.role === "state") return <StateHome />;
  if (profile.role === "admin") return <AdminHome />;
  return <CommonManHome />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/login" replace />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/signup" element={<SignupPage />} />

      <Route path="/app" element={<ProtectedRoute />}>
        <Route path="home" element={<RoleHome />} />
        <Route path="leaderboard" element={<LeaderboardPage />} />
        <Route path="explore" element={<ExploreVTPage />} />
        <Route path="national-visuals" element={<NationalVisualsPage />} />
        <Route path="state/timeseries" element={<StateTimeseriesPage />} />
        <Route path="state/relations" element={<StateRelationsPage />} />
        <Route path="projects" element={<ProjectsPage />} />
      </Route>

      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}
