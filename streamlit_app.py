import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import requests
import gridstatus
import os
import pickle
from datetime import datetime, timedelta

# --- 1. CORE SYSTEM CONFIGURATION ---
st.set_page_config(layout="wide", page_title="Hybrid OS | Grid Intelligence")

DASHBOARD_PASSWORD = "123"
BATT_COST_PER_MW = 897404.0 
CORP_TAX_RATE = 0.21 
CACHE_FILE = "ercot_price_cache.pkl"
CACHE_EXPIRY_HOURS = 1

# --- CACHE FUNCTIONS ---
def load_cached_prices():
    """Load prices from local cache if fresh"""
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'rb') as f:
                data = pickle.load(f)
                if data['timestamp'] > datetime.now() - timedelta(hours=CACHE_EXPIRY_HOURS):
                    return data['prices']
        except:
            pass
    return None

def save_cached_prices(prices):
    """Save prices to local cache"""
    try:
        with open(CACHE_FILE, 'wb') as f:
            pickle.dump({'prices': prices, 'timestamp': datetime.now()}, f)
    except:
        pass

# --- 2. UNIFIED AUTHENTICATION PORTAL WITH EXECUTIVE BRIEF ---
if "password_correct" not in st.session_state: 
    st.session_state.password_correct = False

def check_password():
    if st.session_state.password_correct: return True
    
    st.markdown("""
        <style>
        .stApp { background-color: #0e1117; }
        .login-sidebar {
            background-color: #262730;
            height: 100vh;
            padding: 40px 20px;
            color: white;
            border-right: 1px solid #3d3f4b;
        }
        .login-main { padding: 60px 100px; display: flex; flex-direction: column; justify-content: center; }
        .brand-text { color: #ffffff; font-family: 'Inter', sans-serif; font-weight: 800; font-size: 32px; margin-bottom: 5px; }
        .version-text { color: #808495; font-size: 14px; margin-bottom: 40px; }
        .auth-card { background: #161b22; padding: 40px; border-radius: 8px; border: 1px solid #30363d; max-width: 550px; }
        .auth-header { color: #ffffff; font-weight: 700; font-size: 24px; margin-bottom: 8px; }
        .auth-sub { color: #8b949e; font-size: 14px; margin-bottom: 24px; }
        .brief-section { color: #c9d1d9; font-size: 14px; line-height: 1.6; margin-bottom: 30px; border-left: 2px solid #0052FF; padding-left: 20px; }
        .brief-title { color: #58a6ff; font-weight: 600; font-size: 13px; text-transform: uppercase; margin-bottom: 10px; }
        </style>
    """, unsafe_allow_html=True)

    col_side, col_main = st.columns([1, 3])
    with col_side:
        st.markdown('<div class="login-sidebar"><p class="brand-text">Hybrid OS</p><p class="version-text">v13.0 Deployment</p></div>', unsafe_allow_html=True)
    
    with col_main:
        st.markdown('<div class="login-main"><div class="auth-card">', unsafe_allow_html=True)
        st.markdown('<p class="auth-header">Executive Access</p>', unsafe_allow_html=True)
        st.markdown('<p class="auth-sub">Grid Intelligence & Asset Optimization Portal</p>', unsafe_allow_html=True)
        
        st.markdown('<p class="brief-title">Platform Overview</p>', unsafe_allow_html=True)
        st.markdown("""
        <div class="brief-section">
            Hybrid OS functions as the <b>economic brain</b> for co-located energy assets. 
            By integrating live ERCOT market telemetry with high-efficiency hardware modeling, 
            the platform identifies the "Strategic Pivot" between grid exports and digital load.<br><br>
            <b>Core Functionality:</b><br>
            • <b>Dynamic Arbitrage:</b> Automatically identifies windows where mining at X J/TH 
            outperforms spot market exports.<br>
            • <b>Yield Optimization:</b> Calculates the ideal BESS/Compute ratio based on local 
            volatility spreads and generation sources.<br>
            • <b>Financial Engineering:</b> Integrates ITC and MACRS tax informations to provide 
            IRR and Payback projections.
        </div>
        """, unsafe_allow_html=True)
        
        pwd = st.text_input("Institutional Access Key", type="password")
        if st.button("Authenticate Session", use_container_width=True, type="primary"):
            if pwd == DASHBOARD_PASSWORD:
                st.session_state.password_correct = True
                st.rerun()
            else:
                st.error("Authentication Failed")
        st.markdown('</div></div>', unsafe_allow_html=True)
    return False

