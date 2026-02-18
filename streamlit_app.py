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

# Tesla Megapack Configs (Converted to Per MW for the Calculator)
# 4hr Pack: $52,677,640 / 58.7 MW = ~$897,404/MW
BATT_COST_PER_MW = 897404.0 
BATT_MAINT_PER_MW = 5371.0 # $315,300 / 58.7 MW

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
        batt_mw = st.number_input("Battery Size (MW)", value=60)
        hp_cents = st.slider("Hashprice (¢/TH)", 1.0, 10.0, 4.0, 0.1)
        breakeven = (1e6 / m_eff) * (hp_cents / 100.0) / 24.0
        st.metric("Breakeven Floor", f"${breakeven:.2f}/MWh")

    # --- SECTION 2: HYBRID OPTIMIZATION ENGINE ---
    st.markdown("---")
    st.subheader("🎯 Hybrid Optimization Engine")
    
    # Mathematical "Sweet Spot" Logic
    total_gen = solar_cap + wind_cap
    ideal_m = int(total_gen * 0.20)
    ideal_b = int(total_gen * 0.30)
    
    # Revenue Calculation Logic
    capture_2025 = TREND_DATA["Negative (<$0)"]["2025"] + TREND_DATA["$0 - $0.02"]["2025"]
    
    def get_ann_val(m, b):
        m_val = (capture_2025 * 8760 * m * (breakeven - 12))
        b_val = (0.005 * 8760 * b * 1200) - (b * BATT_MAINT_PER_MW)
        return m_val + b_val

    curr_val = get_ann_val(miner_mw, batt_mw)
    ideal_val = get_ann_val(ideal_m, ideal_b)
    
    oc1, oc2 = st.columns(2)
    with oc1:
        st.write(f"**Ideal Sizing for {total_gen}MW Site:**")
        st.info(f"⛏️ {ideal_m}MW Miners | 🔋 {ideal_b}MW Battery")
        st.metric("Annual Optimization Delta", f"${(ideal_val - curr_val):,.0f}", 
                  delta=f"{((ideal_val-curr_val)/curr_val)*100:.1f}% Upside" if curr_val > 0 else "N/A")
    with oc2:
        fig_opt = go.Figure(data=[
            go.Bar(name='Current Setup', x=['Annual Alpha'], y=[curr_val], marker_color='#6c757d'),
            go.Bar(name='Optimized Setup', x=['Annual Alpha'], y=[ideal_val], marker_color='#28a745')
        ])
        fig_trend = fig_opt.update_layout(height=200, template="plotly_dark", margin=dict(l=0,r=0,t=0,b=0))
        st.plotly_chart(fig_opt, use_container_width=True)

    # --- SECTION 3: ASSET ROI & IRR ANALYSIS ---
    st.markdown("---")
    st.subheader("💰 Asset ROI & IRR Analysis")
    miner_capex = ((miner_mw * 1000000) / m_eff) * m_cost
    batt_capex = batt_mw * BATT_COST_PER_MW
    total_capex = miner_capex + batt_capex
    irr_est = (curr_val / total_capex) * 100 if total_capex > 0 else 0

    rc1, rc2, rc3 = st.columns(3)
    rc1.metric("Total Project Capex", f"${total_capex:,.0f}")
    rc2.metric("ROI (Years)", f"{(total_capex / curr_val if curr_val > 0 else 0):.2f} Yrs")
    rc3.metric("Est. IRR", f"{irr_est:.1f}%")

    # --- SECTION 4: PERFORMANCE BREAKDOWN ---
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
        m_y, b_y, g_y = calculate_trend_yield_full(2025, miner_mw, batt_mw, breakeven, solar_cap, wind_cap)
        display_stat_box_v2("Last 1 Year (Trend)", m_y, b_y, g_y)

# Helper for Tab 1 Trend Box
def calculate_trend_yield_full(year, m, b, be, s, w):
    stats = TREND_DATA["Negative (<$0)"]["2025"] + TREND_DATA["$0 - $0.02"]["2025"]
    ma = (stats * 8760 * m * (be - 12))
    ba = (0.005 * 8760 * b * 1200) - (b * BATT_MAINT_PER_MW)
    base = (s * 82500 + w * 124000)
    return ma, ba, base

with tab2:
    st.subheader("📉 3-Year Price Frequency Dataset (ERCOT HB_WEST)")
    df_trend = pd.DataFrame(TREND_DATA).T
    st.table(df_trend.style.format("{:.1%}"))
