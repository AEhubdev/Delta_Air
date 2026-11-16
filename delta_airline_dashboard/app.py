import html
import json
import os
from email.message import EmailMessage
from urllib.parse import quote

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

from data_engine import (
    COMPANIES,
    fetch_company_data,
    extract_financial_summary,
    extract_valuation_multiples,
    run_dcf_model,
)
from pdf_generator import generate_executive_pdf


def build_mailto_url(recipient: str, company_name: str, summary_highlights: str) -> str:
    """Build a mailto link that opens in the viewer's local mail application."""
    subject = f"Client Meeting Prep: {company_name} - Financial, Risk & Hedging Briefing"
    body = (
        f"Hi Team,\n\nAhead of our upcoming client meeting with {company_name}, please find the "
        "latest financial analysis, DCF valuation summary, and corporate hedging strategy briefing attached.\n\n"
        f"Key Highlights:\n{summary_highlights}\n\n"
        "Please review the attached PDF prior to our call.\n\nBest regards,\nCorporate & Transaction Banking Sales"
    )
    return f"mailto:{quote(recipient.strip(), safe='@,;')}?subject={quote(subject)}&body={quote(body)}"


def build_email_eml(
    pdf_bytes: bytes,
    recipient: str,
    company_name: str,
    summary_highlights: str,
    filename: str,
) -> bytes:
    """Build a downloadable email draft with the report attached."""
    message = EmailMessage()
    if recipient.strip():
        message["To"] = recipient.strip()
    message["Subject"] = f"Client Meeting Prep: {company_name} - Financial, Risk & Hedging Briefing"
    message.set_content(
        f"Hi Team,\n\nAhead of our upcoming client meeting with {company_name}, please find the "
        "latest financial analysis, DCF valuation summary, and corporate hedging strategy briefing attached.\n\n"
        f"Key Highlights:\n{summary_highlights}\n\n"
        "Please review the attached PDF prior to our call.\n\nBest regards,\nCorporate & Transaction Banking Sales"
    )
    message.add_attachment(pdf_bytes, maintype="application", subtype="pdf", filename=filename)
    return message.as_bytes()

st.set_page_config(
    page_title="CGI Client Advisory Dashboard",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="locked",
)

