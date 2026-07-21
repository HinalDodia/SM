import { useState, useEffect } from 'react';
import { Routes, Route } from 'react-router-dom';
import Watchlist from './Watchlist';
import Portfolio from './Portfolio';
import Dashboard from './Dashboard.jsx';
import Learnings from './Learnings.jsx';
import Home from './Home.jsx';
import Log from './Log.jsx';
import Signup from './Signup';
import OtpReset from './OTPReset';
import StockPrediction from './StockPrediction.jsx';
import StockDetailPage from './StockDetailPage';
import CompetitorsPage from "./Competitor.jsx";
import DividendPage from "./Dividend.jsx";
import StockChart from './StockChart.jsx';
import EarningsPage from './EarningsPage.jsx';
import FinancialsPage from './FinancialsPage.jsx';
import SecFilingsPage from './SecFilingsPage.jsx';
import ShortInterest from './ShortInterest.jsx';

function AppWrapper() {

  const [portfolio, setPortfolio] = useState(() => {
    const saved = localStorage.getItem('portfolio');
    return saved ? JSON.parse(saved) : [];
  });

  const [wallet, setWallet] = useState(() => {
    const saved = localStorage.getItem('wallet');
    return saved ? parseFloat(saved) : 10000;
  });

  const [watchlist, setWatchlist] = useState(() => {
    const saved = localStorage.getItem('watchlist');
    return saved ? JSON.parse(saved) : [];
  });

  const [transactions] = useState(() => {
    const saved = localStorage.getItem("transactions");
    return saved ? JSON.parse(saved) : [
      { type: "BUY", symbol: "AAPL", shares: 10, price: 180, amount: 1800, date: "2025-09-01 10:00 AM" },
      { type: "BUY", symbol: "GOOGL", shares: 5, price: 140, amount: 700, date: "2025-09-02 2:00 PM" },
    ];
  });

  useEffect(() => {
    localStorage.setItem("transactions", JSON.stringify(transactions));
  }, [transactions]);

  useEffect(() => {
    localStorage.setItem('portfolio', JSON.stringify(portfolio));
  }, [portfolio]);

  useEffect(() => {
    localStorage.setItem('wallet', wallet.toString());
  }, [wallet]);

  useEffect(() => {
    localStorage.setItem('watchlist', JSON.stringify(watchlist));
  }, [watchlist]);

  return (
    <Routes>
      <Route path="/" element={<Home />} />
      <Route path="/Log" element={<Log />} />
      <Route path="/signup" element={<Signup />} />
      <Route path="/forgot-password" element={<OtpReset />} />
      <Route path="/watchlist" element={
        <Watchlist
          portfolio={portfolio}
          setPortfolio={setPortfolio}
          wallet={wallet}
          setWallet={setWallet}
          watchlist={watchlist}
          setWatchlist={setWatchlist}
        />
      } />
      <Route path="/portfolio" element={
        <Portfolio
          portfolio={portfolio}
          setPortfolio={setPortfolio}
          wallet={wallet}
          setWallet={setWallet}
        />
      } />
      <Route
        path="/dashboard"
        element={<Dashboard />}
      />

      <Route path='/learnings' element={
        <Learnings />
      }
      />
      <Route path='/stockprediction' element={
        <StockPrediction />
      }
      />



      <Route path="/stock-page/:symbol" element={<StockDetailPage />} />
      <Route path="/stock-competitors/:symbol" element={<CompetitorsPage />} />
      <Route path="/stock-dividend/:symbol" element={<DividendPage />} />
      <Route path="/stock-chart/:symbol" element={<StockChart />} />
      <Route path="/stock-earnings/:symbol" element={<EarningsPage />} />
      <Route path="/stock-financials/:symbol" element={<FinancialsPage />} />
      <Route path="/stock-news/:symbol" element={<StockDetailPage tab="news" />} />
      <Route path="/insiders/:symbol" element={<StockDetailPage tab="insiders" />} />
      <Route path="/ownership/:symbol" element={<StockDetailPage tab="ownership" />} />
      <Route path="/trends/:symbol" element={<StockDetailPage tab="trends" />} />
      <Route path="/options/:symbol" element={<StockDetailPage tab="options" />} />
      <Route path="/sec/:symbol" element={<SecFilingsPage />} />
      <Route path="/shortinterest/:symbol" element={<StockDetailPage tab="shortinterest" />} />

    </Routes>
  );
}

export default AppWrapper;
