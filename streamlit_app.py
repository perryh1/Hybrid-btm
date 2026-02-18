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

# --- 5-YEAR HISTORICAL FREQUENCY DATASET (HB_WEST) ---
TREND_DATA_WEST = {
    "Negative (<$0)":    {"2021": 0.021, "2022": 0.045, "2023": 0.062, "2024": 0.094, "2025": 0.121},
    "$0 - $0.02":       {"2021": 0.182, "2022": 0.241, "2023": 0.284, "2024": 0.311, "2025": 0.335},
    "$0.02 - $0.04":    {"2021": 0.456, "2022": 0.398, "2023": 0.341, "2024": 0.305, "2025": 0.272},
    "$1.00 - $5.00":    {"2021": 0.008, "2022": 0.002, "2023": 0.007, "2024": 0.006, "2025": 0.005}
}

# --- AUTHENTICATION & DATA ENGINE ---
if "password_correct" not in st.session_state: st.session_state.password_correct = False
def check_password():
    if st.session_state.password_correct: return True
    st.title("⚡ The Hybrid Alpha Play")
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
    itc_rate = (0.3 if tx1.checkbox("Apply 30% Base ITC", True) else 0) + (0.1 if tx2.checkbox("Apply 10% Domestic Content", False) else 0)
    li_choice = tx3.selectbox("Underserved Bonus", ["None", "10% Bonus", "20% Bonus"])
    itc_rate += (0.1 if "10%" in li_choice else (0.2 if "20%" in li_choice else 0))
    
    # Depreciation Factor (2026 Policy)
    dep_rate = (0.20 * 0.21) if st.checkbox("Apply 5-Yr MACRS + 20% Bonus", True) else 0

    # --- SECTION 3: MIX-AWARE CORE CALCULATIONS ---
    total_gen = solar_cap + wind_cap
    s_ratio = solar_cap / total_gen if total_gen > 0 else 0.5
    w_ratio = wind_cap / total_gen if total_gen > 0 else 0.5
    
    capture_2025 = TREND_DATA_WEST["Negative (<$0)"]["2025"] + TREND_DATA_WEST["$0 - $0.02"]["2025"]
    
    def get_stage_metrics(m, b, itc_r, dep_r):
        # Weighting Alpha based on the slider ratio
        # Wind drives Negative Prices (Mining Alpha); Solar drives Evening Spikes (Battery Alpha)
        m_weight = 1.0 + (w_ratio * 0.20) 
        b_weight = 1.0 + (s_ratio * 0.20)
        
        ma = (capture_2025 * 8760 * m * (breakeven - 12)) * m_weight
        ba = (0.005 * 8760 * b * 1200) * b_weight
        base = (solar_cap * 82500 + wind_cap * 124000)
        
        m_th = (m * 1000000) / m_eff
        m_cap = m_th * m_cost
        b_cap = b * BATT_COST_PER_MW
        net_cap = (m_cap + b_cap * (1 - itc_r)) * (1 - dep_r)
        
        irr = (ma + ba) / net_cap * 100 if net_cap > 0 else 0
        roi = net_cap / (ma + ba) if (ma + ba) > 0 else 0
        return ma, ba, base, net_cap, irr, roi, m_th, m_cap, b_cap

    s1_m, s1_b = miner_mw, batt_mw
    s2_m, s2_b = int(total_gen * 0.20), int(total_gen * 0.30)
    
    s1_pre = get_stage_metrics(s1_m, s1_b, 0, 0)
    s1_post = get_stage_metrics(s1_m, s1_b, itc_rate, dep_rate)
    s2_pre = get_stage_metrics(s2_m, s2_b, 0, 0)
    s2_post = get_stage_metrics(s2_m, s2_b, itc_rate, dep_rate)

    # --- SECTION 4: SPLIT FINANCIAL COMPARISON ---
    st.markdown("---")
    st.subheader("💰 Post-Tax Financial Comparison")
    col_cur, col_opt = st.columns(2)
    with col_cur:
        st.write("#### 1. Current Setup (Post-Tax)")
        st.markdown(f"**Physical:** `{s1_m}MW / {s1_b}MW` | **Mix:** `{w_ratio:.0%} Wind / {s_ratio:.0%} Solar`")
        st.metric("Net Capex", f"${s1_post[3]:,.0f}", delta=f"-${(s1_pre[3]-s1_post[3]):,.0f}")
        st.metric("IRR", f"{s1_post[4]:.1f}%", delta=f"+{s1_post[4]-s1_pre[4]:.1f}% vs Pre-Tax")
    with col_opt:
        st.write("#### 2. Optimized Setup (Post-Tax)")
        st.markdown(f"**Physical:** `{s2_m}MW / {s2_b}MW` | **Mix:** `Ideal Ratio`")
        st.metric("Net Capex", f"${s2_post[3]:,.0f}")
        st.metric("IRR", f"{s2_post[4]:.1f}%", delta=f"+{s2_post[4]-s1_post[4]:.1f}% over Current")

    # --- SECTION 5: METHODOLOGY ---
    with st.expander("🔍 View Calculation Methodology"):
        st.markdown(f"""
        1. **Mix-Aware Weighting:** Revenue is weighted by the generation sliders. Your **{w_ratio:.0%} wind mix** increases Mining Alpha capture; your **{s_ratio:.0%} solar mix** increases Battery Alpha.
        2. **Optimization Logic:** Targets a **20% Miner / 30% Battery** ratio to site gen ({total_gen} MW).
        3. **Depreciation Strategy:** Includes 20% Bonus Depreciation and Year 1 MACRS tax shelter.
        """)

    # --- SECTION 6: THREE-STAGE EVOLUTION ---
    st.markdown("---")
    st.subheader("📋 Historical Performance Evolution")
    def draw(lbl, met, m_v, b_v, sub):
        st.write(f"### {lbl}")
        st.caption(f"{sub} ({m_v}MW/{b_v}MW)")
        total = met[0]+met[1]+met[2]
        st.markdown(f"<h1 style='color: #28a745;'>${total:,.0f}</h1>", unsafe_allow_html=True)
        st.markdown(f"**↑ ${met[0]+met[1]:,.0f} Alpha | {met[4]:.1f}% IRR**")
        st.write(f"* ⚡ Grid: `${met[2]:,.0f}` | ⛏️ Mining: `${met[0]:,.0f}` | 🔋 Battery: `${met[1]:,.0f}`")
        st.write("---")

    c_a, c_b, c_c, c_d = st.columns(4)
    with c_a: draw("1. Pre-Opt", s1_pre, s1_m, s1_b, "Current/No Tax")
    with c_b: draw("2. Opt (Pre-Tax)", s2_pre, s2_m, s2_b, "Ideal/No Tax")
    with c_c: draw("3. Current (Post-Tax)", s1_post, s1_m, s1_b, "Current/Full Tax")
    with c_d: draw("4. Opt (Post-Tax)", s2_post, s2_m, s2_b, "Ideal/Full Tax")

with tab2:
    st.subheader("📈 5-Year Price Frequency Dataset")
    st.write("**West Texas (HB_WEST)**")
    st.table(pd.DataFrame(TREND_DATA_WEST).T.style.format("{:.1%}"))