# Robust High-Contrast CGI Styling with Custom Table and Card Classes
st.markdown(
    """
    <style>
    /* Global App Background & Typography */
    .stApp {
        background-color: #F8F9FA !important;
        color: #1A1A1A !important;
    }

    p, span, label, .stMarkdown, li, .streamlit-expanderHeader {
        color: #1A1A1A !important;
    }

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

    /* CGI White Accent Card */
    .cgi-card {
        background-color: #FFFFFF !important;
        border: 1px solid #E2E8F0;
        border-top: 4px solid #E31937;
        padding: 18px;
        border-radius: 8px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04);
        color: #1A1A1A !important;
        margin-bottom: 1rem;
    }
    .cgi-card b, .cgi-card h4, .cgi-card p {
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

    /* CLEAN WHITE TABLES STYLING (Guarantees white background and dark text) */
    .clean-table {
        width: 100%;
        border-collapse: collapse;
        background-color: #FFFFFF !important;
        color: #1A1A1A !important;
        border: 1px solid #E2E8F0;
        border-radius: 8px;
        overflow: hidden;
        margin-bottom: 1rem;
        box-shadow: 0 2px 6px rgba(0,0,0,0.02);
    }
    .clean-table th {
        background-color: #5236AB !important;
        color: #FFFFFF !important;
        padding: 10px 14px;
        text-align: left;
        font-weight: 600;
        border: none !important;
    }
    .clean-table td {
        background-color: #FFFFFF !important;
        color: #1A1A1A !important;
        padding: 9px 14px;
        border-bottom: 1px solid #EDF2F7;
        border-top: none !important;
    }
    .clean-table tr:hover td {
        background-color: #F8F9FA !important;
    }

    /* Expander Styling */
    div[data-testid="stExpander"] {
        background-color: #FFFFFF !important;
        border: 1px solid #E2E8F0 !important;
        border-radius: 8px;
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

    /* Floating AI assistant: keyed Streamlit containers become st-key-* classes. */
    .st-key-ai_chat_launcher {
        position: fixed;
        right: 1.25rem;
        bottom: 1.1rem;
        z-index: 10000;
        width: 215px;
    }
    .st-key-ai_chat_launcher button {
        min-height: 3.2rem;
        border-radius: 999px !important;
    }
    .st-key-ai_chat_panel {
        position: fixed;
        right: 1.25rem;
        bottom: 5.2rem;
        z-index: 9999;
        width: min(520px, calc(100vw - 2rem));
        max-height: calc(100vh - 7rem);
        overflow-y: auto;
        background: #FFFFFF;
        border: 1px solid #D8D4E5;
        border-top: 4px solid #E31937;
        border-radius: 14px;
        padding: 0.8rem 1rem 1rem;
        box-shadow: 0 12px 36px rgba(23, 17, 43, 0.24);
    }
    .st-key-ai_chat_panel [data-testid="stVerticalBlock"] { gap: 0.45rem; }
    .st-key-ai_chat_history {
        max-height: 390px;
        overflow-y: auto;
        border: 1px solid #E2E8F0;
        border-radius: 8px;
        padding: 0.45rem 0.65rem;
    }
    @media (max-width: 540px) {
        .st-key-ai_chat_launcher { right: 0.65rem; bottom: 0.65rem; }
        .st-key-ai_chat_panel {
            right: 0.5rem;
            bottom: 4.8rem;
            width: calc(100vw - 1rem);
            max-height: calc(100vh - 6rem);
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(ttl=3600, show_spinner="Fetching live company and benchmark data...")
def load_all_data(ticker: str, benchmarks: tuple[str, ...], currency: str, exclude_years: tuple[str, ...]):
    raw = fetch_company_data(ticker, benchmarks, currency)
    fin_df = extract_financial_summary(raw, exclude_years=exclude_years)
    multiples = extract_valuation_multiples(raw, fin_df)
    return raw, fin_df, multiples

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
    selected_company = st.selectbox("Company", options=list(COMPANIES.keys()), key="company_selector")
    company_config = COMPANIES[selected_company]
    ticker_symbol = company_config["ticker"]
    currency_code = company_config["currency"]
    currency_symbol = company_config["currency_symbol"]
    st.caption(f"Selected client: {selected_company}")
    st.markdown("### ⚙️ DCF Model Assumptions")
    rev_growth = st.slider("5Y Avg. Revenue Growth (%)", 1.0, 12.0, 4.5, 0.5) / 100.0
    ebit_margin = st.slider("Target Operating (EBIT) Margin (%)", 5.0, 18.0, 10.5, 0.5) / 100.0
    tax_rate = st.slider("Effective Tax Rate (%)", 15.0, 30.0, 23.0, 1.0) / 100.0
    capex_pct = st.slider("CapEx (% of Revenue)", 4.0, 12.0, 7.5, 0.5) / 100.0
    rf_rate = st.slider("Risk-Free Rate Reference (%)", 2.5, 6.5, 4.2, 0.1, help="Set this to the relevant 10-year sovereign yield for the selected reporting currency.") / 100.0
    erp = st.slider("Equity Risk Premium (%)", 3.5, 7.5, 5.0, 0.25) / 100.0
    tgr = st.slider("Terminal Growth Rate (%)", 1.0, 4.0, 2.5, 0.25) / 100.0

    st.markdown("---")
    st.markdown("### 📧 Sales Meeting Prep")
    recipient_email = st.text_input("Recipient Email (Optional)", placeholder="sales.team@cgi.com")
    if st.button("🔄 Refresh Live yfinance Data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

try:
    raw_data, fin_df, multiples = load_all_data(
        ticker_symbol,
        tuple(company_config["benchmarks"]),
        currency_code,
        tuple(company_config["exclude_years"]),
    )
except Exception as exc:
    st.error(f"Error retrieving data for {selected_company}: {exc}")
    st.stop()

info = raw_data["info"]
company_name = info.get("longName") or selected_company.split(" (")[0]
company_label = f"{company_name} ({ticker_symbol})"
currency_symbol = {"USD": "$", "EUR": "€", "GBP": "£", "CHF": "CHF ", "CAD": "C$", "JPY": "¥"}.get(raw_data.get("currency", currency_code), currency_symbol)

for data_warning in raw_data.get("warnings", []):
    st.warning(data_warning)

if fin_df.empty or float(fin_df.iloc[-1]["Revenue ($B)"]) <= 0:
    st.error(
        f"Yahoo Finance did not return usable annual or trailing revenue for {company_label}. "
        "Choose another company or refresh the data; the DCF dashboard needs a revenue base."
    )
    st.stop()

if str(fin_df.iloc[-1]["Year"]).upper() == "TTM":
    st.info(
        f"Annual statements were unavailable for {company_label}. Financials and DCF use Yahoo Finance trailing-twelve-month quote data; "
        "validate these figures before using them with a client."
    )

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
        <div class='cgi-banner-title'>💼 {html.escape(company_label)}</div>
        <div class='cgi-banner-sub'>
            CGI Financial & Treasury Advisory | Company overview, risk discussion, DCF valuation & client preparation &bull;
            {currency_code} reporting currency &bull; Updated: {html.escape(raw_data['fetched_at'])}
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

k1, k2, k3, k4, k5, k6 = st.columns(6)
k1.metric("Share Price", f"{currency_symbol}{multiples['Current Share Price ($)']:.2f}")
k2.metric("Market Cap", f"{currency_symbol}{multiples['Market Cap ($B)']:.2f}B")
k3.metric("Enterprise Value", f"{currency_symbol}{multiples['Enterprise Value ($B)']:.2f}B")
k4.metric("EV / EBITDA", f"{multiples['EV / EBITDA (x)']}x")
k5.metric("Trailing / Fwd P/E", f"{multiples['Trailing P/E (x)']}x / {multiples['Forward P/E (x)']}x")
k6.metric(
    "DCF Implied Price",
    f"{currency_symbol}{dcf_results['valuation_bridge']['Implied Share Price ($)']:.2f}",
    f"{dcf_results['valuation_bridge']['Implied Upside / Downside (%)']:+.1f}%",
)

st.markdown("<br>", unsafe_allow_html=True)

tab1, tab2, tab3 = st.tabs(
    [
        "📊 Company Overview & Financials",
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
                <b>Headquarters:</b> {html.escape(str(info.get('city') or 'Not reported'))}, {html.escape(str(info.get('country') or ''))}<br>
            <b>Employees:</b> {f"{info['fullTimeEmployees']:,}" if info.get('fullTimeEmployees') else 'Not reported'}<br>
            <b>Sector:</b> {html.escape(str(info.get('sector') or 'Not reported'))}<br>
            <b>Industry:</b> {html.escape(str(info.get('industry') or 'Not reported'))}<br>
            <b>52W Range:</b> {currency_symbol}{info.get('fiftyTwoWeekLow', 0) or 0:.2f} – {currency_symbol}{info.get('fiftyTwoWeekHigh', 0) or 0:.2f}<br>
            <b>Consensus:</b> {html.escape(str(info.get('recommendationKey') or 'Not reported').upper())}
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.subheader(f"2. Relative Market Performance ({company_label} vs. {', '.join(company_config['benchmark_names'])})")
    bench_df = raw_data["benchmarks"].dropna()
    if not bench_df.empty:
        norm_bench = (bench_df / bench_df.iloc[0]) * 100
        fig_bench = px.line(
            norm_bench,
            labels={"value": "Normalized Return (Base = 100)", "Date": "Date", "variable": "Ticker"},
            color_discrete_map={ticker_symbol: "#E31937", **dict(zip(company_config["benchmarks"], ["#5236AB", "#9B185A"]))},
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

    exclude_note = f" (excluding {', '.join(company_config['exclude_years'])})" if company_config["exclude_years"] else ""
    st.subheader(f"3. Multi-Year Financial Performance{exclude_note}")
    if not fin_df.empty:
        c_fin1, c_fin2 = st.columns(2)

        with c_fin1:
            fig_rev = go.Figure()
            fig_rev.add_trace(go.Bar(x=fin_df["Year"], y=fin_df["Revenue ($B)"], name=f"Revenue ({currency_code}B)", marker_color="#5236AB"))
            fig_rev.add_trace(go.Bar(x=fin_df["Year"], y=fin_df["EBITDA ($B)"], name=f"EBITDA ({currency_code}B)", marker_color="#9B185A"))
            fig_rev.add_trace(go.Bar(x=fin_df["Year"], y=fin_df["Free Cash Flow ($B)"], name=f"Free Cash Flow ({currency_code}B)", marker_color="#E31937"))
            fig_rev.update_layout(
                title=f"Revenue, EBITDA & Free Cash Flow ({currency_code}B)",
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
            fig_debt.add_trace(go.Bar(x=fin_df["Year"], y=fin_df["Total Debt ($B)"], name=f"Total Debt ({currency_code}B)", marker_color="#E31937"))
            fig_debt.add_trace(go.Bar(x=fin_df["Year"], y=fin_df["Cash & Equivalents ($B)"], name=f"Cash ({currency_code}B)", marker_color="#5236AB"))
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
                title=f"Balance Sheet & Operating Margin (%)",
                barmode="group",
                yaxis=dict(title=f"{currency_code} Billions"),
                yaxis2=dict(title="Margin (%)", overlaying="y", side="right"),
                height=360,
                margin=dict(l=10, r=10, t=40, b=10),
                plot_bgcolor="#FFFFFF",
                paper_bgcolor="#FFFFFF",
                font=dict(color="#1A1A1A"),
            )
            st.plotly_chart(fig_debt, use_container_width=True)

        with st.expander(f"📋 View Full Financial Summary Table{exclude_note}", expanded=True):
            display_fin_df = fin_df.copy()
            display_fin_df.columns = [c.replace("($B)", f"({currency_code}B)") for c in display_fin_df.columns]
            fin_html = display_fin_df.set_index("Year").T.style.format("{:.2f}").to_html(classes="clean-table")
            st.markdown(fin_html, unsafe_allow_html=True)


# =============================================================================
# TAB 2: CORPORATE RISK MAPPING & HEDGING SCHEME DESIGN
# =============================================================================
with tab2:
    sector = company_config["risk_profile"]
    risk_profiles = {
        "airlines": [
            ["Energy and fuel", "Fuel sensitivity, cost disclosures, hedge policy", "How are fuel assumptions set against capacity plans?"],
            ["Foreign exchange", "Currency mix of revenue, costs, debt and cash", "Which currency mismatches matter most?"],
            ["Rates and liquidity", "Debt maturities, fixed/floating mix, liquidity", "What rate shock could change the funding plan?"],
            ["Operations and labor", "Fleet availability, labor and supplier dependencies", "Which disruption would most affect the next 12 months?"],
            ["Climate and regulation", "Carbon costs, fleet investment, transition disclosures", "How are transition costs reflected in capital plans?"],
        ],
        "consumer_apparel": [
            ["Demand and inventory", "Sell-through, stock levels, markdowns, channel mix", "Where could demand or excess stock pressure margin?"],
            ["Sourcing and logistics", "Supplier concentration, lead times, freight", "Which sourcing dependency could disrupt availability or cost?"],
            ["Foreign exchange", "Revenue and sourcing currency mix, hedge disclosures", "How do forecast exposures compare with settlement flows?"],
            ["Brand and channels", "Retail, wholesale, e-commerce, returns", "Which channel shifts are changing cash conversion?"],
            ["Regulation and sustainability", "Traceability, materials, labor and environmental rules", "Which compliance change affects products or suppliers first?"],
        ],
        "automotive": [
            ["Technology transition", "EV mix, R&D, model pipeline, plant utilization", "Which technology assumption matters most to the investment plan?"],
            ["Supply chain", "Battery/component dependencies, suppliers, lead times", "Where could a supplier constraint affect production?"],
            ["FX and commodities", "Sales/production currency mix, metals and battery inputs", "Which exposures remain after natural offsets?"],
            ["Rates and financing", "Funding costs, customer finance, affordability", "How could funding costs affect demand and margins?"],
            ["Regulation and recalls", "Emissions rules, safety, warranty and recall provisions", "Which event could shift cash needs?"],
        ],
        "industrials": [
            ["Orders and execution", "Backlog, project milestones, contract terms and margins", "Where could delivery timing affect cash conversion?"],
            ["Inputs and suppliers", "Materials, energy, supplier concentration and lead times", "Which input constraint could change bid economics?"],
            ["Foreign exchange", "Order book and production footprint by currency", "How are long-dated contract exposures refreshed?"],
            ["Rates and investment", "Debt maturities, capex and customer financing", "Which investment plans are most rate-sensitive?"],
            ["Cyber and resilience", "Control systems, critical sites and service obligations", "What would a critical site disruption mean for delivery?"],
        ],
        "software": [
            ["Recurring revenue", "Subscription growth, renewals, customer concentration", "Which renewal assumption drives the forecast most?"],
            ["Cloud and AI investment", "Compute commitments, infrastructure cost, product investment", "How do usage growth and infrastructure costs affect margins?"],
            ["Cybersecurity and privacy", "Security incidents, data handling, service availability", "Which control gap carries the greatest financial impact?"],
            ["Talent and execution", "Critical skills, compensation, product dependencies", "Where could talent constraints delay product priorities?"],
            ["FX and rates", "Global revenue/cost mix, cash and funding needs", "How do FX and rates affect cash generation?"],
        ],
    }
    risk_rows = risk_profiles.get(sector, risk_profiles["industrials"])
    st.subheader(f"🛡️ {company_label}: Risk Mapping & Treasury Discussion")
    st.info("Sector-based meeting hypotheses for validation with the client. These are not company-specific findings. Confirm exposures, materiality and controls with approved client data before presenting them as facts.")
    st.markdown("#### Risk areas, evidence to inspect, and client discovery questions")
    risk_df = pd.DataFrame(
        [[area, evidence, question, "Validate exposure, then assess scenarios and controls"] for area, evidence, question in risk_rows],
        columns=["Potential exposure", "Evidence to inspect", "Client discovery question", "Levers to explore"],
    )
    st.markdown(risk_df.to_html(classes="clean-table", index=False), unsafe_allow_html=True)
    st.markdown("---")
    st.subheader("Call preparation priorities")
    p1, p2, p3 = st.columns(3)
    with p1:
        st.markdown("**1 · Establish the baseline**")
        st.write("Confirm the approved forecast, currency mix, funding plan and risk policy with the client.")
    with p2:
        st.markdown("**2 · Quantify sensitivities**")
        st.write("Use agreed scenarios to connect market or operational changes to cash flow, liquidity and investment capacity.")
    with p3:
        st.markdown("**3 · Match options to policy**")
        st.write("Discuss instruments and controls after confirming exposure, objectives, limits and governance.")
    st.markdown("#### Questions to take into the client call")
    for _, _, question in risk_rows:
        st.markdown(f"- {question}")
    st.caption("No risk likelihood, loss estimate or hedge ratio is asserted because this dashboard does not contain client exposure data.")


# =============================================================================
# TAB 3: DCF VALUATION, MULTIPLES & CLIENT EXPORT
# =============================================================================
with tab3:
    latest_fin = fin_df.iloc[-1]
    bridge = dcf_results["valuation_bridge"]
    wacc_details = dcf_results["wacc_details"]

    exec_summary_text = (
        f"{company_label}: in the latest available financial period ({latest_fin['Year']}), reported revenue was "
        f"{currency_symbol}{latest_fin['Revenue ($B)']:.2f}B, EBITDA was {currency_symbol}{latest_fin['EBITDA ($B)']:.2f}B "
        f"({latest_fin['EBITDA Margin (%)']:.1f}% margin), and free cash flow was "
        f"{currency_symbol}{latest_fin['Free Cash Flow ($B)']:.2f}B. Net debt was "
        f"{currency_symbol}{latest_fin['Net Debt ($B)']:.2f}B ({latest_fin['Net Debt / EBITDA (x)']:.2f}x net debt/EBITDA). "
        f"The 5-year DCF scenario uses a {wacc_details['Calculated WACC (%)']:.2f}% WACC and "
        f"{wacc_details['Terminal Growth Rate (%)']:.2f}% terminal growth; it indicates a share value of "
        f"{currency_symbol}{bridge['Implied Share Price ($)']:.2f} ({bridge['Implied Upside / Downside (%)']:+.1f}% vs. the current price). "
        "Use this model output as a discussion scenario and validate its assumptions before client use."
    )

    st.subheader("1. Executive Performance Summary")
    # Replaced st.info with clean CGI white card to eliminate dark blue text background
    st.markdown(
        f"""
        <div class='cgi-card' style='border-left: 5px solid #5236AB;'>
            <h4 style="margin-top: 0; color: #5236AB; font-size: 1.05rem; margin-bottom: 8px;">📋 Executive Summary & Strategic Rationale</h4>
            <p style="color: #1A1A1A; margin-bottom: 0; line-height: 1.6;">{html.escape(exec_summary_text)}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.subheader("2. Trading Multiples & Discounted Cash Flow (DCF) Valuation")
    m_col1, m_col2, m_col3 = st.columns([1.1, 1.2, 1.2])

    with m_col1:
        st.markdown("**📊 Market & Trading Multiples**")
        display_multiples = {
            key.replace("($B)", f"({currency_code}B)").replace("($)", f"({currency_code})"): value
            for key, value in multiples.items()
        }
        mult_df = pd.DataFrame(list(display_multiples.items()), columns=["Multiple / Metric", "Value"])
        st.markdown(mult_df.to_html(classes="clean-table", index=False), unsafe_allow_html=True)

    with m_col2:
        st.markdown("**🧮 CAPM & WACC Breakdown**")
        wacc_df = pd.DataFrame(list(wacc_details.items()), columns=["WACC Component", "Value"])
        st.markdown(wacc_df.to_html(classes="clean-table", index=False), unsafe_allow_html=True)

    with m_col3:
        st.markdown("**🌉 Enterprise to Equity Value Bridge**")
        display_bridge = {
            key.replace("($B)", f"({currency_code}B)").replace("($)", f"({currency_code})"): value
            for key, value in bridge.items()
        }
        bridge_df = pd.DataFrame(list(display_bridge.items()), columns=["Valuation Step", "Value"])
        st.markdown(bridge_df.to_html(classes="clean-table", index=False), unsafe_allow_html=True)

    st.markdown(f"**📈 5-Year Projected Unlevered Free Cash Flow (FCFF) Schedule ({currency_code}B)**")
    projection_display_df = dcf_results["projections"].copy()
    projection_display_df.columns = [c.replace("($B)", f"({currency_code}B)") for c in projection_display_df.columns]
    proj_display = projection_display_df.set_index("Year").T
    st.markdown(proj_display.style.format("{:.2f}").to_html(classes="clean-table"), unsafe_allow_html=True)

    s_col1, s_col2 = st.columns([1.2, 1])
    with s_col1:
        st.markdown(f"**🎯 Implied Share Price Sensitivity: WACC vs. Terminal Growth Rate ({currency_code})**")
        st.markdown(dcf_results["sensitivity"].style.format(f"{currency_symbol}{{:.2f}}").to_html(classes="clean-table"), unsafe_allow_html=True)
    with s_col2:
        projection_chart_df = dcf_results["projections"].copy()
        projection_chart_df.columns = [c.replace("($B)", f"({currency_code}B)") for c in projection_chart_df.columns]
        fig_fcf = px.bar(
            projection_chart_df,
            x="Year",
            y=[f"Unlevered FCF ({currency_code}B)", f"PV of FCF ({currency_code}B)"],
            barmode="group",
            title=f"Projected FCFF vs. Present Value ({currency_code}B)",
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

    st.subheader("3. Treasury discussion points to validate")
    hedging_recs = [
        {
            "title": f"Validate {area}",
            "detail": f"{question} Confirm exposure, policy limits and approved controls before assessing any treasury instrument.",
        }
        for area, _, question in risk_rows[:3]
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
        currency_symbol=currency_symbol,
        currency_code=currency_code,
        company_name=company_label,
        exclude_years=company_config["exclude_years"],
    )

    exp_col1, exp_col2 = st.columns(2)

    pdf_filename = f"{ticker_symbol.replace('.', '_')}_Executive_Briefing.pdf"
    highlights = (
        f"- Current Price: {currency_symbol}{multiples['Current Share Price ($)']:.2f} | DCF scenario: "
        f"{currency_symbol}{bridge['Implied Share Price ($)']:.2f} ({bridge['Implied Upside / Downside (%)']:+.1f}%)\n"
        f"- Revenue: {currency_symbol}{latest_fin['Revenue ($B)']:.2f}B | EBITDA: {currency_symbol}{latest_fin['EBITDA ($B)']:.2f}B | "
        f"FCF: {currency_symbol}{latest_fin['Free Cash Flow ($B)']:.2f}B\n"
        f"- Net Debt / EBITDA: {latest_fin['Net Debt / EBITDA (x)']:.2f}x | EV/EBITDA: {multiples['EV / EBITDA (x)']}x\n"
        f"- Discussion: {', '.join(area for area, _, _ in risk_rows[:3])}"
    )
    mailto_url = build_mailto_url(
        recipient=recipient_email,
        company_name=company_label,
        summary_highlights=highlights,
    )
    eml_bytes = build_email_eml(
        pdf_bytes=pdf_bytes,
        recipient=recipient_email,
        company_name=company_label,
        summary_highlights=highlights,
        filename=pdf_filename,
    )

    with exp_col1:
        st.download_button(
            label="📥 Download Stylized Executive PDF Report",
            data=pdf_bytes,
            file_name=pdf_filename,
            mime="application/pdf",
            use_container_width=True,
        )

    with exp_col2:
        st.link_button(
            "📧 Open email draft in your default mail app",
            mailto_url,
            type="primary",
            use_container_width=True,
        )
        st.download_button(
            label="📎 Download Outlook draft with PDF attached (.eml)",
            data=eml_bytes,
            file_name=f"{ticker_symbol.replace('.', '_')}_Meeting_Email.eml",
            mime="message/rfc822",
            use_container_width=True,
        )
        st.caption(
            "The email link opens a mail app on your device. To keep the report attached, "
            "download and open the .eml draft; or download the PDF and attach it to the email yourself."
        )


# =============================================================================
# FLOATING, COMPANY-GROUNDED AI CHAT
# =============================================================================
if st.session_state.get("ai_chat_company") != ticker_symbol:
    st.session_state["ai_chat_company"] = ticker_symbol
    st.session_state["ai_chat_messages"] = []

if "ai_chat_open" not in st.session_state:
    st.session_state["ai_chat_open"] = False


def get_openai_settings():
    api_key = os.getenv("OPENAI_API_KEY", "")
    model = os.getenv("OPENAI_MODEL", "gpt-6-luna")
    try:
        api_key = st.secrets.get("OPENAI_API_KEY", api_key)
        model = st.secrets.get("OPENAI_MODEL", model)
    except Exception:
        # Streamlit secrets are optional; PyCharm environment variables also work.
        pass
    return api_key, model


latest_chat_fin = fin_df.iloc[-1] if not fin_df.empty else None
historical_chat_fin = [
    {
        "year": str(row["Year"]),
        "revenue_billions": round(float(row["Revenue ($B)"]), 2),
        "ebitda_billions": round(float(row["EBITDA ($B)"]), 2),
        "free_cash_flow_billions": round(float(row["Free Cash Flow ($B)"]), 2),
        "net_debt_billions": round(float(row["Net Debt ($B)"]), 2),
        "operating_margin_percent": round(float(row["Operating Margin (%)"]), 2),
    }
    for _, row in fin_df.iterrows()
]
benchmark_performance = {}
for benchmark_ticker in raw_data["benchmarks"].columns:
    benchmark_prices = raw_data["benchmarks"][benchmark_ticker].dropna()
    if len(benchmark_prices) > 1 and benchmark_prices.iloc[0] != 0:
        benchmark_performance[benchmark_ticker] = round(
            float((benchmark_prices.iloc[-1] / benchmark_prices.iloc[0] - 1) * 100), 2
        )
chat_context = {
    "selected_company": company_label,
    "ticker": ticker_symbol,
    "sector": info.get("sector"),
    "industry": info.get("industry"),
    "reporting_currency": currency_code,
    "data_timestamp": raw_data.get("fetched_at"),
    "latest_financial_year": latest_chat_fin["Year"] if latest_chat_fin is not None else None,
    "latest_financials_billions": {
        "revenue": round(float(latest_chat_fin["Revenue ($B)"]), 2),
        "ebitda": round(float(latest_chat_fin["EBITDA ($B)"]), 2),
        "free_cash_flow": round(float(latest_chat_fin["Free Cash Flow ($B)"]), 2),
        "net_debt": round(float(latest_chat_fin["Net Debt ($B)"]), 2),
    } if latest_chat_fin is not None else {},
    "historical_financials_billions": historical_chat_fin,
    "benchmark_price_return_percent_over_downloaded_period": benchmark_performance,
    "market_and_valuation": {
        "share_price": multiples["Current Share Price ($)"],
        "market_cap_billions": multiples["Market Cap ($B)"],
        "ev_ebitda": multiples["EV / EBITDA (x)"],
        "dcf_scenario_share_value": dcf_results["valuation_bridge"]["Implied Share Price ($)"],
        "dcf_scenario_upside_percent": dcf_results["valuation_bridge"]["Implied Upside / Downside (%)"],
        "dcf_wacc_percent": dcf_results["wacc_details"]["Calculated WACC (%)"],
        "dcf_terminal_growth_percent": dcf_results["wacc_details"]["Terminal Growth Rate (%)"],
    },
    "trading_multiples": {
        key.replace("($B)", f"({currency_code}B)").replace("($)", f"({currency_code})"): value
        for key, value in multiples.items()
    },
    "dcf_projection_billions": [
        {
            "year": str(row["Year"]),
            "revenue": round(float(row["Revenue ($B)"]), 2),
            "unlevered_free_cash_flow": round(float(row["Unlevered FCF ($B)"]), 2),
            "present_value_of_free_cash_flow": round(float(row["PV of FCF ($B)"]), 2),
        }
        for _, row in dcf_results["projections"].iterrows()
    ],
    "dcf_share_price_sensitivity": {
        str(index): {
            str(column): (round(float(value), 2) if pd.notna(value) else None)
            for column, value in row.items()
        }
        for index, row in dcf_results["sensitivity"].iterrows()
    },
    "sector_discussion_hypotheses": [
        {"potential_exposure": area, "evidence_to_validate": evidence, "discovery_question": question}
        for area, evidence, question in risk_rows
    ],
    "limitations": [
        "Financial and market data are provided by yfinance and can be incomplete or delayed.",
        "DCF outputs are scenario estimates based on user-adjustable assumptions, not forecasts or recommendations.",
        "Risk items are sector-level hypotheses; the dashboard contains no client exposure, hedge position or policy-limit data.",
    ],
}

with st.container(key="ai_chat_launcher"):
    launcher_text = "Close AI assistant" if st.session_state["ai_chat_open"] else "💬 Ask AI about this client"
    if st.button(launcher_text, key="toggle_ai_chat", use_container_width=True):
        st.session_state["ai_chat_open"] = not st.session_state["ai_chat_open"]

if st.session_state["ai_chat_open"]:
    with st.container(key="ai_chat_panel"):
        head_col, close_col = st.columns([5, 1])
        with head_col:
            st.markdown("#### CGI AI Client Assistant")
            st.caption(f"Grounded in the current {company_label} dashboard")
        with close_col:
            if st.button("✕", key="close_ai_chat", help="Close assistant"):
                st.session_state["ai_chat_open"] = False
                st.rerun()

        with st.container(key="ai_chat_history"):
            if not st.session_state["ai_chat_messages"]:
                st.info("Ask about the selected company’s reported financials, market multiples, DCF assumptions, or discussion prompts.")
                st.caption("Example: Summarize the DCF assumptions and give me three questions to validate on the call.")
            for chat_message in st.session_state["ai_chat_messages"]:
                with st.chat_message(chat_message["role"]):
                    st.markdown(chat_message["content"])

        with st.form("ai_chat_form", clear_on_submit=True):
            user_question = st.text_input("Your question", placeholder="Ask about the current dashboard…", label_visibility="collapsed")
            send_question = st.form_submit_button("Send", use_container_width=True)

        if send_question and user_question.strip():
            st.session_state["ai_chat_messages"].append({"role": "user", "content": user_question.strip()})
            api_key, model_name = get_openai_settings()
            if not api_key:
                st.session_state["ai_chat_messages"].append({
                    "role": "assistant",
                    "content": "To enable chat, set `OPENAI_API_KEY` in the PyCharm Run Configuration or in Streamlit `secrets.toml`. The key is read server-side and is not saved in this app's source code.",
                })
                st.rerun()

            system_instructions = (
                "You are CGI's client-call preparation assistant. Answer using only the dashboard snapshot supplied in this request. "
                "Separate reported dashboard values from DCF scenario outputs and sector discussion hypotheses. State when information is not present; "
                "never invent client exposures, hedge ratios, company facts, bank products, or current market facts. Offer concise, practical call-preparation help. "
                "Treat risk prompts as hypotheses to validate, and do not present them as confirmed risks or make investment recommendations."
            )
            chat_input = [{
                "role": "developer",
                "content": "Current dashboard snapshot (JSON):\n" + json.dumps(chat_context, ensure_ascii=False, default=str),
            }]
            chat_input.extend(st.session_state["ai_chat_messages"][-12:])
            try:
                from openai import OpenAI

                client = OpenAI(api_key=api_key, timeout=45.0, max_retries=1)
                with st.spinner("Preparing an answer from this dashboard…"):
                    response = client.responses.create(
                        model=model_name,
                        instructions=system_instructions,
                        input=chat_input,
                        max_output_tokens=650,
                        store=False,
                    )
                answer = response.output_text.strip() or "I couldn't produce an answer from the available dashboard data."
                st.session_state["ai_chat_messages"].append({"role": "assistant", "content": answer})
            except Exception:
                st.session_state["ai_chat_messages"].append({
                    "role": "assistant",
                    "content": "I couldn't reach the AI service. Check the API key, model access, and server connection, then try again.",
                })
            st.rerun()
