# --- TAX BREAK SELECTION (UPDATED) ---
st.markdown("---")
st.subheader("🏛️ Commercial Tax Strategy (U.S. Federal)")
tx1, tx2, tx3 = st.columns(3)
apply_itc = tx1.checkbox("Apply 30% Base ITC", value=False)
apply_bonus = tx2.checkbox("Apply 10% Domestic Content Bonus", value=False)
# NEW: Low-Income Adder (Limited to <5MW per unit)
li_bonus = tx3.selectbox("Underserved Community Bonus", ["None", "10% (Low-Income/Tribal)", "20% (Economic Benefit)"])

# Calculation Logic
li_rate = 0.10 if "10%" in li_bonus else (0.20 if "20%" in li_bonus else 0)
itc_rate = (0.30 if apply_itc else 0) + (0.10 if apply_bonus else 0) + li_rate

# --- SECTION 2: ROI COMPARISON (BEFORE vs AFTER) ---
m_capex = ((miner_mw * 1000000) / m_eff) * m_cost
b_capex = batt_mw * BATT_COST_PER_MW
total_gross = m_capex + b_capex

# ITC primarily offsets battery capex for standalone/hybrid BESS
tax_savings = (b_capex * itc_rate)
total_net = total_gross - tax_savings

col_pre, col_post = st.columns(2)
with col_pre:
    st.write("**Pre-Tax Basis**")
    st.metric("Gross Capex", f"${total_gross:,.0f}")
    st.metric("Pre-Tax IRR", f"{(ann_alpha / total_gross * 100 if total_gross > 0 else 0):.1f}%")
        
with col_post:
    st.write("**Post-Tax Basis (Inc. Underserved Bonus)**")
    st.metric("Net Capex", f"${total_net:,.0f}", delta=f"-${tax_savings:,.0f}")
    st.metric("Post-Tax IRR", f"{(ann_alpha / total_net * 100 if total_net > 0 else 0):.1f}%")

# --- RATIO OPTIMIZATION TREND ---
st.markdown("---")
st.subheader("🎯 Optimization Shift")
post_m, post_b = (int(total_gen * 0.15), int(total_gen * 0.55)) if itc_rate >= 0.40 else (pre_m, pre_b)

o1, o2 = st.columns(2)
o1.write("**Standard Ideal Ratio**")
o1.code(f"Miners: {pre_m}MW | Battery: {pre_b}MW")
o2.write("**Subsidized Ideal Ratio**")
o2.code(f"Miners: {post_m}MW | Battery: {post_b}MW")
