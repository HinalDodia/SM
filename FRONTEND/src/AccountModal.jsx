// src/AccountModal.jsx
import React from "react";
import "./AccountModal.css";
import { handleLogout }  from "./Log.jsx";
export default function AccountModal({ open, onClose, user, onLogout }) {
  if (!open) return null;
  return (
    <div className="am-backdrop" onClick={onClose} role="presentation">
      <div className="am-panel" onClick={(e)=>e.stopPropagation()}>
        <div className="am-header">
          <div className="am-name">{user?.name || user?.phone || "Account"}</div>
          <div className="am-email">{user?.email || ""}</div>
        </div>
        <div className="am-actions">
          <button className="am-btn" onClick={() => { onClose(); /* future: open account page */ }}>
            Account
          </button>
          <button className="am-btn am-logout" onClick={handleLogout}>
            Logout
          </button>
        </div>
      </div>
    </div>
  );
}
