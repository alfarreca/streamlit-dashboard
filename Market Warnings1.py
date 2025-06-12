import pandas as pd

# ETF data based on Gundlach's themes
etf_data = {
    "Theme": [
        "Gold (Core Hedge)",
        "Gold (Core Hedge)",
        "Gold Miners (Leveraged Real Asset Exposure)",
        "Gold Miners (Leveraged Real Asset Exposure)",
        "Gold Miners (Leveraged Real Asset Exposure)",
        "India Equity Exposure",
        "India Equity Exposure",
        "India Equity Exposure",
        "India Equity Exposure",
        "Emerging Markets (Currency-Hedged)",
        "Broader EM Equity (Unhedged)"
    ],
    "Ticker": [
        "GLD", "IAU", "GDX", "RING", "GDXJ", 
        "INDA", "EPI", "SMIN", "INDY", "HEEM", "VWO"
    ],
    "Name": [
        "SPDR Gold Shares",
        "iShares Gold Trust",
        "VanEck Gold Miners ETF",
        "iShares MSCI Global Gold Miners ETF",
        "VanEck Junior Gold Miners ETF",
        "iShares MSCI India ETF",
        "WisdomTree India Earnings Fund",
        "iShares MSCI India Small-Cap ETF",
        "iShares India 50 ETF",
        "iShares Currency Hedged MSCI Emerging Markets ETF",
        "Vanguard FTSE Emerging Markets ETF"
    ],
    "Expense Ratio": [
        0.40, 0.25, 0.51, 0.39, 0.52,
        0.62, 0.85, 0.74, 0.94, 0.61, 0.08
    ],
    "Role": [
        "Core ballast for inflation/fiscal shock hedge",
        "Lower-cost gold exposure",
        "Large-cap gold miners with leverage to gold prices",
        "Global gold miners with broader diversification",
        "Higher-risk junior gold miners",
        "Broad large/mid-cap India exposure",
        "Earnings-weighted India strategy",
        "High-growth India small-cap exposure",
        "Top 50 Nifty stocks in India",
        "EM equity exposure without currency risk",
        "Low-cost diversified EM equities"
    ]
}

# Create DataFrame
etf_df = pd.DataFrame(etf_data)

# Print the DataFrame
print("ETF Recommendations Based on Jeffrey Gundlach's Themes:\n")
print(etf_df.to_string(index=False))

# Portfolio allocation suggestion
portfolio_allocation = {
    "Core Allocation (50-60%)": ["GLD/IAU (20-25%)", "INDA/VWO (20-25%)", "HEEM (10%)"],
    "Satellite Allocation (30-40%)": ["GDX/RING (10-15%)", "SMIN (10%)", "GDXJ (5-10%)"],
    "Opportunistic (10%)": ["EPI/INDY (5%)", "Other tactical positions (5%)"]
}

print("\nSuggested Portfolio Allocation Framework:")
for category, allocations in portfolio_allocation.items():
    print(f"\n{category}:")
    for alloc in allocations:
        print(f"- {alloc}")

print("\nInvestment Rationale:")
print("""
1. Gold & miners align with Gundlach's view of gold as the new flight-to-quality asset
2. India/EM equities tap into secular growth and dollar weakness tailwinds
3. Currency-hedged EM (HEEM) cushions against FX volatility
4. Satellite positions provide higher growth potential while core maintains stability
""")

print("Note: Review each ETF's expense ratio, liquidity, and how it fits your risk profile.")
print("Consider periodic rebalancing to maintain target allocations.")
