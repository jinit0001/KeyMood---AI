import { Navigate, Outlet } from "react-router-dom";
import { useAppStore } from "../state/appStore";
import { hasSession } from "../services/api";

export default function ProtectedRoute() {
  const user = useAppStore((s) => s.user);
  // A persisted profile without tokens (cleared storage, expired session) is not a login.
  if (!user || !hasSession()) return <Navigate to="/login" replace />;
  return <Outlet />;
}
