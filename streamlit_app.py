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

# --- 5-YEAR HISTORICAL FREQUENCY DATASET (RESTORED 2¢ INTERVALS) ---
TREND_DATA_WEST = {
    "Negative (<$0)":    {"2021": 0.021, "2022": 0.045, "2023": 0.062, "2024": 0.094, "2025": 0.121},
    "$0 - $0.02":       {"2021": 0.182, "2022": 0.241, "2023": 0.284, "2024": 0.311, "2025": 0.335},
    "$0.02 - $0.04":    {"2021": 0.456, "2022": 0.398, "2023": 0.341, "2024": 0.305, "2025": 0.272},
    "$0.04 - $0.06":    {"2021": 0.158, "2022": 0.165, "2023": 0.142, "2024": 0.124, "2025": 0.110},
    "$0.06 - $0.08":    {"2021": 0.082, "2022": 0.071, "2023": 0.065, "2024": 0.061, "2025": 0.058},
    "$0.08 - $0.10":    {"2021": 0.041, "2022": 0.038, "2023": 0.038, "2024": 0.039, "2025": 0.040},
    "$0.10 - $0.15":    {"2021": 0.022, "2022": 0.021, "2023": 0.024, "2024": 0.026, "2025": 0.028},
    "$0.15 - $0.25":    {"2021": 0.019, "2022": 0.010, "2023": 0.018, "2024": 0.019, "2025": 0.021},
    "$0.25 - $1.00":    {"2021": 0.011, "2022": 0.009, "2023": 0.019, "2024": 0.015, "2025": 0.010},
    "$1.00 - $5.00":    {"2021": 0.008, "2022": 0.002, "2023": 0.007, "2024": 0.006, "2025": 0.005}
}

# --- AUTHENTICATION ---
if "password_correct" not in st.session_state: st.session_state.password_correct = False
def check_password():
    if st.session_state.password_correct: return True
    st.title("⚡ Midland Hybrid Alpha Play")
    pwd = st.text_input("Enter Access Password", type="password")
    if pwd == DASHBOARD_PASSWORD:
        st.session_state.password_correct = True
        st.rerun()
    return False

if not check_password(): st.stop()

@st.cache_data(ttl=300)
def get_site_data():
    try:
        iso = gridstatus.Ercot()
        df = iso.get_rtm_lmp(start=pd.Timestamp.now(tz="US/Central")-pd.Timedelta(days=31), end=pd.Timestamp.now(tz="US/Central"), verbose=False)
        return df[df['Location'] == 'HB_WEST'].set_index('Time').sort_index()['LMP']
    except: return pd.Series(np.random.uniform(15, 45, 744))

price_hist = get_site_data()

# --- APP TABS ---
tab1, tab2 = st.tabs(["📊 Performance Evolution", "📈 Long-Term Volatility"])

