with tab5:
    st.header("📤 Central Bank Gold Holdings & Purchases Upload")

    uploaded_file = st.file_uploader(
        "Upload XLSX file with historical gold holdings (wide or long format)",
        type=["xlsx"]
    )

    if uploaded_file:
        try:
            # Try reading wide format (countries as rows, dates as columns)
            df = pd.read_excel(uploaded_file)
            st.success("File uploaded!")

            # Detect if "wide" format: first column is country, rest are dates
            date_cols = [col for col in df.columns if isinstance(col, str) and '/' in col or '-' in col]
            country_col = df.columns[0]

            if date_cols:
                st.info("Detected wide format. Select a country to chart historical gold holdings.")
                countries = df[country_col].dropna().unique().tolist()
                selected_country = st.selectbox("Select country", countries)
                country_row = df[df[country_col] == selected_country].iloc[0]
                chart_data = pd.DataFrame({
                    "Date": date_cols,
                    "Tonnes": [country_row[col] for col in date_cols]
                })
                # Convert dates to datetime, tonnes to float
                chart_data["Date"] = pd.to_datetime(chart_data["Date"])
                chart_data["Tonnes"] = pd.to_numeric(chart_data["Tonnes"], errors="coerce")
                st.line_chart(chart_data.set_index("Date")["Tonnes"])
                st.dataframe(chart_data)
            else:
                # Try to detect "long" format (Country, Date, Tonnes)
                required_cols = [col for col in df.columns if "country" in str(col).lower() or "area" in str(col).lower()] + \
                                [col for col in df.columns if "date" in str(col).lower()] + \
                                [col for col in df.columns if "tonne" in str(col).lower()]
                if len(required_cols) >= 3:
                    st.info("Detected long format. Select a country to chart historical gold holdings.")
                    country_col = [col for col in df.columns if "country" in str(col).lower() or "area" in str(col).lower()][0]
                    date_col = [col for col in df.columns if "date" in str(col).lower()][0]
                    tonnes_col = [col for col in df.columns if "tonne" in str(col).lower()][0]
                    countries = df[country_col].dropna().unique().tolist()
                    selected_country = st.selectbox("Select country", countries)
                    filtered = df[df[country_col] == selected_country]
                    filtered[date_col] = pd.to_datetime(filtered[date_col])
                    filtered[tonnes_col] = pd.to_numeric(filtered[tonnes_col], errors="coerce")
                    filtered = filtered.sort_values(date_col)
                    st.line_chart(filtered.set_index(date_col)[tonnes_col])
                    st.dataframe(filtered)
                else:
                    st.warning("No recognized historical structure. Please upload a file with either:\n"
                               "- Countries as rows, dates as columns (wide)\n"
                               "- Or with columns: Country, Date, Tonnes (long).")
        except Exception as e:
            st.error(f"Error reading or parsing file: {e}")
    else:
        st.info("Please upload a gold statistics XLSX file with historical data.")
