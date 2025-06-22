import streamlit as st
import pandas as pd
import re

def read_with_auto_header(file):
    preview = pd.read_excel(file, header=None, nrows=15)
    header_row = preview.notna().sum(axis=1).idxmax()  # row with most non-NA
    df = pd.read_excel(file, header=header_row)
    return df

with tab6:
    st.header("📈 Gold Holdings History (Historical)")

    historical_file = st.file_uploader(
        "Upload XLSX file with historical gold holdings (wide or long format)",
        type=["xlsx"], key="hist"
    )

    if historical_file:
        try:
            df_hist = read_with_auto_header(historical_file)
            st.success("Historical file uploaded and parsed!")
            st.dataframe(df_hist)

            # --- Robust date detection: picks up strings, timestamps, Excel floats ---
            date_cols = []
            for col in df_hist.columns[1:]:  # skip first col (Country)
                try:
                    dt = pd.to_datetime(col)
                    date_cols.append(col)
                except Exception:
                    continue
            country_col = df_hist.columns[0]

            if date_cols:
                # --- GLOBAL TOTAL CHART ---
                st.subheader("🌍 Total Global Gold Holdings Over Time")
                global_totals = df_hist[date_cols].apply(pd.to_numeric, errors="coerce").sum(axis=0)
                total_chart = pd.DataFrame({
                    "Date": pd.to_datetime(date_cols, errors="coerce"),
                    "Global Tonnes": global_totals.values
                }).sort_values("Date")
                st.line_chart(total_chart.set_index("Date")["Global Tonnes"])
                st.dataframe(total_chart)

                # --- Optional: Country Picker & Single Country Chart ---
                st.markdown("---")
                st.subheader("By Country (optional)")
                countries = df_hist[country_col].dropna().unique().tolist()
                selected_country = st.selectbox("Select country", countries)
                country_row = df_hist[df_hist[country_col] == selected_country].iloc[0]
                chart_data = pd.DataFrame({
                    "Date": date_cols,
                    "Tonnes": [country_row[col] for col in date_cols]
                })
                chart_data["Date"] = pd.to_datetime(chart_data["Date"], errors="coerce")
                chart_data["Tonnes"] = pd.to_numeric(chart_data["Tonnes"], errors="coerce")
                chart_data = chart_data.dropna(subset=["Tonnes"])
                st.line_chart(chart_data.set_index("Date")["Tonnes"])
                st.dataframe(chart_data)
            else:
                # Try to detect "long" format (Country, Date, Tonnes)
                required_cols = [col for col in df_hist.columns if "country"
