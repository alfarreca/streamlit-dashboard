import yfinance as yf
kgc = yf.Ticker("KGC")
print(kgc.info.get("freeCashflow"))
