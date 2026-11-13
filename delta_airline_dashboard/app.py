import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

from data_engine import (
    fetch_delta_data,
    extract_financial_summary,
    extract_valuation_multiples,
    run_dcf_model,
)
from pdf_generator import generate_executive_pdf
from outlook_helper import open_outlook_with_report

# -----------------------------------------------------------------------------
# PAGE CONFIGURATION & STYLING
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Delta Air Lines (DAL) – Institutional Equity & Treasury Dashboard",
    page_icon="✈️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .main-header {
        font-size: 2.1rem;
        font-weight: 700;
        color: #003366;
        margin-bottom: 0.1rem;
    }
    .sub-header {
        font-size: 1.0rem;
        color: #5A6B7C;
        margin-bottom: 1.2rem;
    }
    .metric-card {
        background-color: #F8FAFC;
        border-left: 4px solid #C01933;
        padding: 12px 16px;
        border-radius: 6px;
        margin-bottom: 10px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# -----------------------------------------------------------------------------
# CACHED DATA LOADER
# -----------------------------------------------------------------------------
@st.cache_data(ttl=3600, show_spinner="Fetching live market & financial data for Delta Air Lines (DAL)...")
def load_all_data():
    raw = fetch_delta_data("DAL")
    fin_df = extract_financial_summary(raw)
    multiples = extract_valuation_multiples(raw, fin_df)
    return raw, fin_df, multiples


try:
    raw_data, fin_df, multiples = load_all_data()
except Exception as exc:
    st.error(f"Error retrieving data from yfinance: {exc}")
    st.stop()

info = raw_data["info"]

# -----------------------------------------------------------------------------
# SIDEBAR: DCF ASSUMPTIONS & SALES PREP CONTROLS
# -----------------------------------------------------------------------------
with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/commons/thumb/d/d1/Delta_logo.svg/320px-Delta_logo.svg.png", width=180)
    st.markdown("### ⚙️ DCF Model Assumptions")
    rev_growth = st.slider("5Y Avg. Revenue Growth (%)", 1.0, 12.0, 4.5, 0.5) / 100.0
    ebit_margin = st.slider("Target Operating (EBIT) Margin (%)", 5.0, 18.0, 10.5, 0.5) / 100.0
    tax_rate = st.slider("Effective Tax Rate (%)", 15.0, 30.0, 23.0, 1.0) / 100.0
    capex_pct = st.slider("CapEx (% of Revenue)", 4.0, 12.0, 7.5, 0.5) / 100.0
    rf_rate = st.slider("Risk-Free Rate – 10Y UST (%)", 2.5, 6.5, 4.2, 0.1) / 100.0
    erp = st.slider("Equity Risk Premium (%)", 3.5, 7.5, 5.0, 0.25) / 100.0
    tgr = st.slider("Terminal Growth Rate (%)", 1.0, 4.0, 2.5, 0.25) / 100.0

    st.markdown("---")
    st.markdown("### 📧 Sales Meeting Prep")
    recipient_email = st.text_input("Recipient Email (Optional)", placeholder="sales.team@bank.com")
    if st.button("🔄 Refresh Live yfinance Data"):
        st.cache_data.clear()
        st.rerun()

# Run DCF dynamically based on sidebar parameters
dcf_results = run_dcf_model(
    data=raw_data,
    fin_df=fin_df,
    rev_growth_rate=rev_growth,
    ebit_margin=ebit_margin,
    tax_rate=tax_rate,
    capex_pct_rev=capex_pct,
    risk_free_rate=rf_rate,
    equity_risk_premium=erp,
    terminal_growth_rate=tgr,
)

# -----------------------------------------------------------------------------
# TOP HEADER & KPI STRIP
# -----------------------------------------------------------------------------
st.markdown(f"<div class='main-header'>✈️ {info.get('longName', 'Delta Air Lines, Inc.')} (NYSE: DAL)</div>", unsafe_allow_html=True)
st.markdown(
    f"<div class='sub-header'>Full Equity Research, Financial Analytics, DCF Valuation & Corporate Hedging Advisory | "
    f"Last Updated: {raw_data['fetched_at']}</div>",
    unsafe_allow_html=True,
)

k1, k2, k3, k4, k5, k6 = st.columns(6)
k1.metric("Share Price", f"${multiples['Current Share Price ($)']:.2f}")
k2.metric("Market Cap", f"${multiples['Market Cap ($B)']:.2f}B")
k3.metric("Enterprise Value", f"${multiples['Enterprise Value ($B)']:.2f}B")
k4.metric("EV / EBITDA", f"{multiples['EV / EBITDA (x)']}x")
k5.metric("Trailing / Fwd P/E", f"{multiples['Trailing P/E (x)']}x / {multiples['Forward P/E (x)']}x")
k6.metric(
    "DCF Implied Price",
    f"${dcf_results['valuation_bridge']['Implied Share Price ($)']:.2f}",
    f"{dcf_results['valuation_bridge']['Implied Upside / Downside (%)']:+.1f}%",
)

st.markdown("---")

# -----------------------------------------------------------------------------
# MAIN TABS
# -----------------------------------------------------------------------------
tab1, tab2 = st.tabs(
    [
        "📊 Tab 1: Company Overview, Financials, Risks & Current Hedging",
        "🎯 Tab 2: DCF Valuation, Multiples, Hedging Strategy & Client Export",
    ]
)

# =============================================================================
# TAB 1: COMPANY OVERVIEW, FINANCIALS, RISKS & CURRENT HEDGING
# =============================================================================
with tab1:
    st.subheader("1. Company Overview & Market Positioning")
    col_ov1, col_ov2 = st.columns([2, 1])

    with col_ov1:
        st.write(info.get("longBusinessSummary", "Business summary unavailable."))
    with col_ov2:
        st.markdown(
            f"""
            <div class='metric-card'>
            <b>Headquarters:</b> {info.get('city', 'Atlanta')}, {info.get('state', 'GA')}, {info.get('country', 'USA')}<br>
            <b>Employees:</b> {info.get('fullTimeEmployees', 100000):,}<br>
            <b>Sector / Industry:</b> {info.get('sector', 'Industrials')} / {info.get('industry', 'Airlines')}<br>
            <b>52-Week Range:</b> ${info.get('fiftyTwoWeekLow', 0):.2f} – ${info.get('fiftyTwoWeekHigh', 0):.2f}<br>
            <b>Analyst Consensus:</b> {str(info.get('recommendationKey', 'BUY')).upper()} (Target: ${info.get('targetMeanPrice', 0):.2f})
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Stock Performance vs Benchmarks
    st.subheader("2. Relative Market Performance (DAL vs. S&P 500 & JETS Airline ETF)")
    bench_df = raw_data["benchmarks"].dropna()
    if not bench_df.empty:
        norm_bench = (bench_df / bench_df.iloc[0]) * 100
        fig_bench = px.line(
            norm_bench,
            labels={"value": "Normalized Return (Base = 100)", "Date": "Date", "variable": "Ticker"},
            color_discrete_map={"DAL": "#C01933", "^GSPC": "#003366", "JETS": "#64748B"},
        )
        fig_bench.update_layout(height=360, margin=dict(l=10, r=10, t=20, b=10), legend_title_text="")
        st.plotly_chart(fig_bench, use_container_width=True)

    # Historical Financials
    st.subheader("3. Multi-Year Financial Performance (yfinance Statements)")
    if not fin_df.empty:
        c_fin1, c_fin2 = st.columns(2)

        with c_fin1:
            fig_rev = go.Figure()
            fig_rev.add_trace(go.Bar(x=fin_df["Year"], y=fin_df["Revenue ($B)"], name="Revenue ($B)", marker_color="#003366"))
            fig_rev.add_trace(go.Bar(x=fin_df["Year"], y=fin_df["EBITDA ($B)"], name="EBITDA ($B)", marker_color="#3B82F6"))
            fig_rev.add_trace(go.Bar(x=fin_df["Year"], y=fin_df["Free Cash Flow ($B)"], name="Free Cash Flow ($B)", marker_color="#10B981"))
            fig_rev.update_layout(
                title="Revenue, EBITDA & Free Cash Flow ($B)",
                barmode="group",
                height=360,
                margin=dict(l=10, r=10, t=40, b=10),
            )
            st.plotly_chart(fig_rev, use_container_width=True)

        with c_fin2:
            fig_debt = go.Figure()
            fig_debt.add_trace(go.Bar(x=fin_df["Year"], y=fin_df["Total Debt ($B)"], name="Total Debt ($B)", marker_color="#C01933"))
            fig_debt.add_trace(go.Bar(x=fin_df["Year"], y=fin_df["Cash & Equivalents ($B)"], name="Cash ($B)", marker_color="#0D9488"))
            fig_debt.add_trace(
                go.Scatter(
                    x=fin_df["Year"],
                    y=fin_df["Operating Margin (%)"],
                    name="Operating Margin (%)",
                    yaxis="y2",
                    mode="lines+markers",
                    line=dict(color="#F59E0B", width=3),
                )
            )
            fig_debt.update_layout(
                title="Balance Sheet De-leveraging & Operating Margin (%)",
                barmode="group",
                yaxis=dict(title="USD Billions"),
                yaxis2=dict(title="Margin (%)", overlaying="y", side="right"),
                height=360,
                margin=dict(l=10, r=10, t=40, b=10),
            )
            st.plotly_chart(fig_debt, use_container_width=True)

        with st.expander("📋 View Full Multi-Year Financial Summary Table", expanded=True):
            st.dataframe(fin_df.set_index("Year").T.style.format("{:.2f}"), use_container_width=True)

    # Risks & Existing Hedging Architecture
    st.subheader("4. Key Business Risks & Current Hedging Architecture")
    r_col1, r_col2 = st.columns(2)

    with r_col1:
        st.markdown("#### ⚠️ Core Operational & Financial Risk Exposures")
        st.markdown(
            """
            - **Jet Fuel Price Volatility:** Fuel represents Delta's second-largest operating expense (~20–24% of operating costs). Unhedged crack-spread spikes directly compress EBIT margins.
            - **High Financial & Operating Leverage:** Heavy fixed aircraft lease/debt obligations amplify earnings sensitivity during macroeconomic slowdowns or corporate travel pullbacks.
            - **Foreign Currency (FX) Exposure:** International ticket sales and overseas station expenses create multi-currency cash flow mismatches (EUR, GBP, JPY, CAD, MXN).
            - **Interest Rate Refinancing Risk:** Floating-rate debt tranches and ongoing fleet modernization CapEx expose financing costs to elevated benchmark rates.
            - **Labor & Supply Chain Inflation:** Pilot/maintenance wage escalations and OEM aircraft delivery delays (Boeing/Airbus) constrain capacity growth.
            """
        )

    with r_col2:
        st.markdown("#### 🛡️ Delta's Current Hedging Strategies")
        st.markdown(
            """
            - **Vertical Integration via Monroe Energy (Trainer Refinery):** Unlike peers relying solely on financial swaps, Delta owns the Trainer refinery in Pennsylvania, using refined non-jet products (gasoline/diesel) to exchange for jet fuel and naturally hedge **refining crack spreads**.
            - **Selective Financial Fuel Derivatives:** Opportunistic use of heating oil/WTI call spreads and collars when crack spreads dislocate, avoiding costly pure-swap premiums.
            - **Foreign Exchange Hedging:** Rolling 12-to-24-month FX forward contracts and zero-cost collars on net EUR, GBP, and JPY operational surpluses.
            - **Interest Rate & Debt Management:** High proportion of fixed-rate aircraft financing (~80%+ fixed) paired with pay-fixed interest rate swaps on floating facilities and aggressive debt paydown.
            """
        )


# =============================================================================
# TAB 2: DCF VALUATION, MULTIPLES, RECOMMENDATIONS & CLIENT EXPORT
# =============================================================================
with tab2:
    latest_fin = fin_df.iloc[-1]
    bridge = dcf_results["valuation_bridge"]
    wacc_details = dcf_results["wacc_details"]

    # Dynamic Executive Summary Text
    exec_summary_text = (
        f"Delta Air Lines (DAL) continues to demonstrate industry-leading operational resilience among US legacy carriers, "
        f"generating ${latest_fin['Revenue ($B)']:.2f}B in annual revenue, ${latest_fin['EBITDA ($B)']:.2f}B in EBITDA "
        f"({latest_fin['EBITDA Margin (%)']:.1f}% margin), and ${latest_fin['Free Cash Flow ($B)']:.2f}B in Free Cash Flow. "
        f"Management has prioritized balance-sheet de-leveraging, bringing Net Debt down to ${latest_fin['Net Debt ($B)']:.2f}B "
        f"({latest_fin['Net Debt / EBITDA (x)']:.2f}x Net Debt/EBITDA). Trading at {multiples['Trailing P/E (x)']}x trailing P/E "
        f"and {multiples['EV / EBITDA (x)']}x EV/EBITDA, our 5-year unlevered DCF model (WACC: {wacc_details['Calculated WACC (%)']:.2f}%, "
        f"Terminal Growth: {wacc_details['Terminal Growth Rate (%)']:.2f}%) implies an intrinsic equity value of "
        f"${bridge['Implied Share Price ($)']:.2f}/share ({bridge['Implied Upside / Downside (%)']:+.1f}% vs. current market price)."
    )

    st.subheader("1. Executive Performance Summary")
    st.info(exec_summary_text)

    # Valuation Multiples & DCF Bridge
    st.subheader("2. Trading Multiples & Discounted Cash Flow (DCF) Valuation")
    m_col1, m_col2, m_col3 = st.columns([1.1, 1.2, 1.2])

    with m_col1:
        st.markdown("**📊 Market & Trading Multiples**")
        mult_df = pd.DataFrame(list(multiples.items()), columns=["Multiple / Metric", "Value"])
        st.dataframe(mult_df, hide_index=True, use_container_width=True)

    with m_col2:
        st.markdown("**🧮 CAPM & WACC Breakdown**")
        wacc_df = pd.DataFrame(list(wacc_details.items()), columns=["WACC Component", "Value"])
        st.dataframe(wacc_df, hide_index=True, use_container_width=True)

    with m_col3:
        st.markdown("**🌉 Enterprise to Equity Value Bridge**")
        bridge_df = pd.DataFrame(list(bridge.items()), columns=["Valuation Step", "Value"])
        st.dataframe(bridge_df, hide_index=True, use_container_width=True)

    # 5-Year Projected FCFF Table & Sensitivity Matrix
    st.markdown("**📈 5-Year Projected Unlevered Free Cash Flow (FCFF) Schedule ($B)**")
    proj_display = dcf_results["projections"].set_index("Year").T
    st.dataframe(proj_display.style.format("{:.2f}"), use_container_width=True)

    s_col1, s_col2 = st.columns([1.2, 1])
    with s_col1:
        st.markdown("**🎯 Implied Share Price Sensitivity: WACC vs. Terminal Growth Rate ($)**")
        st.dataframe(dcf_results["sensitivity"].style.format("${:.2f}"), use_container_width=True)
    with s_col2:
        fig_fcf = px.bar(
            dcf_results["projections"],
            x="Year",
            y=["Unlevered FCF ($B)", "PV of FCF ($B)"],
            barmode="group",
            title="Projected FCFF vs. Present Value ($B)",
            color_discrete_sequence=["#003366", "#C01933"],
        )
        fig_fcf.update_layout(height=270, margin=dict(l=10, r=10, t=35, b=10))
        st.plotly_chart(fig_fcf, use_container_width=True)

    # Hedging Recommendations for Corporate Sales Pitch
    st.subheader("3. Actionable Hedging & Treasury Advisory Recommendations")
    hedging_recs = [
        {
            "title": "Structured Jet Fuel Crack-Spread Collars (Zero-Cost / Participating)",
            "detail": (
                "Supplement Monroe Energy's physical refinery hedge with 12-month rolling NY Harbor ULSD / Gulf Coast "
                "Jet Fuel zero-cost collars to cap extreme upward crack-spread tail risk while preserving downside participation."
            ),
        },
        {
            "title": "Layered FX Cash Flow Hedging (EUR, GBP, JPY)",
            "detail": (
                "Implement layered 18-month FX forwards and Seagull option structures covering 60–75% of forecasted net "
                "transatlantic and transpacific ticket inflows to lock in USD margin certainty."
            ),
        },
        {
            "title": "Pre-Issuance Rate Locks & Liability Management Swaps",
            "detail": (
                "Utilize forward-starting interest rate swaps (or Treasury locks) ahead of upcoming fleet CapEx debt tranches "
                "and EETC (Enhanced Equipment Trust Certificate) issuances to mitigate rate-cut timing volatility."
            ),
        },
        {
            "title": "Liquidity & Working Capital Optimization (GTB Solutions)",
            "detail": (
                "Deploy automated multi-currency notional cash pooling and dynamic supply-chain finance facilities for "
                "aviation maintenance vendors to boost Free Cash Flow conversion."
            ),
        },
    ]

    for rec in hedging_recs:
        st.markdown(f"- **{rec['title']}:** {rec['detail']}")

    st.markdown("---")

    # -------------------------------------------------------------------------
    # EXPORT & OUTLOOK CLIENT MEETING AUTOMATION
    # -------------------------------------------------------------------------
    st.subheader("4. Export Executive PDF & Prepare Client Meeting Email")

    # Generate PDF bytes on demand
    pdf_bytes = generate_executive_pdf(
        data=raw_data,
        fin_df=fin_df,
        multiples=multiples,
        dcf_results=dcf_results,
        executive_summary=exec_summary_text,
        hedging_recommendations=hedging_recs,
    )

    exp_col1, exp_col2 = st.columns(2)

    with exp_col1:
        st.download_button(
            label="📥 Download Stylized Executive PDF Report",
            data=pdf_bytes,
            file_name="Delta_Air_Lines_Executive_Briefing.pdf",
            mime="application/pdf",
            use_container_width=True,
        )

    with exp_col2:
        if st.button("📧 Open Outlook & Attach Report for Client Meeting", type="primary", use_container_width=True):
            highlights = (
                f"- Current Price: ${multiples['Current Share Price ($)']:.2f} | DCF Implied Price: "
                f"${bridge['Implied Share Price ($)']:.2f} ({bridge['Implied Upside / Downside (%)']:+.1f}%)\n"
                f"- Revenue: ${latest_fin['Revenue ($B)']:.2f}B | EBITDA: ${latest_fin['EBITDA ($B)']:.2f}B | "
                f"FCF: ${latest_fin['Free Cash Flow ($B)']:.2f}B\n"
                f"- Net Debt / EBITDA: {latest_fin['Net Debt / EBITDA (x)']:.2f}x | EV/EBITDA: {multiples['EV / EBITDA (x)']}x\n"
                f"- Key Pitch Angles: Jet Fuel Crack-Spread Collars, Transatlantic FX Hedging & Fleet CapEx Rate Locks"
            )
            success, msg = open_outlook_with_report(
                pdf_bytes=pdf_bytes,
                recipient=recipient_email,
                company_name="Delta Air Lines (DAL)",
                summary_highlights=highlights,
            )
            if success:
                st.success(msg)
            else:
                st.warning(msg)