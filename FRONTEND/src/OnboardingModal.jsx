/**
 * OnboardingModal — 3-step first-login wizard.
 *
 * Shown once per account (gated by localStorage "onboarding_done_<userid>").
 * POSTs to /analyzer/profile on completion.
 *
 * Step 1: display_name + experience_level
 * Step 2: risk_tolerance + time_horizon (trading style) + capital_available slider
 * Step 3: investment_goal + goal_text + sectors_of_interest chip picker
 *
 * "Trading style" UI options:
 *   Intraday  → short_term   (mapped in POST handler)
 *   Short term → short_term
 *   Long term  → long_term
 * (medium_term is the DB default; mapped from "Short term" too for simplicity)
 *
 * capital_available: the analyzer's "thinking budget" — NOT the paper-trading
 * wallet (Users.money). These are separate; no duplication.
 */

import React, { useState, useContext } from "react";
import { UserContext } from "./UserContext";
import { saveAnalyzerProfile } from "./api";
import "./OnboardingModal.css";

const TOTAL_STEPS = 3;

const SECTORS = [
  "Energy", "IT", "Banking", "Healthcare", "FMCG",
  "Auto", "Metals", "Realty", "Pharma", "Telecom",
];

const EXPERIENCE_OPTS = ["Beginner", "Intermediate", "Advanced"];

const RISK_OPTS = [
  { label: "Conservative", value: "low", desc: "Preserve capital first" },
  { label: "Balanced",     value: "moderate", desc: "Growth with guardrails" },
  { label: "Aggressive",   value: "high",  desc: "Max upside, accept swings" },
];

const STYLE_OPTS = [
  { label: "Intraday",   value: "intraday"   },
  { label: "Short term", value: "short_term" },
  { label: "Long term",  value: "long_term"  },
];

const GOAL_OPTS = [
  { label: "Growth",           value: "growth" },
  { label: "Income",           value: "income" },
  { label: "Capital preservation", value: "preservation" },
  { label: "Short-term trading", value: "short_term_trading" },
];

function formatCapital(val) {
  if (val >= 10000000) return `₹${(val / 10000000).toFixed(1)} Cr`;
  if (val >= 100000)   return `₹${(val / 100000).toFixed(1)} L`;
  if (val >= 1000)     return `₹${(val / 1000).toFixed(0)}K`;
  return `₹${val}`;
}

// Slider ticks: ₹10K → ₹50L (logarithmic feel via fixed stops)
const CAPITAL_STOPS = [10000, 25000, 50000, 100000, 250000, 500000, 1000000, 2500000, 5000000];

