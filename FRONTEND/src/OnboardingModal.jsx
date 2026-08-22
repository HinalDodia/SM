/**
 * OnboardingModal — investment profile setup modal.
 *
 * Props:
 *   userId   {number}  – authenticated user id
 *   onClose  {fn}      – called when modal is dismissed (cancelled)
 *   onSaved  {fn}      – called after profile is saved successfully
 *
 * Flow:
 *   Step 1 — Identity  : display_name, goal_text
 *   Step 2 — Style     : risk_tolerance, investment_goal, experience_level
 *   Step 3 — Numbers   : capital_available, max_per_trade_pct, time_horizon
 *   Step 4 — Sectors   : sectors_of_interest (multi-select chips)
 *   → Success screen → onSaved()
 */

import React, { useState, useEffect, useCallback } from "react";
import { saveAnalyzerProfile } from "./api";
import "./OnboardingModal.css";

/* ── Static option lists ─────────────────────────────────────── */
const RISK_OPTIONS = [
  { value: "low",      label: "🛡️ Conservative" },
  { value: "moderate", label: "⚖️ Moderate"     },
  { value: "high",     label: "🚀 Aggressive"    },
];

const GOAL_OPTIONS = [
  { value: "growth",             label: "🌱 Wealth Creation"      },
  { value: "income",             label: "💸 Regular Income"        },
  { value: "preservation",       label: "🏦 Capital Preservation"  },
  { value: "short_term_trading", label: "🎯 Speculation"           },
];

const HORIZON_OPTIONS = [
  { value: "short_term",  label: "⚡ Short-term (<1 yr)"  },
  { value: "medium_term", label: "📅 Medium (1–3 yr)"     },
  { value: "long_term",   label: "🌳 Long-term (>3 yr)"   },
];

const EXPERIENCE_OPTIONS = [
  { value: "beginner",     label: "🌱 Beginner"     },
  { value: "intermediate", label: "📈 Intermediate" },
  { value: "advanced",     label: "🧠 Expert"       },
];

const SECTORS = [
  "Information Technology",
  "Financials",
  "Energy",
  "Healthcare",
  "Consumer Discretionary",
  "Consumer Staples",
  "Industrials",
  "Real Estate",
  "Materials",
  "Utilities",
];

