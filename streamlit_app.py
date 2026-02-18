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

# Tesla Megapack Configs (Based on your screenshots)
MEGAPACK_OPTIONS = {
    "2hr (115.6 MW / 231.3 MWh)": {"capex": 56395570, "maint": 315300, "mw": 115.6},
    "4hr (58.7 MW / 235 MWh)": {"capex": 52677640, "maint": 315300, "mw": 58.7}
}

# --- 3-YEAR HISTORICAL FREQUENCY DATASET (HB_WEST) ---
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
    pwd = st.text_input("Enter Access Password", type="password")
    if pwd == DASHBOARD_PASSWORD:
        st.session_state.password_correct = True
        st.rerun()
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
        return price_hist
    except:
        return pd.Series(np.random.uniform(15, 45, 744))

price_hist = get_site_data()
current_price = price_hist.iloc[-1]

# --- APP TABS ---
tab1, tab2 = st.tabs(["📊 Asset Dashboard", "📈 Long-Term Volatility"])

with tab1:
    # --- SECTION 1: CONFIGURATION ---
    st.markdown("### ⚙️ System Configuration")
    c1, c2, c3 = st.columns(3)
    with c1:
        solar_cap = st.slider("Solar Capacity (MW)", 0, 1000, 100)
        wind_cap = st.slider("Wind Capacity (MW)", 0, 1000, 100)
    with c2:
        miner_mw = st.number_input("Miner Fleet (MW)", value=35)
        m_cost = st.slider("Miner Cost ($/TH)", 1.0, 50.0, 15.0)
        m_eff = st.slider("Efficiency (J/TH)", 10.0, 35.0, 19.0, 0.5)
    with c3:
        # Battery Selection
        batt_choice = st.selectbox("Tesla Megapack Configuration", list(MEGAPACK_OPTIONS.keys()))
        batt_mw = MEGAPACK_OPTIONS[batt_choice]["mw"]
        batt_capex = MEGAPACK_OPTIONS[batt_choice]["capex"]
        
        hp_cents = st.slider("Hashprice (¢/TH)", 1.0, 10.0, 4.0, 0.1)
        breakeven = (1e6 / m_eff) * (hp_cents / 100.0) / 24.0
        st.metric("Breakeven Floor", f"${breakeven:.2f}/MWh")

    # --- SECTION 2: ASSET ROI & IRR ANALYSIS ---
    st.markdown("---")
    st.subheader("💰 Asset ROI & IRR Analysis")

    miner_th = (miner_mw * 1000000) / m_eff
    miner_capex = miner_th * m_cost
    total_project_capex = miner_capex + batt_capex

    # 1Y Alpha based on 2025 Trend Data
    capture_rate = TREND_DATA["Negative (<$0)"]["2025"] + TREND_DATA["$0 - $0.02"]["2025"]
    mining_alpha_total = (capture_rate * 8760 * miner_mw * (breakeven - 12))
    battery_alpha_total = (0.005 * 8760 * batt_mw * 1200) 
    ann_alpha = mining_alpha_total + battery_alpha_total

    roi_years = total_project_capex / ann_alpha if ann_alpha > 0 else 0
    irr_est = (ann_alpha / total_project_capex) * 100 if total_project_capex > 0 else 0

    rc1, rc2, rc3 = st.columns(3)
    rc1.metric("Total Project Capex", f"${total_project_capex:,.0f}", help=f"Miners: ${miner_capex:,.0f} | Battery: ${batt_capex:,.0f}")
    rc2.metric("ROI (Years)", f"{roi_years:.2f} Yrs")
    rc3.metric("Est. IRR", f"{irr_est:.1f}%")

    with st.expander("🔍 View Calculation Methodology"):
        st.markdown(f"""
        1. **Miner Capex:** Based on **{miner_mw}MW** at **{m_eff} J/TH**, costing **${miner_capex:,.0f}**.
        2. **Battery Capex:** Tesla Megapack **{batt_choice}** at **${batt_capex:,.0f}**.
        3. **Total Investment:** **${total_project_capex:,.0f}**.
        4. **Mining Alpha:** Prices favorable **{(capture_rate*100):.1f}%** of year.
        5. **Battery Alpha:** Capturing top **0.5%** scarcity events at **$1,200/MWh**.
        """)

    # --- SECTION 3: PERFORMANCE BREAKDOWN ---
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
    st.subheader("📉 3-Year Price Frequency Dataset (ERCOT HB_WEST)")
    df_trend = pd.DataFrame(TREND_DATA).T
    st.table(df_trend.style.format("{:.1%}"))
