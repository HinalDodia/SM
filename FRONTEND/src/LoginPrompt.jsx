import React from "react";
import { Link, useLocation } from "react-router-dom";

// A small, reusable prompt shown when a page requires authentication
// Props:
// - title: string heading
// - message: supporting text
export default function LoginPrompt({
  title = "Login to continue",
  message = "Please sign in to access this section.",
}) {
  const location = useLocation();
  return (
    <div style={{ padding: "40px 24px", width: "100%" }}>
      <div
        className="ultra-card"
        style={{ maxWidth: 680, margin: "60px auto", textAlign: "center" }}
        role="status"
        aria-live="polite"
      >
        <h2 style={{ marginBottom: 8 }}>{title}</h2>
        <p style={{ color: "#9aa", marginBottom: 16 }}>{message}</p>
        <Link
          to="/Log"
          state={{ from: location }}
          className="btn-primary"
          aria-label="Go to login page"
        >
          Go to Login
        </Link>
      </div>
    </div>
  );
}
