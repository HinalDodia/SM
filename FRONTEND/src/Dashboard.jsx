import React, { useState, useEffect, useContext } from "react";
import { UserContext } from "./UserContext";
import { API_URL } from "./config";
import axios from "axios";
import { saveAs } from "file-saver";
import { handleLogout } from "./Log.jsx"; // Fix for Line 86
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  PieChart,
  Pie,
  Cell,
  Sector,
} from "recharts";

import { motion } from "framer-motion";
import { FiPieChart, FiActivity, FiDownload } from "react-icons/fi";
import { BsWallet2 } from "react-icons/bs";
import { MdInsights } from "react-icons/md";
import "./Dashboard.css";
import LoginPrompt from "./LoginPrompt";

// --- Global Helpers & Constants ---
const fmtCurrency = (n) =>
  (n ?? 0).toLocaleString("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 2,
  });

const fmtChartCurrency = (n) => {
  const num = typeof n === "string"
    ? parseFloat(n.replace(/[^0-9.-]/g, ""))
    : Number(n);

  if (isNaN(num)) return "₹0";
  if (num >= 10000000) return `₹${(num / 10000000).toFixed(2)}Cr`;
  if (num >= 100000) return `₹${(num / 100000).toFixed(2)}L`;
  if (num >= 1000) return `₹${(num / 1000).toFixed(1)}K`;
  return `₹${num.toFixed(2)}`;
};

const pieColors = [
  "#2ED3A3", "#7C8CFF", "#54C5FF",
  "#00E676", "#FDBA8C", "#FF6B6B", "#FFD27F"
];

function renderActiveShape(props) {
  const { cx, cy, innerRadius, outerRadius, startAngle, endAngle, fill } = props;
  return (
    <Sector
      cx={cx}
      cy={cy}
      innerRadius={innerRadius}
      outerRadius={outerRadius + 8}
      startAngle={startAngle}
      endAngle={endAngle}
      fill={fill}
    />
  );
}

function exportCSV(data) {
  const headers = [
    "Company", "Stock", "Quantity", "Avg Buy Price",
    "Invested", "LTP", "Now Value", "P/L"
  ];

  const rows = data.map(p => [
    p.companyname,
    p.stockname,
    p.totalquantity,
    p.averagebuyprice,
    p.totalinvested,
    p.ltp,
    p.nowvalue,
    p.profitorloss
  ]);

  let csv = headers.join(",") + "\n" + rows.map(r => r.join(",")).join("\n");
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  saveAs(blob, "portfolio_export.csv");
}

