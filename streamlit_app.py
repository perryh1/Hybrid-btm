import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import requests
import gridstatus
from datetime import datetime, timedelta

# --- 1. CORE SYSTEM CONFIGURATION ---
st.set_page_config(layout="wide", page_title="Hybrid OS | Grid Intelligence")

DASHBOARD_PASSWORD = "123"
BATT_COST_PER_MW = 897404.0
CORP_TAX_RATE = 0.21

# --- 2. UNIFIED AUTHENTICATION PORTAL WITH EXECUTIVE BRIEF ---
if "password_correct" not in st.session_state:
    st.session_state.password_correct = False

def check_password():
    if st.session_state.password_correct: 
        return True
    
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
        .brand-text { color: #ffffff; font-family: 'Inter', sans-serif; font-weight: 800; font-size: 32px; margin-bottom: 5px;}
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
st.sidebar.markdown("### 🏛️ Starting Hardware")
b_mw_in = st.sidebar.number_input("Starting Battery Size (MW)", value=0)

# Revenue Estimation for ERCOT Ancillary Services
def calculate_ercot_revenue(days, battery_size_mw):
    # Revenue estimates per MW for ERCOT ancillary services
    ercot_revenue_per_mw_per_year_low = 30000  # $30,000 per year (low estimate)
    ercot_revenue_per_mw_per_year_high = 50000  # $50,000 per year (high estimate)

    # Average revenue per day for a 1 MW battery
    daily_revenue_low = ercot_revenue_per_mw_per_year_low / 365
    daily_revenue_high = ercot_revenue_per_mw_per_year_high / 365

    # Calculate total revenue for the given days and battery size (MW)
    revenue_low = daily_revenue_low * days * battery_size_mw
    revenue_high = daily_revenue_high * days * battery_size_mw

    return revenue_low, revenue_high

# --- Historical Alpha Potential Section ---
st.subheader("📅 Historical Alpha Potential (Revenue Split)")

h1, h2, h3, h4, h5 = st.columns(5)

def show_split(col, lbl, days):
    # Calculate ancillary revenue estimates
    ercot_low, ercot_high = calculate_ercot_revenue(days, b_mw_in)

    with col:
        st.markdown(f"#### {lbl}")
        # Ancillary Revenue
        st.markdown(f"**🔋 Ancillary Revenue (ERCOT)**")
        st.write(f"${ercot_low:,.0f} - ${ercot_high:,.0f}")

# Display Revenue Split for Different Time Periods
show_split(h1, "24 Hours", 1)
show_split(h2, "7 Days", 7)
show_split(h3, "30 Days", 30)
show_split(h4, "6 Months", 182)
show_split(h5, "1 Year", 365)