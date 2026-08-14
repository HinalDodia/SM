import React, { useState } from "react";
import "./AccountModal.css";
import { handleLogout } from "./Log.jsx";
import AnalyzerProfile from "./AnalyzerProfile.jsx";

export default function AccountModal({ open, onClose, user, onLogout }) {
  const [activeTab, setActiveTab] = useState("overview");

  if (!open) return null;

  return (
    <div className="am-backdrop" onClick={onClose} role="presentation">
      <div
        className="am-panel"
        onClick={(e) => e.stopPropagation()}
        style={{
          maxWidth: activeTab === "profile" ? 640 : 420,
          width: "90%",
          maxHeight: "90vh",
          overflowY: "auto",
          transition: "max-width 0.2s ease-in-out",
        }}
      >
        <div className="am-header" style={{ borderBottom: "1px solid #334155", paddingBottom: 12 }}>
          <div className="am-name" style={{ fontSize: 18, fontWeight: 700, color: "#f8fafc" }}>
            {user?.name || user?.phone || "Account"}
          </div>
          <div className="am-email" style={{ fontSize: 13, color: "#94a3b8" }}>
            {user?.email || ""}
          </div>
        </div>

        {/* Tab selector */}
        <div
          style={{
            display: "flex",
            gap: 8,
            marginTop: 12,
            marginBottom: 16,
            borderBottom: "1px solid #334155",
            paddingBottom: 8,
          }}
        >
          <button
            onClick={() => setActiveTab("overview")}
            style={{
              padding: "6px 12px",
              borderRadius: 6,
              fontSize: 13,
              fontWeight: 600,
              cursor: "pointer",
              backgroundColor: activeTab === "overview" ? "rgba(45, 212, 191, 0.15)" : "transparent",
              color: activeTab === "overview" ? "#2dd4bf" : "#94a3b8",
              border: `1px solid ${activeTab === "overview" ? "rgba(45, 212, 191, 0.3)" : "transparent"}`,
            }}
          >
            Account Overview
          </button>
          <button
            onClick={() => setActiveTab("profile")}
            style={{
              padding: "6px 12px",
              borderRadius: 6,
              fontSize: 13,
              fontWeight: 600,
              cursor: "pointer",
              backgroundColor: activeTab === "profile" ? "rgba(45, 212, 191, 0.15)" : "transparent",
              color: activeTab === "profile" ? "#2dd4bf" : "#94a3b8",
              border: `1px solid ${activeTab === "profile" ? "rgba(45, 212, 191, 0.3)" : "transparent"}`,
            }}
          >
            Investment Profile
          </button>
        </div>

        {activeTab === "overview" ? (
          <div className="am-actions" style={{ marginTop: 12 }}>
            <button
              className="am-btn"
              onClick={() => setActiveTab("profile")}
              style={{ width: "100%", marginBottom: 8 }}
            >
              Configure Investment Profile
            </button>
            <button
              className="am-btn am-logout"
              onClick={handleLogout}
              style={{ width: "100%" }}
            >
              Logout
            </button>
          </div>
        ) : (
          <div style={{ marginTop: 8 }}>
            <AnalyzerProfile />
          </div>
        )}
      </div>
    </div>
  );
}