export default function OnboardingModal({ onClose }) {
  const { user } = useContext(UserContext) || {};
  const uid = user?.userid;

  const [step, setStep]         = useState(1);
  const [saving, setSaving]     = useState(false);
  const [saveErr, setSaveErr]   = useState("");

  // Step 1
  const [displayName, setName]  = useState("");
  const [experience, setExp]    = useState("beginner");

  // Step 2
  const [riskTol, setRisk]      = useState("moderate");
  const [tradingStyle, setStyle]= useState("short_term");
  const [capitalIdx, setCapIdx] = useState(3);  // index into CAPITAL_STOPS

  // Step 3
  const [investGoal, setGoal]   = useState("growth");
  const [goalText, setGoalText] = useState("");
  const [sectors, setSectors]   = useState([]);

  function toggleSector(s) {
    setSectors(prev =>
      prev.includes(s) ? prev.filter(x => x !== s) : [...prev, s]
    );
  }

  async function handleFinish() {
    if (!uid) return;
    setSaving(true);
    setSaveErr("");

    try {
      await saveAnalyzerProfile({
        userid: uid,
        display_name: displayName.trim() || null,
        experience_level: experience,
        risk_tolerance: riskTol,
        time_horizon: tradingStyle,   // server maps "intraday" → "short_term"
        capital_available: CAPITAL_STOPS[capitalIdx],
        investment_goal: investGoal,
        goal_text: goalText.trim() || null,
        sectors_of_interest: sectors.length > 0 ? sectors : null,
        max_per_trade_pct: 10,
      });

      // Mark done so modal doesn't re-appear
      localStorage.setItem(`onboarding_done_${uid}`, "1");
      onClose();
    } catch (err) {
      setSaveErr("Couldn't save your profile — try again.");
    } finally {
      setSaving(false);
    }
  }

  function skipAndClose() {
    if (uid) localStorage.setItem(`onboarding_done_${uid}`, "1");
    onClose();
  }

  // ── Render ───────────────────────────────────────────────────────────────
  return (
    <div className="ob-backdrop" role="dialog" aria-modal="true" aria-label="Onboarding">
      <div className="ob-modal">
        {/* Progress dots */}
        <div className="ob-progress" role="progressbar" aria-valuenow={step} aria-valuemax={TOTAL_STEPS}>
          {Array.from({ length: TOTAL_STEPS }).map((_, i) => (
            <div key={i} className={`ob-step-dot${i < step ? " active" : ""}`} />
          ))}
        </div>

        {/* ── Step 1: Identity ── */}
        {step === 1 && (
          <>
            <div className="ob-header">
              <div className="ob-eyebrow">Step 1 of 3</div>
              <h2 className="ob-title">Let's personalize your read</h2>
              <p className="ob-subtitle">The analyzer will address you by name and adjust its tone to your level.</p>
            </div>

            <div className="ob-field">
              <label className="ob-label" htmlFor="ob-name">What should we call you?</label>
              <input
                id="ob-name"
                className="ob-input"
                type="text"
                maxLength={50}
                placeholder="e.g. Riya, Arjun…"
                value={displayName}
                onChange={e => setName(e.target.value)}
                autoFocus
              />
            </div>

            <div className="ob-field">
              <label className="ob-label">Experience level</label>
              <div className="ob-chips">
                {EXPERIENCE_OPTS.map(opt => (
                  <button
                    key={opt}
                    className={`ob-chip radio${experience === opt.toLowerCase() ? " selected" : ""}`}
                    onClick={() => setExp(opt.toLowerCase())}
                    type="button"
                    id={`ob-exp-${opt.toLowerCase()}`}
                  >
                    {opt}
                  </button>
                ))}
              </div>
            </div>
          </>
        )}

        {/* ── Step 2: Risk + Style + Capital ── */}
        {step === 2 && (
          <>
            <div className="ob-header">
              <div className="ob-eyebrow">Step 2 of 3</div>
              <h2 className="ob-title">Your trading profile</h2>
              <p className="ob-subtitle">This shapes which signals matter most for you.</p>
            </div>

            <div className="ob-field">
              <label className="ob-label">Risk tolerance</label>
              <div className="ob-chips">
                {RISK_OPTS.map(r => (
                  <button
                    key={r.value}
                    className={`ob-chip radio${riskTol === r.value ? " selected" : ""}`}
                    onClick={() => setRisk(r.value)}
                    type="button"
                    id={`ob-risk-${r.value}`}
                    title={r.desc}
                  >
                    {r.label}
                  </button>
                ))}
              </div>
            </div>

            <div className="ob-field">
              <label className="ob-label">Trading style</label>
              <div className="ob-chips">
                {STYLE_OPTS.map(s => (
                  <button
                    key={s.value}
                    className={`ob-chip radio${tradingStyle === s.value ? " selected" : ""}`}
                    onClick={() => setStyle(s.value)}
                    type="button"
                    id={`ob-style-${s.value}`}
                  >
                    {s.label}
                  </button>
                ))}
              </div>
            </div>

            <div className="ob-field">
              <label className="ob-label">Capital I'm thinking with</label>
              <div className="ob-slider-wrap">
                <input
                  id="ob-capital-slider"
                  type="range"
                  className="ob-slider"
                  min={0}
                  max={CAPITAL_STOPS.length - 1}
                  step={1}
                  value={capitalIdx}
                  onChange={e => setCapIdx(Number(e.target.value))}
                />
              </div>
              <div className="ob-slider-val">{formatCapital(CAPITAL_STOPS[capitalIdx])}</div>
              <p style={{ fontSize: 11, color: "#334155", margin: "4px 0 0" }}>
                This is your analyzer budget — separate from your paper-trading wallet.
              </p>
            </div>
          </>
        )}

        {/* ── Step 3: Goals + Sectors ── */}
        {step === 3 && (
          <>
            <div className="ob-header">
              <div className="ob-eyebrow">Step 3 of 3</div>
              <h2 className="ob-title">What are you after?</h2>
              <p className="ob-subtitle">Your goal and preferred sectors fine-tune the AI's action plan.</p>
            </div>

            <div className="ob-field">
              <label className="ob-label">Investment goal</label>
              <div className="ob-chips">
                {GOAL_OPTS.map(g => (
                  <button
                    key={g.value}
                    className={`ob-chip radio${investGoal === g.value ? " selected" : ""}`}
                    onClick={() => setGoal(g.value)}
                    type="button"
                    id={`ob-goal-${g.value}`}
                  >
                    {g.label}
                  </button>
                ))}
              </div>
            </div>

            <div className="ob-field">
              <label className="ob-label" htmlFor="ob-goaltext">
                Describe your goal <span style={{ color: "#475569" }}>(optional)</span>
              </label>
              <textarea
                id="ob-goaltext"
                className="ob-input ob-textarea"
                maxLength={255}
                placeholder="e.g. Grow ₹1L into ₹1.5L in a year without big drawdowns"
                value={goalText}
                onChange={e => setGoalText(e.target.value)}
              />
            </div>

            <div className="ob-field">
              <label className="ob-label">
                Sectors of interest <span style={{ color: "#475569" }}>(pick any)</span>
              </label>
              <div className="ob-chips">
                {SECTORS.map(s => (
                  <button
                    key={s}
                    className={`ob-chip${sectors.includes(s) ? " selected" : ""}`}
                    onClick={() => toggleSector(s)}
                    type="button"
                    id={`ob-sector-${s.toLowerCase()}`}
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>

            {saveErr && <div className="ob-error">{saveErr}</div>}
          </>
        )}

        {/* Footer */}
        <div className="ob-footer">
          {step > 1 ? (
            <button className="ob-btn-back" onClick={() => setStep(s => s - 1)} type="button">
              ← Back
            </button>
          ) : (
            <button className="ob-skip" onClick={skipAndClose} type="button">
              Skip for now
            </button>
          )}

          {step < TOTAL_STEPS ? (
            <button
              className="ob-btn-next"
              onClick={() => setStep(s => s + 1)}
              type="button"
            >
              Continue →
            </button>
          ) : (
            <button
              className="ob-btn-next"
              onClick={handleFinish}
              disabled={saving}
              type="button"
              id="ob-finish-btn"
            >
              {saving ? "Saving…" : "Get my read →"}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
