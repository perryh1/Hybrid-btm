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

# --- DATASET 1: HB_WEST (WEST TEXAS) ---
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

# --- DATASET 2: ERCOT SYSTEM-WIDE ---
TREND_DATA_SYSTEM = {
    "Negative (<$0)":    {"2021": 0.004, "2022": 0.009, "2023": 0.015, "2024": 0.028, "2025": 0.042},
    "$0 - $0.02":       {"2021": 0.112, "2022": 0.156, "2023": 0.201, "2024": 0.245, "2025": 0.288},
    "$0.02 - $0.04":    {"2021": 0.512, "2022": 0.485, "2023": 0.422, "2024": 0.388, "2025": 0.355},
    "$0.04 - $0.06":    {"2021": 0.215, "2022": 0.228, "2023": 0.198, "2024": 0.182, "2025": 0.165},
    "$0.06 - $0.08":    {"2021": 0.091, "2022": 0.082, "2023": 0.077, "2024": 0.072, "2025": 0.068},
    "$0.08 - $0.10":    {"2021": 0.032, "2022": 0.021, "2023": 0.031, "2024": 0.034, "2025": 0.036},
    "$0.10 - $0.15":    {"2021": 0.012, "2022": 0.009, "2023": 0.018, "2024": 0.021, "2025": 0.023},
    "$0.15 - $0.25":    {"2021": 0.008, "2022": 0.004, "2023": 0.012, "2024": 0.014, "2025": 0.016},
    "$0.25 - $1.00":    {"2021": 0.004, "2022": 0.003, "2023": 0.016, "2024": 0.010, "2025": 0.004},
    "$1.00 - $5.00":    {"2021": 0.010, "2022": 0.003, "2023": 0.010, "2024": 0.006, "2025": 0.003}
}

# --- AUTHENTICATION & ENGINE ---
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
    # --- CONFIGURATION ---
    st.markdown("### ⚙️ System Configuration")
    c1, c2, c3 = st.columns(3)
    with c1:
        solar_cap, wind_cap = st.slider("Solar Capacity (MW)", 0, 1000, 100), st.slider("Wind Capacity (MW)", 0, 1000, 100)
    with c2:
        miner_mw = st.number_input("Miner Fleet (MW)", value=35)
        m_cost, m_eff = st.slider("Miner Cost ($/TH)", 1.0, 50.0, 15.0), st.slider("Efficiency (J/TH)", 10.0, 35.0, 19.0, 0.5)
    with c3:
        batt_mw = st.number_input("Battery Size (MW)", value=60)
        hp_cents = st.slider("Hashprice (¢/TH)", 1.0, 10.0, 4.0, 0.1)
        breakeven = (1e6 / m_eff) * (hp_cents / 100.0) / 24.0
        st.metric("Breakeven Floor", f"${breakeven:.2f}/MWh")

    # --- UPDATED TAX STRATEGY ---
    st.markdown("---")
    st.subheader("🏛️ Commercial Tax Strategy")
    tx1, tx2, tx3 = st.columns(3)
    # ITC Logic
    itc_rate = (0.3 if tx1.checkbox("Apply 30% Base ITC", True) else 0) + (0.1 if tx2.checkbox("Apply 10% Domestic Content", False) else 0)
    li_choice = tx3.selectbox("Underserved Bonus", ["None", "10% Bonus", "20% Bonus"])
    itc_rate += (0.1 if "10%" in li_choice else (0.2 if "20%" in li_choice else 0))

    # Depreciation Logic
    st.write("**Depreciation Strategy (2026 Policy)**")
    dep_col1, dep_col2 = st.columns(2)
    use_bonus = dep_col1.checkbox("Apply 20% Bonus Depreciation", False)
    use_macrs = dep_col2.checkbox("Apply 5-Year MACRS Schedule", True)
    
    # Approx cash-value of depreciation in Year 1 (21% Corp Tax)
    dep_rate = (0.20 * 0.21 if use_bonus else 0) + (0.20 * 0.21 if use_macrs else 0) 

    # --- CORE METRICS ENGINE ---
    capture_2025 = TREND_DATA_WEST["Negative (<$0)"]["2025"] + TREND_DATA_WEST["$0 - $0.02"]["2025"]
    def get_metrics(m, b, itc, dep):
        ma, ba, base = (capture_2025*8760*m*(breakeven-12)), (0.005*8760*b*1200), (solar_cap*82500+wind_cap*124000)
        m_cap, b_cap = ((m*1e6)/m_eff)*m_cost, b*BATT_COST_PER_MW
        net = m_cap + b_cap*(1-itc)
        net -= (net * dep) # Applying depreciation tax shelter value
        return ma, ba, base, net, (ma+ba)/net*100 if net>0 else 0, net/(ma+ba) if (ma+ba)>0 else 0

    s1_m, s1_b = miner_mw, batt_mw
    s2_m, s2_b = int((solar_cap+wind_cap)*0.2), int((solar_cap+wind_cap)*0.3)
    s1_pre, s1_post, s2_post = get_metrics(s1_m, s1_b, 0, 0), get_metrics(s1_m, s1_b, itc_rate, dep_rate), get_metrics(s2_m, s2_b, itc_rate, dep_rate)

    # --- ROI COMPARISONS ---
    st.markdown("---")
    st.subheader("💰 Post-Tax Financial Comparison")
    col_cur, col_opt = st.columns(2)
    with col_cur:
        st.write("#### 1. Current Setup")
        st.markdown(f"**Physical:** `{s1_m}MW / {s1_b}MW`")
        st.metric("Net Capex", f"${s1_post[3]:,.0f}", delta=f"-${(s1_pre[3]-s1_post[3]):,.0f}")
        st.metric("IRR", f"{s1_post[4]:.1f}%", delta=f"+{s1_post[4]-s1_pre[4]:.1f}%")
    with col_opt:
        st.write("#### 2. Optimized Setup")
        st.markdown(f"**Physical:** `{s2_m}MW / {s2_b}MW`")
        st.metric("Net Capex", f"${s2_post[3]:,.0f}")
        st.metric("IRR", f"{s2_post[4]:.1f}%", delta=f"+{s2_post[4]-s1_post[4]:.1f}% over Current")

    # --- METHODOLOGY ---
    with st.expander("🔍 Calculation Methodology"):
        st.markdown(f"""
        1. **Bonus Depreciation:** Under 2026 phase-out, the 100% credit has dropped to **20%**.
        2. **MACRS:** We apply the 5-Year schedule at a **21%** effective corporate tax rate.
        3. **ITC Sourcing:** Based on Tesla supply chain for the Midland project.
        """)

    # --- THREE-STAGE EVOLUTION ---
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
    with c_b: draw("2. Opt (Pre-Tax)", get_metrics(s2_m, s2_b, 0, 0), s2_m, s2_b, "Ideal/No Tax")
    with c_c: draw("3. Current (Post-Tax)", s1_post, s1_m, s1_b, "Current/Full Tax")
    with c_d: draw("4. Opt (Post-Tax)", s2_post, s2_m, s2_b, "Ideal/Full Tax")

with tab2:
    st.subheader("📈 5-Year Price Frequency Dataset")
    st.write("**West Texas (HB_WEST)**")
    st.table(pd.DataFrame(TREND_DATA_WEST).T.style.format("{:.1%}"))
    st.write("**ERCOT System-Wide Average**")
    st.table(pd.DataFrame(TREND_DATA_SYSTEM).T.style.format("{:.1%}"))
