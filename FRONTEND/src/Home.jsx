import React from "react";
import { Link } from "react-router-dom";
import { useNavigate } from 'react-router-dom';
import "./Home.css";
import './Log.jsx';
import './Signup.jsx';
function Home() {
  const nav = useNavigate();
  return (
    <div className="home-root">
      {/* Hero Section */}
      <header className="home-hero">
        <h1 className="home-title" style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: "14px" }}>
          <div
            style={{
              width: "76px",
              height: "65px",
              borderRadius: "14px",
              background: "#ffffff",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              overflow: "hidden",
              boxShadow: "0 4px 16px rgba(0,0,0,0.3)",
              flexShrink: 0,
              padding: "0 6px"
            }}
          >
            <img
              src="/LOGO.png"
              alt="FinWise Logo"
              style={{
                width: "100%",
                height: "100%",
                objectFit: "contain",
                transform: "scale(2) translate(-1px, 4px)"
              }}
            />
          </div>
          <span>FinWise</span>
        </h1>
        <p className="home-subtitle">
          Smarter investing starts here — track, learn, and grow your portfolio.
        </p>
        <div className="home-buttons">
          <Link to="/dashboard">
            <button className="hero-cta">🚀 Get Started</button>
          </Link>
          <Link to="/learnings">
            <button className="hero-cta">📚 Learn</button>
          </Link>
        </div>
      </header>

      {/* Features Section */}
      <section className="home-features">
        <div className="feature-card">
          <h3>📊 Dashboard</h3>
          <p>Get a full view of your portfolio performance and daily insights.</p>
        </div>
        <div className="feature-card">
          <h3>💼 Portfolio</h3>
          <p>Manage your holdings, track P&L, and export reports easily.</p>
        </div>
        <div className="feature-card">
          <h3>👀 Watchlist</h3>
          <p>Search, track, and trade stocks with just one click.</p>
        </div>
        <div className="feature-card">
          <h3>📚 Learnings</h3>
          <p>Stay informed with news, articles, and financial learning topics.</p>
        </div>
      </section>

      {/* 🔑 Login Section */}
      <section className="login-section">
        <p>
          🔑 <button onClick={() => nav('/Log')}>Login</button>
        </p>
      </section>
    </div>
  );
}

export default Home;
