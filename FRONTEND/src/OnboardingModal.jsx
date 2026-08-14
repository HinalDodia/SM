import React, { useState, useEffect } from "react";
import { fetchAnalyzerProfile, saveAnalyzerProfile } from "./api";
import { toast } from "react-toastify";
import { Sparkles, Shield, Target, TrendingUp, CheckCircle, ArrowRight } from "lucide-react";

export default function OnboardingModal({ isOpen, onClose, userId }) {
  const [step, setStep] = useState(1); // 1: Profile Setup, 2: Guided Tour
  const [formData, setFormData] = useState({
    risk_tolerance: "moderate",
    investment_goal: "growth",
    time_horizon: "medium_term",
    capital_available: "50000",
    max_per_trade_pct: 10,
    experience_level: "beginner",
  });
  const [submitting, setSubmitting] = useState(false);

  if (!isOpen) return null;

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
  };

  const handleProfileSubmit = async (e) => {
    e.preventDefault();
    const cap = parseFloat(formData.capital_available);
    if (isNaN(cap) || cap <= 0) {
      toast.error("Please enter a valid capital amount.");
      return;
    }

    setSubmitting(true);
    try {
      const res = await saveAnalyzerProfile({
        userid: userId,
        risk_tolerance: formData.risk_tolerance,
        investment_goal: formData.investment_goal,
        time_horizon: formData.time_horizon,
        capital_available: cap,
        max_per_trade_pct: parseFloat(formData.max_per_trade_pct) || 10,
        experience_level: formData.experience_level,
      });

      if (res && !res.error) {
        toast.success("Profile configured!");
        setStep(2); // Proceed to Guided Tour
      } else {
        toast.error(res?.error || "Failed to save profile.");
      }
    } catch (err) {
      console.error("Onboarding error:", err);
      toast.error("Error setting up profile.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        backgroundColor: "rgba(0, 0, 0, 0.75)",
        backdropFilter: "blur(6px)",
        zIndex: 9999,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 20,
      }}
    >
      <div
        style={{
          backgroundColor: "#0f172a",
          border: "1px solid #334155",
          borderRadius: 16,
          maxWidth: 600,
          width: "100%",
          padding: 28,
          color: "#f8fafc",
          boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.5)",
          maxHeight: "90vh",
          overflowY: "auto",
        }}
      >
        {step === 1 ? (
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
              <Sparkles size={24} color="#2dd4bf" />
              <h2 style={{ fontSize: 22, fontWeight: 700, margin: 0, color: "#2dd4bf" }}>
                Welcome to FINWISE AI!
              </h2>
            </div>
            <p style={{ color: "#94a3b8", fontSize: 14, marginBottom: 24 }}>
              Let&apos;s set up your personal investment profile so our AI Personal Stock Analyzer can tailor recommendations specifically to your goals.
            </p>

            <form onSubmit={handleProfileSubmit}>
              {/* Risk Tolerance */}
              <div style={{ marginBottom: 16 }}>
                <label style={{ display: "block", marginBottom: 6, fontSize: 14, fontWeight: 600 }}>
                  <Shield size={16} style={{ display: "inline", marginRight: 6, verticalAlign: "text-bottom" }} />
                  What is your Risk Tolerance?
                </label>
                <select
                  name="risk_tolerance"
                  value={formData.risk_tolerance}
                  onChange={handleChange}
                  style={{
                    width: "100%",
                    padding: "10px 12px",
                    borderRadius: 8,
                    backgroundColor: "#1e293b",
                    color: "#f8fafc",
                    border: "1px solid #334155",
                  }}
                >
                  <option value="low">Low — Conservative &amp; Risk-Averse</option>
                  <option value="moderate">Moderate — Balanced Growth &amp; Protection</option>
                  <option value="high">High — Aggressive Capital Appreciation</option>
                </select>
              </div>

              {/* Investment Goal */}
              <div style={{ marginBottom: 16 }}>
                <label style={{ display: "block", marginBottom: 6, fontSize: 14, fontWeight: 600 }}>
                  <Target size={16} style={{ display: "inline", marginRight: 6, verticalAlign: "text-bottom" }} />
                  Primary Investment Goal
                </label>
                <select
                  name="investment_goal"
                  value={formData.investment_goal}
                  onChange={handleChange}
                  style={{
                    width: "100%",
                    padding: "10px 12px",
                    borderRadius: 8,
                    backgroundColor: "#1e293b",
                    color: "#f8fafc",
                    border: "1px solid #334155",
                  }}
                >
                  <option value="growth">Capital Growth</option>
                  <option value="income">Dividend Income</option>
                  <option value="preservation">Capital Preservation</option>
                  <option value="short_term_trading">Short Term Trading</option>
                </select>
              </div>

              {/* Time Horizon */}
              <div style={{ marginBottom: 16 }}>
                <label style={{ display: "block", marginBottom: 6, fontSize: 14, fontWeight: 600 }}>
                  Time Horizon
                </label>
                <select
                  name="time_horizon"
                  value={formData.time_horizon}
                  onChange={handleChange}
                  style={{
                    width: "100%",
                    padding: "10px 12px",
                    borderRadius: 8,
                    backgroundColor: "#1e293b",
                    color: "#f8fafc",
                    border: "1px solid #334155",
                  }}
                >
                  <option value="short_term">Short Term (&lt; 1 Year)</option>
                  <option value="medium_term">Medium Term (1 - 3 Years)</option>
                  <option value="long_term">Long Term (3+ Years)</option>
                </select>
              </div>

              {/* Capital Available */}
              <div style={{ marginBottom: 20 }}>
                <label style={{ display: "block", marginBottom: 6, fontSize: 14, fontWeight: 600 }}>
                  <TrendingUp size={16} style={{ display: "inline", marginRight: 6, verticalAlign: "text-bottom" }} />
                  Capital Available for Investing (₹)
                </label>
                <input
                  type="number"
                  name="capital_available"
                  value={formData.capital_available}
                  onChange={handleChange}
                  style={{
                    width: "100%",
                    padding: "10px 12px",
                    borderRadius: 8,
                    backgroundColor: "#1e293b",
                    color: "#f8fafc",
                    border: "1px solid #334155",
                  }}
                  required
                />
              </div>

              <button
                type="submit"
                disabled={submitting}
                className="btn-primary"
                style={{
                  width: "100%",
                  padding: "12px",
                  fontSize: 15,
                  fontWeight: 700,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  gap: 8,
                }}
              >
                {submitting ? "Saving..." : <>Save Profile &amp; Take Quick Tour <ArrowRight size={18} /></>}
              </button>
            </form>
          </div>
        ) : (
          <div>
            <div style={{ textAlign: "center", marginBottom: 20 }}>
              <CheckCircle size={48} color="#2dd4bf" style={{ margin: "0 auto 12px" }} />
              <h2 style={{ fontSize: 22, fontWeight: 700, margin: 0, color: "#f8fafc" }}>
                Profile Configured!
              </h2>
              <p style={{ color: "#94a3b8", fontSize: 14, marginTop: 4 }}>
                Here is a quick overview of how FINWISE AI guides your investments:
              </p>
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: 14, marginBottom: 24 }}>
              <div
                style={{
                  padding: 14,
                  borderRadius: 10,
                  backgroundColor: "#1e293b",
                  border: "1px solid #334155",
                }}
              >
                <strong style={{ color: "#2dd4bf" }}>1. Watchlist Recommendations</strong>
                <p style={{ margin: "4px 0 0", fontSize: 13, color: "#cbd5e1" }}>
                  Add stocks to your Watchlist to see personalized AI badges (BUY/HOLD/SELL) and suggested position allocations.
                </p>
              </div>

              <div
                style={{
                  padding: 14,
                  borderRadius: 10,
                  backgroundColor: "#1e293b",
                  border: "1px solid #334155",
                }}
              >
                <strong style={{ color: "#2dd4bf" }}>2. Portfolio Holdings Analyzer</strong>
                <p style={{ margin: "4px 0 0", fontSize: 13, color: "#cbd5e1" }}>
                  For existing stock purchases, FINWISE automatically analyzes your position and advises whether to <strong>BUY MORE</strong>, <strong>HOLD</strong>, or <strong>SELL</strong>.
                </p>
              </div>

              <div
                style={{
                  padding: 14,
                  borderRadius: 10,
                  backgroundColor: "#1e293b",
                  border: "1px solid #334155",
                }}
              >
                <strong style={{ color: "#2dd4bf" }}>3. Account Settings Control</strong>
                <p style={{ margin: "4px 0 0", fontSize: 13, color: "#cbd5e1" }}>
                  You can update your risk tolerance, capital budget, or investment horizon anytime inside <strong>Account Settings</strong>.
                </p>
              </div>
            </div>

            <button
              onClick={onClose}
              className="btn-primary"
              style={{
                width: "100%",
                padding: "12px",
                fontSize: 15,
                fontWeight: 700,
              }}
            >
              Start Exploring FINWISE AI
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
