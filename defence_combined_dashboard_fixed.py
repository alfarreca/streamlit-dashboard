def main() -> None:
    st.set_page_config(page_title="Defense Sector Dashboard", layout="wide")
    st.title("🛡️ Defense Sector: Combined Metrics & Price Dashboard")

    # ─── Move Ticker Input to Top ───────────────────────────────────
    st.markdown("### Tickers")
    tick_input = st.text_input("Enter tickers (e.g., ETR:RHM STO:SAAB-B EPA:HO)", 
                               "ETR:RHM STO:SAAB-B EPA:HO LON:BA BIT:LDO")
    if st.button("🔄 Load Tickers"):
        tickers = tuple(t.strip() for t in tick_input.split())
    else:
        tickers = ("ETR:RHM", "STO:SAAB-B", "EPA:HO", "LON:BA", "BIT:LDO")

    # ─── Fetch Fundamentals & Signals ───────────────────────────────
    fundamentals = fetch_fundamentals(tickers)

    signals, last_dates = [], []
    for tick in tickers:
        wk = fetch_weekly_prices(tick)
        if wk.empty:
            signals.append("n/a")
            last_dates.append("")
        else:
            signals.append(compute_signal(wk))
            last_dates.append(wk.index[-1].strftime("%Y-%m-%d"))

    fundamentals["MA Signal"] = signals
    fundamentals["Last Price Date"] = last_dates

    st.subheader("📊 Fundamentals & Weekly MA Signals")
    st.dataframe(
        fundamentals.style.format({
            "Dividend Yield (%)": "{:.2f}",
            "Payout Ratio (%)": "{:.2f}",
            "Free Cash Flow (m)": "{:,.0f}",
        }),
        use_container_width=True,
    )

    # ─── Weekly Chart ───────────────────────────────────────────────
    st.markdown("---")
    selection = st.selectbox("Select a ticker to view the weekly chart:", tickers)
    chart_df = fetch_weekly_prices(selection)

    if chart_df.empty:
        st.info("❗ Price data not available for the selected ticker.")
    else:
        chart_df = chart_df.copy()
        chart_df["MA10"] = chart_df["Close"].rolling(10).mean()
        chart_df["MA20"] = chart_df["Close"].rolling(20).mean()
        st.subheader(f"📈 Weekly Close & Moving Averages — {selection}")
        st.line_chart(chart_df[["Close", "MA10", "MA20"]])
