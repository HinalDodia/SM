import React, {
  useEffect,
  useRef,
  useState,
  useCallback,
  useMemo,
  memo,
} from "react";
import { useParams } from "react-router-dom";
import Sidenav from "./Sidenav";
import {
  createChart,
  CrosshairMode,
  LineStyle,
} from "lightweight-charts";
import { fetchStockChart } from "./api";
import { API_BASE_URL } from "./config";
import "./StockChart.css";

// ─── Constants ────────────────────────────────────────────────────────────────

const TIMEFRAMES = [
  { label: "1D", period: "1d", interval: "5m" },
  { label: "5D", period: "5d", interval: "30m" },
  { label: "1M", period: "1mo", interval: "1d" },
  { label: "3M", period: "3mo", interval: "1d" },
  { label: "YTD", period: "ytd", interval: "1d" },
  { label: "1Y", period: "1y", interval: "1d" },
  { label: "5Y", period: "5y", interval: "1wk" },
];

const DEFAULT_TF = TIMEFRAMES[5]; // 1Y

const HISTORY_TIMEFRAMES = [
  { label: "Daily", value: "daily" },
  { label: "Weekly", value: "weekly" },
  { label: "Monthly", value: "monthly" },
];

const CHART_TYPES = [
  { label: "Candles", value: "candle" },
  { label: "Line", value: "line" },
];

// ─── Helpers ──────────────────────────────────────────────────────────────────

function fmtVolume(v) {
  if (v == null) return "—";
  if (v >= 1e9) return (v / 1e9).toFixed(2) + "B";
  if (v >= 1e6) return (v / 1e6).toFixed(2) + "M";
  if (v >= 1e3) return (v / 1e3).toFixed(1) + "K";
  return v.toString();
}

