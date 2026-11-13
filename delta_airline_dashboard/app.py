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

st.set_page_config(
    page_title="Delta Air Lines (DAL) – CGI Advisory Dashboard",
    page_icon="✈️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Robust High-Contrast CGI Styling (Eliminating white-on-white and black-on-black table issues)
st.markdown(
    """
    <style>
    /* Global App Background & Typography */
    .stApp {
        background-color: #F8F9FA !important;
        color: #1A1A1A !important;
    }

    /* Force all standard markdown text and paragraphs to be clearly visible */
    p, span, label, .stMarkdown, li, .streamlit-expanderHeader {
        color: #1A1A1A !important;
    }

    /* Headers */
    h1, h2, h3, h4, h5, h6 {
        color: #2A1B4E !important;
    }

    /* Sidebar Styling */
    section[data-testid="stSidebar"] {
        background: #FFFFFF !important;
        border-right: 1px solid #E2E8F0;
    }
    section[data-testid="stSidebar"] p, 
    section[data-testid="stSidebar"] label, 
    section[data-testid="stSidebar"] span,
    section[data-testid="stSidebar"] .stMarkdown {
        color: #1A1A1A !important;
    }

    /* Top CGI Gradient Banner */
    .cgi-banner {
        background: linear-gradient(135deg, #E31937 0%, #9B185A 52%, #5236AB 100%);
        padding: 24px 30px;
        border-radius: 10px;
        color: #FFFFFF !important;
        margin-bottom: 1.5rem;
        box-shadow: 0 6px 18px rgba(82, 54, 171, 0.18);
    }
    .cgi-banner-title {
        font-size: 2.1rem;
        font-weight: 700;
        color: #FFFFFF !important;
        margin: 0 0 6px 0;
        letter-spacing: -0.3px;
    }
    .cgi-banner-sub {
        font-size: 0.98rem;
        color: rgba(255, 255, 255, 0.92) !important;
        margin: 0;
    }

    /* CGI Accent Card */
    .cgi-card {
        background-color: #FFFFFF !important;
        border: 1px solid #E2E8F0;
        border-top: 4px solid #E31937;
        padding: 18px;
        border-radius: 8px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04);
        color: #1A1A1A !important;
    }
    .cgi-card b, .cgi-card h4 {
        color: #1A1A1A !important;
    }

    /* Metric Cards Styling */
    div[data-testid="stMetric"] {
        background-color: #FFFFFF !important;
        border: 1px solid #E2E8F0 !important;
        border-left: 4px solid #E31937 !important;
        padding: 12px 14px;
        border-radius: 8px;
        box-shadow: 0 2px 6px rgba(0,0,0,0.03);
    }
    div[data-testid="stMetricLabel"] {
        color: #64748B !important;
        font-weight: 600 !important;
    }
    div[data-testid="stMetricValue"] {
        color: #1A1A1A !important;
        font-weight: 700 !important;
    }

    /* Dataframes and Tables Contrast Fix */
    div[data-testid="stDataFrame"], table {
        background-color: #FFFFFF !important;
        color: #1A1A1A !important;
    }
    th {
        background-color: #5236AB !important;
        color: #FFFFFF !important;
        font-weight: 600 !important;
    }
    td {
        color: #1A1A1A !important;
        background-color: #FFFFFF !important;
    }

    /* Tabs Styling */
    button[data-baseweb="tab"] {
        font-weight: 600 !important;
        color: #4A5568 !important;
    }
    button[data-baseweb="tab"][aria-selected="true"] {
        color: #E31937 !important;
        border-bottom: 3px solid #E31937 !important;
    }

    /* Primary & Download Buttons with CGI Gradient */
    .stButton > button, .stDownloadButton > button {
        background: linear-gradient(90deg, #E31937 0%, #9B185A 55%, #5236AB 100%) !important;
        color: #FFFFFF !important;
        border: none !important;
        border-radius: 6px !important;
        font-weight: 600 !important;
        padding: 0.6rem 1.2rem !important;
        box-shadow: 0 3px 10px rgba(227, 25, 55, 0.22) !important;
    }
    .stButton > button:hover, .stDownloadButton > button:hover {
        background: linear-gradient(90deg, #C8142F 0%, #83124B 55%, #41298F 100%) !important;
        color: #FFFFFF !important;
        box-shadow: 0 5px 14px rgba(82, 54, 171, 0.30) !important;
    }

    /* Info Box Styling */
    div[data-testid="stAlert"] {
        background-color: #FFFFFF !important;
        border: 1px solid #E2D9F3 !important;
        border-left: 5px solid #5236AB !important;
        color: #1A1A1A !important;
    }
    div[data-testid="stAlert"] p {
        color: #1A1A1A !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


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

with st.sidebar:
    st.markdown(
        """
        <div style="background: linear-gradient(90deg, #E31937 0%, #5236AB 100%);
                    padding: 10px 14px; border-radius: 8px; color: white; font-weight: 700;
                    font-size: 1.15rem; margin-bottom: 12px; letter-spacing: 0.5px;">
            CGI | Advisory Suite
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.image("https://upload.wikimedia.org/wikipedia/commons/thumb/d/d1/Delta_logo.svg/320px-Delta_logo.svg.png", width=170)
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
    recipient_email = st.text_input("Recipient Email (Optional)", placeholder="sales.team@cgi.com")
    if st.button("🔄 Refresh Live yfinance Data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

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

# CGI Gradient Hero Banner
st.markdown(
    f"""
    <div class='cgi-banner'>
        <div class='cgi-banner-title'>✈️ {info.get('longName', 'Delta Air Lines, Inc.')} (NYSE: DAL)</div>
        <div class='cgi-banner-sub'>
            CGI Financial & Treasury Advisory | Corporate Risk Mapping, Underlyings Profiling & DCF Valuation (Excl. 2021) &bull;
            Updated: {raw_data['fetched_at']}
        </div>
    </div>
    """,
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

st.markdown("<br>", unsafe_allow_html=True)

tab1, tab2, tab3 = st.tabs(
    [
        "📊 Tab 1: Company Overview & Financials (Excl. 2021)",
        "🛡️ Tab 2: Corporate Risk Mapping & Hedging Scheme Design",
        "🎯 Tab 3: DCF Valuation, Multiples & Client Export",
    ]
)

# =============================================================================
# TAB 1: COMPANY OVERVIEW & FINANCIALS
# =============================================================================
with tab1:
    st.subheader("1. Company Overview & Market Positioning")
    col_ov1, col_ov2 = st.columns([2, 1])

    with col_ov1:
        st.write(info.get("longBusinessSummary", "Business summary unavailable."))
    with col_ov2:
        st.markdown(
            f"""
            <div class='cgi-card'>
            <h4 style="margin-top: 0; color: #5236AB; font-size: 1.05rem; border-bottom: 1px solid #ECE8F4; padding-bottom: 6px;">
                📊 Client Quick Factsheet
            </h4>
            <b>Headquarters:</b> {info.get('city', 'Atlanta')}, {info.get('state', 'GA')}<br>
            <b>Employees:</b> {info.get('fullTimeEmployees', 100000):,}<br>
            <b>Sector:</b> {info.get('sector', 'Industrials')}<br>
            <b>Industry:</b> {info.get('industry', 'Airlines')}<br>
            <b>52W Range:</b> ${info.get('fiftyTwoWeekLow', 0):.2f} – ${info.get('fiftyTwoWeekHigh', 0):.2f}<br>
            <b>Consensus:</b> {str(info.get('recommendationKey', 'BUY')).upper()}
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.subheader("2. Relative Market Performance (DAL vs. S&P 500 & JETS Airline ETF)")
    bench_df = raw_data["benchmarks"].dropna()
    if not bench_df.empty:
        norm_bench = (bench_df / bench_df.iloc[0]) * 100
        fig_bench = px.line(
            norm_bench,
            labels={"value": "Normalized Return (Base = 100)", "Date": "Date", "variable": "Ticker"},
            color_discrete_map={"DAL": "#E31937", "^GSPC": "#5236AB", "JETS": "#9B185A"},
        )
        fig_bench.update_layout(
            height=360,
            margin=dict(l=10, r=10, t=20, b=10),
            legend_title_text="",
            plot_bgcolor="#FFFFFF",
            paper_bgcolor="#FFFFFF",
            font=dict(color="#1A1A1A"),
        )
        st.plotly_chart(fig_bench, use_container_width=True)

    st.subheader("3. Multi-Year Financial Performance (Excluding 2021)")
    if not fin_df.empty:
        c_fin1, c_fin2 = st.columns(2)

        with c_fin1:
            fig_rev = go.Figure()
            fig_rev.add_trace(go.Bar(x=fin_df["Year"], y=fin_df["Revenue ($B)"], name="Revenue ($B)", marker_color="#5236AB"))
            fig_rev.add_trace(go.Bar(x=fin_df["Year"], y=fin_df["EBITDA ($B)"], name="EBITDA ($B)", marker_color="#9B185A"))
            fig_rev.add_trace(go.Bar(x=fin_df["Year"], y=fin_df["Free Cash Flow ($B)"], name="Free Cash Flow ($B)", marker_color="#E31937"))
            fig_rev.update_layout(
                title="Revenue, EBITDA & Free Cash Flow ($B)",
                barmode="group",
                height=360,
                margin=dict(l=10, r=10, t=40, b=10),
                plot_bgcolor="#FFFFFF",
                paper_bgcolor="#FFFFFF",
                font=dict(color="#1A1A1A"),
            )
            st.plotly_chart(fig_rev, use_container_width=True)

        with c_fin2:
            fig_debt = go.Figure()
            fig_debt.add_trace(go.Bar(x=fin_df["Year"], y=fin_df["Total Debt ($B)"], name="Total Debt ($B)", marker_color="#E31937"))
            fig_debt.add_trace(go.Bar(x=fin_df["Year"], y=fin_df["Cash & Equivalents ($B)"], name="Cash ($B)", marker_color="#5236AB"))
            fig_debt.add_trace(
                go.Scatter(
                    x=fin_df["Year"],
                    y=fin_df["Operating Margin (%)"],
                    name="Operating Margin (%)",
                    yaxis="y2",
                    mode="lines+markers",
                    line=dict(color="#9B185A", width=3),
                )
            )
            fig_debt.update_layout(
                title="Balance Sheet De-leveraging & Operating Margin (%)",
                barmode="group",
                yaxis=dict(title="USD Billions"),
                yaxis2=dict(title="Margin (%)", overlaying="y", side="right"),
                height=360,
                margin=dict(l=10, r=10, t=40, b=10),
                plot_bgcolor="#FFFFFF",
                paper_bgcolor="#FFFFFF",
                font=dict(color="#1A1A1A"),
            )
            st.plotly_chart(fig_debt, use_container_width=True)

        with st.expander("📋 View Full Financial Summary Table (Excluding 2021)", expanded=True):
            st.dataframe(fin_df.set_index("Year").T.style.format("{:.2f}"), use_container_width=True)


# =============================================================================
# TAB 2: CORPORATE RISK MAPPING & HEDGING SCHEME DESIGN
# =============================================================================
with tab2:
    st.subheader("🛡️ CGI Corporate Risk Mapping & Treasury Hedging Scheme Design")
    st.markdown(
        "Following institutional risk-mapping frameworks (analogous to Lufthansa Group's risk architecture), "
        "exposures are categorized by probability and EBIT damage. Financial risks (Fuel and FX) are quantifiable and hedgeable via "
        "derivatives, whereas interest-rate risk is managed through a balanced net-fix structure."
    )

    st.markdown("#### 1. Top-Risk Matrix & Exposure Classification")
    risk_matrix_data = [
        ["Risk Category", "Specific Risk Factor", "Probability", "EBIT Damage / Impact", "Mitigation & Hedging Instrument"],
        ["Financial / Market", "Fuel Prices (Crude/Kerosene)", "High (≥30%)", "Critical (≥€650m)", "12-Month Zero-Cost Collar (Long Call, Short Put)"],
        ["Financial / Market", "Exchange Rate (USD Focus)", "High (≥30%)", "Substantial (€325-650m)", "1-year EUR/USD Plain-Vanilla Forwards (80% ratio)"],
        ["Financial / Market", "Interest Rate Risk", "Low (<20%)", "Moderate (€162.5-325m)", "Net-Fix Strategy (Balancing floating assets & liabilities)"],
        ["Operational", "Labor Disputes / Strikes", "High (≥30%)", "Substantial (€325-650m)", "Process controls & labor negotiations (Unhedgable via fin. instruments)"],
        ["ESG / Regulatory", "Carbon Pricing (EU ETS / SAF)", "High (≥30%)", "Moderate (€162.5-325m)", "Transition programs & SAF blending (Credit/ESG adjustment)"],
    ]
    st.table(pd.DataFrame(risk_matrix_data[1:], columns=risk_matrix_data[0]))

    st.markdown("---")
    st.subheader("2. Interest Rate Risk Hedging Strategy (Net-Fix Approach)")
    i_col1, i_col2 = st.columns(2)
    with i_col1:
        st.markdown(
            """
            - **Net-Fix Strategy Mechanics:** Lufthansa and major network carriers maintain a balanced structure between floating-rate assets and liabilities to neutralize short-term interest rate sensitivity.
            - **Post-Hedge Stability:** Long-term debt is issued at fixed rates or converted via cross-currency interest rate swaps (pay-fixed / receive-floating).
            - **Minimal P&L Impact:** After hedging, a $\pm 100\text{ bps}$ interest rate shift impacts net income by only $\approx \pm \text{€26m}$, rendering interest rate risk immaterial.
            """
        )
    with i_col2:
        st.markdown(
            """
            - **Floating Assets vs. Liabilities:** Short-term money market securities and cash equivalents provide natural offsets to floating borrowings.
            - **Strategic Liquidity Buffer:** A controlled positive difference between floating assets and post-hedge floating debt accounts for timing differences and liquidity reserves.
            """
        )

    st.markdown("---")
    st.subheader("3. Underlyings Distributional & Tail-Risk Analysis (FX vs. Crude Oil)")
    u_col1, u_col2 = st.columns(2)
    with u_col1:
        st.markdown("#### 💱 EUR / USD Exchange Rate Profile")
        st.markdown(
            """
            - **Behavior:** Near-normal distribution with low volatility ($\sim 7.19\%$) and near-symmetric returns.
            - **Valuation / Instrument:** Priced via Interest Rate Parity ($F = S_0 \cdot e^{(r_f - r_d)T}$ with zero premium).
            - **Hedge Implementation:** 1-year plain-vanilla EUR/USD forwards covering **80% of net exposure**.
            - **Simulation Outcome:** Reduces cash flow volatility by **80%** (from €622m to €124m) and 95% VaR by **93%** (from €912m to €66m).
            """
        )
    with u_col2:
        st.markdown("#### 🛢️ Crude Oil / Fuel Price Profile")
        st.markdown(
            """
            - **Behavior:** Extreme positive skewness ($1.83$) and heavy kurtosis ($17.47$), reflecting severe tail risk and energy shocks. Annualized volatility $\sim 44.44\%$.
            - **Valuation / Instrument:** Black-Scholes option pricing. A **12-month zero-cost collar** (buying OTM call, selling OTM put) is chosen over a long call to avoid high upfront premium outlays while capping extreme cost spikes.
            - **Hedge Implementation:** Applied to **70% of annual fuel requirements**.
            - **Simulation Outcome:** Reduces fuel cost volatility by **60%** (from €2,617m to €1,057m) and 95% VaR by **30%** (from €11,449m to €7,999m).
            """
        )

    st.markdown("---")
    st.subheader("4. Strategic Treasury Takeaways for Client Meeting Prep")
    st.markdown(
        """
        - **Combined Hedging Effectiveness:** Implementing 80% FX forwards and a 70% fuel collar effectively neutralizes earnings variance under macroeconomic and geopolitical stress.
        - **Asymmetric Protection:** The zero-cost collar protects against severe energy spikes while retaining downside participation up to the put strike floor.
        - **Stakeholder Confidence:** Aligns Delta with top-tier airline industry standards (hedge ratios between 70% and 90%), stabilizing earnings and supporting an investment-grade credit profile.
        """
    )


# =============================================================================
# TAB 3: DCF VALUATION, MULTIPLES & CLIENT EXPORT
# =============================================================================
with tab3:
    latest_fin = fin_df.iloc[-1]
    bridge = dcf_results["valuation_bridge"]
    wacc_details = dcf_results["wacc_details"]

    exec_summary_text = (
        f"Delta Air Lines (DAL) demonstrates strong operational resilience (excluding 2021 pandemic recovery distortions), "
        f"generating ${latest_fin['Revenue ($B)']:.2f}B in annual revenue, ${latest_fin['EBITDA ($B)']:.2f}B in EBITDA "
        f"({latest_fin['EBITDA Margin (%)']:.1f}% margin), and ${latest_fin['Free Cash Flow ($B)']:.2f}B in Free Cash Flow. "
        f"Net Debt has been reduced to ${latest_fin['Net Debt ($B)']:.2f}B ({latest_fin['Net Debt / EBITDA (x)']:.2f}x Net Debt/EBITDA). "
        f"Trading at {multiples['Trailing P/E (x)']}x trailing P/E and {multiples['EV / EBITDA (x)']}x EV/EBITDA, our 5-year DCF model "
        f"(WACC: {wacc_details['Calculated WACC (%)']:.2f}%, Terminal Growth: {wacc_details['Terminal Growth Rate (%)']:.2f}%) "
        f"implies an intrinsic equity value of ${bridge['Implied Share Price ($)']:.2f}/share "
        f"({bridge['Implied Upside / Downside (%)']:+.1f}% vs. current market price)."
    )

    st.subheader("1. Executive Performance Summary")
    st.info(exec_summary_text)

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
            color_discrete_sequence=["#5236AB", "#E31937"],
        )
        fig_fcf.update_layout(
            height=270,
            margin=dict(l=10, r=10, t=35, b=10),
            plot_bgcolor="#FFFFFF",
            paper_bgcolor="#FFFFFF",
            font=dict(color="#1A1A1A"),
        )
        st.plotly_chart(fig_fcf, use_container_width=True)

    st.subheader("3. Actionable Treasury Recommendations")
    hedging_recs = [
        {
            "title": "12-Month Zero-Cost Crude & Jet Fuel Collars (70% Ratio)",
            "detail": "Implement zero-cost collars (buying OTM call options funded by selling OTM put options) to cap jet fuel spikes while preserving downside participation up to the put floor.",
        },
        {
            "title": "1-Year EUR/USD Plain-Vanilla Forwards (80% Ratio)",
            "detail": "Establish staggered 12-month FX forward contracts covering 80% of forecasted international operational exposures to suppress linear FX volatility.",
        },
        {
            "title": "Net-Fix Interest Rate Management",
            "detail": "Maintain balanced floating assets and liabilities via cross-currency interest rate swaps to ensure rate shifts impact net income by no more than ±€26m.",
        },
    ]

    for rec in hedging_recs:
        st.markdown(f"- **{rec['title']}:** {rec['detail']}")

    st.markdown("---")

    st.subheader("4. Export Executive PDF & Prepare Client Meeting Email")

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
                f"- Key Pitch Angles: Risk Mapping Matrix, Net-Fix Interest Rate Model, 80% FX Forwards & 70% Fuel Collars"
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