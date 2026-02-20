import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import requests
import gridstatus
import os
import pickle
from datetime import datetime, timedelta

# --- 1. CORE SYSTEM CONFIGURATION ---
st.set_page_config(layout="wide", page_title="Hybrid OS | Grid Intelligence")

DASHBOARD_PASSWORD = "123"
BATT_COST_PER_MW = 897404.0 
CORP_TAX_RATE = 0.21 
CACHE_FILE = "ercot_price_cache.pkl"
CACHE_EXPIRY_HOURS = 1

# --- AUTHENTICATION PORTAL (Omitted for brevity - same as v13.4) ---
if "password_correct" not in st.session_state: st.session_state.password_correct = False
def check_password():
    if st.session_state.password_correct: return True
    # [Login logic remains as Version 13.4]
    return False
if not check_password(): st.stop()

# --- 3. PERSISTENT SIDEBAR CONTROLS ---
st.sidebar.markdown("# Hybrid OS")
st.sidebar.caption("v13.5 Deployment")
st.sidebar.write("---")

st.sidebar.markdown("### ⚡ Generation Mix")
solar_cap = st.sidebar.slider("Solar Capacity (MW)", 0, 1000, 100)
wind_cap = st.sidebar.slider("Wind Capacity (MW)", 0, 1000, 100)

st.sidebar.write("---")
st.sidebar.markdown("### ⛏️ Miner Metrics")
m_cost = st.sidebar.slider("Miner Price ($/TH)", 1.0, 50.0, 20.00)
m_eff = st.sidebar.slider("Efficiency (J/TH)", 10.0, 35.0, 15.0)
hp_cents = st.sidebar.slider("Hashprice (¢/TH)", 1.0, 10.0, 4.0)

st.sidebar.write("---")
st.sidebar.markdown("### 🏛️ Starting Hardware")
m_load_in = st.sidebar.number_input("Starting Miner Load (MW)", value=0)
b_mw_in = st.sidebar.number_input("Starting Battery Size (MW)", value=0)

# --- 4. DATA PROCESSING ---
@st.cache_data(ttl=3600)
def get_live_data():
    # [Fetching logic for 365 days of ERCOT HB_WEST data]
    return pd.Series(np.random.uniform(15, 45, 8760)) # Placeholder for actual series

price_hist = get_live_data()
breakeven = (1e6 / m_eff) * (hp_cents / 100.0) / 24.0

def calculate_period_live_metrics(price_series, breakeven_val, ideal_m, ideal_b, days):
    """Calculates actual realized alpha and avg price from live telemetry"""
    try:
        data_points = int(days * 288) # 5-min intervals
        period_data = price_series.iloc[-data_points:]
        
        avg_price = period_data.mean()
        
        # Realized Alpha Logic: Margin captured per 5-min interval
        mining_alpha = sum([max(0, breakeven_val - p) * ideal_m for p in period_data]) / 288.0
        battery_alpha = sum([max(0, p - breakeven_val) * ideal_b for p in period_data]) / 288.0
        
        return mining_alpha, battery_alpha, avg_price
    except:
        return 0, 0, 0

# --- 5. DASHBOARD INTERFACE ---
t_evolution, t_tax, t_volatility = st.tabs(["📊 Performance Evolution", "🏛️ Institutional Tax Strategy", "📈 Long-Term Volatility"])

with t_evolution:
    st.markdown(f"### ⚙️ Institutional Performance Summary")
    
    total_gen = solar_cap + wind_cap
    s_pct = solar_cap / total_gen if total_gen > 0 else 0.5
    w_pct = wind_cap / total_gen if total_gen > 0 else 0.5
    ideal_m, ideal_b = int(total_gen * ((s_pct * 0.10) + (w_pct * 0.25))), int(total_gen * ((s_pct * 0.50) + (w_pct * 0.25)))

    st.markdown("---")
    st.subheader("📅 Comparative Alpha Tracking")
    
    # Toggle for stakeholder comparison
    show_comparison = st.toggle("Compare Actual (Live) vs. Historic Strategy", value=True)
    
    h1, h2, h3 = st.columns(3)
    periods = [("24H", 1, 101116), ("7D", 7, 704735), ("30D", 30, 3009339)]
    
    dm, db = (ideal_m * 45.6 * 8760 * (breakeven - 12) / 8760 / 365), (ideal_b * 12 * 8760 * (breakeven + 30) / 8760 / 365)

    for i, (lbl, days, base_rev) in enumerate(periods):
        with [h1, h2, h3][i]:
            # Calculate Live Actuals
            ma_live, ba_live, avg_p = calculate_period_live_metrics(price_hist, breakeven, ideal_m, ideal_b, days)
            # Calculate Historic Strategy (using $12/$30 logic)
            ma_hist, ba_hist = dm * days, db * days
            
            st.markdown(f"#### {lbl} Performance")
            st.metric("Avg Grid Price", f"${avg_p:.2f}", delta=f"{avg_p - breakeven:.2f} vs Breakeven", delta_color="inverse")
            
            if show_comparison:
                st.markdown("**Actual Realized Alpha (Live)**")
                st.markdown(f"<h3 style='color:#28a745; margin-bottom:0;'>${(ma_live + ba_live):,.0f}</h3>", unsafe_allow_html=True)
                st.caption(f"⛏️ ${ma_live:,.0f} | 🔋 ${ba_live:,.0f}")
                
                st.markdown("**Predicted Strategy (Historic)**")
                st.markdown(f"<h3 style='color:#808495; margin-bottom:0;'>${(ma_hist + ba_hist):,.0f}</h3>", unsafe_allow_html=True)
                st.caption(f"⛏️ ${ma_hist:,.0f} | 🔋 ${ba_hist:,.0f}")
                
                delta = (ma_live + ba_live) - (ma_hist + ba_hist)
                st.write(f"**Strategy Variance:** :{'green' if delta > 0 else 'red'}[${abs(delta):,.0f} {'Outperformance' if delta > 0 else 'Underperformance'}]")
            else:
                st.markdown("**Total Potential Alpha**")
                st.markdown(f"<h2 style='color:#28a745;'>${(ma_live + ba_live):,.0f}</h2>", unsafe_allow_html=True)
            st.write("---")

# [Rest of logic for Tax Strategy and Volatility follows...]
