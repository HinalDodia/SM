import React, { useState, useEffect } from "react";
import { fetchAnalyzerProfile, saveAnalyzerProfile } from "./api";
import { toast } from "react-toastify";
import LoginPrompt from "./LoginPrompt";

export default function AnalyzerProfile() {
  const stored = JSON.parse(localStorage.getItem("user") || "{}");
  const uid = stored?.userid || null;

  const [formData, setFormData] = useState({
    risk_tolerance: "moderate",
    investment_goal: "growth",
    time_horizon: "medium_term",
    capital_available: "",
    max_per_trade_pct: 10,
    experience_level: "beginner",
  });

  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [statusMsg, setStatusMsg] = useState(null);

  useEffect(() => {
    if (!uid) return;
    async function loadProfile() {
      try {
        const data = await fetchAnalyzerProfile(uid);
        if (data && !data.error) {
          setFormData({
            risk_tolerance: data.risk_tolerance || "moderate",
            investment_goal: data.investment_goal || "growth",
            time_horizon: data.time_horizon || "medium_term",
            capital_available: data.capital_available !== undefined ? data.capital_available : "",
            max_per_trade_pct: data.max_per_trade_pct !== undefined ? data.max_per_trade_pct : 10,
            experience_level: data.experience_level || "beginner",
          });
        }
      } catch (err) {
        console.error("Error loading profile:", err);
      } finally {
        setLoading(false);
      }
    }
    loadProfile();
  }, [uid]);

  if (!uid) {
    return <LoginPrompt title="Sign in required" message="Please sign in to set up your investment profile." />;
  }

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setStatusMsg(null);

    const cap = parseFloat(formData.capital_available);
    if (isNaN(cap) || cap <= 0) {
      const errStr = "Capital available must be a positive number.";
      setStatusMsg({ type: "error", text: errStr });
      toast.error(errStr);
      return;
    }

    setSubmitting(true);
    try {
      const payload = {
        userid: uid,
        risk_tolerance: formData.risk_tolerance,
        investment_goal: formData.investment_goal,
        time_horizon: formData.time_horizon,
        capital_available: cap,
        max_per_trade_pct: parseFloat(formData.max_per_trade_pct) || 10,
        experience_level: formData.experience_level,
      };

      const res = await saveAnalyzerProfile(payload);
      if (res && !res.error) {
        const msg = res.message || "Profile saved successfully!";
        setStatusMsg({ type: "success", text: msg });
        toast.success(msg);
      } else {
        const err = res.error || "Failed to save profile.";
        setStatusMsg({ type: "error", text: err });
        toast.error(err);
      }
    } catch (err) {
      console.error("Profile save error:", err);
      const errText = "An error occurred while saving your profile.";
      setStatusMsg({ type: "error", text: errText });
      toast.error(errText);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div style={{ padding: "32px 24px", maxWidth: 760, margin: "0 auto" }}>
      <div className="ultra-card">
        <h1 className="dash__title" style={{ marginBottom: 8 }}>
          Investment Profile Setup
        </h1>
        <p className="dash__subtitle" style={{ marginBottom: 24 }}>
          Configure your risk preference and capital settings for personalized AI recommendations.
        </p>

        {loading ? (
          <div style={{ textAlign: "center", padding: "40px 0", color: "#9aa" }}>
            Loading your profile...
          </div>
        ) : (
          <form onSubmit={handleSubmit}>
            {statusMsg && (
              <div
                style={{
                  padding: "12px 16px",
                  borderRadius: 8,
                  marginBottom: 20,
                  fontSize: 14,
                  backgroundColor: statusMsg.type === "error" ? "rgba(239, 68, 68, 0.15)" : "rgba(34, 197, 94, 0.15)",
                  color: statusMsg.type === "error" ? "#f87171" : "#4ade80",
                  border: `1px solid ${statusMsg.type === "error" ? "rgba(239, 68, 68, 0.3)" : "rgba(34, 197, 94, 0.3)"}`,
                }}
              >
                {statusMsg.text}
              </div>
            )}

            {/* Risk Tolerance */}
            <div style={{ marginBottom: 20 }}>
              <label style={{ display: "block", marginBottom: 8, fontWeight: 600, color: "#f8fafc" }}>
                Risk Tolerance
              </label>
              <select
                name="risk_tolerance"
                value={formData.risk_tolerance}
                onChange={handleChange}
                className="input-field"
                style={{
                  width: "100%",
                  padding: "12px 14px",
                  borderRadius: 8,
                  backgroundColor: "#0f172a",
                  color: "#f8fafc",
                  border: "1px solid #334155",
                  outline: "none",
                }}
              >
                <option value="low" style={{ backgroundColor: "#0f172a", color: "#f8fafc" }}>Low — Conservative &amp; Risk-Averse</option>
                <option value="moderate" style={{ backgroundColor: "#0f172a", color: "#f8fafc" }}>Moderate — Balanced Risk &amp; Return</option>
                <option value="high" style={{ backgroundColor: "#0f172a", color: "#f8fafc" }}>High — Aggressive Growth Seeking</option>
              </select>
            </div>

            {/* Investment Goal */}
            <div style={{ marginBottom: 20 }}>
              <label style={{ display: "block", marginBottom: 8, fontWeight: 600, color: "#f8fafc" }}>
                Investment Goal
              </label>
              <select
                name="investment_goal"
                value={formData.investment_goal}
                onChange={handleChange}
                className="input-field"
                style={{
                  width: "100%",
                  padding: "12px 14px",
                  borderRadius: 8,
                  backgroundColor: "#0f172a",
                  color: "#f8fafc",
                  border: "1px solid #334155",
                  outline: "none",
                }}
              >
                <option value="growth" style={{ backgroundColor: "#0f172a", color: "#f8fafc" }}>Capital Growth</option>
                <option value="income" style={{ backgroundColor: "#0f172a", color: "#f8fafc" }}>Dividend Income</option>
                <option value="preservation" style={{ backgroundColor: "#0f172a", color: "#f8fafc" }}>Capital Preservation</option>
                <option value="short_term_trading" style={{ backgroundColor: "#0f172a", color: "#f8fafc" }}>Short Term Trading</option>
              </select>
            </div>

            {/* Time Horizon */}
            <div style={{ marginBottom: 20 }}>
              <label style={{ display: "block", marginBottom: 8, fontWeight: 600, color: "#f8fafc" }}>
                Time Horizon
              </label>
              <select
                name="time_horizon"
                value={formData.time_horizon}
                onChange={handleChange}
                className="input-field"
                style={{
                  width: "100%",
                  padding: "12px 14px",
                  borderRadius: 8,
                  backgroundColor: "#0f172a",
                  color: "#f8fafc",
                  border: "1px solid #334155",
                  outline: "none",
                }}
              >
                <option value="short_term" style={{ backgroundColor: "#0f172a", color: "#f8fafc" }}>Short Term (&lt; 1 Year)</option>
                <option value="medium_term" style={{ backgroundColor: "#0f172a", color: "#f8fafc" }}>Medium Term (1 - 3 Years)</option>
                <option value="long_term" style={{ backgroundColor: "#0f172a", color: "#f8fafc" }}>Long Term (3+ Years)</option>
              </select>
            </div>

            {/* Capital Available */}
            <div style={{ marginBottom: 20 }}>
              <label style={{ display: "block", marginBottom: 8, fontWeight: 600, color: "#f8fafc" }}>
                Capital Available (₹)
              </label>
              <input
                type="number"
                name="capital_available"
                placeholder="e.g. 50000"
                value={formData.capital_available}
                onChange={handleChange}
                className="input-field"
                style={{
                  width: "100%",
                  padding: "12px 14px",
                  borderRadius: 8,
                  backgroundColor: "#0f172a",
                  color: "#f8fafc",
                  border: "1px solid #334155",
                  outline: "none",
                }}
                step="any"
                required
              />
            </div>

            {/* Max Per Trade % */}
            <div style={{ marginBottom: 20 }}>
              <label style={{ display: "block", marginBottom: 8, fontWeight: 600, color: "#f8fafc" }}>
                Max Allocation Per Trade (%)
              </label>
              <input
                type="number"
                name="max_per_trade_pct"
                placeholder="10"
                value={formData.max_per_trade_pct}
                onChange={handleChange}
                className="input-field"
                style={{
                  width: "100%",
                  padding: "12px 14px",
                  borderRadius: 8,
                  backgroundColor: "#0f172a",
                  color: "#f8fafc",
                  border: "1px solid #334155",
                  outline: "none",
                }}
                step="any"
                min="1"
                max="100"
              />
            </div>

            {/* Experience Level */}
            <div style={{ marginBottom: 24 }}>
              <label style={{ display: "block", marginBottom: 8, fontWeight: 600, color: "#f8fafc" }}>
                Experience Level
              </label>
              <select
                name="experience_level"
                value={formData.experience_level}
                onChange={handleChange}
                className="input-field"
                style={{
                  width: "100%",
                  padding: "12px 14px",
                  borderRadius: 8,
                  backgroundColor: "#0f172a",
                  color: "#f8fafc",
                  border: "1px solid #334155",
                  outline: "none",
                }}
              >
                <option value="beginner" style={{ backgroundColor: "#0f172a", color: "#f8fafc" }}>Beginner</option>
                <option value="intermediate" style={{ backgroundColor: "#0f172a", color: "#f8fafc" }}>Intermediate</option>
                <option value="advanced" style={{ backgroundColor: "#0f172a", color: "#f8fafc" }}>Advanced</option>
              </select>
            </div>

            <button
              type="submit"
              className="btn-primary"
              disabled={submitting}
              style={{ width: "100%", padding: "12px", fontSize: 16 }}
            >
              {submitting ? "Saving Profile..." : "Save Investment Profile"}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
