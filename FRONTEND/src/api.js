import { API_BASE_URL } from "./config";

function authHeaders() {
  const token = localStorage.getItem("id_token");
  const user = JSON.parse(localStorage.getItem("user") || "{}");
  const headers = { "Content-Type": "application/json" };

  // The backend MUST have this token to verify the session
  if (token) headers["Authorization"] = `Bearer ${token}`;

  // Fallback for routes that specifically look for X-User-Id
  if (user.userid) headers["X-User-Id"] = String(user.userid);

  return headers;
}


export async function fetchAutocomplete(query) {
  const res = await fetch(`${API_BASE_URL}/autocomplete?q=${query}`, {
    headers: authHeaders()
  });
  return res.json();
}

export async function fetchStockPrice(symbol) {
  const res = await fetch(`${API_BASE_URL}/get-price/${symbol}`, {
    headers: authHeaders()
  });
  return res.json();
}

export async function fetchWatchlist(userId) {
  const res = await fetch(`${API_BASE_URL}/get_watchlist/${userId}`, {
    headers: authHeaders()
  });
  return res.json();
}

export async function addToWatchlist(data) {
  const res = await fetch(`${API_BASE_URL}/add_to_watchlist`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...authHeaders()
    },
    body: JSON.stringify(data),
  });
  return res.json();
}

export async function removeFromWatchlist(userId, stockId) {
  const res = await fetch(
    `${API_BASE_URL}/remove_from_watchlist/${userId}/${stockId}`,
    {
      method: "DELETE",
      headers: authHeaders()
    }
  );
  return res.json();
}

export async function buyStock(data) {
  const res = await fetch(`${API_BASE_URL}/buy`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...authHeaders()
    },
    body: JSON.stringify(data),
  });
  return res.json();
}

export async function sellStock(data) {
  const res = await fetch(`${API_BASE_URL}/sell`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...authHeaders()
    },
    body: JSON.stringify(data),
  });
  return res.json();
}

export async function fetchPortfolio(userId) {
  const res = await fetch(`${API_BASE_URL}/portfolio/${userId}`, {
    headers: authHeaders()
  });
  return res.json();
}

// ─── Stock Detail Page APIs ───────────────────────────────────────────────────

export async function fetchStockPage(symbol) {
  const res = await fetch(`${API_BASE_URL}/stock-page/${symbol}`, {
    headers: authHeaders()
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}
export async function fetchCompetitors(symbol) {
  const res = await fetch(`${API_BASE_URL}/stock-competitors/${symbol}`, {
    headers: authHeaders()
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function fetchDividendSummary(symbol) {
  const res = await fetch(`${API_BASE_URL}/stock-dividend/${symbol}`, {
    headers: authHeaders()
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function fetchEarnings(symbol) {
  const res = await fetch(`${API_BASE_URL}/stock-earnings/${symbol}`, {
    headers: authHeaders()
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function fetchFinancials(symbol) {
  const res = await fetch(`${API_BASE_URL}/stock-financials/${symbol}`, {
    headers: authHeaders()
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function fetchOptions(symbol, expiry) {
  const url = expiry
    ? `${API_BASE_URL}/stock-options/${symbol}?expiry=${expiry}`
    : `${API_BASE_URL}/stock-options/${symbol}`;
  const res = await fetch(url, { headers: authHeaders() });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function fetchSecFilings(symbol) {
  const res = await fetch(`${API_BASE_URL}/stock-bse-filings/${symbol}`, {
    headers: authHeaders()
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function fetchBseCompany(symbol) {
  const res = await fetch(`${API_BASE_URL}/bse-company/${symbol}`, {
    headers: authHeaders()
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function fetchBseFilings(symbol, params = {}) {
  const url = new URL(`${API_BASE_URL}/stock-bse-filings/${symbol}`);

  Object.keys(params).forEach(key => {
    // Only skip null/undefined — allow empty strings, "false", 0, etc.
    if (params[key] !== null && params[key] !== undefined) {
      url.searchParams.append(key, params[key]);
    }
  });

  const res = await fetch(url, { headers: authHeaders() });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}



export async function fetchShortInterest(symbol) {
  const res = await fetch(`${API_BASE_URL}/stock-short-interest/${symbol}`, {
    headers: authHeaders()
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function fetchHeadlines(symbol) {
  const res = await fetch(`${API_BASE_URL}/stock-headlines/${symbol}`, {
    headers: authHeaders()
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

/**
 * Fetch OHLC + DMA data for the stock chart page.
 * @param {string} symbol  - Ticker symbol, e.g. "AAPL"
 * @param {string} period  - "1d" | "5d" | "1mo" | "3mo" | "1y" | "5y"  (default "1y")
 * @param {string} interval- "1m" | "5m" | "1h" | "1d"                  (default "1d")
 */
export async function fetchStockChart(symbol, period = "1y", interval = "1d") {
  const params = new URLSearchParams({ period, interval });
  const res = await fetch(
    `${API_BASE_URL}/stock-chart/${symbol}?${params}`,
    { headers: authHeaders() }
  );
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}
