import re

# 1. Try standard columns first
close_col = None
if 'Close' in main_data.columns:
    close_col = 'Close'
elif 'Adj Close' in main_data.columns:
    close_col = 'Adj Close'
else:
    # 2. Try columns like "Close_SPY", "Adj Close_SPY", etc.
    close_like = [c for c in main_data.columns if re.match(r'(Adj\s)?Close', c)]
    if len(close_like) == 1:
        close_col = close_like[0]
        st.warning(f"Using '{close_col}' as the price column.")
    elif len(close_like) > 1:
        # Let user choose if multiple found
        close_col = st.sidebar.selectbox("Select price column", close_like)
        st.warning(f"Using '{close_col}' as the price column.")
    else:
        st.error(
            "The data does not contain a usable price column (e.g., 'Close', 'Adj Close', 'Close_SPY'). "
            "Please check the ticker or data source."
        )
        st.write("Raw data columns:", list(main_data.columns))
        st.write(main_data.head())
        st.stop()
