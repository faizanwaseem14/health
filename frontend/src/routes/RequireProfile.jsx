import { Navigate, Outlet } from "react-router-dom";
import { LoadingScreen } from "../components/LoadingScreen/LoadingScreen";
import { useAuth } from "../context/AuthContext";

/**
 * Wraps any route that needs a completed profile, not just a signed-
 * in session (nest this INSIDE <RequireAuth />). A first-time visitor
 * with no profile yet is sent to set one up before they can go
 * further.
 */
export function RequireProfile() {
  const { profiles, profilesLoading, hasProfile } = useAuth();

  if (profiles === null || profilesLoading) {
    return <LoadingScreen message="Loading your profile…" />;
  }

  if (!hasProfile) {
    return <Navigate to="/profile-setup" replace />;
  }

  return <Outlet />;
}
