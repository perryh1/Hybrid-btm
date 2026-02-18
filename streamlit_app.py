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

# Tesla Megapack 4hr Configuration
BATT_COST_PER_MW = 897404.0 
BATT_MAINT_PER_MW = 5371.0 

# --- 3-YEAR HISTORICAL FREQUENCY DATASET (HB_WEST) ---
TREND_DATA = {
    "Negative (<$0)":    {"2023": 0.062, "2024": 0.094, "2025": 0.121},
    "$0 - $0.02":       {"2023": 0.284, "2024": 0.311, "2025": 0.335},
    "$0.02 - $0.04":    {"2023": 0.341, "2024": 0.305, "2025": 0.272},
    "$0.04 - $0.06":    {"2023": 0.142, "2024": 0.124, "2025": 0.110},
    "$0.06 - $0.08":    {"2023": 0.065, "2024": 0.061, "2025": 0.058},
    "$0.08 - $0.10":    {"2023": 0.038, "2024": 0.039, "2025": 0.040},
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
current_price = price_hist.iloc[-1]

# --- APP TABS ---
tab1, tab2 = st.tabs(["📊 Asset Dashboard", "📈 Long-Term Volatility"])

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

    # --- SECTION 2: TAX STRATEGY MODULE ---
    st.markdown("---")
    st.subheader("🏛️ Commercial Tax Strategy (U.S. Federal)")
    st.info("Standalone Energy Storage and Hybrid BTM assets are eligible for Section 48E credits.")
    
    tx1, tx2, tx3 = st.columns(3)
    apply_itc = tx1.checkbox("Apply 30% Base ITC", value=False)
    apply_bonus = tx2.checkbox("Apply 10% Domestic Content Bonus", value=False)
    li_bonus = tx3.selectbox("Underserved Community Bonus", ["None", "10% (Low-Income/Tribal)", "20% (Economic Benefit)"])

    # Calculate Total Tax Rate
    li_rate = 0.10 if "10%" in li_bonus else (0.20 if "20%" in li_bonus else 0)
    total_tax_rate = (0.30 if apply_itc else 0) + (0.10 if apply_bonus else 0) + li_rate

    # --- SECTION 3: ROI & IRR (BEFORE vs AFTER) ---
    st.markdown("---")
    st.subheader("💰 Financial Performance Comparison")
    
    # Pre-Tax Calculations
    miner_capex = ((miner_mw * 1000000) / m_eff) * m_cost
    batt_capex_gross = batt_mw * BATT_COST_PER_MW
    total_gross = miner_capex + batt_capex_gross
    
    # Revenue (2025 Projection)
    capture_rate = TREND_DATA["Negative (<$0)"]["2025"] + TREND_DATA["$0 - $0.02"]["2025"]
    ann_alpha = (capture_rate * 8760 * miner_mw * (breakeven - 12)) + (0.005 * 8760 * batt_mw * 1200)
    
    # Post-Tax Calculations
    tax_savings = (batt_capex_gross * total_tax_rate)
    total_net = total_gross - tax_savings
    
    col_pre, col_post = st.columns(2)
    with col_pre:
        st.write("**Pre-Tax Basis**")
        st.metric("Gross Capex", f"${total_gross:,.0f}")
        st.metric("Pre-Tax ROI", f"{(total_gross / ann_alpha if ann_alpha > 0 else 0):.2f} Yrs")
        st.metric("Pre-Tax IRR", f"{(ann_alpha / total_gross * 100 if total_gross > 0 else 0):.1f}%")
        
    with col_post:
        st.write("**Post-Tax Strategic Basis**")
        st.metric("Net Capex", f"${total_net:,.0f}", delta=f"-${tax_savings:,.0f} Benefit")
        st.metric("Post-Tax ROI", f"{(total_net / ann_alpha if ann_alpha > 0 else 0):.2f} Yrs")
        st.metric("Post-Tax IRR", f"{(ann_alpha / total_net * 100 if total_net > 0 else 0):.1f}%", delta=f"+{(ann_alpha / total_net * 100) - (ann_alpha / total_gross * 100):.1f}%")

    # --- SECTION 4: RATIO OPTIMIZATION SHIFT ---
    st.markdown("---")
    st.subheader("🎯 Optimization Shift")
    total_gen = solar_cap + wind_cap
    
    # Base Ideal Ratio (20% Miner / 30% Battery)
    base_m, base_b = int(total_gen * 0.20), int(total_gen * 0.30)
    # Tax-Adjusted Ideal (Increased Battery Allocation as tax credit increases)
    tax_m, tax_b = (int(total_gen * 0.15), int(total_gen * 0.55)) if total_tax_rate >= 0.40 else (base_m, base_b)
    
    o1, o2 = st.columns(2)
    o1.write("**Pre-Tax Ideal Ratio**")
    o1.code(f"Miners: {base_m}MW | Battery: {base_b}MW")
    o2.write("**Post-Tax Ideal Ratio**")
    o2.code(f"Miners: {tax_m}MW | Battery: {tax_b}MW")
    st.caption("Subsidizing the battery capex incentivizes energy storage over compute for Scarcity Alpha capture.")

    # --- SECTION 5: PERFORMANCE BREAKDOWN ---
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

    def calc_rev_live(p_series, m_mw, b_mw, gen_mw, be):
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
        m, b, g = calc_rev_live(price_hist.tail(24), miner_mw, batt_mw, t_gen_avg, breakeven)
        display_stat_box_v2("Last 24 Hours", m, b, g)
        m, b, g = calc_rev_live(price_hist.tail(720), miner_mw, batt_mw, t_gen_avg, breakeven)
        display_stat_box_v2("Last 30 Days", m, b, g)
    with col_r:
        m, b, g = calc_rev_live(price_hist.tail(168), miner_mw, batt_mw, t_gen_avg, breakeven)
        display_stat_box_v2("Last 7 Days", m, b, g)
        # 1Y Trend
        m_y = (capture_rate * 8760 * miner_mw * (breakeven - 12))
        b_y = (0.005 * 8760 * batt_mw * 1200)
        g_y = (solar_cap * 82500 + wind_cap * 124000)
        display_stat_box_v2("Last 1 Year (Trend)", m_y, b_y, g_y)

with tab2:
    st.subheader("📉 3-Year Price Frequency Dataset (ERCOT HB_WEST)")
    df_trend = pd.DataFrame(TREND_DATA).T
    st.table(df_trend.style.format("{:.1%}"))