function fmtPrice(v) {
  if (v == null) return "—";
  return "₹" + Number(v).toLocaleString("en-IN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}
function toDateInput(d) { return d.toISOString().slice(0, 10); }

function formatTableDate(dateStr) {
  if (!dateStr) return "—";
  try {
    return new Date(dateStr).toLocaleDateString("en-IN", {
      day: "2-digit",
      month: "short",
      year: "numeric",
    });
  } catch {
    return dateStr.slice(0, 10);
  }
}

function fmtMarketCap(v) {
  if (v == null) return "—";
  if (v >= 1e12) return "₹" + (v / 1e12).toFixed(2) + "T";
  if (v >= 1e7) return "₹" + (v / 1e7).toFixed(2) + "Cr";
  if (v >= 1e5) return "₹" + (v / 1e5).toFixed(2) + "L";
  return "₹" + v.toFixed(2);
}

function resampleData(data, mode) {
  if (mode === "daily" || !data.length) return data;
  const buckets = {};
  for (const row of data) {
    const d = new Date(row.date);
    let key;
    if (mode === "weekly") {
      const day = d.getDay();
      const diff = day === 0 ? -6 : 1 - day;
      const mon = new Date(d);
      mon.setDate(d.getDate() + diff);
      key = mon.toISOString().slice(0, 10);
    } else {
      key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-01`;
    }
    if (!buckets[key]) {
      buckets[key] = {
        date: key, open: row.open, high: row.high, low: row.low,
        close: row.close, volume: 0,
        dma50: row.dma50, dma200: row.dma200, market_cap: row.market_cap,
      };
    } else {
      buckets[key].high = Math.max(buckets[key].high ?? 0, row.high ?? 0);
      buckets[key].low = Math.min(buckets[key].low ?? Infinity, row.low ?? Infinity);
      buckets[key].close = row.close;
      buckets[key].volume += (row.volume || 0);
      buckets[key].dma50 = row.dma50;
      buckets[key].dma200 = row.dma200;
    }
  }
  return Object.values(buckets).sort((a, b) => a.date.localeCompare(b.date));
}

// Convert a date string to a UTC Unix timestamp (seconds).
// We ALWAYS use timestamps — never BusinessDay objects — so that
// lightweight-charts never inserts blank space for weekends/holidays.
// The chart is configured with tickMarkFormatter to show nice date labels.
function toChartTime(dateStr) {
  // For "YYYY-MM-DD" strings, parse as UTC noon to avoid any DST edge cases
  const s = dateStr.slice(0, 10);          // "2023-01-15"
  const [y, m, d] = s.split("-").map(Number);
  // Use noon UTC so no date can accidentally roll to the previous day
  return Math.floor(Date.UTC(y, m - 1, d, 12, 0, 0) / 1000);
}

// Stable string key for a chart time value
function timeToKey(t) {
  if (t == null) return "";
  // t is always a number (Unix seconds) in our implementation
  return String(t);
}

// ─── Shared lightweight-charts options ────────────────────────────────────────

const BASE_CHART_OPTS = {
  layout: {
    background: { color: "#161c27" },
    textColor: "#94a3b8",
    fontFamily: "'DM Sans', 'Segoe UI', system-ui, sans-serif",
    fontSize: 12,
  },
  grid: {
    vertLines: { color: "rgba(255,255,255,0.03)" },
    horzLines: { color: "rgba(255,255,255,0.05)" },
  },
  crosshair: {
    mode: CrosshairMode.Normal,
    vertLine: {
      color: "rgba(148,163,184,0.4)",
      width: 1,
      style: LineStyle.Solid,
      labelBackgroundColor: "#1e2d3d",
    },
    horzLine: {
      color: "rgba(148,163,184,0.4)",
      width: 1,
      style: LineStyle.Solid,
      labelBackgroundColor: "#1e2d3d",
    },
  },
  rightPriceScale: {
    borderColor: "rgba(255,255,255,0.08)",
    textColor: "#64748b",
    scaleMargins: { top: 0.08, bottom: 0.26 },
    // Prevent the price scale from adding extra internal left padding
    entireTextOnly: false,
  },
  // Disable unused left price scale so it doesn't reserve space
  leftPriceScale: {
    visible: false,
  },
  timeScale: {
    borderColor: "rgba(255,255,255,0.08)",
    timeVisible: true,
    secondsVisible: false,
    // Tighter spacing so bars fill the full width naturally
    barSpacing: 8,
    minBarSpacing: 1,
    // Small right offset so the last bar isn't flush against the price axis
    rightOffset: 5,
    // Fix left edge so there's no blank canvas to the left of data
    fixLeftEdge: true,
    fixRightEdge: true,
    lockVisibleTimeRangeOnResize: true,
    // Custom formatter: monthly ticks → "Jan '24", intra-month → "15 Jun"
    tickMarkFormatter: (time, tickMarkType) => {
      const d = new Date(time * 1000);
      const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
      const mon = MONTHS[d.getUTCMonth()];
      const yr = String(d.getUTCFullYear()).slice(2); // "24"
      const day = d.getUTCDate();
      // TickMarkType: 0=Year, 1=Month, 2=DayOfMonth, 3=Time, 4=TimeWithSeconds
      if (tickMarkType === 0) return String(d.getUTCFullYear());
      if (tickMarkType === 1) return `${mon} '${yr}`;
      return `${day} ${mon}`;
    },
  },
  handleScroll: {
    mouseWheel: true,
    pressedMouseMove: true,
    horzTouchDrag: true,
    vertTouchDrag: false,
  },
  handleScale: {
    mouseWheel: true,
    pinch: true,
    axisPressedMouseMove: { time: true, price: false },
    axisDoubleClickReset: true,
  },
  // autoSize: false — we manually drive width via ResizeObserver for precise control
  autoSize: false,
};

// ─── LWChart component ────────────────────────────────────────────────────────

const LWChart = memo(({ data, chartType, onHover, showDma50, showDma200, chartRef }) => {
  const containerRef = useRef(null);
  const chartInst = useRef(null);
  const seriesRef = useRef({});
  const dataMapRef = useRef({});   // key → row

  // ── Build & destroy chart once ────────────────────────────────────────────
  useEffect(() => {
    if (!containerRef.current) return;

    // Read exact pixel width — no padding/margin adjustments needed here because
    // the CSS already zeroes them on .sc-lw-price
    const containerWidth = containerRef.current.clientWidth;

    const chart = createChart(containerRef.current, {
      ...BASE_CHART_OPTS,
      width: containerWidth,
      height: 520,
    });

    // Immediately fit so chart occupies full width on first paint
    chart.timeScale().fitContent();

    // ── Price series (candlestick or line) ─────────────────────────────────
    let priceSeries;
    if (chartType === "candle") {
      priceSeries = chart.addCandlestickSeries({
        upColor: "#26a69a",
        downColor: "#ef5350",
        borderUpColor: "#26a69a",
        borderDownColor: "#ef5350",
        wickUpColor: "#26a69a",
        wickDownColor: "#ef5350",
      });
    } else {
      priceSeries = chart.addLineSeries({
        color: "#54C5FF",
        lineWidth: 2,
        crosshairMarkerVisible: true,
        crosshairMarkerRadius: 5,
        lastValueVisible: true,
        priceLineVisible: true,
        priceLineStyle: LineStyle.Dashed,
        priceLineColor: "rgba(84,197,255,0.4)",
      });
    }

    // ── DMA 50 ─────────────────────────────────────────────────────────────
    const dma50Series = chart.addLineSeries({
      color: "#60a5fa",
      lineWidth: 1.5,
      lineStyle: LineStyle.Dashed,
      lastValueVisible: false,
      priceLineVisible: false,
      crosshairMarkerVisible: false,
      title: "DMA50",
    });

    // ── DMA 200 ────────────────────────────────────────────────────────────
    const dma200Series = chart.addLineSeries({
      color: "#fb923c",
      lineWidth: 1.5,
      lineStyle: LineStyle.Solid,
      lastValueVisible: false,
      priceLineVisible: false,
      crosshairMarkerVisible: false,
      title: "DMA200",
    });

    // ── Volume histogram on separate price scale ───────────────────────────
    const volSeries = chart.addHistogramSeries({
      priceFormat: { type: "volume" },
      priceScaleId: "vol",
      lastValueVisible: false,
    });
    chart.priceScale("vol").applyOptions({
      scaleMargins: { top: 0.78, bottom: 0 },
    });

    // ── Crosshair subscriber ───────────────────────────────────────────────
    chart.subscribeCrosshairMove((param) => {
      if (!param || !param.time) {
        onHover?.(null);
        return;
      }
      const key = timeToKey(param.time);
      const row = dataMapRef.current[key];
      if (row) onHover?.(row);
    });

    chartInst.current = chart;
    seriesRef.current = { price: priceSeries, dma50: dma50Series, dma200: dma200Series, vol: volSeries };
    if (chartRef) chartRef.current = chart;

    // ResizeObserver — keep chart flush with container width at all times
    const ro = new ResizeObserver((entries) => {
      if (!containerRef.current || !chartInst.current) return;
      // Use offsetWidth (includes border, excludes margin) for the most accurate measure
      const newWidth = containerRef.current.offsetWidth;
      if (newWidth > 0) {
        chartInst.current.applyOptions({ width: newWidth });
        // Re-fit after resize to prevent left dead-space re-appearing
        chartInst.current.timeScale().fitContent();
      }
    });
    ro.observe(containerRef.current);

    return () => {
      ro.disconnect();
      chart.remove();
      chartInst.current = null;
    };
  }, [chartType]); // re-create when chart type switches

  // ── Feed data whenever it changes ─────────────────────────────────────────
  useEffect(() => {
    if (!data.length || !seriesRef.current.price) return;

    const seen = new Set();
    const sorted = [...data]
      .map((d) => ({ ...d, _t: toChartTime(d.date) }))
      .filter((d) => {
        const k = timeToKey(d._t);
        if (seen.has(k)) return false;
        seen.add(k);
        return true;
      })
      .sort((a, b) => a._t - b._t);  // numeric sort — always correct for UTC timestamps

    // Build the lookup map
    const map = {};
    sorted.forEach((d) => { map[timeToKey(d._t)] = d; });
    dataMapRef.current = map;

    const { price: priceSeries, dma50: dma50S, dma200: dma200S, vol: volS } = seriesRef.current;

    // Price data
    if (priceSeries) {
      if (chartType === "candle") {
        priceSeries.setData(
          sorted
            .filter((d) => d.open != null && d.close != null)
            .map((d) => ({
              time: d._t,
              open: d.open,
              high: d.high,
              low: d.low,
              close: d.close,
            }))
        );
      } else {
        priceSeries.setData(
          sorted
            .filter((d) => d.close != null)
            .map((d) => ({ time: d._t, value: d.close }))
        );
      }
    }

    // DMA 50
    dma50S?.setData(
      sorted.filter((d) => d.dma50 != null).map((d) => ({ time: d._t, value: d.dma50 }))
    );

    // DMA 200
    dma200S?.setData(
      sorted.filter((d) => d.dma200 != null).map((d) => ({ time: d._t, value: d.dma200 }))
    );

    // Volume — deliberately different from candlestick green/red
    volS?.setData(
      sorted.map((d) => ({
        time: d._t,
        value: d.volume ?? 0,
        color: (d.close ?? 0) >= (d.open ?? 0)
          ? "rgba(99,179,237,0.55)"   // blue for up bars
          : "rgba(251,191,36,0.55)",  // amber for down bars
      }))
    );

    // Show full history — let user scroll freely to the left
    // fitContent ensures no dead space on left after every data change
    chartInst.current?.timeScale().fitContent();

    // Re-apply width after data load in case container measured differently
    if (containerRef.current && chartInst.current) {
      const w = containerRef.current.offsetWidth;
      if (w > 0) chartInst.current.applyOptions({ width: w });
      chartInst.current.timeScale().fitContent();
    }
  }, [data, chartType]);  // interval no longer needed — we always use UTC timestamps

  // ── Toggle DMA visibility without rebuilding the chart ────────────────────
  useEffect(() => {
    const s = seriesRef.current.dma50;
    if (!s) return;
    s.applyOptions({ visible: showDma50 });
  }, [showDma50]);

  useEffect(() => {
    const s = seriesRef.current.dma200;
    if (!s) return;
    s.applyOptions({ visible: showDma200 });
  }, [showDma200]);

  return (
    <div
      ref={containerRef}
      className="sc-lw-price"
      style={{
        width: "100%",
        minHeight: 520,
        userSelect: "none",
        // Explicitly zero out any inherited padding so lightweight-charts
        // never sees a narrower bounding box than the true container width
        padding: 0,
        margin: 0,
      }}
    />
  );
});
LWChart.displayName = "LWChart";

// ─── OHLCV legend bar (shown above chart) ────────────────────────────────────

const OHLCVLegend = memo(({ row, symbol, chartType }) => {
  const fmt = (v) => (v != null ? Number(v).toFixed(2) : "—");
  const fmtV = fmtVolume;

  if (!row) {
    return (
      <div className="sc-ohlcv-legend sc-ohlcv-legend--empty">
        <span className="lwl-sym">{symbol?.toUpperCase()}</span>
        <span className="lwl-hint">Hover over chart to see OHLCV values</span>
      </div>
    );
  }

  const isUp = (row.close ?? 0) >= (row.open ?? 0);
  const chg = row.close != null && row.open != null ? row.close - row.open : null;
  const pct = chg != null && row.open ? ((chg / row.open) * 100).toFixed(2) : null;
  const chgClr = isUp ? "#26c6a2" : "#ef5350";

  const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  let dateLabel = "";
  try {
    // Parse from the ISO date string directly — never from a timestamp — to avoid TZ shifts
    const s = row.date.slice(0, 10);   // "2023-06-15"
    const [y, mo, dy] = s.split("-").map(Number);
    dateLabel = `${MONTHS[mo - 1]} ${dy}, ${y}`;
  } catch { dateLabel = row.date?.slice(0, 10) ?? ""; }

  return (
    <div className="sc-ohlcv-legend">
      <span className="lwl-sym">{symbol?.toUpperCase()}</span>
      <span className="lwl-date">{dateLabel}</span>
      {chartType === "candle" && (
        <>
          <span className="lwl-item"><span className="lwl-lbl">O</span><span className="lwl-val">{fmt(row.open)}</span></span>
          <span className="lwl-item"><span className="lwl-lbl">H</span><span className="lwl-val lwl-high">{fmt(row.high)}</span></span>
          <span className="lwl-item"><span className="lwl-lbl">L</span><span className="lwl-val lwl-low">{fmt(row.low)}</span></span>
          <span className="lwl-item"><span className="lwl-lbl">C</span><span className="lwl-val" style={{ color: "#54C5FF" }}>{fmt(row.close)}</span></span>
        </>
      )}
      {chartType === "line" && (
        <span className="lwl-item"><span className="lwl-lbl">Price</span><span className="lwl-val" style={{ color: "#54C5FF" }}>{fmt(row.close)}</span></span>
      )}
      <span className="lwl-item"><span className="lwl-lbl">Vol</span><span className="lwl-val" style={{ color: chgClr }}>{fmtV(row.volume)}</span></span>
      {pct != null && (
        <span className="lwl-item">
          <span className="lwl-val" style={{ color: chgClr }}>
            {isUp ? "▲" : "▼"} {isUp ? "+" : ""}{pct}%
          </span>
        </span>
      )}
      {row.dma50 != null && <span className="lwl-item"><span className="lwl-lbl" style={{ color: "#60a5fa" }}>DMA50</span><span className="lwl-val">{fmt(row.dma50)}</span></span>}
      {row.dma200 != null && <span className="lwl-item"><span className="lwl-lbl" style={{ color: "#fb923c" }}>DMA200</span><span className="lwl-val">{fmt(row.dma200)}</span></span>}
    </div>
  );
});
OHLCVLegend.displayName = "OHLCVLegend";

// ─── ChartSkeleton ────────────────────────────────────────────────────────────

const ChartSkeleton = () => (
  <div className="sc-skeleton">
    {[...Array(12)].map((_, i) => (
      <div key={i} className="sc-skeleton__pulse" style={{ animationDelay: `${i * 0.08}s`, height: `${35 + Math.random() * 55}%` }} />
    ))}
  </div>
);

// ─── LegendPill ───────────────────────────────────────────────────────────────

const LegendPill = memo(({ color, label, dashed }) => (
  <div className="sc-legend-pill">
    {dashed
      ? <span className="sc-legend-pill__dash" style={{ borderTopColor: color }} />
      : <span className="sc-legend-pill__dot" style={{ background: color }} />
    }
    <span className="sc-legend-pill__label">{label}</span>
  </div>
));
LegendPill.displayName = "LegendPill";

// ─── PriceHistoryTable ────────────────────────────────────────────────────────

const PriceHistoryTable = memo(({ rawData, symbol }) => {
  const today = new Date();
  const oneMonthAgo = new Date(today);
  oneMonthAgo.setMonth(today.getMonth() - 1);

  const [historyTF, setHistoryTF] = useState("daily");
  const [startDate, setStartDate] = useState(toDateInput(oneMonthAgo));
  const [endDate, setEndDate] = useState(toDateInput(today));
  const [rangeMode, setRangeMode] = useState("Custom Range");

  useEffect(() => {
    const t = new Date(); const s = new Date(t);
    if (rangeMode === "Last Month") s.setMonth(t.getMonth() - 1);
    else if (rangeMode === "Last 3 Months") s.setMonth(t.getMonth() - 3);
    else if (rangeMode === "Last Year") s.setFullYear(t.getFullYear() - 1);
    else return;
    setStartDate(toDateInput(s));
    setEndDate(toDateInput(t));
  }, [rangeMode]);

  const filtered = useMemo(() =>
    rawData.filter((r) => r.date.slice(0, 10) >= startDate && r.date.slice(0, 10) <= endDate),
    [rawData, startDate, endDate]
  );
  const tableData = useMemo(
    () => resampleData([...filtered].reverse(), historyTF).reverse(),
    [filtered, historyTF]
  );

  const handleExport = useCallback(() => {
    const header = ["Date", "Opening Price", "Closing Price", "High", "Low", "Volume", "Market Cap"];
    const rows = tableData.map((r) => [
      formatTableDate(r.date),
      r.open?.toFixed(2) ?? "",
      r.close?.toFixed(2) ?? "",
      r.high?.toFixed(2) ?? "",
      r.low?.toFixed(2) ?? "",
      r.volume ?? "",
      r.market_cap ?? "",
    ]);
    const csv = [header, ...rows].map((r) => r.join(",")).join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = `${symbol}_price_history.csv`; a.click();
    URL.revokeObjectURL(url);
  }, [tableData, symbol]);

  return (
    <div className="sc-history-card">
      <h2 className="sc-history-title">{symbol?.toUpperCase()} Price History</h2>

      <div className="sc-history-controls">
        {/* Timeframe */}
        <div className="sc-history-select-wrap">
          <label className="sc-history-select-label">INTERVAL</label>
          <select className="sc-history-select" value={historyTF} onChange={(e) => setHistoryTF(e.target.value)}>
            {HISTORY_TIMEFRAMES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
          </select>
        </div>

        {/* Preset range */}
        <div className="sc-history-select-wrap">
          <label className="sc-history-select-label">RANGE</label>
          <select className="sc-history-select" value={rangeMode} onChange={(e) => setRangeMode(e.target.value)}>
            <option>Custom Range</option>
            <option>Last Month</option>
            <option>Last 3 Months</option>
            <option>Last Year</option>
          </select>
        </div>

        {/* Start / End dates */}
        <div className="sc-history-select-wrap">
          <label className="sc-history-select-label">START DATE</label>
          <input type="date" className="sc-history-date" value={startDate}
            onChange={(e) => { setStartDate(e.target.value); setRangeMode("Custom Range"); }} />
        </div>
        <div className="sc-history-select-wrap">
          <label className="sc-history-select-label">END DATE</label>
          <input type="date" className="sc-history-date" value={endDate}
            onChange={(e) => { setEndDate(e.target.value); setRangeMode("Custom Range"); }} />
        </div>

        <div style={{ flex: 1 }} />

        <button className="sc-history-export-btn" onClick={handleExport}>
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2">
            <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" />
            <polyline points="7 10 12 15 17 10" />
            <line x1="12" y1="15" x2="12" y2="3" />
          </svg>
          EXPORT CSV
        </button>
      </div>

      <div className="sc-history-table-wrap">
        <table className="sc-history-table">
          <thead>
            <tr>
              <th>DATE</th>
              <th>PRICE</th>
              <th>CHANGE</th>
              <th>HIGH</th>
              <th>LOW</th>
              <th>VOLUME</th>
              <th>MKT CAP</th>
            </tr>
          </thead>
          <tbody>
            {tableData.length === 0 ? (
              <tr>
                <td colSpan={7} className="sc-history-empty">
                  No data for selected range
                </td>
              </tr>
            ) : tableData.map((row, i) => {
              const ch = row.close != null && row.open != null ? row.close - row.open : null;
              const pct = ch != null && row.open ? (ch / row.open) * 100 : null;
              const up = ch == null || ch >= 0;

              return (
                <tr key={i}>
                  <td>{formatTableDate(row.date)}</td>

                  <td className="sc-price-cell">
                    {fmtPrice(row.close)}
                  </td>

                  <td>
                    {pct != null && (
                      <span className={up ? "sc-change up" : "sc-change down"}>
                        {up ? "▲" : "▼"} {Math.abs(pct).toFixed(2)}%
                      </span>
                    )}
                  </td>

                  <td className="sc-high">{fmtPrice(row.high)}</td>
                  <td className="sc-low">{fmtPrice(row.low)}</td>
                  <td>{fmtVolume(row.volume)}</td>
                  <td>{fmtMarketCap(row.market_cap)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
});
PriceHistoryTable.displayName = "PriceHistoryTable";

// ─── Main StockChart ──────────────────────────────────────────────────────────

const StockChart = () => {
  const { symbol } = useParams();

  const [chartData, setChartData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [activeTF, setActiveTF] = useState(DEFAULT_TF);
  const [chartType, setChartType] = useState("candle");
  const [companyName, setCompanyName] = useState("");
  const [updatedAt, setUpdatedAt] = useState("");
  const [hoveredRow, setHoveredRow] = useState(null);  // live crosshair data
  const [showDma50, setShowDma50] = useState(false);
  const [showDma200, setShowDma200] = useState(false);
  const lwChartRef = useRef(null);

  // ── Load chart data ────────────────────────────────────────────────────────
  const loadChart = useCallback(async (tf) => {
    if (!symbol) return;
    setLoading(true); setError(null); setHoveredRow(null);
    try {
      const data = await fetchStockChart(symbol, tf.period, tf.interval);
      if (Array.isArray(data) && data.length > 0) {
        setChartData(data);
        setUpdatedAt(new Date().toLocaleTimeString());
      } else if (data?.error) {
        setError(data.error);
      } else {
        setError("No data returned from API.");
      }
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [symbol]);

  // Fetch company name
  useEffect(() => {
    if (!symbol) return;
    fetch(`${API_BASE_URL}/stock-page/${symbol}`)
      .then((r) => r.json())
      .then((d) => setCompanyName(d?.company_overview?.name || ""))
      .catch(() => { });
  }, [symbol]);

  useEffect(() => { loadChart(activeTF); }, [symbol, activeTF, loadChart]);

  const handleTFChange = useCallback((tf) => setActiveTF(tf), []);
  const handleHover = useCallback((row) => setHoveredRow(row), []);

  // ── Derived values ─────────────────────────────────────────────────────────
  const lastPoint = useMemo(
    () => (chartData.length > 0 ? chartData[chartData.length - 1] : null),
    [chartData]
  );

  // Header price shows hovered bar if available, else last bar
  const displayRow = hoveredRow ?? lastPoint;

  const { price, change, changePct, isUp } = useMemo(() => {
    if (!displayRow) return { price: null, change: null, changePct: null, isUp: true };
    const p = displayRow.close;
    const o = displayRow.open;
    const ch = p != null && o != null ? p - o : null;
    const cp = ch != null && o ? (ch / o) * 100 : null;
    return { price: p, change: ch, changePct: cp, isUp: ch == null || ch >= 0 };
  }, [displayRow]);

  // Stats strip uses last point always (or hovered)
  const statsRow = hoveredRow ?? lastPoint;

  return (
    <div className="sc-page">
      {/* ── Sidenav ─────────────────────────────────────────────────────── */}
      <Sidenav symbol={symbol} />

      {/* ── Main ────────────────────────────────────────────────────────── */}
      <div className="sc-main">

        {/* Header */}
        <div className="sc-header-band">
          <div className="sc-price-header">
            <div className="sc-price-header__left">
              <span className="sc-price-header__symbol">{symbol?.toUpperCase()}</span>
              {companyName && <span className="sc-price-header__name">{companyName}</span>}
            </div>
            <div className="sc-price-header__right">
              {price != null && (
                <span className="sc-price-header__price">₹{fmtPrice(price)}</span>
              )}
              {changePct != null && (
                <span className={`sc-price-header__change ${isUp ? "up" : "down"}`}>
                  {isUp ? "▲" : "▼"}&nbsp;
                  {Math.abs(change ?? 0).toFixed(2)} ({Math.abs(changePct).toFixed(2)}%)
                </span>
              )}
              {updatedAt && (
                <span className="sc-price-header__updated">Updated {updatedAt}</span>
              )}
            </div>
          </div>
        </div>

        {/* Controls row */}
        <div className="sc-controls-row">
          {/* Timeframe buttons */}
          <div className="sc-tf-bar">
            {TIMEFRAMES.map((tf) => (
              <button
                key={tf.label}
                className={`sc-tf-btn${activeTF.label === tf.label ? " active" : ""}`}
                onClick={() => handleTFChange(tf)}
              >
                {tf.label}
              </button>
            ))}
          </div>

          {/* Chart type toggle */}
          <div className="sc-chart-type-bar">
            {CHART_TYPES.map((ct) => (
              <button
                key={ct.value}
                className={`sc-chart-type-btn${chartType === ct.value ? " active" : ""}`}
                onClick={() => setChartType(ct.value)}
              >
                {ct.label}
              </button>
            ))}
          </div>

          {/* Zoom controls */}
          <div className="sc-zoom-bar">
            <button
              className="sc-zoom-btn"
              title="Zoom In"
              onClick={() => {
                const ts = lwChartRef.current?.timeScale();
                if (!ts) return;
                const cur = ts.options().barSpacing ?? 8;
                ts.applyOptions({ barSpacing: Math.min(cur * 1.3, 60) });
              }}
            >＋</button>
            <button
              className="sc-zoom-btn"
              title="Zoom Out"
              onClick={() => {
                const ts = lwChartRef.current?.timeScale();
                if (!ts) return;
                const cur = ts.options().barSpacing ?? 8;
                ts.applyOptions({ barSpacing: Math.max(cur / 1.3, 1) });
              }}
            >－</button>
            <button
              className="sc-zoom-btn sc-zoom-btn--reset"
              title="Reset zoom"
              onClick={() => lwChartRef.current?.timeScale().fitContent()}
            >↺</button>
          </div>

          {/* DMA Checkboxes */}
          <div className="sc-dma-checks">
            <label className="sc-dma-label">
              <input
                type="checkbox"
                checked={showDma50}
                onChange={(e) => setShowDma50(e.target.checked)}
              />
              <span className="sc-dma-dot" style={{ background: "#60a5fa" }} />
              <span>DMA 50</span>
            </label>
            <label className="sc-dma-label">
              <input
                type="checkbox"
                checked={showDma200}
                onChange={(e) => setShowDma200(e.target.checked)}
              />
              <span className="sc-dma-dot" style={{ background: "#fb923c" }} />
              <span>DMA 200</span>
            </label>
          </div>

          {/* Legend */}
          <div className="sc-legend-row">
            <LegendPill color="rgba(99,179,237,0.8)" label="Up Vol" />
            <LegendPill color="rgba(251,191,36,0.8)" label="Down Vol" />
          </div>
        </div>

        {/* Chart card */}
        <div className="sc-chart-card">
          {error && <div className="sc-error">⚠ {error}</div>}
          {/* OHLCV legend bar above chart */}
          {!loading && (
            <OHLCVLegend row={hoveredRow ?? lastPoint} symbol={symbol} chartType={chartType} />
          )}
          {loading
            ? <ChartSkeleton />
            : (
              <LWChart
                data={chartData}
                chartType={chartType}
                onHover={handleHover}
                showDma50={showDma50}
                showDma200={showDma200}
                chartRef={lwChartRef}
              />
            )
          }
        </div>

        {/* Stats strip */}
        {!loading && statsRow && (
          <div className="sc-stats-strip">
            {[
              { label: "OPEN", val: fmtPrice(statsRow.open), color: null },
              { label: "HIGH", val: fmtPrice(statsRow.high), color: "#26c6a2" },
              { label: "LOW", val: fmtPrice(statsRow.low), color: "#ef5350" },
              { label: "CLOSE", val: fmtPrice(statsRow.close), color: null },
              { label: "VOLUME", val: fmtVolume(statsRow.volume), color: null },
              { label: "DMA 50", val: fmtPrice(statsRow.dma50), color: "#60a5fa" },
              { label: "DMA 200", val: fmtPrice(statsRow.dma200), color: "#fb923c" },
            ].map(({ label, val, color }) => (
              <div key={label} className="sc-stat">
                <span className="sc-stat__label">{label}</span>
                <span className="sc-stat__val" style={color ? { color } : {}}>{val}</span>
              </div>
            ))}
          </div>
        )}

        {/* Price History Table */}
        {!loading && chartData.length > 0 && (
          <PriceHistoryTable rawData={chartData} symbol={symbol} />
        )}
      </div>
    </div>
  );
};

export default StockChart;