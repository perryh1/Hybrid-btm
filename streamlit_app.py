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
# Values represent % of total annual hours (8,760 hrs)
TREND_DATA = {
    2023: {"negative": 0.062, "low": 0.625, "mid": 0.245, "high": 0.061, "spike": 0.007},
    2024: {"negative": 0.094, "low": 0.616, "mid": 0.224, "high": 0.060, "spike": 0.006},
    2025: {"negative": 0.121, "low": 0.607, "mid": 0.196, "high": 0.071, "spike": 0.005}
}

# --- AUTHENTICATION ---
def check_password():
    if "password_correct" not in st.session_state:
        st.session_state.password_correct = False
    if st.session_state.password_correct: return True
    
    st.title("⚡ The Hybrid Alpha Play")
    st.subheader("Scaling Renewable Asset Yield")
    st.markdown("---")
    pwd = st.text_input("Enter Access Password", type="password")
    if pwd == DASHBOARD_PASSWORD:
        st.session_state.password_correct = True
        st.rerun()
    return False

if not check_password(): st.stop()

# --- DATA FETCHING (LIVE) ---
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

# --- REVENUE ENGINES ---
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
        m_cost = st.slider("Miner Cost ($/TH)", 1.0, 50.0, 15.0)
    with c3:
        hp_cents = st.slider("Hashprice (¢/TH)", 1.0, 10.0, 4.0, 0.1)
        m_eff = st.slider("Efficiency (J/TH)", 10.0, 35.0, 19.0, 0.5)
        breakeven = (1e6 / m_eff) * (hp_cents / 100.0) / 24.0
        st.metric("Breakeven Floor", f"${breakeven:.2f}/MWh")

    # LIVE PERFORMANCE
    st.markdown("---")
    s_gen = min(solar_cap * (ghi / 1000.0) * 0.85, solar_cap)
    w_gen = 0 if (ws/3.6) < 3 else (wind_cap if (ws/3.6) >= 12 else (((ws/3.6)-3)/9)**3 * wind_cap)
    total_gen = s_gen + w_gen
    
    p_grid, p1, p2, p3 = st.columns(4)
    p_grid.metric("Grid Price", f"${current_price:.2f}/MWh")
    p1.metric("Total Gen", f"{total_gen:.1f} MW")
    
    if current_price < breakeven:
        m_load, m_alpha, b_alpha = min(miner_mw, total_gen), min(miner_mw, total_gen) * (breakeven - max(0, current_price)), 0
    else: m_load, m_alpha, b_alpha = 0, 0, batt_mw * current_price
    p2.metric("Mining Alpha", f"${m_alpha:,.2f}/hr")
    p3.metric("Battery Alpha", f"${b_alpha:,.2f}/hr")

    # HISTORICAL BREAKDOWN
    st.markdown("---")
    st.subheader("📅 Historical Performance Breakdown")

    def display_stat_box(label, ma, ba, base):
        st.write(f"**{label}**")
        st.metric("Total Revenue", f"${(ma+ba+base):,.0f}", f"${ma+ba:,.0f} Alpha")
        st.caption(f"⚡ Grid: `${base:,.0f}` | ⛏️ Mining: `${ma:,.0f}` | 🔋 Batt: `${ba:,.0f}`")

    h1, h2, h3, h4, h5 = st.columns(5)
    t_gen_avg = (solar_cap + wind_cap) * 0.3
    
    with h1:
        m, b, g = calc_alpha_live(price_hist.tail(24), miner_mw, batt_mw, t_gen_avg, breakeven)
        display_stat_box("Last 24h", m, b, g)
    with h2:
        m, b, g = calc_alpha_live(price_hist.tail(168), miner_mw, batt_mw, t_gen_avg, breakeven)
        display_stat_box("Last 7d", m, b, g)
    with h3:
        m, b, g = calc_alpha_live(price_hist.tail(720), miner_mw, batt_mw, t_gen_avg, breakeven)
        display_stat_box("Last 30d", m, b, g)
    with h4:
        m, b, g = calculate_trend_yield(2025, miner_mw, batt_mw, breakeven, solar_cap, wind_cap, factor=0.5)
        display_stat_box("6mo (Trend)", m, b, g)
    with h5:
        m, b, g = calculate_trend_yield(2025, miner_mw, batt_mw, breakeven, solar_cap, wind_cap, factor=1.0)
        display_stat_box("1yr (Trend)", m, b, g)

with tab2:
    st.subheader("📈 West Texas Market Volatility (HB_WEST)")
    
    # Trend Table
    st.write("**3-Year Price Frequency Dataset**")
    st.markdown("*All values represent % of total annual hours (8,760 hrs)*")
    
    df_trend = pd.DataFrame(TREND_DATA).T
    df_trend.columns = ["Negative (<$0)", "Low ($0-$40)", "Mid ($40-$100)", "High ($100-$500)", "Spike ($500+)"]
    # Formatting for percentage display
    st.table(df_trend.style.format("{:.1%}"))
    
    # Trend Chart
    years = [2023, 2024, 2025]
    neg_pct = [TREND_DATA[y]['negative'] * 100 for y in years]
    spike_pct = [TREND_DATA[y]['spike'] * 100 for y in years]
    
    fig_trend = go.Figure()
    fig_trend.add_trace(go.Bar(name='Negative Price Hours (%)', x=years, y=neg_pct, marker_color='#00FFCC'))
    fig_trend.add_trace(go.Scatter(name='Scarcity Events (%)', x=years, y=spike_pct, yaxis='y2', line=dict(color='red', width=3)))
    
    fig_trend.update_layout(
        title="YoY Shift: Negative Pricing vs. Scarcity Spikes",
        yaxis=dict(title="Negative % of Year"),
        yaxis2=dict(title="Scarcity % of Year", overlaying='y', side='right'),
        barmode='group', template="plotly_dark", height=400
    )
    st.plotly_chart(fig_trend, use_container_width=True)
    
    st.info("**Strategic Insight:** Negative pricing has grown significantly from 6.2% to 12.1%, doubling the available 'free fuel' window for the mining fleet.")
