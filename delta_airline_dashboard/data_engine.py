import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime


def fetch_delta_data(ticker_symbol: str = "DAL") -> dict:
    ticker = yf.Ticker(ticker_symbol)
    info = ticker.info
    hist = ticker.history(period="3y")

    income_stmt = ticker.financials
    balance_sheet = ticker.balance_sheet
    cash_flow = ticker.cashflow

    if not income_stmt.empty:
        income_stmt = income_stmt.iloc[:, ::-1]
    if not balance_sheet.empty:
        balance_sheet = balance_sheet.iloc[:, ::-1]
    if not cash_flow.empty:
        cash_flow = cash_flow.iloc[:, ::-1]

    benchmarks = yf.download(["DAL", "^GSPC", "JETS"], period="2y", progress=False)["Close"]

    return {
        "ticker": ticker_symbol,
        "info": info,
        "history": hist,
        "income_stmt": income_stmt,
        "balance_sheet": balance_sheet,
        "cash_flow": cash_flow,
        "benchmarks": benchmarks,
        "fetched_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def _safe_get(df: pd.DataFrame, possible_keys: list) -> pd.Series:
    if df is None or df.empty:
        return pd.Series(dtype=float)
    for key in possible_keys:
        if key in df.index:
            return pd.to_numeric(df.loc[key], errors="coerce").fillna(0)
    return pd.Series(0.0, index=df.columns)


def extract_financial_summary(data: dict) -> pd.DataFrame:
    inc = data["income_stmt"]
    bs = data["balance_sheet"]
    cf = data["cash_flow"]

    if inc.empty:
        return pd.DataFrame()

    raw_years = [col.strftime("%Y") if hasattr(col, "strftime") else str(col)[:4] for col in inc.columns]

    rev = _safe_get(inc, ["Total Revenue", "Operating Revenue"]).values
    ebit = _safe_get(inc, ["EBIT", "Operating Income"]).values
    ebitda = _safe_get(inc, ["EBITDA", "Normalized EBITDA"]).values
    net_inc = _safe_get(inc, ["Net Income", "Net Income Common Stockholders"]).values
    int_exp = np.abs(_safe_get(inc, ["Interest Expense", "Interest Expense Non Operating"]).values)

    total_debt = _safe_get(bs, ["Total Debt"]).values
    cash = _safe_get(bs, ["Cash And Cash Equivalents", "Cash Cash Equivalents And Short Term Investments"]).values
    equity = _safe_get(bs, ["Stockholders Equity", "Total Equity Gross Minority Interest"]).values

    ocf = _safe_get(cf, ["Operating Cash Flow", "Cash Flow From Continuing Operating Activities"]).values
    capex = np.abs(_safe_get(cf, ["Capital Expenditure"]).values)
    fcf = ocf - capex

    df = pd.DataFrame(
        {
            "Year": raw_years,
            "Revenue ($B)": rev / 1e9,
            "EBIT ($B)": ebit / 1e9,
            "EBITDA ($B)": ebitda / 1e9,
            "Net Income ($B)": net_inc / 1e9,
            "Operating Cash Flow ($B)": ocf / 1e9,
            "CapEx ($B)": capex / 1e9,
            "Free Cash Flow ($B)": fcf / 1e9,
            "Total Debt ($B)": total_debt / 1e9,
            "Cash & Equivalents ($B)": cash / 1e9,
            "Net Debt ($B)": (total_debt - cash) / 1e9,
            "Total Equity ($B)": equity / 1e9,
            "Interest Expense ($B)": int_exp / 1e9,
        }
    )

    # Exclude 2021 per instructions
    df = df[df["Year"] != "2021"].reset_index(drop=True)

    df["Operating Margin (%)"] = np.where(df["Revenue ($B)"] > 0, (df["EBIT ($B)"] / df["Revenue ($B)"]) * 100, 0)
    df["EBITDA Margin (%)"] = np.where(df["Revenue ($B)"] > 0, (df["EBITDA ($B)"] / df["Revenue ($B)"]) * 100, 0)
    df["Net Margin (%)"] = np.where(df["Revenue ($B)"] > 0, (df["Net Income ($B)"] / df["Revenue ($B)"]) * 100, 0)
    df["Net Debt / EBITDA (x)"] = np.where(df["EBITDA ($B)"] > 0, df["Net Debt ($B)"] / df["EBITDA ($B)"], 0)

    return df


def extract_valuation_multiples(data: dict, fin_df: pd.DataFrame) -> dict:
    info = data["info"]
    price = info.get("currentPrice") or info.get("regularMarketPrice") or 0.0
    mkt_cap = info.get("marketCap") or 0.0
    ev = info.get("enterpriseValue") or 0.0

    latest = fin_df.iloc[-1] if not fin_df.empty else None
    latest_rev = (latest["Revenue ($B)"] * 1e9) if latest is not None else 0.0
    latest_ebitda = (latest["EBITDA ($B)"] * 1e9) if latest is not None else 0.0
    latest_fcf = (latest["Free Cash Flow ($B)"] * 1e9) if latest is not None else 0.0

    return {
        "Current Share Price ($)": round(price, 2),
        "Market Cap ($B)": round(mkt_cap / 1e9, 2),
        "Enterprise Value ($B)": round(ev / 1e9, 2),
        "Trailing P/E (x)": round(info.get("trailingPE") or 0.0, 2),
        "Forward P/E (x)": round(info.get("forwardPE") or 0.0, 2),
        "EV / EBITDA (x)": round(info.get("enterpriseToEbitda") or (ev / latest_ebitda if latest_ebitda > 0 else 0.0), 2),
        "EV / Revenue (x)": round(info.get("enterpriseToRevenue") or (ev / latest_rev if latest_rev > 0 else 0.0), 2),
        "Price / Book (x)": round(info.get("priceToBook") or 0.0, 2),
        "Price / FCF (x)": round(mkt_cap / latest_fcf if latest_fcf > 0 else 0.0, 2),
        "FCF Yield (%)": round((latest_fcf / mkt_cap) * 100 if mkt_cap > 0 else 0.0, 2),
        "Dividend Yield (%)": round((info.get("dividendYield") or 0.0) * 100, 2),
        "Beta (5Y Monthly)": round(info.get("beta") or 1.25, 2),
    }


def run_dcf_model(
    data: dict,
    fin_df: pd.DataFrame,
    rev_growth_rate: float = 0.045,
    ebit_margin: float = 0.105,
    tax_rate: float = 0.23,
    da_pct_rev: float = 0.042,
    capex_pct_rev: float = 0.075,
    nwc_pct_rev: float = 0.005,
    risk_free_rate: float = 0.042,
    equity_risk_premium: float = 0.050,
    terminal_growth_rate: float = 0.025,
    projection_years: int = 5,
) -> dict:
    info = data["info"]
    latest = fin_df.iloc[-1]

    base_rev = latest["Revenue ($B)"] * 1e9
    total_debt = latest["Total Debt ($B)"] * 1e9
    cash = latest["Cash & Equivalents ($B)"] * 1e9
    int_exp = latest["Interest Expense ($B)"] * 1e9

    mkt_cap = info.get("marketCap") or (latest["Total Equity ($B)"] * 1e9)
    shares_out = info.get("sharesOutstanding") or (mkt_cap / (info.get("currentPrice") or 50.0))
    beta = info.get("beta") or 1.25

    cost_of_equity = risk_free_rate + beta * equity_risk_premium
    pre_tax_cost_debt = (int_exp / total_debt) if total_debt > 0 and int_exp > 0 else 0.055
    pre_tax_cost_debt = np.clip(pre_tax_cost_debt, 0.03, 0.10)
    after_tax_cost_debt = pre_tax_cost_debt * (1 - tax_rate)

    total_capital = mkt_cap + total_debt
    weight_equity = mkt_cap / total_capital if total_capital > 0 else 0.65
    weight_debt = total_debt / total_capital if total_capital > 0 else 0.35
    wacc = (weight_equity * cost_of_equity) + (weight_debt * after_tax_cost_debt)
    wacc = max(wacc, terminal_growth_rate + 0.015)

    rows = []
    curr_rev = base_rev
    base_year = int(latest["Year"])

    for t in range(1, projection_years + 1):
        proj_year = base_year + t
        step_growth = rev_growth_rate - ((rev_growth_rate - terminal_growth_rate) * ((t - 1) / projection_years) * 0.4)
        proj_rev = curr_rev * (1 + step_growth)
        proj_ebit = proj_rev * ebit_margin
        nopat = proj_ebit * (1 - tax_rate)
        da = proj_rev * da_pct_rev
        capex = proj_rev * capex_pct_rev
        delta_nwc = (proj_rev - curr_rev) * nwc_pct_rev

        fcff = nopat + da - capex - delta_nwc
        discount_factor = 1 / ((1 + wacc) ** t)
        pv_fcff = fcff * discount_factor

        rows.append(
            {
                "Year": str(proj_year),
                "Revenue ($B)": proj_rev / 1e9,
                "EBIT ($B)": proj_ebit / 1e9,
                "NOPAT ($B)": nopat / 1e9,
                "D&A ($B)": da / 1e9,
                "CapEx ($B)": capex / 1e9,
                "Change in NWC ($B)": delta_nwc / 1e9,
                "Unlevered FCF ($B)": fcff / 1e9,
                "Discount Factor": discount_factor,
                "PV of FCF ($B)": pv_fcff / 1e9,
            }
        )
        curr_rev = proj_rev

    proj_df = pd.DataFrame(rows)

    final_fcff = proj_df.iloc[-1]["Unlevered FCF ($B)"] * 1e9
    terminal_value = (final_fcff * (1 + terminal_growth_rate)) / (wacc - terminal_growth_rate)
    pv_terminal_value = terminal_value / ((1 + wacc) ** projection_years)

    sum_pv_fcff = proj_df["PV of FCF ($B)"].sum() * 1e9
    implied_ev = sum_pv_fcff + pv_terminal_value
    implied_equity_val = implied_ev + cash - total_debt
    implied_share_price = max(implied_equity_val / shares_out, 0.0) if shares_out > 0 else 0.0
    current_price = info.get("currentPrice") or info.get("regularMarketPrice") or 0.0
    upside_pct = ((implied_share_price - current_price) / current_price * 100) if current_price > 0 else 0.0

    wacc_range = [wacc - 0.01, wacc - 0.005, wacc, wacc + 0.005, wacc + 0.01]
    tgr_range = [terminal_growth_rate - 0.005, terminal_growth_rate, terminal_growth_rate + 0.005]
    sens_data = {}
    for g in tgr_range:
        col_prices = []
        for w in wacc_range:
            if w <= g + 0.005:
                col_prices.append(np.nan)
            else:
                pv_f = sum(
                    (proj_df.loc[i, "Unlevered FCF ($B)"] * 1e9) / ((1 + w) ** (i + 1))
                    for i in range(projection_years)
                )
                tv = (final_fcff * (1 + g)) / (w - g)
                pv_tv = tv / ((1 + w) ** projection_years)
                eq_v = pv_f + pv_tv + cash - total_debt
                col_prices.append(round(max(eq_v / shares_out, 0.0), 2))
        sens_data[f"TGR {g*100:.1f}%"] = col_prices

    sens_df = pd.DataFrame(sens_data, index=[f"WACC {w*100:.2f}%" for w in wacc_range])

    return {
        "projections": proj_df,
        "sensitivity": sens_df,
        "wacc_details": {
            "Cost of Equity (%)": round(cost_of_equity * 100, 2),
            "After-Tax Cost of Debt (%)": round(after_tax_cost_debt * 100, 2),
            "Equity Weight (%)": round(weight_equity * 100, 1),
            "Debt Weight (%)": round(weight_debt * 100, 1),
            "Calculated WACC (%)": round(wacc * 100, 2),
            "Terminal Growth Rate (%)": round(terminal_growth_rate * 100, 2),
        },
        "valuation_bridge": {
            "PV of 5Y Cash Flows ($B)": round(sum_pv_fcff / 1e9, 2),
            "PV of Terminal Value ($B)": round(pv_terminal_value / 1e9, 2),
            "Implied Enterprise Value ($B)": round(implied_ev / 1e9, 2),
            "Plus: Cash & Equivalents ($B)": round(cash / 1e9, 2),
            "Less: Total Debt ($B)": round(total_debt / 1e9, 2),
            "Implied Equity Value ($B)": round(implied_equity_val / 1e9, 2),
            "Implied Share Price ($)": round(implied_share_price, 2),
            "Current Market Price ($)": round(current_price, 2),
            "Implied Upside / Downside (%)": round(upside_pct, 2),
        },
    }