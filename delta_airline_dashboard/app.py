import html
import inspect
import json
import os
import re
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
try:
    from pdf_generator import generate_custom_client_pdf as _generate_custom_client_pdf
except ImportError:
    # Older Streamlit deployments may have the previous pdf_generator.py revision.
    _generate_custom_client_pdf = None


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


def build_coordination_email(subject: str, body: str, recipient: str = "", cc: str = "") -> bytes:
    """Build a plain email draft that preserves To, Cc, subject, and tab content."""
    message = EmailMessage()
    if recipient.strip():
        message["To"] = recipient.strip()
    if cc.strip():
        message["Cc"] = cc.strip()
    message["Subject"] = subject
    message.set_content(body)
    return message.as_bytes()


def build_coordination_mailto_url(subject: str, body: str, recipient: str = "", cc: str = "") -> str:
    """Create a mailto URL for the viewer's default email application."""
    to_part = quote(recipient.strip(), safe="@,;")
    query = [
        f"subject={quote(subject)}",
        f"body={quote(body)}",
    ]
    if cc.strip():
        query.insert(0, f"cc={quote(cc.strip(), safe='@,;')}")
    return f"mailto:{to_part}?{'&'.join(query)}"


def get_department_cc_default() -> str:
    """Read real department distribution lists from Streamlit secrets or the environment."""
    configured = os.getenv("DEPARTMENT_CC_EMAILS", "")
    try:
        configured = st.secrets.get("DEPARTMENT_CC_EMAILS", configured)
    except Exception:
        pass
    if isinstance(configured, (list, tuple)):
        return ", ".join(str(address).strip() for address in configured if str(address).strip())
    return str(configured or "").strip()


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


def generate_executive_pdf_compat(**report_args):
    """Pass the fields supported by the deployed PDF module; fold new content into legacy reports."""
    parameters = inspect.signature(generate_executive_pdf).parameters
    accepts_extra = any(parameter.kind == inspect.Parameter.VAR_KEYWORD for parameter in parameters.values())
    supported = set(parameters)
    summary = report_args.get("executive_summary", "")
    recommendations = list(report_args.get("hedging_recommendations", []))

    for argument, heading in (
        ("ai_financial_summary", "AI Financial Analytics"),
        ("ai_news_summary", "AI Recent News Analysis"),
    ):
        content = report_args.get(argument, "")
        if content and argument not in supported and not accepts_extra:
            recommendations.append({"title": heading, "detail": content})

    assumptions = report_args.get("dcf_assumptions") or {}
    if assumptions and "dcf_assumptions" not in supported and not accepts_extra:
        recommendations.append({
            "title": "DCF Scenario Assumptions",
            "detail": " | ".join(f"{name}: {value}" for name, value in assumptions.items()),
        })

    if report_args.get("company_news") and "company_news" not in supported and not accepts_extra:
        recommendations.extend(
            {
                "title": f"News: {article.get('title') or 'Recent company article'}",
                "detail": " | ".join(filter(None, [
                    str(article.get("publisher") or ""),
                    str(article.get("published_display") or ""),
                    str(article.get("url") or ""),
                ])),
            }
            for article in report_args["company_news"][:6]
        )

    report_args["executive_summary"] = summary
    report_args["hedging_recommendations"] = recommendations
    if accepts_extra:
        return generate_executive_pdf(**report_args)
    return generate_executive_pdf(**{
        name: value for name, value in report_args.items() if name in supported
    })