/* ── Pill selector sub-component ────────────────────────────── */
function PillGroup({ options, value, onChange }) {
  return (
    <div className="ob-pills">
      {options.map(o => (
        <button
          key={o.value}
          type="button"
          className={`ob-pill ${value === o.value ? "selected" : ""}`}
          onClick={() => onChange(o.value)}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

/* ── Step dot bar ────────────────────────────────────────────── */
function StepDots({ total, current }) {
  return (
    <div className="ob-steps">
      {Array.from({ length: total }).map((_, i) => (
        <div
          key={i}
          className={`ob-step-dot ${i === current ? "active" : i < current ? "done" : ""}`}
        />
      ))}
    </div>
  );
}

/* ── Main component ──────────────────────────────────────────── */
const TOTAL_STEPS = 4;

export default function OnboardingModal({ userId, onClose, onSaved }) {
  const [step, setStep]       = useState(0);
  const [saving, setSaving]   = useState(false);
  const [saved, setSaved]     = useState(false);
  const [error, setError]     = useState(null);

  // Step 1 — Identity
  const [displayName, setDisplayName] = useState("");
  const [goalText,    setGoalText]    = useState("");

  // Step 2 — Style
  const [riskTolerance,  setRiskTolerance]  = useState("");
  const [investmentGoal, setInvestmentGoal] = useState("");
  const [experienceLevel,setExperienceLevel]= useState("");

  // Step 3 — Numbers
  const [capital,     setCapital]     = useState("");
  const [maxPctInput, setMaxPctInput] = useState(10);
  const [timeHorizon, setTimeHorizon] = useState("");

  // Step 4 — Sectors
  const [sectors, setSectors] = useState([]);

  // Close on Escape
  useEffect(() => {
    const handler = (e) => { if (e.key === "Escape" && !saving) onClose(); };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose, saving]);

  const toggleSector = useCallback((s) => {
    setSectors(prev =>
      prev.includes(s) ? prev.filter(x => x !== s) : [...prev, s]
    );
  }, []);

  /* ── Validation per step ── */
  const canProceed = () => {
    if (step === 0) return true;                          // name/goal optional
    if (step === 1) return riskTolerance && investmentGoal && experienceLevel;
    if (step === 2) return capital && Number(capital) > 0 && timeHorizon;
    if (step === 3) return true;                          // sectors optional
    return false;
  };

  /* ── Submit ── */
  const handleSave = async () => {
    setError(null);
    setSaving(true);
    try {
      await saveAnalyzerProfile({
        userid:             userId,
        risk_tolerance:     riskTolerance,
        investment_goal:    investmentGoal,
        time_horizon:       timeHorizon,
        capital_available:  parseFloat(capital),
        max_per_trade_pct:  maxPctInput,
        experience_level:   experienceLevel,
        display_name:       displayName.trim() || null,
        goal_text:          goalText.trim()    || null,
        sectors_of_interest: sectors.length > 0 ? sectors : null,
      });
      setSaved(true);
      setTimeout(() => { onSaved(); }, 1600);
    } catch (err) {
      setError(err.message || "Save failed. Please try again.");
    } finally {
      setSaving(false);
    }
  };

  /* ── Success screen ── */
  if (saved) {
    return (
      <div className="ob-backdrop">
        <div className="ob-modal">
          <div className="ob-success">
            <span className="ob-success-icon">🎉</span>
            <h2 className="ob-success-title">
              {displayName ? `You're all set, ${displayName}!` : "Profile saved!"}
            </h2>
            <p className="ob-success-sub">
              Your analyzer is now personalised. Loading your first read…
            </p>
          </div>
        </div>
      </div>
    );
  }

  /* ── Step content ── */
  const renderStep = () => {
    switch (step) {
      case 0:
        return (
          <>
            <div className="ob-field">
              <label className="ob-label">What should I call you?</label>
              <p className="ob-hint">Optional — personalises your analyzer headlines</p>
              <input
                className="ob-input"
                type="text"
                placeholder="e.g. Arjun, Priya…"
                maxLength={50}
                value={displayName}
                onChange={e => setDisplayName(e.target.value)}
                autoFocus
              />
            </div>
            <div className="ob-field">
              <label className="ob-label">What's your investment goal?</label>
              <p className="ob-hint">Free text — helps Claude give context-aware advice</p>
              <textarea
                className="ob-textarea"
                placeholder="e.g. Grow ₹1L into ₹1.5L in a year without big drawdowns"
                maxLength={255}
                value={goalText}
                onChange={e => setGoalText(e.target.value)}
              />
            </div>
          </>
        );

      case 1:
        return (
          <>
            <div className="ob-field">
              <label className="ob-label">Risk Tolerance</label>
              <PillGroup
                options={RISK_OPTIONS}
                value={riskTolerance}
                onChange={setRiskTolerance}
              />
            </div>
            <div className="ob-field">
              <label className="ob-label">Investment Goal</label>
              <PillGroup
                options={GOAL_OPTIONS}
                value={investmentGoal}
                onChange={setInvestmentGoal}
              />
            </div>
            <div className="ob-field">
              <label className="ob-label">Experience Level</label>
              <PillGroup
                options={EXPERIENCE_OPTIONS}
                value={experienceLevel}
                onChange={setExperienceLevel}
              />
            </div>
          </>
        );

      case 2:
        return (
          <>
            <div className="ob-number-row">
              <div className="ob-field">
                <label className="ob-label">Capital Available</label>
                <div className="ob-prefix-wrap">
                  <span className="ob-prefix">₹</span>
                  <input
                    className="ob-input"
                    type="number"
                    min="1"
                    placeholder="100000"
                    value={capital}
                    onChange={e => setCapital(e.target.value)}
                  />
                </div>
              </div>
            </div>
            <div className="ob-field">
              <label className="ob-label">Max per-trade %</label>
              <p className="ob-hint">Cap on how much of capital to risk per trade</p>
              <div className="ob-slider-wrap">
                <input
                  type="range"
                  min={1}
                  max={50}
                  value={maxPctInput}
                  className="ob-slider"
                  style={{ "--val": `${((maxPctInput - 1) / 49) * 100}%` }}
                  onChange={e => setMaxPctInput(Number(e.target.value))}
                />
                <span className="ob-slider-val">{maxPctInput}%</span>
              </div>
            </div>
            <div className="ob-field">
              <label className="ob-label">Time Horizon</label>
              <PillGroup
                options={HORIZON_OPTIONS}
                value={timeHorizon}
                onChange={setTimeHorizon}
              />
            </div>
          </>
        );

      case 3:
        return (
          <div className="ob-field">
            <label className="ob-label">Sectors of Interest</label>
            <p className="ob-hint">Optional — select any that apply</p>
            <div className="ob-chips">
              {SECTORS.map(s => (
                <button
                  key={s}
                  type="button"
                  className={`ob-chip ${sectors.includes(s) ? "selected" : ""}`}
                  onClick={() => toggleSector(s)}
                >
                  {sectors.includes(s) && <span className="ob-chip-check">✓</span>}
                  {s}
                </button>
              ))}
            </div>
          </div>
        );

      default:
        return null;
    }
  };

  const isLastStep = step === TOTAL_STEPS - 1;

  return (
    <div className="ob-backdrop" onClick={e => { if (e.target === e.currentTarget && !saving) onClose(); }}>
      <div className="ob-modal">
        {/* Close button */}
        <button
          className="ob-close"
          onClick={onClose}
          disabled={saving}
          aria-label="Close"
        >
          ✕
        </button>

        {/* Header */}
        <div className="ob-hero">
          <span className="ob-robot" role="img" aria-label="Robot">🤖</span>
          <h2 className="ob-title">Set Up Your Analyzer</h2>
          <p className="ob-subtitle">
            A few quick questions so your personal read is always on point.
          </p>
        </div>

        {/* Step dots */}
        <StepDots total={TOTAL_STEPS} current={step} />

        {/* Error */}
        {error && (
          <div className="ob-error">
            <span>⚠️</span> {error}
          </div>
        )}

        {/* Step body */}
        <div className="ob-body">
          {renderStep()}
        </div>

        {/* Footer */}
        <div className="ob-footer">
          {step > 0 ? (
            <button className="ob-btn-back" onClick={() => setStep(s => s - 1)} disabled={saving}>
              ← Back
            </button>
          ) : (
            <div />
          )}

          {isLastStep ? (
            <button
              className="ob-btn-save"
              onClick={handleSave}
              disabled={saving || !canProceed()}
            >
              {saving ? "Saving…" : "✓ Save Profile"}
            </button>
          ) : (
            <button
              className="ob-btn-next"
              onClick={() => setStep(s => s + 1)}
              disabled={!canProceed()}
            >
              Next →
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