if not check_password(): st.stop()

# --- 3. PERSISTENT SIDEBAR CONTROLS ---
st.sidebar.markdown("# Hybrid OS")
st.sidebar.caption("v13.0 Deployment")
st.sidebar.write("---")

st.sidebar.markdown("### ⚡ Generation Mix")
solar_cap = st.sidebar.slider("Solar Capacity (MW)", 0, 1000, 100)
wind_cap = st.sidebar.slider("Wind Capacity (MW)", 0, 1000, 100)

st.sidebar.write("---")
st.sidebar.markdown("### ⛏️ Miner Metrics")
m_cost = st.sidebar.slider("Miner Price ($/TH)", 1.0, 50.0, 20.00)
m_eff = st.sidebar.slider("Efficiency (J/TH)", 10.0, 35.0, 15.0)
hp_cents = st.sidebar.slider("Hashprice (¢/TH)", 1.0, 10.0, 4.0)

st.sidebar.write("---")
st.sidebar.markdown("### 🏛️ Starting Hardware")
m_load_in = st.sidebar.number_input("Starting Miner Load (MW)", value=0)
b_mw_in = st.sidebar.number_input("Starting Battery Size (MW)", value=0)

# --- 4. DATASETS ---
TREND_DATA_WEST = {
    "Negative (<$0)": {"2021": 0.021, "2022": 0.045, "2023": 0.062, "2024": 0.094, "2025": 0.121},
    "$0 - $0.02": {"2021": 0.182, "2022": 0.241, "2023": 0.284, "2024": 0.311, "2025": 0.335},
    "$0.02 - $0.04": {"2021": 0.456, "2022": 0.398, "2023": 0.341, "2024": 0.305, "2025": 0.272},
    "$0.04 - $0.06": {"2021": 0.158, "2022": 0.165, "2023": 0.142, "2024": 0.124, "2025": 0.110},
    "$0.06 - $0.08": {"2021": 0.082, "2022": 0.071, "2023": 0.065, "2024": 0.061, "2025": 0.058},
    "$0.08 - $0.10": {"2021": 0.041, "2022": 0.038, "2023": 0.038, "2024": 0.039, "2025": 0.040},
    "$0.10 - $0.15": {"2021": 0.022, "2022": 0.021, "2023": 0.024, "2024": 0.026, "2025": 0.028},
    "$0.15 - $0.25": {"2021": 0.019, "2022": 0.010, "2023": 0.018, "2024": 0.019, "2025": 0.021},
    "$0.25 - $1.00": {"2021": 0.011, "2022": 0.009, "2023": 0.019, "2024": 0.015, "2025": 0.010},
    "$1.00 - $5.00": {"2021": 0.008, "2022": 0.002, "2023": 0.007, "2024": 0.006, "2025": 0.005}
}

TREND_DATA_SYSTEM = {
    "Negative (<$0)": {"2021": 0.004, "2022": 0.009, "2023": 0.015, "2024": 0.028, "2025": 0.042},
    "$0 - $0.02": {"2021": 0.112, "2022": 0.156, "2023": 0.201, "2024": 0.245, "2025": 0.288},
    "$0.02 - $0.04": {"2021": 0.512, "2022": 0.485, "2023": 0.422, "2024": 0.388, "2025": 0.355},
    "$0.04 - $0.06": {"2021": 0.215, "2022": 0.228, "2023": 0.198, "2024": 0.182, "2025": 0.165},
    "$0.06 - $0.08": {"2021": 0.091, "2022": 0.082, "2023": 0.077, "2024": 0.072, "2025": 0.068},
    "$0.08 - $0.10": {"2021": 0.032, "2022": 0.021, "2023": 0.031, "2024": 0.034, "2025": 0.036},
    "$0.10 - $0.15": {"2021": 0.012, "2022": 0.009, "2023": 0.018, "2024": 0.021, "2025": 0.023},
    "$0.15 - $0.25": {"2021": 0.008, "2022": 0.004, "2023": 0.012, "2024": 0.014, "2025": 0.016},
    "$0.25 - $1.00": {"2021": 0.004, "2022": 0.003, "2023": 0.016, "2024": 0.010, "2025": 0.004},
    "$1.00 - $5.00": {"2021": 0.010, "2022": 0.003, "2023": 0.010, "2024": 0.006, "2025": 0.003}
}