def generate_custom_client_pdf_compat(**report_args):
    """Use the tailored report generator when deployed, otherwise build a client-focused legacy PDF."""
    if callable(_generate_custom_client_pdf):
        parameters = inspect.signature(_generate_custom_client_pdf).parameters
        accepts_extra = any(parameter.kind == inspect.Parameter.VAR_KEYWORD for parameter in parameters.values())
        supported = set(parameters)
        if accepts_extra:
            return _generate_custom_client_pdf(**report_args)
        return _generate_custom_client_pdf(**{
            name: value for name, value in report_args.items() if name in supported
        })

    client_summary = (
        f"Custom client meeting brief for {report_args['company_name']}. "
        f"{report_args.get('executive_summary', '')}"
    )
    return generate_executive_pdf_compat(
        data=report_args["data"],
        fin_df=report_args["fin_df"],
        multiples=report_args["multiples"],
        dcf_results=report_args["dcf_results"],
        executive_summary=client_summary,
        hedging_recommendations=report_args.get("discussion_points", []),
        currency_symbol=report_args["currency_symbol"],
        currency_code=report_args["currency_code"],
        company_name=report_args["company_name"],
        exclude_years=report_args.get("exclude_years", ()),
        ai_financial_summary=report_args.get("ai_financial_summary", ""),
        ai_news_summary=report_args.get("ai_news_summary", ""),
        company_news=report_args.get("company_news", []),
        dcf_assumptions=report_args.get("dcf_assumptions", {}),
        data_timestamp=report_args.get("data_timestamp", "Not available"),
    )

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
    section[data-testid="stSidebar"] .cgi-sidebar-brand,
    section[data-testid="stSidebar"] .cgi-sidebar-brand * {
        color: #FFFFFF !important;
        -webkit-text-fill-color: #FFFFFF !important;
    }

    /* Top navy banner */
    .cgi-banner {
        background: #001E60;
        padding: 24px 30px;
        border-radius: 10px;
        color: #FFFFFF !important;
        margin-bottom: 1.5rem;
        box-shadow: 0 6px 18px rgba(0, 30, 96, 0.18);
    }
    .cgi-banner, .cgi-banner * {
        color: #FFFFFF !important;
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
        border-top: 4px solid #001E60;
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
        border-left: 4px solid #001E60 !important;
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
        background-color: #001E60 !important;
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
        color: #001E60 !important;
        border-bottom: 3px solid #001E60 !important;
    }

    /* Primary and download buttons */
    .stButton > button, .stDownloadButton > button {
        background: #001E60 !important;
        color: #FFFFFF !important;
        border: none !important;
        border-radius: 6px !important;
        font-weight: 600 !important;
        padding: 0.6rem 1.2rem !important;
        box-shadow: 0 3px 10px rgba(0, 30, 96, 0.22) !important;
    }
    div[data-testid="stButton"] button,
    div[data-testid="stButton"] button *,
    div[data-testid="stButton"] button[kind],
    div[data-testid="stButton"] button[kind] *,
    div[data-testid="stDownloadButton"] button[kind],
    div[data-testid="stDownloadButton"] button[kind] *,
    div[data-testid="stLinkButton"] a,
    div[data-testid="stLinkButton"] a *,
    div[data-testid="stLinkButton"] a p,
    div[data-testid="stLinkButton"] a span {
        color: #FFFFFF !important;
        -webkit-text-fill-color: #FFFFFF !important;
    }
    .stButton > button:hover, .stDownloadButton > button:hover {
        background: #001E60 !important;
        color: #FFFFFF !important;
        box-shadow: 0 5px 14px rgba(0, 30, 96, 0.30) !important;
    }

    /* Email draft links */
    [data-testid="stLinkButton"] a, a[data-testid="stLinkButton"] {
        background: #001E60 !important;
        color: #FFFFFF !important;
        border: none !important;
    }
    [data-testid="stLinkButton"] a *, a[data-testid="stLinkButton"] * {
        color: #FFFFFF !important;
    }
    [data-testid="stLinkButton"] a:hover, a[data-testid="stLinkButton"]:hover {
        background: #001E60 !important;
        color: #FFFFFF !important;
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
        border-top: 4px solid #001E60;
        border-radius: 14px;
        padding: 0.8rem 1rem 1rem;
        box-shadow: 0 12px 36px rgba(23, 17, 43, 0.24);
    }
    .st-key-ai_chat_panel [data-testid="stVerticalBlock"] { gap: 0.45rem; }
    .st-key-ai_chat_history {
        min-height: min(48vh, 460px);
        max-height: min(65vh, 650px);
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
        .st-key-ai_chat_history {
            min-height: min(36vh, 300px);
            max-height: min(52vh, 440px);
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


DATA_CACHE_VERSION = "forward-pe-yahoo-valuation-fallback-v5"

# Keep a presentation-safe fallback in the app itself as well as data_engine.
# Streamlit can rerun this script while retaining a previously imported local
# module; this prevents the Client Quick Factsheet from losing static company
# profile data during that transition.
FACTSHEET_PROFILE_FALLBACKS = {
    "DAL": {
        "headquarters": "Atlanta, Georgia, United States",
        "employee_display": "103,000 FTE (FY2025)",
        "employee_source_label": "Delta 2025 Form 10-K",
        "employee_source_url": "https://www.sec.gov/Archives/edgar/data/27904/000002790426000013/dal-20251231.htm",
    },
    "ADS.DE": {
        "headquarters": "Herzogenaurach, Germany",
        "employee_display": "64,938 (FY2025)",
        "employee_source_label": "adidas Annual Report 2025",
        "employee_source_url": "https://www.report.adidas-group.com/2025/en/group-management-report-sustainability-statement/esrs-s1-own-workforce/metrics-and-targets.html",
    },
    "LHA.DE": {
        "headquarters": "Cologne, Germany",
        "employee_display": "103,255 (FY2025)",
        "employee_source_label": "Lufthansa Group Annual Report 2025",
        "employee_source_url": "https://report.lufthansagroup.com/2025/annual-report/en/combined-management-report/principles-of-the-group/employees/",
    },
    "BMW.DE": {
        "headquarters": "Munich, Germany",
        "employee_display": "154,540 (FY2025)",
        "employee_source_label": "BMW Group Report 2025",
        "employee_source_url": "https://www.bmwgroup.com/en/report/2025/management-report/index.html",
    },
    "SIE.DE": {
        "headquarters": "Munich, Germany",
        "employee_display": "Approx. 318,000 (FY2025)",
        "employee_source_label": "Siemens Annual Report 2025",
        "employee_source_url": "https://assets.new.siemens.com/siemens/assets/api/uuid%3A428ea18a-e7ab-4f93-a160-33908f1c3540/Siemens-Annual-Report-2025.pdf",
    },
    "SAP.DE": {
        "headquarters": "Walldorf, Germany",
        "employee_display": "111,397 (FY2025 headcount)",
        "employee_source_label": "SAP Integrated Report 2025",
        "employee_source_url": "https://www.sap.com/integrated-reports/2025/en/csrd/social-performance.html",
    },
}


@st.cache_data(ttl=3600, show_spinner="Fetching live company and benchmark data...")
def load_all_data(
    ticker: str,
    benchmarks: tuple[str, ...],
    currency: str,
    exclude_years: tuple[str, ...],
    cache_version: str,
):
    # Imported data_engine changes are not always enough to invalidate this
    # Streamlit cache, so include a manually bumped revision in the cache key.
    _ = cache_version
    raw = fetch_company_data(ticker, benchmarks, currency)
    fin_df = extract_financial_summary(raw, exclude_years=exclude_years)
    multiples = extract_valuation_multiples(raw, fin_df)
    return raw, fin_df, multiples

with st.sidebar:
    st.markdown(
        """
        <div class="cgi-sidebar-brand" style="background: #001E60;
                    padding: 10px 14px; border-radius: 8px; font-weight: 700;
                    font-size: 1.15rem; margin-bottom: 12px; letter-spacing: 0.5px;">
            <span>CGI | Advisory Suite</span>
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
        DATA_CACHE_VERSION,
    )
except Exception as exc:
    st.error(f"Error retrieving data for {selected_company}: {exc}")
    st.stop()

info = raw_data["info"]
company_name = info.get("longName") or selected_company.split(" (")[0]
company_label = f"{company_name} ({ticker_symbol})"
currency_symbol = {"USD": "$", "EUR": "€", "GBP": "£", "CHF": "CHF ", "CAD": "C$", "JPY": "¥"}.get(raw_data.get("currency", currency_code), currency_symbol)
live_business_summary = str(info.get("longBusinessSummary") or "").strip()
business_summary = live_business_summary or company_config.get(
    "overview",
    f"{company_name} is included in this dashboard for company and financial review. Yahoo Finance did not provide a current business description.",
)

def quote_text(value, suffix=""):
    try:
        number = float(value)
        return f"{number:,.2f}{suffix}" if np.isfinite(number) and number > 0 else "Not available"
    except (TypeError, ValueError):
        return "Not available"


def currency_text(value, suffix=""):
    formatted = quote_text(value)
    return f"{currency_symbol}{formatted}{suffix}" if formatted != "Not available" else formatted


company_profile = company_config.get("profile") or FACTSHEET_PROFILE_FALLBACKS.get(ticker_symbol, {})
live_headquarters = ", ".join(
    filter(None, [str(info.get("city") or "").strip(), str(info.get("country") or "").strip()])
)
headquarters = str(company_profile.get("headquarters") or live_headquarters or "Not reported")
employee_text = str(company_profile.get("employee_display") or "").strip()
if not employee_text:
    try:
        employee_count = int(float(info.get("fullTimeEmployees") or 0))
        employee_text = f"{employee_count:,}" if employee_count > 0 else "Not reported"
    except (TypeError, ValueError):
        employee_text = "Not reported"

employee_html = html.escape(employee_text)
employee_source_url = str(company_profile.get("employee_source_url") or "").strip()
employee_source_label = str(company_profile.get("employee_source_label") or "Company report").strip()
if employee_source_url:
    employee_html += (
        f' <small>(<a href="{html.escape(employee_source_url, quote=True)}" '
        f'target="_blank" rel="noopener noreferrer">{html.escape(employee_source_label)}</a>)</small>'
    )
sector_text = str(info.get("sector") or company_config.get("sector") or "Not reported")
industry_text = str(info.get("industry") or company_config.get("industry") or "Not reported")
low_52w = info.get("fiftyTwoWeekLow")
high_52w = info.get("fiftyTwoWeekHigh")
range_text = (
    f"{currency_symbol}{quote_text(low_52w)} – {currency_symbol}{quote_text(high_52w)}"
    if quote_text(low_52w) != "Not available" and quote_text(high_52w) != "Not available"
    else "Not available"
)
factsheet_html = f"""
<div class='cgi-card'>
<h4 style="margin-top: 0; color: #5236AB; font-size: 1.05rem; border-bottom: 1px solid #ECE8F4; padding-bottom: 6px;">
    📊 Client Quick Factsheet
</h4>
<b>Headquarters:</b> {html.escape(headquarters)}<br>
<b>Employees:</b> {employee_html}<br>
<b>Sector:</b> {html.escape(sector_text)}<br>
<b>Industry:</b> {html.escape(industry_text)}<br>
<b>52W Range:</b> {html.escape(range_text)}
</div>
"""

for data_warning in raw_data.get("warnings", []):
    st.warning(data_warning)

if fin_df.empty or float(fin_df.iloc[-1]["Revenue ($B)"]) <= 0:
    st.warning(
        f"Yahoo Finance did not return usable annual or trailing revenue for {company_label}. "
        "Financial valuation is unavailable until a revenue base is returned. The company profile and available market data are shown below."
    )
    st.subheader("Company Overview & Market Positioning")
    overview_col, facts_col = st.columns([2, 1])
    with overview_col:
        st.write(business_summary)
        if not live_business_summary:
            st.caption("Yahoo Finance did not provide a company description; this is the dashboard’s static overview.")
    with facts_col:
        st.markdown(factsheet_html, unsafe_allow_html=True)
    quote_cols = st.columns(3)
    quote_cols[0].metric("Share Price", currency_text(multiples["Current Share Price ($)"]))
    quote_cols[1].metric("Market Cap", currency_text(multiples["Market Cap ($B)"], "B"))
    quote_cols[2].metric("Enterprise Value", currency_text(multiples["Enterprise Value ($B)"], "B"))
    market_cap_basis = raw_data.get("market_cap_basis", "")
    if market_cap_basis:
        source_url = raw_data.get("shares_source_url", "")
        if source_url and market_cap_basis.startswith("Estimated"):
            st.markdown(f"_{market_cap_basis} [Share-count source]({source_url})_")
        else:
            st.caption(market_cap_basis)
    st.stop()

if str(fin_df.iloc[-1]["Year"]).upper() == "TTM":
    if raw_data.get("annual_financials_available"):
        st.info(
            f"A separate TTM row supplements annual statements for {company_label} because Yahoo omitted one or more key statement items. "
            "The row is clearly labelled and uses trailing-twelve-month quote or quarterly data where available. Validate the period basis before client use."
        )
    else:
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

# Navy Hero Banner
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
k1.metric("Share Price", currency_text(multiples["Current Share Price ($)"]))
k2.metric("Market Cap", currency_text(multiples["Market Cap ($B)"], "B"))
k3.metric("Enterprise Value", currency_text(multiples["Enterprise Value ($B)"], "B"))
k4.metric("EV / EBITDA", f"{quote_text(multiples['EV / EBITDA (x)'], 'x')}")
k5.metric(
    "Trailing / Fwd P/E",
    f"{quote_text(multiples['Trailing P/E (x)'], 'x')} / {quote_text(multiples['Forward P/E (x)'], 'x')}",
)
k6.metric(
    "DCF Implied Price",
    currency_text(dcf_results["valuation_bridge"]["Implied Share Price ($)"]),
    f"{dcf_results['valuation_bridge']['Implied Upside / Downside (%)']:+.1f}%",
)
market_cap_basis = raw_data.get("market_cap_basis", "")
if market_cap_basis:
    source_url = raw_data.get("shares_source_url", "")
    if source_url and market_cap_basis.startswith("Estimated"):
        st.markdown(f"_{market_cap_basis} [Share-count source]({source_url})_")
    else:
        st.caption(market_cap_basis)

st.markdown("<br>", unsafe_allow_html=True)

tab1, tab2, tab3, tab4 = st.tabs(
    [
        "📊 Financials & Company Overview",
        "🛡️ Risk & Hedging",
        "🎯 Valuation & Client Export",
        "🤝 Cross-Department Coordination",
    ]
)

# =============================================================================
# TAB 1: COMPANY OVERVIEW & FINANCIALS
# =============================================================================
with tab1:
    st.subheader("1. Company Overview & Market Positioning")
    col_ov1, col_ov2 = st.columns([2, 1])

    with col_ov1:
        st.write(business_summary)
        if not live_business_summary:
            st.caption("Yahoo Finance did not provide a company description; this is the dashboard’s static overview.")
    with col_ov2:
        st.markdown(factsheet_html, unsafe_allow_html=True)

    st.markdown("---")
    st.subheader("✨ Advanced AI Financial Analytics Summary")
    st.caption(
        "On-demand analysis of reported financials, trading multiples, and the current DCF scenario. "
        "The AI uses this dashboard snapshot and does not add client-specific exposure data."
    )

    analytics_periods = []
    for period_index, period_row in fin_df.reset_index(drop=True).iterrows():
        previous_period = fin_df.iloc[period_index - 1] if period_index > 0 else None
        revenue = float(period_row["Revenue ($B)"])
        ebitda = float(period_row["EBITDA ($B)"])
        free_cash_flow = float(period_row["Free Cash Flow ($B)"])
        analytics_periods.append({
            "period": str(period_row["Year"]),
            "revenue_billions": round(revenue, 2),
            "revenue_growth_percent_vs_previous_period": round(
                (revenue / float(previous_period["Revenue ($B)"]) - 1) * 100, 1
            ) if previous_period is not None and float(previous_period["Revenue ($B)"]) > 0 else None,
            "ebitda_billions": round(ebitda, 2),
            "ebitda_margin_percent": round(float(period_row["EBITDA Margin (%)"]), 1),
            "operating_margin_percent": round(float(period_row["Operating Margin (%)"]), 1),
            "free_cash_flow_billions": round(free_cash_flow, 2),
            "free_cash_flow_to_ebitda_percent": round(free_cash_flow / ebitda * 100, 1) if ebitda > 0 else None,
            "net_debt_billions": round(float(period_row["Net Debt ($B)"]), 2),
            "net_debt_to_ebitda": round(float(period_row["Net Debt / EBITDA (x)"]), 2),
        })

    analytics_context = {
        "company": company_label,
        "industry": info.get("industry"),
        "reporting_currency": currency_code,
        "financial_data_source": "Yahoo Finance via yfinance; values may be incomplete or delayed.",
        "data_timestamp": raw_data.get("fetched_at"),
        "historical_financial_periods": analytics_periods,
        "market_valuation": {
            key: value for key, value in multiples.items()
        },
        "dcf_scenario": {
            "assumptions": {
                "revenue_growth_percent": round(rev_growth * 100, 2),
                "target_ebit_margin_percent": round(ebit_margin * 100, 2),
                "tax_rate_percent": round(tax_rate * 100, 2),
                "capex_percent_of_revenue": round(capex_pct * 100, 2),
                "risk_free_rate_percent": round(rf_rate * 100, 2),
                "equity_risk_premium_percent": round(erp * 100, 2),
                "terminal_growth_percent": round(tgr * 100, 2),
            },
            "valuation_bridge": dcf_results["valuation_bridge"],
            "wacc_percent": dcf_results["wacc_details"]["Calculated WACC (%)"],
        },
    }
    analytics_key = json.dumps({
        "ticker": ticker_symbol,
        "data_timestamp": raw_data.get("fetched_at"),
        "assumptions": analytics_context["dcf_scenario"]["assumptions"],
    }, sort_keys=True)
    saved_analytics = st.session_state.get("ai_financial_analytics", {})
    generate_label = "🔄 Refresh AI financial analytics" if analytics_key in saved_analytics else "✨ Generate AI financial analytics"

    if st.button(generate_label, key=f"generate_financial_analytics_{ticker_symbol}", type="primary"):
        api_key, model_name = get_openai_settings()
        if not api_key:
            st.warning("Set `OPENAI_API_KEY` in Streamlit Secrets to generate the AI financial analysis.")
        else:
            instructions = (
                "You are a senior financial analyst preparing an evidence-based client-call briefing. "
                "Use only the supplied dashboard JSON. Explain trends across periods, profitability and cash conversion, leverage, "
                "trading multiples, and what the DCF scenario implies under its stated assumptions. Clearly distinguish reported data, "
                "calculated ratios, and scenario outputs. Do not claim why a metric changed unless the supplied data establishes a cause. "
                "Call out missing or limited data. Never invent facts, client exposures, or products, and do not give investment advice. "
                "Return concise Markdown with headings: Executive readout; Performance and cash generation; Leverage and valuation; "
                "Three questions to validate on the client call; Data caveats."
            )
            try:
                from openai import OpenAI

                client = OpenAI(api_key=api_key, timeout=45.0, max_retries=1)
                with st.spinner("Analyzing the selected company’s financial trends and valuation…"):
                    response = client.responses.create(
                        model=model_name,
                        instructions=instructions,
                        input="Dashboard financial analytics (JSON):\n" + json.dumps(
                            analytics_context, ensure_ascii=False, default=str
                        ),
                        max_output_tokens=900,
                        store=False,
                    )
                analysis = response.output_text.strip()
                if analysis:
                    saved_analytics[analytics_key] = analysis
                    st.session_state["ai_financial_analytics"] = saved_analytics
                else:
                    st.error("The AI service returned an empty analysis. Please try again.")
            except Exception:
                st.error("AI financial analysis failed. Check the API key, selected model, and server connection, then try again.")

    saved_analytics = st.session_state.get("ai_financial_analytics", {})
    if analytics_key in saved_analytics:
        st.markdown(saved_analytics[analytics_key])
        st.caption(f"AI-generated from dashboard data updated {raw_data.get('fetched_at')}; verify figures before client use.")
    else:
        st.info("Generate an analysis to review financial trends, cash generation, leverage, valuation signals, and client-call questions.")

    st.markdown("---")
    st.subheader("📰 Recent AI News Summary")
    st.caption("News is drawn from Yahoo Finance and limited to recent coverage; AI commentary is based on the headline and available article excerpt.")
    company_news = raw_data.get("news", [])
    news_context = [
        {
            "title": item["title"],
            "publisher": item["publisher"],
            "published": item["published_display"],
            "available_excerpt": item.get("summary") or "No article excerpt was provided; headline only.",
            "source_url": item.get("url", ""),
        }
        for item in company_news
    ]
    news_analytics_key = json.dumps(
        {
            "ticker": ticker_symbol,
            "articles": [
                {"title": item["title"], "published_at": item["published_at"], "url": item["url"]}
                for item in company_news
            ],
        },
        sort_keys=True,
    )
    saved_news_analytics = st.session_state.get("ai_news_summaries", {})
    if company_news:
        news_button_label = "🔄 Refresh AI news summary" if news_analytics_key in saved_news_analytics else "📰 Summarize recent company news with AI"
        if st.button(news_button_label, key=f"summarize_company_news_{ticker_symbol}"):
            api_key, model_name = get_openai_settings()
            if not api_key:
                st.warning("Set `OPENAI_API_KEY` in Streamlit Secrets to summarize company news.")
            else:
                news_instructions = (
                    "You are preparing a sourced company news briefing for a corporate banking client call. "
                    "Use only the supplied news items. Summarize the main themes and possible financial relevance as hypotheses, "
                    "not confirmed impacts. Distinguish article facts from headline-only signals, do not infer facts absent from excerpts, "
                    "and do not give investment advice. Mention if coverage is thin or sources overlap. "
                    "Return concise Markdown with headings: News themes; Potential business or financial relevance to validate; "
                    "Three client-call questions; Coverage limitations."
                )
                try:
                    from openai import OpenAI

                    client = OpenAI(api_key=api_key, timeout=45.0, max_retries=1)
                    with st.spinner("Summarizing recent company headlines…"):
                        response = client.responses.create(
                            model=model_name,
                            instructions=news_instructions,
                            input="Recent company news and source metadata (JSON):\n" + json.dumps(
                                news_context, ensure_ascii=False, default=str
                            ),
                            max_output_tokens=650,
                            store=False,
                        )
                    news_analysis = response.output_text.strip()
                    if news_analysis:
                        saved_news_analytics[news_analytics_key] = news_analysis
                        st.session_state["ai_news_summaries"] = saved_news_analytics
                    else:
                        st.error("The AI service returned an empty news summary. Please try again.")
                except Exception:
                    st.error("AI news summary failed. Check the API key, selected model, and server connection, then try again.")

        saved_news_analytics = st.session_state.get("ai_news_summaries", {})
        if news_analytics_key in saved_news_analytics:
            st.markdown(saved_news_analytics[news_analytics_key])
            st.caption("AI synthesis is based on the displayed article metadata and available excerpts, not full-text verification.")
        else:
            st.info("Generate an AI summary to identify recent themes and client-call questions from the available coverage.")

        with st.expander(f"View {len(company_news)} recent source articles", expanded=False):
            for item in company_news:
                title = item["title"]
                publisher = item["publisher"]
                published = item["published_display"]
                url = item.get("url", "")
                if url.startswith(("https://", "http://")):
                    st.markdown(f"- [{title}]({url}) — {publisher} · {published}")
                else:
                    st.markdown(f"- **{title}** — {publisher} · {published}")
                if item.get("summary"):
                    st.caption(item["summary"])
    else:
        st.info("No recent company articles were returned by the news feed. The PDF will note that no recent news was available.")

    st.subheader(f"2. Relative Market Performance ({company_label} vs. {', '.join(company_config['benchmark_names'])})")
    bench_df = raw_data["benchmarks"].dropna()
    if not bench_df.empty:
        norm_bench = (bench_df / bench_df.iloc[0]) * 100
        fig_bench = px.line(
            norm_bench,
            labels={"value": "Normalized Return (Base = 100)", "Date": "Date", "variable": "Ticker"},
            color_discrete_map={ticker_symbol: "#001E60", **dict(zip(company_config["benchmarks"], ["#5236AB", "#9B185A"]))},
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
            fig_rev.add_trace(go.Bar(x=fin_df["Year"], y=fin_df["Free Cash Flow ($B)"], name=f"Free Cash Flow ({currency_code}B)", marker_color="#001E60"))
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
            fig_debt.add_trace(go.Bar(x=fin_df["Year"], y=fin_df["Total Debt ($B)"], name=f"Total Debt ({currency_code}B)", marker_color="#001E60"))
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
            color_discrete_sequence=["#5236AB", "#001E60"],
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

    saved_ai_financial_summaries = st.session_state.get("ai_financial_analytics", {})
    saved_ai_news_summaries = st.session_state.get("ai_news_summaries", {})
    ai_financial_summary = saved_ai_financial_summaries.get(analytics_key, "")
    ai_news_summary = saved_ai_news_summaries.get(news_analytics_key, "")
    dcf_assumptions = {
        "Revenue growth": f"{rev_growth * 100:.2f}%",
        "Target EBIT margin": f"{ebit_margin * 100:.2f}%",
        "Effective tax rate": f"{tax_rate * 100:.2f}%",
        "CapEx / revenue": f"{capex_pct * 100:.2f}%",
        "Risk-free rate": f"{rf_rate * 100:.2f}%",
        "Equity risk premium": f"{erp * 100:.2f}%",
        "Terminal growth": f"{tgr * 100:.2f}%",
    }
    if not ai_financial_summary or (company_news and not ai_news_summary):
        st.info("For the full AI-enhanced PDF, generate the financial and recent news summaries in Tab 1 before downloading.")

    pdf_bytes = generate_executive_pdf_compat(
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
        ai_financial_summary=ai_financial_summary,
        ai_news_summary=ai_news_summary,
        company_news=company_news,
        dcf_assumptions=dcf_assumptions,
        data_timestamp=raw_data.get("fetched_at", "Not available"),
    )
    custom_client_pdf_bytes = generate_custom_client_pdf_compat(
        data=raw_data,
        company_name=company_label,
        sector=info.get("sector") or "Not reported",
        industry=info.get("industry") or "Not reported",
        fin_df=fin_df,
        multiples=multiples,
        dcf_results=dcf_results,
        executive_summary=exec_summary_text,
        ai_financial_summary=ai_financial_summary,
        ai_news_summary=ai_news_summary,
        company_news=company_news,
        discussion_points=hedging_recs,
        dcf_assumptions=dcf_assumptions,
        currency_symbol=currency_symbol,
        currency_code=currency_code,
        data_timestamp=raw_data.get("fetched_at", "Not available"),
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
        st.download_button(
            label="📄 Download Custom Client Report",
            data=custom_client_pdf_bytes,
            file_name=f"{ticker_symbol.replace('.', '_')}_Custom_Client_Report.pdf",
            mime="application/pdf",
            use_container_width=True,
        )
        st.caption("Client-focused meeting brief tailored to the selected company.")

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

    st.button(
        "☁️ Save on SharePoint",
        key="sharepoint_export_placeholder",
        use_container_width=True,
    )


# =============================================================================
# TAB 4: CROSS-DEPARTMENT COORDINATION
# =============================================================================
with tab4:
    if st.session_state.get("coordination_company") != ticker_symbol:
        st.session_state["coordination_company"] = ticker_symbol
        st.session_state.pop("coordination_comment", None)
        st.session_state.pop("coordination_confirmed", None)

    st.subheader("🤝 Cross-Department Review & Alignment")
    st.write(
        "Capture input from the teams supporting this client discussion. The generated draft includes the selected client, "
        "team, contributor, comment, and confirmation status. It opens in the device's default email app; the app does not send it."
    )

    coordination_team = st.selectbox(
        "Your team",
        ["Legal", "Compliance", "IT", "Coverage", "PAM", "Sales Representative"],
        key="coordination_team",
    )
    coordination_person = st.selectbox(
        "Your name",
        ["User 1", "User 2", "User 3"],
        key="coordination_person",
    )
    coordination_comment = st.text_area(
        "Comments for the other teams",
        placeholder="Add your review, questions, dependencies, or follow-up actions…",
        height=150,
        key="coordination_comment",
    )
    coordination_confirmed = st.checkbox(
        "Everything is good from my side",
        key="coordination_confirmed",
    )

    department_cc_default = get_department_cc_default()
    if "coordination_to" not in st.session_state:
        st.session_state["coordination_to"] = recipient_email
    if "coordination_cc" not in st.session_state or (
        not str(st.session_state.get("coordination_cc", "")).strip() and department_cc_default
    ):
        st.session_state["coordination_cc"] = department_cc_default

    with st.expander("Email routing", expanded=not bool(st.session_state.get("coordination_cc"))):
        coordination_to = st.text_input(
            "To (optional)",
            placeholder="colleague@company.com",
            key="coordination_to",
        )
        coordination_cc = st.text_input(
            "All department distribution lists for CC (comma-separated)",
            placeholder="legal-list@…, compliance-list@…, it-list@…, coverage-list@…, pam-list@…, sales-list@…",
            help="Enter at least six real department addresses. Set DEPARTMENT_CC_EMAILS in Streamlit Secrets to prefill the list; the app does not invent internal addresses.",
            key="coordination_cc",
        )

    cc_addresses = [address.strip() for address in re.split(r"[,;]", coordination_cc) if address.strip()]
    cc_syntax_valid = bool(cc_addresses) and all(
        re.fullmatch(r"[^\s@,;]+@[^\s@,;]+\.[^\s@,;]+", address)
        for address in cc_addresses
    )
    valid_cc_addresses = len(cc_addresses) >= 6 and cc_syntax_valid

    if coordination_cc.strip() and not cc_syntax_valid:
        st.warning("One or more CC entries do not look like email addresses. Check the department list before generating the draft.")
    elif coordination_cc.strip() and len(cc_addresses) < 6:
        st.warning("Enter at least six valid group addresses so Legal, Compliance, IT, Coverage, PAM, and Sales are all copied.")

    confirmation_text = (
        "Confirmed: everything is good from my side."
        if coordination_confirmed
        else "Not confirmed: follow-up or review is still needed."
    )
    comment_for_email = coordination_comment.strip() or "No comment provided."
    coordination_subject = f"Cross-Department Review — {company_label} — {coordination_team}"
    coordination_body = (
        f"Hello all,\n\n"
        f"Cross-department review for {company_label}\n\n"
        f"Submitting team: {coordination_team}\n"
        f"Contributor: {coordination_person}\n"
        f"Client / company: {company_label}\n\n"
        f"Comment and follow-up:\n{comment_for_email}\n\n"
        f"Confirmation: {confirmation_text}\n\n"
        "Please reply all with any questions or required actions.\n"
    )

    coordination_cc_header = ", ".join(cc_addresses)
    coordination_mailto_url = build_coordination_mailto_url(
        subject=coordination_subject,
        body=coordination_body,
        recipient=coordination_to,
        cc=coordination_cc_header,
    )
    coordination_eml = build_coordination_email(
        subject=coordination_subject,
        body=coordination_body,
        recipient=coordination_to,
        cc=coordination_cc_header,
    )

    st.markdown("---")
    st.subheader("Email draft")
    email_col, eml_col = st.columns(2)
    with email_col:
        st.link_button(
            "📧 Generate email draft and open default mail app",
            coordination_mailto_url,
            type="primary",
            disabled=not valid_cc_addresses,
            help=None if valid_cc_addresses else "Add all six department email addresses in Email routing.",
            use_container_width=True,
        )
    with eml_col:
        st.download_button(
            "📨 Download draft (.eml)",
            data=coordination_eml,
            file_name=f"{ticker_symbol.replace('.', '_')}_Department_Review.eml",
            mime="message/rfc822",
            disabled=not valid_cc_addresses,
            use_container_width=True,
        )

    if valid_cc_addresses:
        with st.expander("Preview email"):
            st.markdown(f"**To:** {html.escape(coordination_to or 'Not specified')}  \n**Cc:** {html.escape(coordination_cc_header)}  \n**Subject:** {html.escape(coordination_subject)}")
            st.text(coordination_body)


# =============================================================================
# FLOATING, COMPANY-GROUNDED AI CHAT
# =============================================================================
if st.session_state.get("ai_chat_company") != ticker_symbol:
    st.session_state["ai_chat_company"] = ticker_symbol
    st.session_state["ai_chat_messages"] = []

if "ai_chat_open" not in st.session_state:
    st.session_state["ai_chat_open"] = False


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
    "recent_company_news": raw_data.get("news", []),
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