with tab1:
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

    # --- TAX STRATEGY ---
    st.markdown("---")
    st.subheader("🏛️ Commercial Tax Strategy")
    tx1, tx2, tx3 = st.columns(3)
    t_rate = (0.3 if tx1.checkbox("Apply 30% Base ITC", True) else 0) + (0.1 if tx2.checkbox("Apply 10% Domestic Content", False) else 0)
    li_choice = tx3.selectbox("Underserved Bonus", ["None", "10% Bonus", "20% Bonus"])
    t_rate += (0.1 if "10%" in li_choice else (0.2 if "20%" in li_choice else 0))

    # --- ELASTIC BLEND ENGINE ---
    total_gen = solar_cap + wind_cap
    if total_gen > 0:
        s_pct, w_pct = solar_cap / total_gen, wind_cap / total_gen
    else:
        s_pct, w_pct = 0.5, 0.5

    # Interpolated Targets
    ideal_m_mw = int(total_gen * ((s_pct * 0.10) + (w_pct * 0.25)))
    ideal_b_mw = int(total_gen * ((s_pct * 0.50) + (w_pct * 0.25)))

    # --- REVENUE ENGINE ---
    capture_2025 = TREND_DATA_WEST["Negative (<$0)"]["2025"] + TREND_DATA_WEST["$0 - $0.02"]["2025"]
    
    def get_stage_metrics(m, b, itc_r):
        ma_factor = 1.0 + (w_pct * 0.20)
        ba_factor = 1.0 + (s_pct * 0.25)
        ma = (capture_2025 * 8760 * m * (breakeven - 12)) * ma_factor
        ba = (0.005 * 8760 * b * 1200) * ba_factor
        base = (solar_cap * 82500 + wind_cap * 124000)
        m_th = (m * 1000000) / m_eff
        m_cap, b_cap = m_th * m_cost, b * BATT_COST_PER_MW
        net = m_cap + (b_cap * (1 - itc_r))
        irr = (ma + ba) / net * 100 if net > 0 else 0
        roi = net / (ma + ba) if (ma + ba) > 0 else 0
        return ma, ba, base, net, irr, roi, m_th, m_cap, b_cap

    s1_metrics = get_stage_metrics(miner_mw, batt_mw, 0)
    s2_metrics = get_stage_metrics(ideal_m_mw, ideal_b_mw, 0)
    s3_metrics = get_stage_metrics(miner_mw, batt_mw, t_rate)
    s4_metrics = get_stage_metrics(ideal_m_mw, ideal_b_mw, t_rate)

    # --- FINANCIAL COMPARISON ---
    st.markdown("---")
    st.subheader("💰 Post-Tax Financial Comparison")
    cl1, cl2 = st.columns(2)
    with cl1:
        st.write("#### 1. Current Setup (Post-Tax)")
        st.caption(f"{miner_mw}MW Miners | {batt_mw}MW Battery")
        st.metric("Post-Tax IRR", f"{s3_metrics[4]:.1f}%", delta=f"+{s3_metrics[4]-s1_metrics[4]:.1f}%")
    with cl2:
        st.write("#### 2. Optimized Setup (Post-Tax)")
        st.caption(f"{ideal_m_mw}MW Miners | {ideal_b_mw}MW Battery")
        st.metric("Post-Tax IRR", f"{s4_metrics[4]:.1f}%", delta=f"+{s4_metrics[4]-s3_metrics[4]:.1f}% over Current")

    # --- EVOLUTION CARDS ---
    st.markdown("---")
    st.subheader("📋 Historical Performance Evolution")
    def draw_c(lbl, met, m_v, b_v, sub):
        st.write(f"### {lbl}")
        st.caption(f"{sub} ({m_v}MW / {b_v}MW)")
        total = met[0] + met[1] + met[2]
        st.markdown(f"<h1 style='color: #28a745;'>${total:,.0f}</h1>", unsafe_allow_html=True)
        st.markdown(f"**↑ ${met[0]+met[1]:,.0f} Alpha | {met[4]:.1f}% IRR**")
        st.write(f"* ⚡ Grid: `${met[2]:,.0f}` | ⛏️ Mining: `${met[0]:,.0f}` | 🔋 Battery: `${met[1]:,.0f}`")
        st.write("---")

    c_a, c_b, c_c, c_d = st.columns(4)
    with c_a: draw_c("1. Pre-Opt", s1_metrics, miner_mw, batt_mw, "Current/No Tax")
    with c_b: draw_c("2. Opt (Pre-Tax)", s2_metrics, ideal_m_mw, ideal_b_mw, "Ideal/No Tax")
    with c_c: draw_c("3. Current (Post-Tax)", s3_metrics, miner_mw, batt_mw, "Current/Full Tax")
    with c_d: draw_c("4. Opt (Post-Tax)", s4_metrics, ideal_m_mw, ideal_b_mw, "Ideal/Full Tax")

with tab2:
    st.subheader("📈 5-Year Price Frequency (HB_WEST)")
    st.table(pd.DataFrame(TREND_DATA_WEST).T.style.format("{:.1%}"))
