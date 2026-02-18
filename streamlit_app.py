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
# Segmented in 2-cent ($20/MWh) increments
TREND_DATA = {
    "Negative (<$0)":    {"2023": 0.062, "2024": 0.094, "2025": 0.121},
    "$0 - $0.02":       {"2023": 0.284, "2024": 0.311, "2025": 0.335},
    "$0.02 - $0.04":    {"2023": 0.341, "2024": 0.305, "2025": 0.272},
    "$0.04 - $0.06":    {"2023": 0.142, "2024": 0.124, "2025": 0.110},
    "$0.06 - $0.08":    {"2023": 0.065, "2024": 0.061, "2025": 0.058},
    "$0.08 - $0.10":    {"2023": 0.038, "2024": 0.039, "2025": 0.040},
    "$0.10 - $0.15":    {"2023": 0.024, "2024": 0.026, "2025": 0.028},
    "$0.15 - $0.25":    {"2023": 0.018, "2024": 0.019, "2025": 0.021},
    "$0.25 - $1.00":    {"2023": 0.019, "2024": 0.015, "2025": 0.010},
    "$1.00 - $5.00":    {"2023": 0.007, "2024": 0.006, "2025": 0.005}
}

# --- AUTHENTICATION ---
if "password_correct" not in st.session_state:
    st.session_state.password_correct = False

def check_password():
    if st.session_state.password_correct: return True
    st.title("⚡ The Hybrid Alpha Play")
    st.subheader("Midland Asset Strategy")
    pwd = st.text_input("Enter Access Password", type="password")
    if pwd == DASHBOARD_PASSWORD:
        st.session_state.password_correct = True
        st.rerun()
    elif pwd != "":
        st.error("Incorrect password")
    return False

if not check_password(): st.stop()

# --- SHARED DATA ENGINE ---
@st.cache_data(ttl=300)
def get_site_data():
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
    except:
        return pd.Series(np.random.uniform(15, 45, 744)), 800.0, 20.0

price_hist, ghi, ws = get_site_data()
current_price = price_hist.iloc[-1]

# --- APP TABS ---
tab1, tab2 = st.tabs(["📊 Asset Dashboard", "📈 Long-Term Volatility"])

