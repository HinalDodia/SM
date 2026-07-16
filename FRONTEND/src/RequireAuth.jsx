import React, { useContext } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { UserContext } from "./UserContext";

export default function RequireAuth({ children }) {
  const { user } = useContext(UserContext) || {};
  const location = useLocation();
  if (!user || !user.userid) {
    return <Navigate to="/Log" state={{ from: location }} replace />;
  }
  return children;
}
