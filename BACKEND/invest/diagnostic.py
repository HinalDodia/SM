from insert import bse_filings

data = bse_filings("RELIANCE")
filings = data.get("filings", [])

# Show every single filing between July 15-22, 2025, unfiltered,
# so we can see exactly what BSE returned around the June 2025 results date
for f in filings:
    date = f.get("date", "")
    if "2025-07-1" in date or "2025-07-2" in date:
        print(f"{date}")
        print(f"    category: {f.get('category_raw')}")
        print(f"    desc:     {f.get('description')}")
        print()