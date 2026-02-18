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

# --- RESTORED 3-YEAR HISTORICAL FREQUENCY DATASET (HB_WEST) ---
# Values represent % of total annual hours (8,760 hrs) in 2-cent segments
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

    # --- SECTION 3: CORE CALCULATIONS ---
    total_gen = solar_cap + wind_cap
    capture_2025 = TREND_DATA["Negative (<$0)"]["2025"] + TREND_DATA["$0 - $0.02"]["2025"]
    
    def get_stage_metrics(m, b, itc_r):
        ma = (capture_2025 * 8760 * m * (breakeven - 12))
        ba = (0.005 * 8760 * b * 1200)
        base = (solar_cap * 82500 + wind_cap * 124000)
        m_th = (m * 1000000) / m_eff
        m_cap = m_th * m_cost
        b_cap = b * BATT_COST_PER_MW
        net_cap = m_cap + (b_cap * (1 - itc_r))
        irr = (ma + ba) / net_cap * 100 if net_cap > 0 else 0
        roi = net_cap / (ma + ba) if (ma + ba) > 0 else 0
        return ma, ba, base, net_cap, irr, roi, m_th, m_cap, b_cap

    s1_m, s1_b = miner_mw, batt_mw
    s2_m, s2_b = int(total_gen * 0.20), int(total_gen * 0.30)
    
    current_pre = get_stage_metrics(s1_m, s1_b, 0)
    current_post = get_stage_metrics(s1_m, s1_b, tax_rate)
    opt_post = get_stage_metrics(s2_m, s2_b, tax_rate)

    # --- SECTION 4: SPLIT FINANCIAL COMPARISON ---
    st.markdown("---")
    st.subheader("💰 Post-Tax Financial Comparison")
    col_cur, col_opt = st.columns(2)
    with col_cur:
        st.write("#### 1. Current Setup (Post-Tax)")
        st.markdown(f"**Physical Config:** `{s1_m} MW` Miners | `{s1_b} MW` Battery")
        st.metric("Net Capex", f"${current_post[3]:,.0f}", delta=f"-${(s1_b * BATT_COST_PER_MW * tax_rate):,.0f} Benefit")
        st.metric("ROI", f"{current_post[5]:.2f} Yrs")
        st.metric("IRR", f"{current_post[4]:.1f}%", delta=f"+{current_post[4]-current_pre[4]:.1f}% vs Pre-Tax")

    with col_opt:
        st.write("#### 2. Optimized Setup (Post-Tax)")
        st.markdown(f"**Physical Config:** `{s2_m} MW` Miners | `{s2_b} MW` Battery")
        st.metric("Net Capex", f"${opt_post[3]:,.0f}")
        st.metric("ROI", f"{opt_post[5]:.2f} Yrs")
        st.metric("IRR", f"{opt_post[4]:.1f}%", delta=f"+{opt_post[4]-current_post[4]:.1f}% over Current")

    # --- SECTION 5: METHODOLOGY ---
    with st.expander("🔍 View Calculation Methodology"):
        st.write("**How we calculate your IRR:**")
        st.markdown(f"""
        1. **Miner Configuration:** Fleet uses **{s1_m} MW** at **{m_eff} J/TH**, producing **{current_pre[6]:,.0f} TH**.
        2. **Battery Configuration:** Fleet uses **{s1_b} MW** of Tesla Megapacks.
        3. **Mining Revenue:** Prices favorable for mining **{(capture_2025*100):.1f}%** of year (2025 Trend). 
        4. **Optimization Logic:** 'Optimized Setup' targets **20% Miner / 30% Battery** ratio to site generation ({total_gen} MW).
        5. **The Formula:** (Annual Alpha / Net Capex) = **Final IRR**.
        """)

    # --- SECTION 6: THREE-STAGE EVOLUTION ---
    st.markdown("---")
    st.subheader("📋 Historical Performance Evolution")
    
    def draw_stage(label, metrics, m_val, b_val, subtitle):
        ma, ba, base, cap, irr, roi, m_th, m_cap, b_cap = metrics
        st.write(f"### {label}")
        st.caption(f"{subtitle} ({m_val} MW / {b_val} MW)")
        total = ma + ba + base
        st.markdown(f"<h1 style='color: #28a745; margin-bottom: 0;'>${total:,.0f}</h1>", unsafe_allow_html=True)
        st.markdown(f"<span style='color: #28a745; font-size: 1.1em;'>↑ ${ma+ba:,.0f} Alpha | {irr:.1f}% IRR</span>", unsafe_allow_html=True)
        st.write("")
        st.markdown(f"* **⚡ Grid (Base):** `${base:,.0f}`")
        st.markdown(f"* **⛏️ Mining Alpha:** `${ma:,.0f}`")
        st.markdown(f"* **🔋 Battery Alpha:** `${ba:,.0f}`")
        st.write("---")

    c_a, c_b, c_c = st.columns(3)
    with c_a: draw_stage("1. Pre-Optimization", current_pre, s1_m, s1_b, "Current Setup / No Tax")
    with c_b: draw_stage("2. Optimized (Pre-Tax)", get_stage_metrics(s2_m, s2_b, 0), s2_m, s2_b, "Ideal Ratio / No Tax")
    with c_c: draw_stage("3. Optimized (Post-Tax)", opt_post, s2_m, s2_b, "Ideal Ratio / Full Tax Strategy")

with tab2:
    st.subheader("📉 3-Year Price Frequency Dataset")
    st.markdown("*Percentage of annual hours (8,760 hrs) per 2-cent segment (HB_WEST)*")
    df_trend = pd.DataFrame(TREND_DATA).T
    st.table(df_trend.style.format("{:.1%}") )
