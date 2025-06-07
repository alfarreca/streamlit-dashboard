import yfinance as yf

# Fetch ACWX holdings (may not be 100% complete via Yahoo Finance)
acwx = yf.Ticker("ACWX")
holdings = acwx.fund_holdings  # Use the correct attribute for holdings
if holdings is not None:
    print(holdings.head(10))  # Top 10 holdings
else:
    print("Holdings data not available from Yahoo Finance.")
