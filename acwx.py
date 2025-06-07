import yfinance as yf

# Fetch ACWX holdings (may not be 100% complete via Yahoo Finance)
acwx = yf.Ticker("ACWX")
holdings = acwx.get_holdings()  # Works if available, otherwise use iShares website
print(holdings.head(10))  # Top 10 holdings
