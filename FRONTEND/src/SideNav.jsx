import { NavLink } from "react-router-dom";
import {
    LayoutDashboard,
    CandlestickChart,
    GitCompare,
    Coins,
    TrendingUp,
    BookOpen,
    Newspaper,
    Layers,
    FileSearch,
    Radar,
} from "lucide-react";

// Single source of truth for the stock-detail sidebar.
// Used by: StockDetailPage, StockChart, Competitor, Dividend,
// EarningsPage, FinancialsPage, SecFilingsPage.
//
// Props:
//   symbol       (required) - the stock symbol, used to build every link
//   onBuyClick   (optional) - if provided, "BUY STOCK" runs this instead
//                             of just navigating to the stock page
//                             (StockDetailPage passes its real buy-flow handler here)

const NAV_ITEMS = [
    { to: (s) => `/stock-page/${s}`, label: "Overview", icon: LayoutDashboard, end: true },
    { to: (s) => `/stock-chart/${s}`, label: "Price Action", icon: CandlestickChart },
    { to: (s) => `/stock-competitor/${s}`, label: "Peer Compare", icon: GitCompare },
    { to: (s) => `/stock-dividend/${s}`, label: "Dividends", icon: Coins },
    { to: (s) => `/stock-earnings/${s}`, label: "Earnings", icon: TrendingUp },
    { to: (s) => `/stock-financials/${s}`, label: "Fundamentals", icon: BookOpen },
    { to: (s) => `/stock-headlines/${s}`, label: "News Feed", icon: Newspaper },
    { to: (s) => `/stock-options/${s}`, label: "Options Desk", icon: Layers },
    { to: (s) => `/stock-bse-filings/${s}`, label: "Disclosures", icon: FileSearch },
    { to: (s) => `/stock-short-interest/${s}`, label: "Short Radar", icon: Radar },
];

function Sidenav({ symbol, onBuyClick }) {
    return (
        <div className="stock-sidenav">
            {NAV_ITEMS.map(({ to, label, icon: Icon, end }) => (
                <NavLink key={label} to={to(symbol)} className="nav-item" end={end}>
                    <Icon className="w-4 h-4 inline-block mr-2 mb-0.5" /> {label}
                </NavLink>
            ))}

            {onBuyClick ? (
                <button
                    onClick={onBuyClick}
                    className="nav-item buy-item w-full text-left"
                    style={{ cursor: "pointer", border: "none", outline: "none", fontWeight: "bold" }}
                >
                    BUY STOCK
                </button>
            ) : (
                <NavLink to={`/stock-page/${symbol}`} className="nav-item buy-item">
                    BUY STOCK
                </NavLink>
            )}
        </div>
    );
}

export default Sidenav;