export default function Dashboard() {
  // ----------- USER -----------
  const { user } = useContext(UserContext) || {};
  const stored = JSON.parse(localStorage.getItem("user"));
  const activeUser = user || stored;
  const uid = activeUser?.userid || null;

  // ----------- STATE -----------
  // These must be defined here to fix the "not defined" errors
  const [wallet, setWallet] = useState(0);
  const [portfolio, setPortfolio] = useState([]);
  const [metrics, setMetrics] = useState({});
  const [sectorSplit, setSectorSplit] = useState([]);
  const [portfolioValueSeries, setPortfolioValueSeries] = useState([]);
  const [plSeries, setPlSeries] = useState([]);
  const [transactions, setTransactions] = useState([]);
  const [activePieIndex, setActivePieIndex] = useState(-1);

  // ----------- FETCH DASHBOARD DATA -----------
  useEffect(() => {
    if (!uid) return;

    async function fetchData() {
      try {
        const token = localStorage.getItem("id_token");

        const res = await axios.get(
          `${API_URL}/dashboard/${uid}`,
          {
            headers: {
              "Content-Type": "application/json",
              Authorization: token ? `Bearer ${token}` : "",
              "X-User-Id": String(uid)
            }
          }
        );

        setWallet(res.data.wallet || 0);
        setPortfolio(res.data.portfolio || []);
        setMetrics(res.data.metrics || {});
        setPortfolioValueSeries(res.data.portfolio_value_trend || []);
        setPlSeries(res.data.profit_loss_trend || []);
        console.log("PL SERIES:", plSeries);
        console.log("PORTFOLIO SERIES:", portfolioValueSeries);
        setTransactions(res.data.transactions || []);

        const sectorData = {};
        (res.data.investment_split || []).forEach((s) => {
          const sector = s.sector || "Other";
          sectorData[sector] = (sectorData[sector] || 0) + s.amount;
        });

        setSectorSplit(
          Object.entries(sectorData).map(([sector, value]) => ({
            name: sector,
            value,
          }))
        );

      } catch (err) {
        console.error("Error fetching dashboard data:", err);
        if (err.response?.status === 401) {
          handleLogout(); // Now defined via import
        }
      }
    }

    fetchData();
    const interval = setInterval(fetchData, 15000);
    return () => clearInterval(interval);
  }, [uid]);

  // ----------- AUTH GUARD -----------
  if (!uid) {
    return <LoginPrompt message="Sign in to view your dashboard and analytics." />;
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="dash page-bg"
    >
      {/* HEADER */}
      <div className="dash__header">
        <div>
          <h1 className="dash__title">Dashboard</h1>
          <p className="dash__subtitle">Your trading overview and performance metrics</p>
        </div>

        <div className="header-tools">
          <div className="wallet-pill">
            <BsWallet2 />
            <span>
              Wallet: <strong>{fmtCurrency(wallet)}</strong>
            </span>
          </div>

          <button className="export-btn" onClick={() => exportCSV(portfolio)}>
            <FiDownload /> Quick Export
          </button>

          <button
            className="export-btn"
            onClick={() => window.open(`${API_URL}/dashboard/${uid}/export`)}
          >
            <FiDownload /> Full Export
          </button>
        </div>
      </div>

      {/* Metric Cards */}
      <div className="grid grid--4">
        <MetricCard
          icon={<BsWallet2 />}
          label="Portfolio Value"
          value={fmtCurrency(portfolio.reduce((acc, p) => acc + p.nowvalue, 0))}
          sub={`Holdings: ${portfolio.length}`}
        />
        <MetricCard
          icon={<MdInsights />}
          label="Progress"
          value={`${metrics.progress_score || 0}%`}
          sub={metrics.level || "—"}
        />
        <MetricCard
          icon={<FiPieChart />}
          label="Holdings"
          value={portfolio.length}
          sub="Active positions"
        />
        <MetricCard
          icon={<FiActivity />}
          label="Login Streak"
          value={`${metrics.login_streak || 5} days`}
          sub="Consistency"
        />
      </div>

      {/* Charts */}
      <div className="charts-row" style={{ display: 'flex', width: '100%', gap: '18px', marginBottom: '18px' }}>
        <div style={{ flex: '1 1 0%', minWidth: 0, height: '100%' }}>
          <ChartCard title="Portfolio Value" tag="overview">
            <AreaChartPanel
              data={portfolioValueSeries}
              dataKey="value"
              stroke="#26E07F"
              fill="rgba(38,224,127,0.18)"
              label="Value"
            />
          </ChartCard>
        </div>

        <div style={{ flex: '1 1 0%', minWidth: 0, height: '100%' }}>
          <ChartCard title="Profit & Loss" tag="overview">
            <AreaChartPanel
              data={plSeries}
              dataKey="profit_loss"
              stroke="#7C8CFF"
              fill="rgba(124,140,255,0.18)"
              label="Return"
            />
          </ChartCard>
        </div>
      </div>

      {/* Lower row */}
      <div className="grid grid--3">
        <Card title="Top Performers">
          {portfolio.length === 0 ? (
            <div className="empty">
              <div className="empty__icon">📈</div>
              <div>No holdings to display</div>
            </div>
          ) : (
            <div className="list-container">
              {[...portfolio]
                .sort((a, b) => b.profitorloss - a.profitorloss)
                .slice(0, 5)
                .map((p, i) => (
                  <div key={i} className="list-box">
                    <span className="list-title">{p.companyname}</span>
                    <span className={p.profitorloss >= 0 ? "text-green-400" : "text-red-400"}>
                      {fmtCurrency(p.profitorloss)}
                    </span>
                  </div>
                ))}
            </div>
          )}
        </Card>

        <Card title="Investment Split">
          {sectorSplit.length === 0 ? (
            <div className="empty">
              <div className="empty__icon">🥧</div>
              <div>No data to display</div>
            </div>
          ) : (
            <div className="pie-wrapper" style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'center' }}>
              <div style={{ flex: '1 1 200px', height: 260, display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
                <ResponsiveContainer width="100%" height={260} aspect={1}>
                  <PieChart>
                    <Pie
                      data={sectorSplit}
                      dataKey="value"
                      nameKey="name"
                      cx="50%"
                      cy="50%"
                      innerRadius={55}
                      outerRadius={85}
                      paddingAngle={4}
                      activeIndex={activePieIndex}
                      activeShape={renderActiveShape}
                      onMouseEnter={(_, idx) => setActivePieIndex(idx)}
                      onMouseLeave={() => setActivePieIndex(-1)}
                    >
                      {sectorSplit.map((_, i) => (
                        <Cell key={`cell-${i}`} fill={pieColors[i % pieColors.length]} />
                      ))}
                    </Pie>
                  </PieChart>
                </ResponsiveContainer>
              </div>

              <div className="legend legend-grid" style={{ flex: '1 1 200px', minWidth: '180px' }}>
                {sectorSplit.map((s, i) => (
                  <div key={`${s.name}-${i}`} className="legend__row">
                    <span className="dot" style={{ background: pieColors[i % pieColors.length] }} />
                    <div className="legend__label">
                      <div className="legend__name">{s.name}</div>
                      <div className="legend__val">
                        {fmtCurrency(s.value)} (
                        {((s.value / sectorSplit.reduce((acc, x) => acc + x.value, 0)) * 100).toFixed(1)}%)
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </Card>

        <Card title="Recent Transactions">
          {transactions.length === 0 ? (
            <div className="empty">
              <div className="empty__icon">🧾</div>
              <div>No recent activity</div>
            </div>
          ) : (
            <div className="list-container">
              {transactions.map((t, i) => (
                <div key={i} className="list-box">
                  <div className="list-left">
                    <span className={`tx-type ${t.type.toLowerCase()}`}>{t.type.toUpperCase()}</span>
                    <span className="list-title">{t.stockname}</span>
                    <span className="list-date">{t.date ? new Date(t.date).toLocaleString() : ""}</span>
                  </div>
                  <div className="list-right">
                    <span className="tx-price">{fmtCurrency(t.price)}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>
    </motion.div>
  );
}

function AreaChartPanel({ data = [], dataKey, stroke, fill, label }) {
  // Normalize values
  const normalised = data.map((d) => ({
    ...d,
    [dataKey]: typeof d[dataKey] === "string"
      ? parseFloat(d[dataKey].replace(/[^0-9.-]/g, "")) || 0
      : Number(d[dataKey]) || 0,
  }));

  // Handle empty/single point datasets
  const chartData =
    normalised.length === 1
      ? [
        {
          ...normalised[0],
          date: "Start",
          [dataKey]: 0,
        },
        normalised[0],
      ]
      : normalised.length === 0
        ? [
          { date: "—", [dataKey]: 0 },
          { date: "—", [dataKey]: 0 },
        ]
        : normalised;

  // ---------- FIXED Y DOMAIN ----------
  const values = chartData.map((d) => Number(d[dataKey]) || 0);

  const minValue = Math.min(...values);
  const maxValue = Math.max(...values);

  // Dynamic padding
  const padding = Math.max(
    Math.abs(maxValue - minValue) * 0.2,
    50
  );

  let yMin = minValue - padding;
  let yMax = maxValue + padding;

  // Prevent flat line issue
  if (minValue === maxValue) {
    yMin = minValue - 100;
    yMax = maxValue + 100;
  }

  // If all values are negative
  if (maxValue <= 0) {
    yMax = maxValue + padding;
  }

  // Better scaling for all-positive data
  if (minValue >= 0) {
    yMin = minValue - padding;
  }

  const yDomain = [yMin, yMax];

  // ---------- CUSTOM TOOLTIP ----------
  const CustomTooltip = ({ active, payload, label: lbl }) => {
    if (!active || !payload?.length) return null;

    return (
      <div
        style={{
          background: "#0e1722",
          border: "1px solid rgba(255,255,255,0.08)",
          borderRadius: 10,
          padding: "10px 14px",
          fontSize: 13,
          color: "#E6EEF6",
          boxShadow: "0 8px 30px rgba(0,0,0,0.5)",
        }}
      >
        <div
          style={{
            color: "#9aa7b6",
            marginBottom: 4,
          }}
        >
          {lbl}
        </div>

        <div
          style={{
            color: stroke,
            fontWeight: 700,
          }}
        >
          {label}: {fmtCurrency(payload[0].value)}
        </div>
      </div>
    );
  };

  return (
    <div style={{ width: '100%', height: 320 }}>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart
          data={chartData}
          margin={{ top: 10, right: 10, left: 0, bottom: 0 }}
        >
          <defs>
            <linearGradient
              id={`grad-${dataKey}`}
              x1="0"
              y1="0"
              x2="0"
              y2="1"
            >
              <stop
                offset="5%"
                stopColor={stroke}
                stopOpacity={0.35}
              />
              <stop
                offset="95%"
                stopColor={stroke}
                stopOpacity={0}
              />
            </linearGradient>
          </defs>

          <CartesianGrid
            stroke="rgba(255,255,255,0.04)"
            vertical={false}
          />

          <XAxis
            dataKey="date"
            tick={{
              fill: "#9aa7b6",
              fontSize: 12,
            }}
            axisLine={false}
            tickLine={false}
          />

          <YAxis
            width={70}
            tick={{
              fill: "#9aa7b6",
              fontSize: 12,
            }}
            tickFormatter={fmtChartCurrency}
            domain={yDomain}
            axisLine={false}
            tickLine={false}
          />

          <Tooltip content={<CustomTooltip />} />

          <Area
            type="monotone"
            dataKey={dataKey}
            stroke={stroke}
            strokeWidth={2.5}
            fill={`url(#grad-${dataKey})`}
            dot={false}
            connectNulls={true}
            isAnimationActive={true}
            activeDot={{
              r: 5,
              fill: stroke,
              strokeWidth: 0,
            }}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
function MetricCard({ icon, label, value, sub }) {
  return (
    <div className="metric">
      <div className="metric__icon">{icon}</div>
      <div className="metric__body">
        <div className="metric__label">{label}</div>
        <div className="metric__value">{value}</div>
        {sub && <div className="metric__sub">{sub}</div>}
      </div>
    </div>
  );
}

function ChartCard({ title, tag, children }) {
  return (
    <div className="chart-card">
      <div className="card__head">
        <h3>{title}</h3>
        <span className="tag">{tag}</span>
      </div>
      <div className="card__body chart-container">
        {children}
      </div>
    </div>
  );
}

function Card({ title, children }) {
  return (
    <div className="chart-card">
      <div className="card__head">
        <h3>{title}</h3>
      </div>
      <div className="card__body chart-container">{children}</div>
    </div>
  );
}