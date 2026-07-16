import yfinance as yf

def get_stock_data(ticker):
    try:
        if not ticker.endswith(".NS"):
            ticker += ".NS"

        stock = yf.Ticker(ticker)
        info = stock.info

        return {
            "ltp": round(info.get('regularMarketPrice', 0), 2),
            "change": round(info.get('regularMarketChange', 0), 2),
            "percent_change": round(info.get('regularMarketChangePercent', 0), 2)
        }
    except Exception as e:
        return {"error": str(e)}
    
result = get_stock_data("DAVANGERE.NS")
print(result)
