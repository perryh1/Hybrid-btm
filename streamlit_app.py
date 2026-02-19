import streamlit as st
import requests

# Initialize the Streamlit application
st.title('Hybrid BTM Analysis')

# Function to fetch live ERCOT data

def calculate_24h_live_alpha():
    # Sample URL for fetching data (replace it with actual endpoint)
    url = 'https://your_ercot_api_endpoint'
    response = requests.get(url)
    data = response.json()  # Assuming the data is in JSON format
    # Process the data to calculate alpha (hypothetical processing)
    live_alpha = data['live_alpha']
    return live_alpha

# Toggle for historical estimate vs live data
option = st.selectbox('Select data type:', ['Historical Estimate', 'Live 24-hour Actual'])

if option == 'Historical Estimate':
    st.subheader('Historical Alpha Potential')
    # (Add your existing code for historical calculations)
    historical_alpha = calculate_historical_alpha() 
    st.write(f"Historical Alpha: {historical_alpha}")

elif option == 'Live 24-hour Actual':
    st.subheader('Live Alpha Potential')
    live_alpha = calculate_24h_live_alpha()
    st.write(f"Live Alpha: {live_alpha}")

# Explanatory text
st.write("### Understanding Historical Calculations\n\nHistorical calculations are based on past market data and could differ from live data due to various factors like market volatility and supply-demand dynamics.")

# Example of displaying percentage increase for mining and battery alpha
mining_alpha = 10  # Replace with actual mining alpha values
battery_alpha = 20  # Replace with actual battery alpha values
percentage_increase_mining = ((live_alpha - mining_alpha) / mining_alpha) * 100
percentage_increase_battery = ((live_alpha - battery_alpha) / battery_alpha) * 100
st.write(f"Mining Alpha Percentage Increase: {percentage_increase_mining:.2f}%")
st.write(f"Battery Alpha Percentage Increase: {percentage_increase_battery:.2f}%")
