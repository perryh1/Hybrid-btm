import streamlit as st

# Function to calculate the 24-hour live alpha
def calculate_24h_live_alpha(data):
    # Your logic for calculating 24H live alpha goes here.
    # This is a placeholder for demonstration.
    return (data['current_price'] - data['price_24h_ago']) / data['price_24h_ago'] * 100

# Streamlit application
st.title("Hybrid BTM Alpha Calculator")

# Toggle for live 24H data
live_data_toggle = st.sidebar.checkbox("Live 24H Data")

# Sample data structure for testing
sample_data = {
    'current_price': 100,
    'price_24h_ago': 90
}

if live_data_toggle:
    alpha = calculate_24h_live_alpha(sample_data)
    st.write(f"24H Live Alpha: {alpha:.2f}%")
else:
    st.write("Live data is toggled off. Showing historical data instead.")

# Display percentage increase and explanatory text
st.write("This application calculates the 24-hour live alpha based on the price changes.")
st.write("The percentage increase is calculated based on the current price versus the price 24 hours ago.")

# Additional historical calculations explanations
st.write("Historical calculations provide insights into price trends and can be useful for understanding market movements.")