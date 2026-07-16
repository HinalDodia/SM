import React, { useState, useEffect, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { fetchShortInterest } from './api';
import { 
  ComposedChart, 
  Line, 
  Bar, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer 
} from 'recharts';
import { AlertCircle, RefreshCw } from 'lucide-react';

const STOCKS = [
  "RELIANCE","TCS","INFY","HDFCBANK","ICICIBANK",
  "SBIN","AXISBANK","KOTAKBANK","BAJFINANCE","BAJAJFINSV",
  "LT","ITC","HINDUNILVR","NESTLEIND","BRITANNIA",
  "TITAN","MARUTI","EICHERMOT","HEROMOTOCO","TATASTEEL",
  "JSWSTEEL","ULTRACEMCO","POWERGRID","NTPC","ONGC",
  "SUNPHARMA","DRREDDY","CIPLA","DIVISLAB","APOLLOHOSP",
  "HCLTECH","TECHM","WIPRO","ADANIENT","ADANIPORTS",
  "COALINDIA","INDUSINDBK","PIDILITIND","ASIANPAINT","GRASIM"
];

const SIGNAL_COLORS = {
  "Short Build-up": "bg-red-500/20 text-red-500 border-red-500/30",
  "Short Covering": "bg-green-500/20 text-green-500 border-green-500/30",
  "Long Build-up": "bg-blue-500/20 text-blue-500 border-blue-500/30",
  "Long Unwinding": "bg-yellow-500/20 text-yellow-500 border-yellow-500/30",
};

const formatNumber = (num) => {
  if (num === null || num === undefined) return '-';
  return num.toLocaleString('en-IN');
};

const formatPercent = (num) => {
  if (num === null || num === undefined) return '-';
  return `${num > 0 ? '+' : ''}${num.toFixed(2)}%`;
};

export default function ShortInterest({ symbol: propSymbol }) {
  const { symbol: routeSymbol } = useParams();
  const navigate = useNavigate();
  
  const currentUrlSymbol = propSymbol || routeSymbol;
  const initialSymbol = currentUrlSymbol && STOCKS.includes(currentUrlSymbol.toUpperCase()) 
    ? currentUrlSymbol.toUpperCase() 
    : STOCKS[0];
    
  const [symbol, setSymbol] = useState(initialSymbol);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [timeFilter, setTimeFilter] = useState('1M');

  const loadData = async (sym) => {
    setLoading(true);
    setError(null);
    try {
      const result = await fetchShortInterest(sym);
      setData(result);
    } catch (err) {
      console.error(err);
      setError(err.message || 'Failed to fetch short interest data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData(symbol);
  }, [symbol]);

  useEffect(() => {
    const newSymbol = propSymbol || routeSymbol;
    if (newSymbol && STOCKS.includes(newSymbol.toUpperCase()) && newSymbol.toUpperCase() !== symbol) {
      setSymbol(newSymbol.toUpperCase());
    }
  }, [propSymbol, routeSymbol, symbol]);

  const filteredHistory = useMemo(() => {
    if (!data?.price_history) return [];
    const history = [...data.price_history];
    let sliceLen = history.length;
    if (timeFilter === '1W') sliceLen = 5;
    else if (timeFilter === '2W') sliceLen = 10;
    else if (timeFilter === '1M') sliceLen = 22;
    
    return history.slice(Math.max(history.length - sliceLen, 0));
  }, [data?.price_history, timeFilter]);

  if (error) {
    return (
      <div className="w-full p-6 flex items-center justify-center font-sans text-slate-100">
        <div className="bg-slate-800 p-8 rounded-xl border border-slate-700 max-w-md w-full text-center">
          <AlertCircle className="w-12 h-12 text-red-500 mx-auto mb-4" />
          <h2 className="text-xl font-semibold mb-2">Failed to load data</h2>
          <p className="text-slate-400 mb-6">{error} for {symbol}</p>
          <button 
            onClick={() => loadData(symbol)}
            className="flex items-center justify-center w-full gap-2 bg-blue-600 hover:bg-blue-700 text-white py-2 px-4 rounded-lg transition-colors"
          >
            <RefreshCw className="w-4 h-4" /> Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="full-width w-full font-sans text-slate-100 selection:bg-blue-500/30">
      <div className="w-full space-y-6">
        
        {/* SECTION 1: Header Bar */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-slate-800 p-4 md:p-6 rounded-xl border border-slate-700">
          <div className="flex flex-col gap-2">
            <div className="flex items-center gap-3">
              <select 
                value={symbol}
                onChange={(e) => {
                  setSymbol(e.target.value);
                  navigate(`/shortinterest/${e.target.value}`);
                }}
                className="bg-slate-900 border border-slate-700 text-lg font-bold px-3 py-1.5 rounded-lg focus:outline-none focus:border-blue-500 transition-colors"
              >
                {STOCKS.map(s => <option key={s} value={s}>{s}</option>)}
              </select>
              {loading ? (
                <div className="h-6 w-32 bg-slate-700 animate-pulse rounded"></div>
              ) : (
                <h1 className="text-xl md:text-2xl font-semibold text-slate-200">{data?.name || symbol}</h1>
              )}
            </div>
            {loading ? (
              <div className="h-5 w-48 bg-slate-700 animate-pulse rounded mt-1"></div>
            ) : (
              <div className="flex flex-wrap items-center gap-3 text-sm text-slate-400">
                <span className="px-2.5 py-0.5 bg-slate-900 rounded-md border border-slate-700">
                  {data?.sector || 'Sector N/A'}
                </span>
                <span>As of {data?.as_of || '-'}</span>
              </div>
            )}
          </div>
          
          <div className="flex items-center">
            {loading ? (
              <div className="h-8 w-32 bg-slate-700 animate-pulse rounded-full"></div>
            ) : (
              data?.signal && (
                <div className={`px-4 py-1.5 rounded-full border font-medium text-sm ${SIGNAL_COLORS[data.signal] || 'bg-slate-800 border-slate-600 text-slate-300'}`}>
                  {data.signal}
                </div>
              )
            )}
          </div>
        </div>

        {/* SECTION 2: KPI Cards Row */}
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
          {/* Card 1: Current Price */}
          <div className="bg-slate-800 p-4 rounded-xl border border-slate-700 flex flex-col gap-1">
            <span className="text-slate-400 text-xs font-medium uppercase tracking-wider">Current Price</span>
            {loading ? (
              <div className="h-8 w-24 bg-slate-700 animate-pulse rounded mt-1"></div>
            ) : (
              <div className="flex items-baseline gap-2">
                <span className="text-xl md:text-2xl font-bold">₹{data?.price?.toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2}) || '-'}</span>
                {data?.price_change != null && (
                  <span className={`text-xs font-medium px-1.5 py-0.5 rounded ${data.price_change >= 0 ? 'bg-green-500/10 text-green-500' : 'bg-red-500/10 text-red-500'}`}>
                    {data.price_change > 0 ? '+' : ''}{data.price_change}%
                  </span>
                )}
              </div>
            )}
          </div>

          {/* Card 2: Short Quantity */}
          <div className="bg-slate-800 p-4 rounded-xl border border-slate-700 flex flex-col gap-1">
            <span className="text-slate-400 text-xs font-medium uppercase tracking-wider">Short Quantity</span>
            {loading ? (
              <div className="h-8 w-24 bg-slate-700 animate-pulse rounded mt-1"></div>
            ) : (
              <span className="text-xl md:text-2xl font-bold">{formatNumber(data?.short_qty)}</span>
            )}
          </div>

          {/* Card 3: Short Qty Change */}
          <div className="bg-slate-800 p-4 rounded-xl border border-slate-700 flex flex-col gap-1">
            <span className="text-slate-400 text-xs font-medium uppercase tracking-wider">Short Qty Chg</span>
            {loading ? (
              <div className="h-8 w-24 bg-slate-700 animate-pulse rounded mt-1"></div>
            ) : (
              <span className={`text-xl md:text-2xl font-bold ${data?.short_qty_change > 0 ? 'text-red-400' : data?.short_qty_change < 0 ? 'text-green-400' : 'text-slate-100'}`}>
                {data?.short_qty_change > 0 ? '+' : ''}{formatNumber(data?.short_qty_change)}
              </span>
            )}
          </div>

          {/* Card 4: Delivery % */}
          <div className="bg-slate-800 p-4 rounded-xl border border-slate-700 flex flex-col gap-1">
            <span className="text-slate-400 text-xs font-medium uppercase tracking-wider">Delivery %</span>
            {loading ? (
              <>
                <div className="h-8 w-20 bg-slate-700 animate-pulse rounded mt-1"></div>
                <div className="h-4 w-16 bg-slate-700 animate-pulse rounded mt-1"></div>
              </>
            ) : (
              <>
                <span className="text-xl md:text-2xl font-bold">{data?.delivery_pct != null ? `${data.delivery_pct}%` : '-'}</span>
                <span className="text-xs text-slate-500">5D Avg: {data?.delivery_pct_5d_avg != null ? `${data.delivery_pct_5d_avg}%` : '-'}</span>
              </>
            )}
          </div>

          {/* Card 5: Speculative Pressure */}
          <div className="bg-slate-800 p-4 rounded-xl border border-slate-700 flex flex-col justify-between gap-2">
            <div className="flex justify-between items-center">
              <span className="text-slate-400 text-xs font-medium uppercase tracking-wider">Spec Pressure</span>
              {!loading && <span className="text-sm font-bold">{data?.mwpl_pct != null ? `${data.mwpl_pct}%` : '-'}</span>}
            </div>
            {loading ? (
              <div className="h-2 w-full bg-slate-700 animate-pulse rounded-full mt-2"></div>
            ) : (
              <div className="h-2 w-full bg-slate-900 rounded-full overflow-hidden">
                <div 
                  className={`h-full ${data?.mwpl_pct > 80 ? 'bg-red-500' : data?.mwpl_pct > 50 ? 'bg-yellow-500' : 'bg-blue-500'}`} 
                  style={{ width: `${Math.min(Math.max(data?.mwpl_pct || 0, 0), 100)}%` }}
                ></div>
              </div>
            )}
          </div>

          {/* Card 6: Short Pressure Score */}
          <div className="bg-slate-800 p-4 rounded-xl border border-slate-700 flex flex-col items-center justify-center relative overflow-hidden">
            <span className="text-slate-400 text-[10px] sm:text-xs font-medium uppercase tracking-wider absolute top-4 left-4">Score</span>
            {loading ? (
              <div className="h-12 w-12 rounded-full bg-slate-700 animate-pulse mt-4"></div>
            ) : (
              <div className="mt-4 relative flex items-center justify-center">
                <svg className="w-16 h-16 transform -rotate-90">
                  <circle cx="32" cy="32" r="28" stroke="currentColor" strokeWidth="4" fill="transparent" className="text-slate-700" />
                  <circle 
                    cx="32" cy="32" r="28" stroke="currentColor" strokeWidth="4" fill="transparent" 
                    strokeDasharray={2 * Math.PI * 28}
                    strokeDashoffset={2 * Math.PI * 28 * (1 - (data?.score || 0) / 100)}
                    className={`${data?.score > 75 ? 'text-red-500' : data?.score > 40 ? 'text-yellow-500' : 'text-green-500'} transition-all duration-1000 ease-out`}
                  />
                </svg>
                <div className="absolute inset-0 flex items-center justify-center flex-col">
                  <span className="text-lg font-bold leading-none">{data?.score || 0}</span>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* SECTION 3: THE PREMIUM CHART */}
        <div className="bg-slate-800 p-4 md:p-6 rounded-xl border border-slate-700">
          <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-6">
            <h3 className="text-lg font-semibold">Price & Volume History</h3>
            <div className="flex bg-slate-900 rounded-lg p-1 border border-slate-700">
              {['1W', '2W', '1M'].map(tf => (
                <button
                  key={tf}
                  onClick={() => setTimeFilter(tf)}
                  disabled={loading}
                  className={`px-3 py-1 text-sm font-medium rounded-md transition-colors ${timeFilter === tf ? 'bg-slate-700 text-white' : 'text-slate-400 hover:text-slate-200'} disabled:opacity-50`}
                >
                  {tf}
                </button>
              ))}
            </div>
          </div>
          
          <div className="h-[300px] w-full">
            {loading ? (
              <div className="w-full h-full bg-slate-700/50 animate-pulse rounded-lg flex items-center justify-center text-slate-500">Loading Chart...</div>
            ) : filteredHistory.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={filteredHistory} margin={{ top: 5, right: 0, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#334155" vertical={false} />
                  <XAxis 
                    dataKey="date" 
                    stroke="#94a3b8" 
                    fontSize={12} 
                    tickLine={false} 
                    axisLine={false} 
                    dy={10}
                  />
                  <YAxis 
                    yAxisId="left" 
                    stroke="#94a3b8" 
                    fontSize={12} 
                    tickLine={false} 
                    axisLine={false} 
                    domain={['auto', 'auto']}
                    tickFormatter={(val) => `₹${val}`}
                    dx={-10}
                  />
                  <YAxis 
                    yAxisId="right" 
                    orientation="right" 
                    stroke="#94a3b8" 
                    fontSize={12} 
                    tickLine={false} 
                    axisLine={false} 
                    tickFormatter={(val) => `${(val / 1000000).toFixed(1)}M`}
                    dx={10}
                  />
                  <Tooltip 
                    contentStyle={{ backgroundColor: '#1e293b', borderColor: '#334155', borderRadius: '0.5rem', color: '#f1f5f9' }}
                    itemStyle={{ color: '#f1f5f9' }}
                    labelStyle={{ color: '#94a3b8', marginBottom: '4px' }}
                  />
                  <Bar yAxisId="right" dataKey="volume" fill="#94a3b8" opacity={0.3} radius={[2, 2, 0, 0]} name="Volume" />
                  <Line yAxisId="left" type="monotone" dataKey="close" stroke="#3b82f6" strokeWidth={3} dot={false} activeDot={{ r: 6, fill: '#3b82f6', stroke: '#1e293b', strokeWidth: 2 }} name="Close Price" />
                </ComposedChart>
              </ResponsiveContainer>
            ) : (
              <div className="w-full h-full flex items-center justify-center text-slate-500 bg-slate-900/50 rounded-lg border border-slate-700/50">
                No history data available
              </div>
            )}
          </div>
        </div>

        {/* SECTION 4: Positioning Details Table */}
        <div className="bg-slate-800 rounded-xl border border-slate-700 overflow-hidden">
          <div className="p-4 md:p-6 border-b border-slate-700">
            <h3 className="text-lg font-semibold">Positioning Details</h3>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm whitespace-nowrap">
              <thead className="bg-slate-900/50 text-slate-400 border-b border-slate-700 uppercase text-xs tracking-wider">
                <tr>
                  <th className="px-6 py-4 font-medium">Metric</th>
                  <th className="px-6 py-4 font-medium">Value</th>
                  <th className="px-6 py-4 font-medium">What it means</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-700/50">
                {loading ? (
                  Array.from({ length: 12 }).map((_, i) => (
                    <tr key={i} className="hover:bg-slate-700/20 transition-colors">
                      <td className="px-6 py-3"><div className="h-4 w-32 bg-slate-700 animate-pulse rounded"></div></td>
                      <td className="px-6 py-3"><div className="h-4 w-16 bg-slate-700 animate-pulse rounded"></div></td>
                      <td className="px-6 py-3"><div className="h-4 w-64 bg-slate-700 animate-pulse rounded"></div></td>
                    </tr>
                  ))
                ) : (
                  <>
                    <tr className="hover:bg-slate-700/20 transition-colors">
                      <td className="px-6 py-3 font-medium text-slate-300">Short Quantity</td>
                      <td className="px-6 py-3 font-semibold">{formatNumber(data?.short_qty)}</td>
                      <td className="px-6 py-3 text-slate-400">Shares sold short on NSE today</td>
                    </tr>
                    <tr className="hover:bg-slate-700/20 transition-colors">
                      <td className="px-6 py-3 font-medium text-slate-300">Short Qty Change</td>
                      <td className={`px-6 py-3 font-semibold ${data?.short_qty_change > 0 ? 'text-red-400' : data?.short_qty_change < 0 ? 'text-green-400' : ''}`}>
                        {data?.short_qty_change > 0 ? '+' : ''}{formatNumber(data?.short_qty_change)}
                      </td>
                      <td className="px-6 py-3 text-slate-400">Change from previous trading day</td>
                    </tr>
                    <tr className="hover:bg-slate-700/20 transition-colors">
                      <td className="px-6 py-3 font-medium text-slate-300">OI Change %</td>
                      <td className="px-6 py-3 font-semibold">{formatPercent(data?.oi_change_pct)}</td>
                      <td className="px-6 py-3 text-slate-400">Short activity change (capped ±50%)</td>
                    </tr>
                    <tr className="hover:bg-slate-700/20 transition-colors">
                      <td className="px-6 py-3 font-medium text-slate-300">Delivery %</td>
                      <td className="px-6 py-3 font-semibold">{data?.delivery_pct != null ? `${data.delivery_pct}%` : '-'}</td>
                      <td className="px-6 py-3 text-slate-400">% of volume held overnight (higher = more conviction)</td>
                    </tr>
                    <tr className="hover:bg-slate-700/20 transition-colors">
                      <td className="px-6 py-3 font-medium text-slate-300">5D Avg Delivery</td>
                      <td className="px-6 py-3 font-semibold">{data?.delivery_pct_5d_avg != null ? `${data.delivery_pct_5d_avg}%` : '-'}</td>
                      <td className="px-6 py-3 text-slate-400">5-day smoothed delivery trend</td>
                    </tr>
                    <tr className="hover:bg-slate-700/20 transition-colors">
                      <td className="px-6 py-3 font-medium text-slate-300">Speculative Pressure</td>
                      <td className="px-6 py-3 font-semibold">{data?.mwpl_pct != null ? `${data.mwpl_pct}%` : '-'}</td>
                      <td className="px-6 py-3 text-slate-400">Inverse of delivery — higher means more intraday speculation</td>
                    </tr>
                    <tr className="hover:bg-slate-700/20 transition-colors">
                      <td className="px-6 py-3 font-medium text-slate-300">PCR Proxy</td>
                      <td className="px-6 py-3 font-semibold">{data?.pcr != null ? data.pcr.toFixed(2) : '-'}</td>
                      <td className="px-6 py-3 text-slate-400">Put/Call ratio estimate (&gt;1 = more bearish bets)</td>
                    </tr>
                    <tr className="hover:bg-slate-700/20 transition-colors">
                      <td className="px-6 py-3 font-medium text-slate-300">Volume Today</td>
                      <td className="px-6 py-3 font-semibold">{formatNumber(data?.volume)}</td>
                      <td className="px-6 py-3 text-slate-400">Total shares traded today</td>
                    </tr>
                    <tr className="hover:bg-slate-700/20 transition-colors">
                      <td className="px-6 py-3 font-medium text-slate-300">Avg Volume (20D)</td>
                      <td className="px-6 py-3 font-semibold">{formatNumber(data?.avg_volume_20d)}</td>
                      <td className="px-6 py-3 text-slate-400">20-day average daily volume</td>
                    </tr>
                    <tr className="hover:bg-slate-700/20 transition-colors">
                      <td className="px-6 py-3 font-medium text-slate-300">Volume Ratio</td>
                      <td className="px-6 py-3 font-semibold">{data?.volume_ratio != null ? `${data.volume_ratio}x` : '-'}</td>
                      <td className="px-6 py-3 text-slate-400">Today vs 20D average (&gt;1 = unusual activity)</td>
                    </tr>
                    <tr className="hover:bg-slate-700/20 transition-colors">
                      <td className="px-6 py-3 font-medium text-slate-300">52W High</td>
                      <td className="px-6 py-3 font-semibold">{data?.week52_high != null ? `₹${data.week52_high.toLocaleString('en-IN')}` : '-'}</td>
                      <td className="px-6 py-3 text-slate-400">Highest price in last 52 weeks</td>
                    </tr>
                    <tr className="hover:bg-slate-700/20 transition-colors">
                      <td className="px-6 py-3 font-medium text-slate-300">52W Low</td>
                      <td className="px-6 py-3 font-semibold">{data?.week52_low != null ? `₹${data.week52_low.toLocaleString('en-IN')}` : '-'}</td>
                      <td className="px-6 py-3 text-slate-400">Lowest price in last 52 weeks</td>
                    </tr>
                  </>
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* SECTION 5: Footer note */}
        <p className="text-center text-xs text-slate-500 pt-4 pb-8">
          Short quantity data sourced from NSE official short selling reports. 
          Delivery data from NSE equity bhav copy. All figures end-of-day.
        </p>

      </div>
    </div>
  );
}
