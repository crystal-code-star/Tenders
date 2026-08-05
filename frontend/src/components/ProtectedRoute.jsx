import { Navigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function ProtectedRoute({ children }) {
  const { session, loading } = useAuth();

  if (loading) return <p>Loading...</p>;   // still checking auth status
  if (!session) return <Navigate to="/login" />; // not logged in → redirect
  return children; // logged in → show the actual page
}