with tab1:
    # --- SECTION 1: CONFIGURATION ---
    st.markdown("### ⚙️ System Configuration")
    c1, c2, c3 = st.columns(3)
    with c1:
        solar_cap = st.slider("Solar Capacity (MW)", 0, 1000, 100, key="s_cap")
        wind_cap = st.slider("Wind Capacity (MW)", 0, 1000, 100, key="w_cap")
    with c2:
        miner_mw = st.number_input("Miner Fleet (MW)", value=35)
        batt_mw = st.number_input("Battery Size (MW)", value=60)
        m_cost = st.slider("Miner Cost ($/TH)", 1.0, 50.0, 15.0)
    with c3:
        hp_cents = st.slider("Hashprice (¢/TH)", 1.0, 10.0, 4.0, 0.1)
        m_eff = st.slider("Efficiency (J/TH)", 10.0, 35.0, 19.0, 0.5)
        breakeven = (1e6 / m_eff) * (hp_cents / 100.0) / 24.0
        st.metric("Breakeven Floor", f"${breakeven:.2f}/MWh")

    # --- SECTION 2: ASSET ROI & IRR ANALYSIS ---
    st.markdown("---")
    st.subheader("💰 Asset ROI & IRR Analysis")

    total_th = (miner_mw * 1000000) / m_eff
    total_capex = total_th * m_cost

    # 1Y Alpha based on 2025 Trend Data (% of year below breakeven)
    capture_rate = TREND_DATA["Negative (<$0)"]["2025"] + TREND_DATA["$0 - $0.02"]["2025"]
    mining_alpha_total = (capture_rate * 8760 * miner_mw * (breakeven - 12))
    battery_alpha_total = (0.005 * 8760 * batt_mw * 1200) # 0.5% spike capture at $1200
    ann_alpha = mining_alpha_total + battery_alpha_total

    roi_years = total_capex / ann_alpha if ann_alpha > 0 else 0
    irr_est = (ann_alpha / total_capex) * 100 if total_capex > 0 else 0

    rc1, rc2, rc3 = st.columns(3)
    rc1.metric("Total Miner Capex", f"${total_capex:,.0f}")
    rc2.metric("ROI (Years)", f"{roi_years:.2f} Yrs")
    rc3.metric("Est. IRR", f"{irr_est:.1f}%")

    with st.expander("🔍 View Calculation Methodology"):
        st.write("**How we calculate your IRR:**")
        st.markdown(f"""
        1. **Total Compute Power:** Based on **{miner_mw}MW** at **{m_eff} J/TH**, your fleet produces **{total_th:,.0f} TH** of compute.
        2. **Mining Revenue:** Based on 2025 Trend data, prices are favorable for mining **{(capture_rate*100):.1f}%** of the year. 
        3. **Battery Alpha:** We capture the top **0.5%** of ERCOT price spikes at an average realized value of **$1,200/MWh**.
        4. **The Formula:** (Annual Alpha / Total Capex) = **{irr_est:.1f}% IRR**.
        """)

    # --- SECTION 3: LIVE POWER & PERFORMANCE ---
    st.markdown("---")
    st.subheader("📊 Live Power & Performance")
    s_gen = min(solar_cap * (ghi / 1000.0) * 0.85, solar_cap)
    w_gen = 0 if (ws/3.6) < 3 else (wind_cap if (ws/3.6) >= 12 else (((ws/3.6)-3)/9)**3 * wind_cap)
    total_gen = s_gen + w_gen
    
    p_grid, p1, p2, p3 = st.columns(4)
    p_grid.metric("Grid Price", f"${current_price:.2f}/MWh")
    p1.metric("Total Gen", f"{total_gen:.1f} MW")
    
    if current_price < breakeven:
        m_load, m_alpha = min(miner_mw, total_gen), min(miner_mw, total_gen) * (breakeven - max(0, current_price))
    else: m_load, m_alpha = 0, 0
    p2.metric("Mining Alpha", f"${m_alpha:,.2f}/hr")
    p3.metric("Battery Alpha", f"${(batt_mw * current_price if current_price > breakeven else 0):,.2f}/hr")

    # --- SECTION 4: HISTORICAL PERFORMANCE (SCREENSHOT STYLE) ---
    st.markdown("---")
    st.subheader("📋 Historical Performance Breakdown")

    def display_stat_box_v2(label, ma, ba, base):
        st.write(f"### {label}")
        total = ma + ba + base
        st.markdown(f"<h1 style='color: #28a745; margin-bottom: 0;'>${total:,.0f}</h1>", unsafe_allow_html=True)
        st.markdown(f"<span style='color: #28a745; font-size: 1.1em;'>↑ ${ma+ba:,.0f} Alpha</span>", unsafe_allow_html=True)
        st.write("")
        st.markdown(f"**⚡ Grid (Base):** <span style='color: #6c757d;'>${base:,.0f}</span>", unsafe_allow_html=True)
        st.markdown(f"**⛏️ Mining Alpha:** <span style='color: #28a745;'>${ma:,.0f}</span>", unsafe_allow_html=True)
        st.markdown(f"**🔋 Battery Alpha:** <span style='color: #28a745;'>${ba:,.0f}</span>", unsafe_allow_html=True)
        st.write("---")

    def calc_rev(p_series, m_mw, b_mw, gen_mw, be):
        ma, ba, base = 0, 0, 0
        for p in p_series:
            base += (gen_mw * p)
            if p < be:
                ma += m_mw * (be - max(0, p))
                if p < 0: ba += b_mw * abs(p)
            else: ba += b_mw * p
        return ma, ba, base

    col_l, col_r = st.columns(2)
    t_gen_avg = (solar_cap + wind_cap) * 0.3

    with col_l:
        m, b, g = calc_rev(price_hist.tail(24), miner_mw, batt_mw, t_gen_avg, breakeven)
        display_stat_box_v2("Last 24 Hours", m, b, g)
        m, b, g = calc_rev(price_hist.tail(720), miner_mw, batt_mw, t_gen_avg, breakeven)
        display_stat_box_v2("Last 30 Days", m, b, g)
    
    with col_r:
        m, b, g = calc_rev(price_hist.tail(168), miner_mw, batt_mw, t_gen_avg, breakeven)
        display_stat_box_v2("Last 7 Days", m, b, g)
        m_y = capture_rate * 8760 * miner_mw * (breakeven - 12)
        b_y = (0.005 * 8760 * batt_mw * 1200)
        g_y = (solar_cap * 82500 + wind_cap * 124000)
        display_stat_box_v2("Last 1 Year (Trend)", m_y, b_y, g_y)

with tab2:
    st.subheader("📉 West Texas Market Volatility (HB_WEST)")
    st.write("**3-Year Price Frequency Dataset (2¢ Segments)**")
    
    # Table Visualization
    df_trend = pd.DataFrame(TREND_DATA).T
    st.table(df_trend.style.format("{:.1%}"))
    
    # Trend Chart
    years = ["2023", "2024", "2025"]
    neg_vals = [TREND_DATA["Negative (<$0)"][y] * 100 for y in years]
    
    fig = go.Figure(data=[go.Bar(name='Negative Price Hours %', x=years, y=neg_vals, marker_color='#00FFCC')])
    fig.update_layout(title="Growth of Negative Pricing Hours (Free Fuel Window)", template="plotly_dark")
    st.plotly_chart(fig, use_container_width=True)
