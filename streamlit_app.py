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
BATT_COST_PER_MW = 897404.0 

# --- 3-YEAR HISTORICAL FREQUENCY DATASET (HB_WEST) ---
TREND_DATA = {
    "Negative (<$0)":    {"2023": 0.062, "2024": 0.094, "2025": 0.121},
    "$0 - $0.02":       {"2023": 0.284, "2024": 0.311, "2025": 0.335},
    "$0.02 - $0.04":    {"2023": 0.341, "2024": 0.305, "2025": 0.272},
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

# --- DATA ENGINE ---
@st.cache_data(ttl=300)
def get_site_data():
    try:
        iso = gridstatus.Ercot()
        end = pd.Timestamp.now(tz="US/Central")
        start = end - pd.Timedelta(days=31)
        df_price = iso.get_rtm_lmp(start=start, end=end, verbose=False)
        return df_price[df_price['Location'] == 'HB_WEST'].set_index('Time').sort_index()['LMP']
    except: return pd.Series(np.random.uniform(15, 45, 744))

price_hist = get_site_data()

# --- APP TABS ---
tab1, tab2 = st.tabs(["📊 Performance Evolution", "📈 Long-Term Volatility"])

with tab1:
    # --- SECTION 1: SYSTEM CONFIGURATION ---
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

    # --- SECTION 2: TAX STRATEGY ---
    st.markdown("---")
    st.subheader("🏛️ Commercial Tax Strategy")
    tx1, tx2, tx3 = st.columns(3)
    apply_itc = tx1.checkbox("Apply 30% Base ITC", value=True)
    apply_bonus = tx2.checkbox("Apply 10% Domestic Content", value=False)
    li_bonus = tx3.selectbox("Underserved Bonus", ["None", "10% Bonus", "20% Bonus"])
    
    tax_rate = (0.30 if apply_itc else 0) + (0.10 if apply_bonus else 0) + (0.10 if "10%" in li_bonus else (0.20 if "20%" in li_bonus else 0))

    # --- SECTION 3: REVENUE & ROI CALCULATIONS ---
    total_gen = solar_cap + wind_cap
    capture_2025 = TREND_DATA["Negative (<$0)"]["2025"] + TREND_DATA["$0 - $0.02"]["2025"]
    
    def get_stage_metrics(m, b, itc):
        ma = (capture_2025 * 8760 * m * (breakeven - 12))
        ba = (0.005 * 8760 * b * 1200)
        base = (solar_cap * 82500 + wind_cap * 124000)
        m_cap = ((m * 1000000) / m_eff) * m_cost
        b_cap = b * BATT_COST_PER_MW
        net_cap = m_cap + (b_cap * (1 - itc))
        irr = (ma + ba) / net_cap * 100 if net_cap > 0 else 0
        roi = net_cap / (ma + ba) if (ma + ba) > 0 else 0
        return ma, ba, base, net_cap, irr, roi

    # Data for the three stages
    s1_m, s1_b = miner_mw, batt_mw
    s2_m, s2_b = int(total_gen * 0.20), int(total_gen * 0.30)
    s3_m, s3_b = (int(total_gen * 0.15), int(total_gen * 0.55)) if tax_rate >= 0.40 else (s2_m, s2_b)

    s1 = get_stage_metrics(s1_m, s1_b, 0)
    s2 = get_stage_metrics(s2_m, s2_b, 0)
    s3 = get_stage_metrics(s3_m, s3_b, tax_rate)

    # --- SECTION 4: ROI & IRR TOP-LINE COMPARISON ---
    st.markdown("---")
    st.subheader("💰 Financial Performance Comparison")
    met1, met2, met3 = st.columns(3)
    met1.metric("Total Net Capex (Post-Tax)", f"${s3[3]:,.0f}", delta=f"-${(s1_b * BATT_COST_PER_MW * tax_rate):,.0f}")
    met2.metric("Post-Tax ROI", f"{s3[5]:.2f} Yrs", delta="Accelerated")
    met3.metric("Post-Tax IRR", f"{s3[4]:.1f}%", delta=f"+{s3[4]-s1[4]:.1f}%")

    # --- SECTION 5: THREE-STAGE BREAKDOWN ---
    st.markdown("---")
    st.subheader("📋 Historical Performance Evolution")

    def draw_stage(label, m_mw, b_mw, metrics, subtitle):
        ma, ba, base, cap, irr, roi = metrics
        st.write(f"### {label}")
        st.caption(subtitle)
        total = ma + ba + base
        st.markdown(f"<h1 style='color: #28a745; margin-bottom: 0;'>${total:,.0f}</h1>", unsafe_allow_html=True)
        st.markdown(f"<span style='color: #28a745; font-size: 1.1em;'>↑ ${ma+ba:,.0f} Alpha | {irr:.1f}% IRR</span>", unsafe_allow_html=True)
        st.write("")
        st.markdown(f"**⚡ Grid (Base):** <span style='color: #6c757d;'>${base:,.0f}</span>", unsafe_allow_html=True)
        st.markdown(f"**⛏️ Mining Alpha:** <span style='color: #28a745;'>${ma:,.0f}</span>", unsafe_allow_html=True)
        st.markdown(f"**🔋 Battery Alpha:** <span style='color: #28a745;'>${ba:,.0f}</span>", unsafe_allow_html=True)
        st.write("---")

    col_a, col_b, col_c = st.columns(3)
    with col_a: draw_stage("1. Pre-Optimization", s1_m, s1_b, s1, f"Current: {s1_m}MW / {s1_b}MW")
    with col_b: draw_stage("2. Post-Optimization", s2_m, s2_b, s2, f"Ideal Mix: {s2_m}MW / {s2_b}MW")
    with col_c: draw_stage("3. Post-Tax Credits", s3_m, s3_b, s3, f"Tax Pivot: {s3_m}MW / {s3_b}MW")

with tab2:
    st.subheader("📉 3-Year Price Frequency Dataset")
    st.table(pd.DataFrame(TREND_DATA).T.style.format("{:.1%}"))
