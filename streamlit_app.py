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

# --- DATASETS (HB_WEST & SYSTEM-WIDE) ---
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

# --- AUTHENTICATION ---
if "password_correct" not in st.session_state: st.session_state.password_correct = False
def check_password():
    if st.session_state.password_correct: return True
    st.title("⚡ Midland Hybrid Alpha")
    pwd = st.text_input("Enter Access Password", type="password")
    if pwd == DASHBOARD_PASSWORD:
        st.session_state.password_correct = True
        st.rerun()
    return False

if not check_password(): st.stop()

@st.cache_data(ttl=300)
def get_live_data():
    try:
        iso = gridstatus.Ercot()
        df = iso.get_rtm_lmp(start=pd.Timestamp.now(tz="US/Central")-pd.Timedelta(days=31), end=pd.Timestamp.now(tz="US/Central"), verbose=False)
        return df[df['Location'] == 'HB_WEST'].set_index('Time').sort_index()['LMP']
    except: return pd.Series(np.random.uniform(15, 45, 744))

price_hist = get_live_data()

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
        m_cost = st.slider("Miner Cost ($/TH)", 1.0, 50.0, 18.20)
        m_eff = st.slider("Efficiency (J/TH)", 10.0, 35.0, 28.0)
    with c3:
        hp_cents = st.slider("Hashprice (¢/TH)", 1.0, 10.0, 4.0)
        # Battery Size moved below Hashprice slider
        batt_mw = st.number_input("Battery Size (MW)", value=60)
        
        breakeven = (1e6 / m_eff) * (hp_cents / 100.0) / 24.0
        st.markdown(f"#### Breakeven Floor: **${breakeven:.2f}/MWh**")

    # --- SECTION 2: HYBRID OPTIMIZATION ENGINE ---
    st.markdown("---")
    st.subheader("🎯 Hybrid Optimization Engine")
    total_gen = solar_cap + wind_cap
    if total_gen > 0:
        s_pct, w_pct = solar_cap / total_gen, wind_cap / total_gen
    else:
        s_pct, w_pct = 0.5, 0.5
    
    # Elastic Sizing Logic
    ideal_m = int(total_gen * ((s_pct * 0.10) + (w_pct * 0.25)))
    ideal_b = int(total_gen * ((s_pct * 0.50) + (w_pct * 0.25)))
    
    st.write(f"**Ideal Sizing:** {ideal_m}MW Miners | {ideal_b}MW Battery")
    
    # Revenue Factor for Engine Comparison
    capture_2025 = TREND_DATA_WEST["Negative (<$0)"]["2025"] + TREND_DATA_WEST["$0 - $0.02"]["2025"]
    def get_simple_rev(m, b):
        ma = (capture_2025 * 8760 * m * (breakeven - 12)) * (1.0 + (w_pct * 0.20))
        ba = (0.005 * 8760 * b * 1200) * (1.0 + (s_pct * 0.25))
        return ma + ba

    cur_rev, idl_rev = get_simple_rev(35, batt_mw), get_simple_rev(ideal_m, ideal_b)
    delta = idl_rev - cur_rev
    upside = (delta / cur_rev * 100) if cur_rev > 0 else 0
    
    st.metric("Annual Optimization Delta", f"${delta:,.0f}", delta=f"{upside:.1f}% Upside")
    
    fig = go.Figure(data=[
        go.Bar(name='Current', x=['Rev'], y=[cur_rev], marker_color='#A0C4FF'),
        go.Bar(name='Ideal', x=['Rev'], y=[idl_rev], marker_color='#3A86FF')
    ])
    fig.update_layout(barmode='group', height=300, margin=dict(t=0, b=0, l=0, r=0))
    st.plotly_chart(fig, use_container_width=True)

    # --- SECTION 3: LIVE POWER & PERFORMANCE ---
    st.markdown("---")
    st.subheader("📊 Live Power & Performance")
    lp1, lp2, lp3 = st.columns(3)
    curr_p = price_hist.iloc[-1]
    lp1.metric("Current Grid Price", f"${curr_p:.2f}/MWh")
    lp2.metric("Total Generation", f"{(total_gen * 0.35):.1f} MW") # Approx 35% CF for live view
    lp3.metric("Miner Load", f"{35.0 if curr_p < breakeven else 0.0} MW")
    
    ma_live = 35 * (breakeven - max(0, curr_p)) if curr_p < breakeven else 0
    ba_live = batt_mw * curr_p if curr_p > 100 else (batt_mw * abs(curr_p) if curr_p < 0 else 0)
    
    st.metric("Mining Alpha", f"${ma_live:,.2f}/hr")
    st.metric("Battery Alpha", f"${ba_live:,.2f}/hr")

    # --- SECTION 4: COMMERCIAL TAX STRATEGY ---
    st.markdown("---")
    st.subheader("🏛️ Commercial Tax Strategy")
    tx1, tx2, tx3 = st.columns(3)
    t_rate = (0.3 if tx1.checkbox("Apply 30% Base ITC", True) else 0) + (0.1 if tx2.checkbox("Apply 10% Domestic Content", False) else 0)
    li_choice = tx3.selectbox("Underserved Bonus", ["None", "10% Bonus", "20% Bonus"])
    t_rate += (0.1 if "10%" in li_choice else (0.2 if "20%" in li_choice else 0))

    # --- SECTION 5: EVOLUTION CARDS ---
    st.markdown("---")
    st.subheader("📋 Historical Performance Evolution")
    
    def get_metrics(m, b, itc):
        ma = (capture_2025 * 8760 * m * (breakeven - 12)) * (1.0 + (w_pct * 0.20))
        ba = (0.005 * 8760 * b * 1200) * (1.0 + (s_pct * 0.25))
        base = (solar_cap * 82500 + wind_cap * 124000)
        net = ((m*1e6)/m_eff)*m_cost + (b*BATT_COST_PER_MW*(1-itc))
        irr = (ma + ba) / net * 100 if net > 0 else 0
        return ma, ba, base, net, irr

    s1, s2, s3, s4 = get_metrics(35, batt_mw, 0), get_metrics(ideal_m, ideal_b, 0), get_metrics(35, batt_mw, t_rate), get_metrics(ideal_m, ideal_b, t_rate)

    def draw(lbl, met, m_v, b_v, sub):
        st.write(f"### {lbl}")
        st.caption(f"{sub} ({m_v}MW / {b_v}MW)")
        total = met[0] + met[1] + met[2]
        st.markdown(f"<h1 style='color: #28a745;'>${total:,.0f}</h1>", unsafe_allow_html=True)
        st.markdown(f"**↑ ${met[0]+met[1]:,.0f} Alpha | {met[4]:.1f}% IRR**")
        st.write("---")

    c_a, c_b, c_c, c_d = st.columns(4)
    with c_a: draw("1. Pre-Opt", s1, 35, batt_mw, "Current/No Tax")
    with c_b: draw("2. Opt (Pre-Tax)", s2, ideal_m, ideal_b, "Ideal/No Tax")
    with c_c: draw("3. Current (Post-Tax)", s3, 35, batt_mw, "Current/Full Tax")
    with c_d: draw("4. Opt (Post-Tax)", s4, ideal_m, ideal_b, "Ideal/Full Tax")

with tab2:
    st.subheader("📈 5-Year Price Frequency Dataset")
    st.markdown("#### 1. West Texas (HB_WEST)")
    st.table(pd.DataFrame(TREND_DATA_WEST).T.style.format("{:.1%}"))
    st.markdown("#### 2. ERCOT System-Wide Average")
    st.table(pd.DataFrame(TREND_DATA_SYSTEM).T.style.format("{:.1%}"))