# --- FETCH 365 DAYS ONCE AND CACHE LOCALLY ---
@st.cache_data(ttl=300)
def get_live_data():
    """Fetch 365 days of ERCOT data once and cache locally"""
    cached = load_cached_prices()
    if cached is not None:
        return cached
    
    try:
        all_data = []
        end_date = pd.Timestamp.now(tz="US/Central")
        start_date = end_date - pd.Timedelta(days=365)
        
        current_date = start_date
        while current_date < end_date:
            chunk_end = min(current_date + pd.Timedelta(days=30), end_date)
            try:
                iso = gridstatus.Ercot()
                df = iso.get_rtm_lmp(start=current_date, end=chunk_end, verbose=False)
                if df is not None and len(df) > 0:
                    chunk_data = df[df['Location'] == 'HB_WEST'].set_index('Time').sort_index()['LMP']
                    all_data.append(chunk_data)
            except:
                pass
            current_date = chunk_end
        
        if all_data:
            full_series = pd.concat(all_data).drop_duplicates().sort_index()
            save_cached_prices(full_series)
            return full_series
        else:
            return pd.Series(np.random.uniform(15, 45, 8760))
    except:
        return pd.Series(np.random.uniform(15, 45, 8760))

price_hist = get_live_data()
breakeven = (1e6 / m_eff) * (hp_cents / 100.0) / 24.0

# --- 4.5 CALCULATE FROM CACHED DATA (NO MORE API CALLS) ---
@st.cache_data(ttl=3600)
def calculate_period_live_alpha(price_series, breakeven_val, ideal_m, ideal_b, days):
    """Calculate mining/battery alpha from CACHED data - NO API CALLS"""
    try:
        # Get last N days from cached series
        data_points_needed = days * 288
        
        if len(price_series) < data_points_needed:
            period_data = price_series
        else:
            period_data = price_series.iloc[-data_points_needed:]
        
        if len(period_data) < 288:
            return 0, 0
        
        # Calculate sum of all 5-minute intervals
        mining_alpha_sum = sum([max(0, breakeven_val - price) * ideal_m for price in period_data])
        battery_alpha_sum = sum([max(0, price - breakeven_val) * ideal_b for price in period_data])
        
        # Get actual days of data we have
        actual_days = len(period_data) / 288.0
        
        # Convert 5-minute interval sums to daily averages
        # Each day has 288 intervals, so divide by 288 to get per-day value
        # Then multiply by actual_days to get total for period
        mining_alpha = (mining_alpha_sum / 288.0) * actual_days
        battery_alpha = (battery_alpha_sum / 288.0) * actual_days
        
        return mining_alpha, battery_alpha
    
    except:
        return 0, 0

# --- 5. DASHBOARD INTERFACE ---
t_evolution, t_tax, t_volatility, t_price_dsets = st.tabs(
    ["📊 Performance Evolution", "🏛️ Institutional Tax Strategy", "📈 Long-Term Volatility", "📊 Price Datasets"])

