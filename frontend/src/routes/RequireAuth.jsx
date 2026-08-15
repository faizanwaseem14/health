import { Navigate, Outlet, useLocation } from "react-router-dom";
import { LoadingScreen } from "../components/LoadingScreen/LoadingScreen";
import { useAuth } from "../context/AuthContext";

/**
 * Wraps any route that needs someone signed in. Sends a signed-out
 * visitor to /login, remembering where they were headed so Login can
 * send them back after they finish.
 */
export function RequireAuth() {
  const { status } = useAuth();
  const location = useLocation();

  if (status === "loading") {
    return <LoadingScreen message="Checking your session…" />;
  }

  if (status === "signed-out") {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }

  return <Outlet />;
}
