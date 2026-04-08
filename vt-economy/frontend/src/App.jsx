import { Navigate, Route, Routes, Outlet, useLocation } from "react-router-dom";

import LoadingSpinner from "./components/common/LoadingSpinner";
import { useAuth } from "./context/AuthContext";

import Navbar from "./components/layout/Navbar";

import AdminHome from "./pages/admin/AdminHome";
import LoginPage from "./pages/auth/LoginPage";
import ProfileRecoveryPage from "./pages/auth/ProfileRecoveryPage";
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

/* ROLE BASED HOME */
function RoleHome() {
  const { profile, loading } = useAuth();

  if (loading) return <LoadingSpinner />;
  if (!profile) return <Navigate to="/app/complete-profile" replace />;
  if (profile.role === "state") return <StateHome />;
  if (profile.role === "admin") return <AdminHome />;
  return <CommonManHome />;
}

/* 🔥 NAVBAR LAYOUT */
function AppLayout() {
  const location = useLocation();
  const { user, profile, loading } = useAuth();

  if (loading) return <LoadingSpinner />;

  if (!user) return <Navigate to="/login" replace />;

  const isProfileCompletionRoute = location.pathname === "/app/complete-profile";
  if (!profile && !isProfileCompletionRoute) {
    return <Navigate to="/app/complete-profile" replace />;
  }
  if (profile && isProfileCompletionRoute) {
    return <Navigate to="/app/home" replace />;
  }

  return (
    <div className="min-h-screen text-slate-200">
      
      {/* Navbar - Fixed at top with glass effect */}
      <Navbar />

      {/* Page Content */}
      <div className="pt-24 p-6 max-w-7xl mx-auto animate-fade-in">
        <Outlet />
      </div>
    </div>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/login" replace />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/signup" element={<SignupPage />} />

      {/* ALL APP ROUTES */}
      <Route path="/app" element={<AppLayout />}>
        <Route path="complete-profile" element={<ProfileRecoveryPage />} />
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