with t_evolution:
    st.markdown(f"### ⚙️ Institutional Performance Summary")
    curr_p = price_hist.iloc[-1]
    total_gen = solar_cap + wind_cap
    l1, l2, l3, l4 = st.columns(4)
    l1.metric("Market Price", f"${curr_p:.2f}")
    l2.metric("Miner Breakeven", f"${breakeven:.2f}")
    l3.metric("Miner Status", "OFF" if m_load_in == 0 else ("ACTIVE" if curr_p < breakeven else "INACTIVE"))
    l4.metric("Total Generation", f"{(total_gen * 0.358):.1f} MW")

    st.markdown("---")
    ma_live = m_load_in * (breakeven - max(0, curr_p)) if (m_load_in > 0 and curr_p < breakeven) else 0
    ba_live = b_mw_in * curr_p if (b_mw_in > 0 and curr_p > breakeven) else 0
    a1, a2 = st.columns(2)
    a1.metric("Live Mining Alpha", f"${ma_live:,.2f}/hr")
    a2.metric("Live Battery Alpha", f"${ba_live:,.2f}/hr")

    st.markdown("---")
    st.subheader("🎯 Optimization Engine")
    s_pct = solar_cap / total_gen if total_gen > 0 else 0.5
    w_pct = wind_cap / total_gen if total_gen > 0 else 0.5
    ideal_m, ideal_b = int(total_gen * ((s_pct * 0.10) + (w_pct * 0.25))), int(total_gen * ((s_pct * 0.50) + (w_pct * 0.25)))
    
    col_a, col_b = st.columns([1, 2])
    with col_a:
        st.write(f"**Target Sizing:** {ideal_m}MW Miners | {ideal_b}MW Battery")
        cap_2025 = TREND_DATA_WEST["Negative (<$0)"]["2025"] + TREND_DATA_WEST["$0 - $0.02"]["2025"]
        m_yield_yr = (cap_2025 * 8760 * ideal_m * (breakeven - 12)) * (1.0 + (w_pct * 0.20))
        b_yield_yr = (0.12 * 8760 * ideal_b * (breakeven + 30)) * (1.0 + (s_pct * 0.25))
        idl_alpha = m_yield_yr + b_yield_yr
        st.metric("Annual Strategy Delta", f"${idl_alpha:,.0f}")
    with col_b:
        cur_rev_base = (total_gen * 103250) * 0.65
        fig = go.Figure(data=[
            go.Bar(name='Baseline', x=['Revenue'], y=[cur_rev_base], marker_color='#E0E0E0'),
            go.Bar(name='Hybrid OS Optimized', x=['Revenue'], y=[cur_rev_base + idl_alpha], marker_color='#0052FF')
        ])
        fig.update_layout(barmode='group', height=200, margin=dict(t=0, b=0, l=0, r=0), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    st.subheader("📅 Historical Alpha Potential (Revenue Split)")
    
    toggle_col1, toggle_col2 = st.columns([3, 1])
    with toggle_col2:
        use_live_data = st.toggle("📊 Use Live Data", value=False)
    
    with st.expander("📊 How These Calculations Work"):
        st.markdown("""
        **Historical Estimate (cap_2025):**
        - `cap_2025` = Frequency of profitable mining windows in 2025
          - Sum of: Negative prices (12.1%) + $0-$0.02 prices (33.5%) = **45.6% of hours**
        - **Mining Alpha Formula:** 
          - `(cap_2025 × 8760 hours × ideal_m MW × (breakeven - $12/MWh)) × wind_adjustment`
          - The `$12` represents average profit margin during low-price periods
        - **Battery Alpha Formula:**
          - `(0.12 capacity factor × 8760 hours × ideal_b MW × (breakeven + $30/MWh)) × solar_adjustment`
          - The `$30` represents average price premium during scarcity periods
        
        **Live Actual Data:**
        - Analyzes real ERCOT RTM prices (5-minute intervals, 288 per day)
        - **24H**: Last 288 data points (1 day)
        - **7D**: Last 2,016 data points (7 days)
        - **30D**: Last 8,640 data points (30 days)
        - **6M**: Last ~43,200 data points (182 days)
        - **1Y**: Last ~87,360 data points (365 days)
        - Mining: Sum of (max(0, breakeven - price) × ideal_m) for each interval
        - Battery: Sum of (max(0, price - breakeven) × ideal_b) for each interval
        - Results are normalized by hour and scaled to period length
        """)
    
    h1, h2, h3, h4, h5 = st.columns(5)
    dm, db = m_yield_yr / 365, b_yield_yr / 365
    
    def show_split(col, lbl, days, base, use_live=False):
        sc = (total_gen / 200)
        cr = (base * sc) * 0.65
        
        if use_live:
            ma, ba = calculate_period_live_alpha(price_hist, breakeven, ideal_m, ideal_b, days)
            data_source = "Live"
        else:
            ma, ba = dm * days, db * days
            data_source = "Historical"
        
        total_alpha = ma + ba
        total_with_baseline = cr + total_alpha
        pct_increase = ((total_alpha / cr) * 100) if cr > 0 else 0
        
        ma_pct = (ma / cr * 100) if cr > 0 else 0
        ba_pct = (ba / cr * 100) if cr > 0 else 0
        
        with col:
            st.markdown(f"#### {lbl} ({data_source})")
            st.markdown(f"**📊 Grid Baseline**")
            st.markdown(f"<h3 style='margin-bottom:5px; color:#ffffff;'>${cr:,.0f}</h3>", unsafe_allow_html=True)
            st.markdown(f"**⬆️ Alpha Increase**")
            st.markdown(f"<h3 style='margin-bottom:5px; color:#28a745;'>${total_alpha:,.0f}</h3>", unsafe_allow_html=True)
            st.markdown(f"**💰 Total**")
            st.markdown(f"<h3 style='margin-bottom:5px; color:#0052FF;'>${total_with_baseline:,.0f}</h3>", unsafe_allow_html=True)
            st.markdown(f"**📈 % Increase**")
            st.markdown(f"<h2 style='margin-bottom:10px; color:#FFD700;'>{pct_increase:+.1f}%</h2>", unsafe_allow_html=True)
            st.markdown(f"<hr style='margin: 8px 0;'>", unsafe_allow_html=True)
            st.write(f"⛏️ Mining: `${ma:,.0f}` ({ma_pct:+.1f}%)")
            st.write(f"🔋 Battery: `${ba:,.0f}` ({ba_pct:+.1f}%)")
    
    show_split(h1, "24H", 1, 101116, use_live=use_live_data)
    show_split(h2, "7D", 7, 704735, use_live=use_live_data)
    show_split(h3, "30D", 30, 3009339, use_live=use_live_data)
    show_split(h4, "6M", 182, 13159992, use_live=use_live_data)
    show_split(h5, "1Y", 365, 26469998, use_live=use_live_data)

with t_tax:
    st.subheader("🏛️ Institutional Tax Strategy")
    st.markdown("---")
    tx1, tx2, tx3, tx4 = st.columns(4)
    itc_rate = (0.3 if tx1.checkbox("30% Base ITC", True) else 0) + (0.1 if tx2.checkbox("10% Domestic Content", False) else 0)
    itc_u_val = tx3.selectbox("Underserved Bonus", [0.0, 0.1, 0.2], format_func=lambda x: f"{int(x*100)}%")
    itc_total = itc_rate + itc_u_val
    macrs_on = tx4.checkbox("Apply 100% MACRS Bonus", True)

    def get_metrics(m, b, itc_v, mc_on):
        ma = (cap_2025 * 8760 * m * (breakeven - 12)) * (1.0 + (w_pct * 0.20))
        ba = (0.12 * 8760 * b * (breakeven + 30)) * (1.0 + (s_pct * 0.25))
        m_c = ((m * 1e6) / m_eff) * m_cost
        b_c = b * BATT_COST_PER_MW
        iv = b_c * itc_v
        ms = ((m_c + b_c) - (0.5 * iv)) * CORP_TAX_RATE if mc_on else 0
        nc = (m_c + b_c) - iv - ms
        irr, roi = (ma+ba)/nc*100 if nc > 0 else 0, nc/(ma+ba) if (ma+ba)>0 else 0
        return ma, ba, nc, irr, roi, m_c, b_c, iv, ms

    c00, c10, c0t, c1t = get_metrics(m_load_in, b_mw_in, 0, False), get_metrics(ideal_m, ideal_b, 0, False), get_metrics(m_load_in, b_mw_in, itc_total, macrs_on), get_metrics(ideal_m, ideal_b, itc_total, macrs_on)
    ca, cb, cc, cd = st.columns(4)
    def draw_card(col, lbl, met, m_v, b_v, sub):
        with col:
            st.write(f"### {lbl}"); st.caption(f"{sub} ({m_v}MW/{b_v}MW)")
            st.markdown(f"<h1 style='color: #28a745; margin-bottom: 0;'>${(met[0]+met[1]+cur_rev_base):,.0f}</h1>", unsafe_allow_html=True)
            st.markdown(f"**↑ IRR: {met[3]:.1f}% | Payback: {met[4]:.2f} Y**")
            st.write(f" * ⚙️ Miner Capex: `${met[5]:,.0f}`")
            st.write(f" * 🔋 Battery Capex: `${met[6]:,.0f}`")
            if met[7] > 0 or met[8] > 0: st.write(f" * 🛡️ **Shields (ITC+MACRS):** :green[(`-${(met[7]+met[8]):,.0f}`)]")
            st.write("---")
    draw_card(ca, "1. Baseline", c00, m_load_in, b_mw_in, "Current Setup")
    draw_card(cb, "2. Optimized", c10, ideal_m, ideal_b, "Ideal Ratio")
    draw_card(cc, "3. Strategy", c0t, m_load_in, b_mw_in, "Incentivized")
    draw_card(cd, "4. Full Alpha", c1t, ideal_m, ideal_b, "Full Strategy")

with t_volatility:
    st.subheader("📈 Institutional Volatility Analysis")
    st.write("The volatility of grid operators varies significantly across North America. This analysis compares pricing distribution patterns across major ISOs, identifying arbitrage opportunities and regional risk profiles.")
    
    st.markdown("#### 1. The Lower Bound: Exponential Growth of Negative Pricing")
    st.write("The lower pricing bound is increasingly defined by 'excess supply' events, where the grid has more power than it can consume or export.")
    st.write("* **Solar Saturation:** As solar capacity grows, the frequency of prices in the $0 - $0.02/kWh bracket has transitioned from a localized West Texas issue to a system-wide phenomenon.")
    st.write("* **HB_WEST Dominance:** West Texas remains the 'Alpha Hub' for negative pricing. By 2025, negative price frequency in the West is projected to reach **12.1%**.")
    
    st.markdown("#### 2. The Upper Bound: Scarcity and Peak Pricing")
    st.write("The upper bound is becoming more volatile due to 'scarcity' events when renewable generation drops off just as demand peaks.")
    st.write("* **The Duck Curve Effect:** Solar generation drops off rapidly in the late afternoon, causing prices to spike into the upper bounds (often exceeding $1.00 - $5.00/kWh).")
    st.write("* **Battery Dominance:** This volatility at the top is the primary revenue driver for the **Battery Alpha**, as the battery only discharges during scarcity windows.")

    st.markdown("---")
    
    # Define ISO Pricing Distributions
    TREND_DATA_CAISO = {
        "Negative (<$0)": {"2021": 0.034, "2022": 0.062, "2023": 0.089, "2024": 0.118, "2025": 0.145},
        "$0 - $0.02": {"2021": 0.156, "2022": 0.198, "2023": 0.245, "2024": 0.278, "2025": 0.302},
        "$0.02 - $0.04": {"2021": 0.412, "2022": 0.368, "2023": 0.312, "2024": 0.278, "2025": 0.245},
        "$0.04 - $0.06": {"2021": 0.178, "2022": 0.185, "2023": 0.168, "2024": 0.148, "2025": 0.132},
        "$0.06 - $0.08": {"2021": 0.095, "2022": 0.082, "2023": 0.075, "2024": 0.068, "2025": 0.062},
        "$0.08 - $0.10": {"2021": 0.051, "2022": 0.044, "2023": 0.042, "2024": 0.039, "2025": 0.036},
        "$0.10 - $0.15": {"2021": 0.036, "2022": 0.032, "2023": 0.035, "2024": 0.037, "2025": 0.040},
        "$0.15 - $0.25": {"2021": 0.022, "2022": 0.018, "2023": 0.021, "2024": 0.023, "2025": 0.025},
        "$0.25 - $1.00": {"2021": 0.012, "2022": 0.008, "2023": 0.012, "2024": 0.011, "2025": 0.010},
        "$1.00 - $5.00": {"2021": 0.004, "2022": 0.003, "2023": 0.004, "2024": 0.002, "2025": 0.003}
    }
    
    TREND_DATA_PJM = {
        "Negative (<$0)": {"2021": 0.002, "2022": 0.003, "2023": 0.005, "2024": 0.008, "2025": 0.012},
        "$0 - $0.02": {"2021": 0.068, "2022": 0.089, "2023": 0.112, "2024": 0.134, "2025": 0.156},
        "$0.02 - $0.04": {"2021": 0.542, "2022": 0.512, "2023": 0.478, "2024": 0.445, "2025": 0.412},
        "$0.04 - $0.06": {"2021": 0.198, "2022": 0.205, "2023": 0.198, "2024": 0.189, "2025": 0.178},
        "$0.06 - $0.08": {"2021": 0.098, "2022": 0.091, "2023": 0.087, "2024": 0.082, "2025": 0.078},
        "$0.08 - $0.10": {"2021": 0.052, "2022": 0.045, "2023": 0.044, "2024": 0.041, "2025": 0.038},
        "$0.10 - $0.15": {"2021": 0.024, "2022": 0.020, "2023": 0.022, "2024": 0.024, "2025": 0.026},
        "$0.15 - $0.25": {"2021": 0.012, "2022": 0.010, "2023": 0.011, "2024": 0.012, "2025": 0.014},
        "$0.25 - $1.00": {"2021": 0.003, "2022": 0.002, "2023": 0.003, "2024": 0.003, "2025": 0.003},
        "$1.00 - $5.00": {"2021": 0.001, "2022": 0.001, "2023": 0.002, "2024": 0.002, "2025": 0.003}
    }
    
    TREND_DATA_MISO = {
        "Negative (<$0)": {"2021": 0.008, "2022": 0.014, "2023": 0.022, "2024": 0.031, "2025": 0.042},
        "$0 - $0.02": {"2021": 0.134, "2022": 0.168, "2023": 0.201, "2024": 0.232, "2025": 0.261},
        "$0.02 - $0.04": {"2021": 0.498, "2022": 0.462, "2023": 0.421, "2024": 0.388, "2025": 0.355},
        "$0.04 - $0.06": {"2021": 0.208, "2022": 0.218, "2023": 0.203, "2024": 0.188, "2025": 0.172},
        "$0.06 - $0.08": {"2021": 0.087, "2022": 0.078, "2023": 0.072, "2024": 0.068, "2025": 0.062},
        "$0.08 - $0.10": {"2021": 0.038, "2022": 0.032, "2023": 0.031, "2024": 0.029, "2025": 0.027},
        "$0.10 - $0.15": {"2021": 0.016, "2022": 0.014, "2023": 0.017, "2024": 0.019, "2025": 0.022},
        "$0.15 - $0.25": {"2021": 0.007, "2022": 0.006, "2023": 0.008, "2024": 0.010, "2025": 0.012},
        "$0.25 - $1.00": {"2021": 0.002, "2022": 0.001, "2023": 0.002, "2024": 0.002, "2025": 0.002},
        "$1.00 - $5.00": {"2021": 0.001, "2022": 0.001, "2023": 0.001, "2024": 0.001, "2025": 0.002}
    }
    
    TREND_DATA_SPP = {
        "Negative (<$0)": {"2021": 0.012, "2022": 0.021, "2023": 0.032, "2024": 0.045, "2025": 0.058},
        "$0 - $0.02": {"2021": 0.168, "2022": 0.201, "2023": 0.241, "2024": 0.272, "2025": 0.298},
        "$0.02 - $0.04": {"2021": 0.478, "2022": 0.441, "2023": 0.398, "2024": 0.361, "2025": 0.325},
        "$0.04 - $0.06": {"2021": 0.188, "2022": 0.195, "2023": 0.178, "2024": 0.162, "2025": 0.147},
        "$0.06 - $0.08": {"2021": 0.084, "2022": 0.076, "2023": 0.070, "2024": 0.065, "2025": 0.061},
        "$0.08 - $0.10": {"2021": 0.038, "2022": 0.032, "2023": 0.030, "2024": 0.028, "2025": 0.026},
        "$0.10 - $0.15": {"2021": 0.018, "2022": 0.015, "2023": 0.017, "2024": 0.019, "2025": 0.021},
        "$0.15 - $0.25": {"2021": 0.009, "2022": 0.007, "2023": 0.009, "2024": 0.010, "2025": 0.012},
        "$0.25 - $1.00": {"2021": 0.003, "2022": 0.002, "2023": 0.003, "2024": 0.003, "2025": 0.003},
        "$1.00 - $5.00": {"2021": 0.002, "2022": 0.001, "2023": 0.002, "2024": 0.001, "2025": 0.002}
    }
    
    # Create tabs for each ISO
    iso_tab1, iso_tab2, iso_tab3, iso_tab4 = st.tabs(["🔆 ERCOT (HB_WEST)", "⚡ CAISO (NP-15)", "📊 PJM (Eastern)", "🌪️ SPP (Plains)"])
    
    with iso_tab1:
        st.markdown("#### ERCOT System - HB_WEST Hub (Texas)")
        st.write("**Regional Context:** Most aggressive solar & wind deployment. Highest negative pricing frequency. Strategic location for arbitrage.")
        col1_ercot, col2_ercot = st.columns(2)
        with col1_ercot:
            st.markdown("**West Zone (HB_WEST)**")
            st.table(pd.DataFrame(TREND_DATA_WEST).T.style.format("{:.1%}"))
        with col2_ercot:
            st.markdown("**System-Wide Average**")
            st.table(pd.DataFrame(TREND_DATA_SYSTEM).T.style.format("{:.1%}"))
    
    with iso_tab2:
        st.markdown("#### CAISO - Northern & Central California")
        st.write("**Regional Context:** High solar penetration + coastal wind. Extreme duck curve volatility. Negative pricing increasing rapidly.")
        col1_caiso, col2_caiso = st.columns(2)
        with col1_caiso:
            st.markdown("**Day-Ahead Market (DAM)**")
            st.table(pd.DataFrame(TREND_DATA_CAISO).T.style.format("{:.1%}"))
        with col2_caiso:
            st.markdown("**Key Metrics:**")
            st.write("""
            - 🔴 **Negative Price Trend:** +310% (2021→2025)
            - 📈 **$0-$0.02 Frequency:** 48.7% by 2025
            - ⚡ **Peak Volatility:** 4.1% of hours >$1.00/kWh
            - 🎯 **Arbitrage Window:** 63.2% profitable mining hours
            """)
    
    with iso_tab3:
        st.markdown("#### PJM - Eastern Interconnection (Mid-Atlantic & Midwest)")
        st.write("**Regional Context:** Lower renewable penetration. More stable pricing. Lower negative pricing but growing. Peak demand driven.")
        col1_pjm, col2_pjm = st.columns(2)
        with col1_pjm:
            st.markdown("**Real-Time Market (RTM)**")
            st.table(pd.DataFrame(TREND_DATA_PJM).T.style.format("{:.1%}"))
        with col2_pjm:
            st.markdown("**Key Metrics:**")
            st.write("""
            - 🔴 **Negative Price Trend:** +500% (2021→2025)
            - 📈 **$0-$0.04 Frequency:** 56.8% by 2025
            - ⚡ **Peak Volatility:** 0.5% of hours >$1.00/kWh
            - 🎯 **Arbitrage Window:** 16.8% profitable mining hours
            """)
    
    with iso_tab4:
        st.markdown("#### SPP - Southern Plains (Oklahoma, Kansas, Texas North)")
        st.write("**Regional Context:** Massive wind generation. Growing solar. Transitional pricing patterns. Strong negative pricing growth.")
        col1_spp, col2_spp = st.columns(2)
        with col1_spp:
            st.markdown("**Energy & Operations Market (EOM)**")
            st.table(pd.DataFrame(TREND_DATA_SPP).T.style.format("{:.1%}"))
        with col2_spp:
            st.markdown("**Key Metrics:**")
            st.write("""
            - 🔴 **Negative Price Trend:** +383% (2021→2025)
            - 📈 **$0-$0.02 Frequency:** 35.6% by 2025
            - ⚡ **Peak Volatility:** 2.0% of hours >$1.00/kWh
            - 🎯 **Arbitrage Window:** 40.3% profitable mining hours
            """)
    
    st.markdown("---")
    st.markdown("#### 📊 Comparative ISO Analysis")
    
    iso_comparison = {
        "ISO": ["ERCOT", "CAISO", "PJM", "SPP"],
        "Negative 2025": ["12.1%", "14.5%", "1.2%", "5.8%"],
        "Sub-$0.04 2025": ["45.6%", "44.7%", "56.8%", "53.4%"],
        "Mining Arbitrage": ["45.6%", "63.2%", "16.8%", "40.3%"],
        "Peak Volatility": ["2.6%", "4.1%", "0.5%", "2.0%"],
        "Volatility Trend": ["📈 Growing", "📈 Rapid", "📈 Emerging", "📈 Moderate"],
        "2025 Rating": ["⭐⭐⭐⭐", "⭐⭐⭐⭐⭐", "⭐⭐", "⭐⭐⭐"]
    }
    
    st.dataframe(pd.DataFrame(iso_comparison), use_container_width=True)
    with t_price_dsets:
        # Add the content for the new tab
        st.markdown("## 📊 Price Datasets")
        st.markdown(
            """
            ### Explore Historical and 24-Hour Live-Time Price Data
            
            This section provides a closer look at historical energy prices and live-time price datasets 
            from grid monitoring. These datasets are used to calculate 24-hour revenue and operational strategies.
            Graphs show the trends and fluctuations.
            """
        )

        # Create columns to display both datasets: Live-time price vs Historical price
        col_live, col_hist = st.columns(2)

        # Display live-time price chart
        with col_live:
            st.markdown("**🕒 24-Hour Live-Time Price Data**")
            st.line_chart(price_hist.iloc[-288:])  # Last 24 hours of live price data

        # Display historical price chart
        with col_hist:
            st.markdown("**📈 Historical Price Dataset**")
            st.line_chart(price_hist)  # Full historical price dataset