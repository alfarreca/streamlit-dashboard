# In the sidebar section (around line 40), add this after the file uploader:
    st.header("OR")
    manual_ticker = st.text_input("Enter a single ticker (e.g. SPY, AAPL, 9618.HK)", 
                                 help="For HKEX stocks use format XXXX.HK (e.g. 9618.HK)")

# Modify the main logic (around line 300) to handle manual ticker input:
def main():
    # Get sheet names first (not cached)
    sheet_names = get_sheet_names(uploaded_file)
    
    # Let user select which sheet to use (outside cached function)
    if len(sheet_names) > 1:
        selected_sheet = st.selectbox("Select sheet to use", sheet_names, key="sheet_selector")
        st.markdown(f"<div class='sheet-selector'>Using sheet: <strong>{selected_sheet}</strong></div>", unsafe_allow_html=True)
    elif len(sheet_names) == 1:
        selected_sheet = sheet_names[0]
    else:
        selected_sheet = None
    
    # Show available sheets info
    if len(sheet_names) > 1:
        st.info(f"Available sheets: {', '.join(sheet_names)}")
    
    # Load tickers from selected sheet (cached) or use manual ticker
    if manual_ticker and not uploaded_file:
        # Create a dummy DataFrame for manual ticker entry
        tickers_df = pd.DataFrame({
            'Symbol': [manual_ticker],
            'Exchange': ['MANUAL'],
            'YFinance_Symbol': [manual_ticker],
            'Display_Name': [manual_ticker]
        })
        analysis_type = "Single Company"  # Force single company mode for manual entry
    else:
        tickers_df = load_tickers_from_sheet(uploaded_file, selected_sheet)
    
    if tickers_df is not None:
        if analysis_type == "Single Company":
            # Single company analysis mode
            if manual_ticker and not uploaded_file:
                selected_display = manual_ticker
                base_symbol = manual_ticker
            else:
                selected_display = st.selectbox("Select a ticker to analyze", tickers_df['Display_Name'])
                selected_row = tickers_df[tickers_df['Display_Name'] == selected_display].iloc[0]
                base_symbol = selected_row['YFinance_Symbol']
            
            stock_data = load_stock_data(base_symbol, start_date, end_date)
            
            # Rest of the single company analysis code remains the same...
            # [keep all the existing single company analysis code]
            
        elif analysis_type == "Multi-Company Compare":
            # Multi-company comparison mode
            if manual_ticker and not uploaded_file:
                st.warning("Multi-company comparison requires an uploaded file with multiple tickers")
            else:
                st.markdown("<div class='company-comparison'>", unsafe_allow_html=True)
                selected_companies = st.multiselect(
                    "Select companies to compare (2-5)", 
                    tickers_df['Display_Name'],
                    default=tickers_df['Display_Name'].head(2).tolist()
                )
                
                # Rest of the multi-company comparison code remains the same...
                # [keep all the existing multi-company comparison code]
    
    else:
        if not manual_ticker:
            if uploaded_file is not None:
                st.info("Please select a valid sheet with 'Symbol' and 'Exchange' columns")
            else:
                st.info("Please upload an XLSX file or enter a ticker manually to begin.")
