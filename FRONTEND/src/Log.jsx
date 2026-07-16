import React, { useState, useContext } from "react";
import { useNavigate, Link } from "react-router-dom";
import axios from "axios";
import { toast } from "react-toastify";
import { UserContext } from "./UserContext.jsx";
import { API_URL } from "./config.js";
import "./Log.css";

// ─── Local logout (clears session — no Cognito redirect) ─────────────────────
export function handleLogout() {
  localStorage.removeItem("user");
  localStorage.removeItem("id_token");
  localStorage.removeItem("wallet");
  localStorage.removeItem("portfolio");
  window.location.href = "/Log";
}

// ─── Login page ───────────────────────────────────────────────────────────────
export default function Login() {
  const { setUser } = useContext(UserContext);
  const navigate = useNavigate();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [devEmail, setDevEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [devLoading, setDevLoading] = useState(false);

  // ── Standard login (email + password) ─────────────────────────────────────
  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!email || !password) {
      toast.error("Please enter your email and password.");
      return;
    }
    setLoading(true);
    try {
      const res = await axios.post(`${API_URL}/auth/login`, { email, password });
      if (res.data?.status === "success" && res.data?.user) {
        const user = res.data.user;
        setUser(user);
        localStorage.setItem("user", JSON.stringify(user));
        localStorage.setItem("id_token", `local_${user.userid}`);
        navigate(`/dashboard/${user.userid}`, { replace: true });
      } else {
        toast.error(res.data?.message || "Login failed.");
      }
    } catch (err) {
      toast.error(err.response?.data?.message || "Invalid email or password.");
    } finally {
      setLoading(false);
    }
  };

  // ── Dev login (email only — no password needed) ────────────────────────────
  const handleDevLogin = async (e) => {
    e.preventDefault();
    if (!devEmail) {
      toast.error("Enter an email to use dev login.");
      return;
    }
    setDevLoading(true);
    try {
      const res = await axios.post(`${API_URL}/auth/dev-login`, { email: devEmail });
      if (res.data?.status === "success" && res.data?.user) {
        const user = res.data.user;
        setUser(user);
        localStorage.setItem("user", JSON.stringify(user));
        localStorage.setItem("id_token", `dev_${user.userid}`);
        navigate(`/dashboard/${user.userid}`, { replace: true });
      } else {
        toast.error(res.data?.message || "Dev login failed.");
      }
    } catch (err) {
      toast.error(err.response?.data?.message || "User not found in database.");
    } finally {
      setDevLoading(false);
    }
  };

  return (
    <div className="login-page">
      <main className="login-main" style={{ flexDirection: "column", gap: "24px" }}>

        {/* ── Standard login card ─────────────────────────────────── */}
        <div className="login-card" role="form" aria-label="Login form">
          <h2 className="login-title">Sign in to your account</h2>

          <form onSubmit={handleSubmit} className="login-form">
            <div className="login-field">
              <label htmlFor="login-email">Email</label>
              <input
                id="login-email"
                type="email"
                placeholder="your@email.com"
                value={email}
                required
                autoComplete="email"
                onChange={(e) => setEmail(e.target.value)}
              />
            </div>

            <div className="login-field">
              <label htmlFor="login-password">Password</label>
              <input
                id="login-password"
                type="password"
                placeholder="Your password"
                value={password}
                required
                autoComplete="current-password"
                onChange={(e) => setPassword(e.target.value)}
              />
            </div>

            <button type="submit" className="btn-primary" disabled={loading}>
              {loading ? "Signing in…" : "Sign In"}
            </button>
          </form>

          <p className="login-footer-text">
            <Link to="/forgot-password">Forgot password?</Link>
          </p>
          <p className="login-footer-text">
            Don't have an account? <Link to="/signup">Sign up</Link>
          </p>
        </div>

        {/* ── Dev login card (shown only in development) ──────────── */}
        {import.meta.env.DEV && (
          <div className="login-card dev-login-card" role="form" aria-label="Dev login form">
            <div className="dev-badge">🛠 DEV MODE — No password required</div>
            <h2 className="login-title" style={{ fontSize: "17px", marginTop: "10px" }}>
              Quick Dev Login
            </h2>
            <p style={{ fontSize: "13px", color: "var(--muted)", marginBottom: "12px" }}>
              Type any existing Cognito email to log in instantly without a password.
            </p>

            <form onSubmit={handleDevLogin} className="login-form">
              <div className="login-field">
                <label htmlFor="dev-email">Email (from DB / Cognito)</label>
                <input
                  id="dev-email"
                  type="email"
                  placeholder="rohandodia21@gmail.com"
                  value={devEmail}
                  autoComplete="off"
                  onChange={(e) => setDevEmail(e.target.value)}
                />
              </div>
              <button type="submit" className="btn-primary dev-login-btn" disabled={devLoading}>
                {devLoading ? "Logging in…" : "⚡ Dev Login"}
              </button>
            </form>
          </div>
        )}

      </main>
    </div>
  );
}