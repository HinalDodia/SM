// src/Navbar.jsx
import React, { useContext, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { UserContext } from "./UserContext";
import AccountModal from "./AccountModal";
import "./Navbar.css"; // keep your existing navbar styles
import './Home.jsx';
export default function Navbar() {
  const { user, setUser } = useContext(UserContext) || {};
  const [open, setOpen] = useState(false);
  const navigate = useNavigate();

  const handleLogout = () => {
    setUser(null);
    navigate("/", { replace: true });
  };

  return (
    <nav className="app-navbar">
      <div className="nav-left">
        <Link to="/" className="brand">FINWISE</Link>
      </div>

      <div className="nav-right">
        <Link to="/watchlist" className="nav-link">Watchlist</Link>
        <Link to="/portfolio" className="nav-link">Portfolio</Link>
        <Link to="/learnings" className="nav-link">Learnings</Link>
        <Link to="/dashboard" className="nav-link">Dashboard</Link>
        <Link to="/stockprediction" className="nav-link">Stock Prediction</Link>
        {user ? (
          <>
            <button className="nav-account" onClick={() => setOpen(true)}>
              Hi, {user.name || user.phone} ▾
            </button>
            <AccountModal open={open} onClose={()=>setOpen(false)} user={user} onLogout={handleLogout} />
          </>
        ) : (
          <Link to="/Log" className="nav-cta">Login</Link>
        )}
      </div>
    </nav>
  );
}
