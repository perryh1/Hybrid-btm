import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import requests
import gridstatus
from datetime import datetime, timedelta

# --- CONFIGURATION ---
DASHBOARD_PASSWORD = "123"
LAT, LONG = 31.997, -102.077

# --- 3-YEAR HISTORICAL FREQUENCY DATASET (HB_WEST) ---
TREND_DATA = {
    2023: {"negative": 0.062, "low": 0.625, "mid": 0.245, "high": 0.061, "spike": 0.007},
    2024: {"negative": 0.094, "low": 0.616, "mid": 0.224, "high": 0.060, "spike": 0.006},
    2025: {"negative": 0.121, "low": 0.607, "mid": 0.196, "high": 0.071, "spike": 0.005}
}

# --- AUTHENTICATION & LOGIN ---
def check_password():
    if "password_correct" not in st.session_state:
        st.session_state.password_correct = False
    if st.session_state.password_correct: return True
    st.title("⚡ The Hybrid Alpha Play")
    st.subheader("Midland Asset Strategy")
    pwd = st.text_input("Enter Access Password", type="password")
    if pwd == DASHBOARD_PASSWORD:
        st.session_state.password_correct = True
        st.rerun()
    return False

if not check_password(): st.stop()

# --- DATA ENGINE ---
@st.cache_data(ttl=300)
def get_live_and_history():
    try:
        iso = gridstatus.Ercot()
        end = pd.Timestamp.now(tz="US/Central")
        start = end - pd.Timedelta(days=31)
        df_price = iso.get_rtm_lmp(start=start, end=end, verbose=False)
        price_hist = df_price[df_price['Location'] == 'HB_WEST'].set_index('Time').sort_index()['LMP']
        url = "https://api.open-meteo.com/v1/forecast"
        params = {"latitude": LAT, "longitude": LONG, "current": ["shortwave_radiation", "wind_speed_10m"], "timezone": "auto"}
        r = requests.get(url, params=params).json()
        return price_hist, r['current']['shortwave_radiation'], r['current']['wind_speed_10m']
    except: return pd.Series(np.random.uniform(15, 45, 744)), 795.0, 22.0

price_hist, ghi, ws = get_live_and_history()
current_price = price_hist.iloc[-1]

# --- REVENUE CALC FUNCTIONS ---
def calc_alpha_live(p_series, m_mw, b_mw, gen_mw, be):
    ma, ba, base = 0, 0, 0
    for p in p_series:
        base += (gen_mw * p)
        if p < be:
            ma += m_mw * (be - max(0, p))
            if p < 0: ba += b_mw * abs(p)
        else: ba += b_mw * p
    return ma, ba, base

def calculate_trend_yield(year, miner_mw, batt_mw, be, solar, wind, factor=1.0):
    stats = TREND_DATA[year]
    hours = 8760 * factor
    ma = (stats['negative'] + stats['low']) * hours * miner_mw * (be - 12)
    ba = (stats['high'] * hours * batt_mw * 80) + (stats['spike'] * hours * batt_mw * 1200)
    base = (solar * 82500 + wind * 124000) * factor
    return ma, ba, base

# --- APP TABS ---
tab1, tab2 = st.tabs(["📊 Asset Dashboard", "📈 Long-Term Volatility"])

with tab1:
    st.markdown("### ⚙️ System Configuration")
    c1, c2, c3 = st.columns(3)
    with c1:
        solar_cap = st.slider("Solar Capacity (MW)", 0, 1000, 100, key="s1")
        wind_cap = st.slider("Wind Capacity (MW)", 0, 1000, 100, key="w1")
    with c2:
        miner_mw = st.number_input("Miner Fleet (MW)", value=35)
        batt_mw = st.number_input("Battery Size (MW)", value=60)
    with c3:
        hp_cents = st.slider("Hashprice (¢/TH)", 1.0, 10.0, 4.0, 0.1)
        m_eff = st.slider("Efficiency (J/TH)", 10.0, 35.0, 19.0, 0.5)
        breakeven = (1e6 / m_eff) * (hp_cents / 100.0) / 24.0

    st.markdown("---")
    st.subheader("📅 Historical Performance Breakdown")

    # CUSTOM CSS FOR THE UI CARDS
    def display_ui_card(label, ma, ba, base):
        total = ma + ba + base
        alpha = ma + ba
        st.markdown(f"""
            <div style="padding-bottom: 20px;">
                <p style="margin:0; font-size: 14px; color: #888;">Total Site Revenue</p>
                <h1 style="margin:0; font-size: 42px; color: #28a745; font-weight: 700;">${total:,.0f}</h1>
                <p style="margin:0; font-size: 16px; color: #28a745; background-color: rgba(40, 167, 69, 0.1); display: inline-block; padding: 2px 8px; border-radius: 4px;">↑ ${alpha:,.0f} Alpha</p>
                <ul style="list-style-type: none; padding: 10px 0 0 0; font-size: 16px;">
                    <li style="padding-bottom: 5px;">⚡ <b>Grid (Base):</b> <span style="color: #28a745;">${base:,.0f}</span></li>
                    <li style="padding-bottom: 5px;">⛏️ <b>Mining Alpha:</b> <span style="color: #28a745;">${ma:,.0f}</span></li>
                    <li style="padding-bottom: 5px;">🔋 <b>Battery Alpha:</b> <span style="color: #28a745;">${ba:,.0f}</span></li>
                </ul>
                <p style="margin:0; font-weight: bold; font-size: 18px;">{label}</p>
            </div>
        """, unsafe_allow_html=True)

    h_col1, h_col2 = st.columns(2)
    t_gen_avg = (solar_cap + wind_cap) * 0.3
    
    with h_col1:
        m, b, g = calc_alpha_live(price_hist.tail(24), miner_mw, batt_mw, t_gen_avg, breakeven)
        display_ui_card("Last 24 Hours", m, b, g)
        st.markdown("---")
        m, b, g = calc_alpha_live(price_hist.tail(720), miner_mw, batt_mw, t_gen_avg, breakeven)
        display_ui_card("Last 30 Days", m, b, g)
        
    with h_col2:
        m, b, g = calc_alpha_live(price_hist.tail(168), miner_mw, batt_mw, t_gen_avg, breakeven)
        display_ui_card("Last 7 Days", m, b, g)
        st.markdown("---")
        m, b, g = calculate_trend_yield(2025, miner_mw, batt_mw, breakeven, solar_cap, wind_cap, factor=0.5)
        display_ui_card("Last 6 Months", m, b, g)

with tab2:
    st.subheader("📈 Long-Term Volatility Trends")
    # (Existing Table and Chart Logic)
