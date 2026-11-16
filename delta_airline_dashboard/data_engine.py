import yfinance as yf
import pandas as pd
import numpy as np
import html
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse


COMPANIES = {
    "Delta Air Lines (DAL)": {
        "ticker": "DAL", "currency": "USD", "currency_symbol": "$",
        "benchmarks": ("^GSPC", "JETS"), "benchmark_names": ("S&P 500", "U.S. Airlines ETF"),
        "risk_profile": "airlines", "exclude_years": ("2021",),
        "sector": "Industrials", "industry": "Airlines",
        "overview": "Delta Air Lines is a U.S.-based passenger airline. Use this dashboard to prepare a client discussion on its financial performance, market position, and exposure to fuel, currency, and interest-rate movements.",
    },
    "adidas AG (ADS.DE)": {
        "ticker": "ADS.DE", "currency": "EUR", "currency_symbol": "€",
        "benchmarks": ("^GDAXI", "^GSPC"), "benchmark_names": ("DAX", "S&P 500"),
        "risk_profile": "consumer_apparel", "exclude_years": (),
        "sector": "Consumer Cyclical", "industry": "Apparel and Sporting Goods",
        "overview": "adidas is a global sportswear and sporting-goods company. This dashboard supports discussion of its financial performance, market position, and exposure to consumer demand, sourcing, and foreign exchange.",
    },
    "Deutsche Lufthansa AG (LHA.DE)": {
        "ticker": "LHA.DE", "currency": "EUR", "currency_symbol": "€",
        "benchmarks": ("^GDAXI", "^GSPC"), "benchmark_names": ("DAX", "S&P 500"),
        "risk_profile": "airlines", "exclude_years": (),
        "sector": "Industrials", "industry": "Airlines and Aviation Services",
        "overview": "Deutsche Lufthansa AG is an airline and aviation-services group. This dashboard supports discussion of its financial performance, market position, and exposure to fuel, currency, and interest-rate movements.",
    },
    "BMW AG (BMW.DE)": {
        "ticker": "BMW.DE", "currency": "EUR", "currency_symbol": "€",
        "benchmarks": ("^GDAXI", "^GSPC"), "benchmark_names": ("DAX", "S&P 500"),
        "risk_profile": "automotive", "exclude_years": (),
        "sector": "Consumer Cyclical", "industry": "Automobiles",
        "overview": "BMW AG is an automotive manufacturer. This dashboard supports discussion of its financial performance, market position, and exposure to consumer demand, supply chains, and foreign exchange.",
    },
    "Siemens AG (SIE.DE)": {
        "ticker": "SIE.DE", "currency": "EUR", "currency_symbol": "€",
        "benchmarks": ("^GDAXI", "^GSPC"), "benchmark_names": ("DAX", "S&P 500"),
        "risk_profile": "industrials", "exclude_years": (),
        "sector": "Industrials", "industry": "Industrial Technology",
        "overview": "Siemens AG is an industrial technology company. This dashboard supports discussion of its financial performance, market position, and exposure to industrial investment, project delivery, and foreign exchange.",
    },
    "SAP SE (SAP.DE)": {
        "ticker": "SAP.DE", "currency": "EUR", "currency_symbol": "€",
        "benchmarks": ("^GDAXI", "^GSPC"), "benchmark_names": ("DAX", "S&P 500"),
        "risk_profile": "software", "exclude_years": (),
        "sector": "Technology", "industry": "Enterprise Software",
        "overview": "SAP SE develops enterprise software. This dashboard supports discussion of its financial performance, market position, and exposure to software demand, cloud adoption, and foreign exchange.",
    },
}


def fetch_company_data(
    ticker_symbol: str,
    benchmark_symbols: tuple[str, ...] = ("^GSPC", "JETS"),
    currency: str = "USD",
) -> dict:
    """Fetch market and statement data for the selected company and benchmarks."""
    ticker = yf.Ticker(ticker_symbol)
    warnings = []

    try:
        info = ticker.info or {}
    except Exception as exc:
        info = {}
        warnings.append(f"Quote profile unavailable ({type(exc).__name__}).")
    if not info:
        warnings.append("Yahoo Finance returned no quote profile for this ticker.")

    # fast_info is often available even when Yahoo's full quote profile is
    # incomplete. Read each field independently because yfinance properties
    # are lazy and a single unavailable field should not discard the others.
    fast_info = {}
    try:
        fast_source = ticker.fast_info
    except Exception:
        fast_source = None
    for field, aliases in {
        "currency": ("currency",),
        "market_cap": ("market_cap", "marketCap"),
        "last_price": ("last_price", "lastPrice"),
        "shares": ("shares", "shares_outstanding", "sharesOutstanding"),
        "year_high": ("year_high", "yearHigh"),
        "year_low": ("year_low", "yearLow"),
    }.items():
        for alias in aliases:
            try:
                value = fast_source.get(alias) if hasattr(fast_source, "get") else getattr(fast_source, alias, None)
                if value is not None and np.isfinite(float(value)):
                    fast_info[field] = value
                    break
            except Exception:
                continue

    try:
        hist = ticker.history(period="3y")
    except Exception as exc:
        hist = pd.DataFrame()
        warnings.append(f"Price history unavailable ({type(exc).__name__}).")
    if hist.empty:
        warnings.append("Yahoo Finance returned no daily price history for this ticker.")

    latest_history_price = 0.0
    if not hist.empty and "Close" in hist:
        close_values = pd.to_numeric(hist["Close"], errors="coerce").dropna()
        if not close_values.empty:
            latest_history_price = float(close_values.iloc[-1])

    # Normalize the commonly used quote fields so downstream valuation
    # functions have one consistent fallback path.
    if not _safe_info_number(info, "currentPrice", "regularMarketPrice"):
        fallback_price = _safe_info_number(fast_info, "last_price") or latest_history_price
        if fallback_price > 0:
            info["currentPrice"] = fallback_price
            info["regularMarketPrice"] = fallback_price
    if not _safe_info_number(info, "marketCap") and _safe_info_number(fast_info, "market_cap") > 0:
        info["marketCap"] = _safe_info_number(fast_info, "market_cap")
    if not _safe_info_number(info, "sharesOutstanding") and _safe_info_number(fast_info, "shares") > 0:
        info["sharesOutstanding"] = _safe_info_number(fast_info, "shares")
    if not info.get("currency"):
        info["currency"] = fast_info.get("currency") or currency
    for info_key, fast_key in (("fiftyTwoWeekHigh", "year_high"), ("fiftyTwoWeekLow", "year_low")):
        if not _safe_info_number(info, info_key) and _safe_info_number(fast_info, fast_key) > 0:
            info[info_key] = _safe_info_number(fast_info, fast_key)

    try:
        if callable(getattr(ticker, "get_news", None)):
            raw_news = ticker.get_news(count=12, tab="news") or []
        else:
            raw_news = ticker.news or []
    except Exception as exc:
        raw_news = []
        warnings.append(f"Company news unavailable ({type(exc).__name__}).")
    if not raw_news and callable(getattr(yf, "Search", None)):
        try:
            search_results = yf.Search(ticker_symbol, max_results=1, news_count=12)
            raw_news = getattr(search_results, "news", []) or []
        except Exception:
            # Keep the dashboard usable when the secondary news endpoint is unavailable.
            raw_news = []

    def normalize_news_item(item: dict) -> dict | None:
        content = item.get("content") if isinstance(item.get("content"), dict) else item
        title = str(content.get("title") or "").strip()
        if not title:
            return None

        provider_value = content.get("provider") or content.get("publisher") or {}
        provider = provider_value.get("displayName", "") if isinstance(provider_value, dict) else str(provider_value)
        url_value = content.get("canonicalUrl") or content.get("clickThroughUrl") or content.get("link") or item.get("link")
        url = url_value.get("url", "") if isinstance(url_value, dict) else str(url_value or "")
        try:
            if urlparse(url).scheme not in {"http", "https"}:
                url = ""
        except ValueError:
            url = ""
        summary = str(content.get("summary") or content.get("description") or content.get("snippet") or "").strip()
        summary = html.unescape(re.sub(r"<[^>]+>", " ", summary))
        summary = re.sub(r"\s+", " ", summary)

        published_value = content.get("pubDate") or content.get("displayTime") or content.get("providerPublishTime") or item.get("providerPublishTime")
        published_at = ""
        published_display = "Date not provided"
        published_dt = None
        try:
            if isinstance(published_value, (int, float)):
                published_dt = datetime.fromtimestamp(published_value, tz=timezone.utc)
            elif published_value:
                published_dt = datetime.fromisoformat(str(published_value).replace("Z", "+00:00"))
                if published_dt.tzinfo is None:
                    published_dt = published_dt.replace(tzinfo=timezone.utc)
                published_dt = published_dt.astimezone(timezone.utc)
        except (OverflowError, OSError, TypeError, ValueError):
            published_dt = None
        if published_dt is not None:
            published_at = published_dt.isoformat()
            published_display = published_dt.strftime("%d %b %Y %H:%M UTC")

        return {
            "title": title,
            "summary": summary,
            "publisher": provider or "Publisher not listed",
            "published_at": published_at,
            "published_display": published_display,
            "url": url,
        }

    normalized_news = [
        normalized for item in raw_news
        if isinstance(item, dict) and (normalized := normalize_news_item(item)) is not None
    ]
    news_cutoff = datetime.now(timezone.utc) - timedelta(days=45)
    news = []
    for item in normalized_news:
        if item["published_at"]:
            published_dt = datetime.fromisoformat(item["published_at"])
            if published_dt < news_cutoff:
                continue
        news.append(item)
        if len(news) >= 8:
            break

    def fetch_statement(attribute: str, label: str) -> pd.DataFrame:
        try:
            statement = getattr(ticker, attribute)
            return statement if isinstance(statement, pd.DataFrame) else pd.DataFrame()
        except Exception as exc:
            warnings.append(f"{label} unavailable ({type(exc).__name__}).")
            return pd.DataFrame()

    income_stmt = fetch_statement("financials", "Annual income statement")
    balance_sheet = fetch_statement("balance_sheet", "Balance sheet")
    cash_flow = fetch_statement("cashflow", "Cash flow statement")

    has_annual_revenue = not income_stmt.empty and bool(
        (_safe_get(income_stmt, ["Total Revenue", "Operating Revenue", "Revenue", "Total Revenues"])).gt(0).any()
    )
    quarterly_income_stmt = pd.DataFrame()
    quarterly_balance_sheet = pd.DataFrame()
    quarterly_cash_flow = pd.DataFrame()
    if not has_annual_revenue:
        quarterly_income_stmt = fetch_statement("quarterly_financials", "Quarterly income statement")
        quarterly_balance_sheet = fetch_statement("quarterly_balance_sheet", "Quarterly balance sheet")
        quarterly_cash_flow = fetch_statement("quarterly_cashflow", "Quarterly cash flow statement")
    else:
        needs_quarterly_supplement = False

        def has_statement_values(statement: pd.DataFrame, keys: list[str]) -> bool:
            return not statement.empty and bool(_safe_get(statement, keys).abs().gt(0).any())

        has_ebit = has_statement_values(income_stmt, ["EBIT", "Operating Income", "Operating Income Loss", "Income From Operations"])
        has_net_income = has_statement_values(income_stmt, ["Net Income", "Net Income Common Stockholders", "Net Income From Continuing Operations"])
        if not (has_ebit and has_net_income):
            needs_quarterly_supplement = True
            quarterly_income_stmt = fetch_statement("quarterly_financials", "Quarterly income statement")
        has_total_debt = has_statement_values(balance_sheet, ["Total Debt", "Total Debt And Capital Lease Obligation"])
        has_debt_components = (
            has_statement_values(balance_sheet, ["Long Term Debt And Capital Lease Obligation", "Long Term Debt"])
            and has_statement_values(balance_sheet, ["Current Debt And Capital Lease Obligation", "Current Debt", "Short Term Debt"])
        )
        has_cash = has_statement_values(balance_sheet, ["Cash And Cash Equivalents", "Cash Cash Equivalents And Short Term Investments", "Cash And Cash Equivalents And Short Term Investments"])
        has_equity = has_statement_values(balance_sheet, ["Stockholders Equity", "Total Equity Gross Minority Interest", "Common Stock Equity"])
        if not ((has_total_debt or has_debt_components) and has_cash and has_equity):
            needs_quarterly_supplement = True
            quarterly_balance_sheet = fetch_statement("quarterly_balance_sheet", "Quarterly balance sheet")
        has_operating_cash_flow = has_statement_values(cash_flow, ["Operating Cash Flow", "Cash Flow From Continuing Operating Activities", "Net Cash Provided By Operating Activities"])
        has_capex = has_statement_values(cash_flow, ["Capital Expenditure", "Capital Expenditures", "Purchase Of PPE", "Payments To Acquire Property Plant And Equipment"])
        has_depreciation = has_statement_values(cash_flow, ["Depreciation And Amortization", "Depreciation Amortization Depletion", "Depreciation Depletion And Amortization"])
        has_reported_ebitda = has_statement_values(income_stmt, ["EBITDA", "Normalized EBITDA", "Adjusted EBITDA"])
        if not (has_operating_cash_flow and has_capex) or (not has_reported_ebitda and not has_depreciation):
            needs_quarterly_supplement = True
            quarterly_cash_flow = fetch_statement("quarterly_cashflow", "Quarterly cash flow statement")
        if needs_quarterly_supplement and quarterly_income_stmt.empty:
            quarterly_income_stmt = fetch_statement("quarterly_financials", "Quarterly income statement")

    if not income_stmt.empty:
        income_stmt = income_stmt.iloc[:, ::-1]
    if not balance_sheet.empty:
        balance_sheet = balance_sheet.iloc[:, ::-1]
    if not cash_flow.empty:
        cash_flow = cash_flow.iloc[:, ::-1]
    if not quarterly_income_stmt.empty:
        quarterly_income_stmt = quarterly_income_stmt.iloc[:, ::-1]
    if not quarterly_balance_sheet.empty:
        quarterly_balance_sheet = quarterly_balance_sheet.iloc[:, ::-1]
    if not quarterly_cash_flow.empty:
        quarterly_cash_flow = quarterly_cash_flow.iloc[:, ::-1]
    if income_stmt.empty:
        warnings.append("Annual income statement was not returned; using trailing-twelve-month quote or quarterly data when available.")
    elif not has_annual_revenue:
        warnings.append("Annual revenue rows were missing; using trailing-twelve-month quote or quarterly data when available.")

    symbols = list(dict.fromkeys([ticker_symbol, *benchmark_symbols]))
    benchmarks = pd.DataFrame()
    try:
        downloaded = yf.download(symbols, period="2y", progress=False, auto_adjust=True)
        if isinstance(downloaded.columns, pd.MultiIndex):
            close_level = next(
                (level for level in range(downloaded.columns.nlevels) if "Close" in downloaded.columns.get_level_values(level)),
                None,
            )
            if close_level is not None:
                benchmarks = downloaded.xs("Close", axis=1, level=close_level, drop_level=True)
                if isinstance(benchmarks, pd.Series):
                    benchmarks = benchmarks.to_frame(name=ticker_symbol)
        elif "Close" in downloaded.columns:
            benchmarks = downloaded[["Close"]].rename(columns={"Close": ticker_symbol})
    except Exception:
        benchmarks = pd.DataFrame()

    # Yahoo's multi-symbol endpoint can fail or change column layout for some
    # listings. Retry missing instruments individually so one bad symbol does
    # not remove the selected company's chart or every benchmark.
    for symbol in symbols:
        if symbol in benchmarks.columns:
            continue
        try:
            individual_history = yf.Ticker(symbol).history(period="2y", auto_adjust=True)
            if not individual_history.empty and "Close" in individual_history.columns:
                benchmarks[symbol] = pd.to_numeric(individual_history["Close"], errors="coerce")
        except Exception:
            continue

    missing_symbols = [symbol for symbol in symbols if symbol not in benchmarks.columns]
    if missing_symbols:
        warnings.append(f"No market chart data was returned for: {', '.join(missing_symbols)}.")

    return {
        "ticker": ticker_symbol,
        "currency": info.get("currency") or currency,
        "info": info,
        "fast_info": fast_info,
        "history": hist,
        "news": news,
        "income_stmt": income_stmt,
        "balance_sheet": balance_sheet,
        "cash_flow": cash_flow,
        "quarterly_income_stmt": quarterly_income_stmt,
        "quarterly_balance_sheet": quarterly_balance_sheet,
        "quarterly_cash_flow": quarterly_cash_flow,
        "annual_financials_available": has_annual_revenue,
        "benchmarks": benchmarks,
        "warnings": warnings,
        "fetched_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def fetch_delta_data(ticker_symbol: str = "DAL") -> dict:
    """Backward-compatible alias for the original Delta data loader."""
    return fetch_company_data(ticker_symbol)


def _normalized_label(value) -> str:
    value = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def _safe_get(df: pd.DataFrame, possible_keys: list, columns=None) -> pd.Series:
    target_columns = list(columns) if columns is not None else None
    if df is None or df.empty:
        return pd.Series(0.0, index=target_columns or [])

    rows_by_label = {}
    for label in df.index:
        rows_by_label.setdefault(_normalized_label(label), label)
    for key in possible_keys:
        matched_label = rows_by_label.get(_normalized_label(key))
        if matched_label is None:
            continue
        row = df.loc[matched_label]
        if isinstance(row, pd.DataFrame):
            row = row.iloc[0]
        series = pd.to_numeric(row, errors="coerce").fillna(0)
        if target_columns is not None:
            return series.reindex(target_columns).fillna(0)
        return series
    return pd.Series(0.0, index=target_columns if target_columns is not None else df.columns)


def _safe_info_number(info: dict, *keys: str) -> float:
    for key in keys:
        try:
            value = float(info.get(key) or 0.0)
            if np.isfinite(value):
                return value
        except (TypeError, ValueError):
            continue
    return 0.0


def _summary_from_ttm_info(data: dict) -> pd.DataFrame:
    """Build a clearly labelled TTM row when Yahoo omits annual statements."""
    info = data.get("info") or {}
    q_inc = data.get("quarterly_income_stmt", pd.DataFrame())
    q_cf = data.get("quarterly_cash_flow", pd.DataFrame())
    q_bs = data.get("quarterly_balance_sheet", pd.DataFrame())

    def trailing_sum(statement: pd.DataFrame, keys: list[str]) -> float:
        if statement is None or statement.empty:
            return 0.0
        periods = list(statement.columns[-4:])
        return float(_safe_get(statement, keys, periods).sum())

    revenue = _safe_info_number(info, "totalRevenue") or trailing_sum(
        q_inc, ["Total Revenue", "Operating Revenue", "Revenue", "Total Revenues"]
    )
    if revenue <= 0:
        return pd.DataFrame()

    ebitda = _safe_info_number(info, "ebitda", "normalizedEBITDA") or trailing_sum(
        q_inc, ["EBITDA", "Normalized EBITDA", "Adjusted EBITDA"]
    )
    ebit = _safe_info_number(info, "operatingIncome", "ebit") or trailing_sum(
        q_inc, ["EBIT", "Operating Income", "Operating Income Loss", "Income From Operations"]
    )
    if ebitda == 0 and ebit:
        depreciation = abs(trailing_sum(
            q_cf,
            ["Depreciation And Amortization", "Depreciation Amortization Depletion", "Depreciation Depletion And Amortization"],
        ))
        ebitda = ebit + depreciation
    net_income = _safe_info_number(info, "netIncomeToCommon", "netIncome") or trailing_sum(
        q_inc,
        ["Net Income", "Net Income Common Stockholders", "Net Income From Continuing Operations", "Net Income From Continuing Operation Net Minority Interest"],
    )
    operating_cash_flow = _safe_info_number(info, "operatingCashflow", "operatingCashFlow") or trailing_sum(
        q_cf, ["Operating Cash Flow", "Cash Flow From Continuing Operating Activities", "Net Cash Provided By Operating Activities"]
    )
    free_cash_flow = _safe_info_number(info, "freeCashflow", "freeCashFlow")
    if not free_cash_flow and operating_cash_flow:
        quarterly_capex = abs(trailing_sum(q_cf, ["Capital Expenditure", "Capital Expenditures", "Purchase Of PPE", "Payments To Acquire Property Plant And Equipment"]))
        free_cash_flow = operating_cash_flow - quarterly_capex
    capex = max(operating_cash_flow - free_cash_flow, 0.0)
    latest_balance_column = list(q_bs.columns[-1:]) if q_bs is not None and not q_bs.empty else []
    total_debt = _safe_info_number(info, "totalDebt") or float(
        _safe_get(q_bs, ["Total Debt", "Total Debt And Capital Lease Obligation"], latest_balance_column).sum()
    )
    if total_debt == 0:
        total_debt = float(_safe_get(
            q_bs,
            ["Long Term Debt And Capital Lease Obligation", "Long Term Debt"],
            latest_balance_column,
        ).sum()) + float(_safe_get(
            q_bs,
            ["Current Debt And Capital Lease Obligation", "Current Debt", "Short Term Debt"],
            latest_balance_column,
        ).sum())
    cash = _safe_info_number(info, "totalCash") or float(
        _safe_get(q_bs, ["Cash And Cash Equivalents And Short Term Investments", "Cash Cash Equivalents And Short Term Investments", "Cash And Cash Equivalents"], latest_balance_column).sum()
    )
    equity = _safe_info_number(info, "totalStockholderEquity") or float(
        _safe_get(q_bs, ["Stockholders Equity", "Total Equity Gross Minority Interest", "Common Stock Equity", "Total Shareholders Equity"], latest_balance_column).sum()
    )
    interest_expense = abs(_safe_info_number(info, "interestExpense") or trailing_sum(
        q_inc, ["Interest Expense", "Interest Expense Non Operating", "Interest And Debt Expense"]
    ))
    operating_margin = _safe_info_number(info, "operatingMargins") * 100
    if operating_margin == 0 and ebit > 0:
        operating_margin = ebit / revenue * 100

    row = {
        "Year": "TTM",
        "Revenue ($B)": revenue / 1e9,
        "EBIT ($B)": ebit / 1e9,
        "EBITDA ($B)": ebitda / 1e9,
        "Net Income ($B)": net_income / 1e9,
        "Operating Cash Flow ($B)": operating_cash_flow / 1e9,
        "CapEx ($B)": capex / 1e9,
        "Free Cash Flow ($B)": free_cash_flow / 1e9,
        "Total Debt ($B)": total_debt / 1e9,
        "Cash & Equivalents ($B)": cash / 1e9,
        "Net Debt ($B)": (total_debt - cash) / 1e9,
        "Total Equity ($B)": equity / 1e9,
        "Interest Expense ($B)": interest_expense / 1e9,
        "Operating Margin (%)": operating_margin,
        "EBITDA Margin (%)": ebitda / revenue * 100 if ebitda else 0,
        "Net Margin (%)": net_income / revenue * 100 if net_income else 0,
        "Net Debt / EBITDA (x)": (total_debt - cash) / ebitda if ebitda > 0 else 0,
    }
    return pd.DataFrame([row])


def extract_financial_summary(data: dict, exclude_years: tuple[str, ...] = ()) -> pd.DataFrame:
    inc = data["income_stmt"]
    bs = data["balance_sheet"]
    cf = data["cash_flow"]

    if inc.empty:
        return _summary_from_ttm_info(data)

    raw_years = [col.strftime("%Y") if hasattr(col, "strftime") else str(col)[:4] for col in inc.columns]

    periods = inc.columns
    rev = _safe_get(inc, ["Total Revenue", "Operating Revenue", "Revenue", "Total Revenues"], periods).values
    if not np.any(np.asarray(rev, dtype=float) > 0):
        return _summary_from_ttm_info(data)
    ebit = _safe_get(inc, ["EBIT", "Operating Income", "Operating Income Loss", "Income From Operations"], periods).values
    ebitda = _safe_get(inc, ["EBITDA", "Normalized EBITDA", "Adjusted EBITDA"], periods).values
    net_inc = _safe_get(inc, ["Net Income", "Net Income Common Stockholders", "Net Income From Continuing Operations", "Net Income From Continuing Operation Net Minority Interest"], periods).values
    int_exp = np.abs(_safe_get(inc, ["Interest Expense", "Interest Expense Non Operating", "Interest And Debt Expense"], periods).values)

    depreciation = np.abs(_safe_get(
        cf,
        ["Depreciation And Amortization", "Depreciation Amortization Depletion", "Depreciation Depletion And Amortization"],
        periods,
    ).values)
    ebitda = np.asarray(ebitda, dtype=float)
    calculated_ebitda = np.asarray(ebit, dtype=float) + depreciation
    ebitda = np.where((ebitda == 0) & (calculated_ebitda != 0), calculated_ebitda, ebitda)

    total_debt = _safe_get(bs, ["Total Debt", "Total Debt And Capital Lease Obligation"], periods).values
    debt_components = _safe_get(bs, ["Long Term Debt And Capital Lease Obligation", "Long Term Debt"], periods).values + _safe_get(
        bs, ["Current Debt And Capital Lease Obligation", "Current Debt", "Short Term Debt"], periods
    ).values
    total_debt = np.where((np.asarray(total_debt, dtype=float) == 0) & (debt_components != 0), debt_components, total_debt)
    cash = _safe_get(bs, ["Cash And Cash Equivalents And Short Term Investments", "Cash Cash Equivalents And Short Term Investments", "Cash And Cash Equivalents"], periods).values
    equity = _safe_get(bs, ["Stockholders Equity", "Total Equity Gross Minority Interest", "Common Stock Equity", "Total Shareholders Equity"], periods).values

    ocf = _safe_get(cf, ["Operating Cash Flow", "Cash Flow From Continuing Operating Activities", "Net Cash Provided By Operating Activities"], periods).values
    capex = np.abs(_safe_get(cf, ["Capital Expenditure", "Capital Expenditures", "Purchase Of PPE", "Payments To Acquire Property Plant And Equipment"], periods).values)
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

    if exclude_years:
        df = df[~df["Year"].isin(exclude_years)].reset_index(drop=True)

    df["Operating Margin (%)"] = np.where(df["Revenue ($B)"] > 0, (df["EBIT ($B)"] / df["Revenue ($B)"]) * 100, 0)
    df["EBITDA Margin (%)"] = np.where(df["Revenue ($B)"] > 0, (df["EBITDA ($B)"] / df["Revenue ($B)"]) * 100, 0)
    df["Net Margin (%)"] = np.where(df["Revenue ($B)"] > 0, (df["Net Income ($B)"] / df["Revenue ($B)"]) * 100, 0)
    df["Net Debt / EBITDA (x)"] = np.where(df["EBITDA ($B)"] > 0, df["Net Debt ($B)"] / df["EBITDA ($B)"], 0)

    # When a full annual statement is present but omits specific rows, add a
    # separately labelled TTM row if Yahoo's quote or quarterly data can fill
    # those gaps. This preserves the period basis and avoids disguising missing
    # annual values as zeroes.
    ttm_df = _summary_from_ttm_info(data)
    if not ttm_df.empty and not df.empty:
        supplemental_fields = [
            "EBIT ($B)", "EBITDA ($B)", "Net Income ($B)",
            "Operating Cash Flow ($B)", "Free Cash Flow ($B)",
            "Total Debt ($B)", "Cash & Equivalents ($B)", "Total Equity ($B)",
        ]
        latest_annual = df.iloc[-1]
        ttm_values = ttm_df.iloc[0]
        has_missing_values = any(
            float(latest_annual.get(field, 0) or 0) == 0 and float(ttm_values.get(field, 0) or 0) != 0
            for field in supplemental_fields
        )
        if has_missing_values:
            df = pd.concat([df, ttm_df], ignore_index=True)

    return df


def extract_valuation_multiples(data: dict, fin_df: pd.DataFrame) -> dict:
    info = data.get("info") or {}
    fast_info = data.get("fast_info") or {}
    price = _safe_info_number(info, "currentPrice", "regularMarketPrice") or _safe_info_number(fast_info, "last_price")
    history = data.get("history")
    if price <= 0 and history is not None and not history.empty and "Close" in history:
        prices = pd.to_numeric(history["Close"], errors="coerce").dropna()
        price = float(prices.iloc[-1]) if not prices.empty else 0.0

    shares = _safe_info_number(info, "sharesOutstanding") or _safe_info_number(fast_info, "shares")
    balance_sheet = data.get("balance_sheet", pd.DataFrame())
    if shares <= 0 and balance_sheet is not None and not balance_sheet.empty:
        latest_balance_period = list(balance_sheet.columns[-1:])
        shares = float(_safe_get(
            balance_sheet,
            ["Ordinary Shares Number", "Share Issued", "Common Stock Shares Outstanding", "Common Shares Outstanding"],
            latest_balance_period,
        ).sum())

    mkt_cap = _safe_info_number(info, "marketCap") or _safe_info_number(fast_info, "market_cap")
    if mkt_cap <= 0:
        mkt_cap = shares * price
    if shares <= 0 and mkt_cap > 0 and price > 0:
        shares = mkt_cap / price

    latest = fin_df.iloc[-1] if not fin_df.empty else None
    latest_rev = (latest["Revenue ($B)"] * 1e9) if latest is not None else 0.0
    latest_ebitda = (latest["EBITDA ($B)"] * 1e9) if latest is not None else 0.0
    latest_fcf = (latest["Free Cash Flow ($B)"] * 1e9) if latest is not None else 0.0
    net_debt = (latest["Net Debt ($B)"] * 1e9) if latest is not None else 0.0
    ev = _safe_info_number(info, "enterpriseValue") or (mkt_cap + net_debt)
    latest_net_income = (latest["Net Income ($B)"] * 1e9) if latest is not None else 0.0
    latest_equity = (latest["Total Equity ($B)"] * 1e9) if latest is not None else 0.0

    trailing_pe = _safe_info_number(info, "trailingPE")
    if trailing_pe <= 0 and latest_net_income > 0 and mkt_cap > 0:
        trailing_pe = mkt_cap / latest_net_income
    price_to_book = _safe_info_number(info, "priceToBook")
    if price_to_book <= 0 and latest_equity > 0 and mkt_cap > 0:
        price_to_book = mkt_cap / latest_equity
    dividend_yield = _safe_info_number(info, "dividendYield")
    if dividend_yield <= 0 and price > 0:
        dividend_yield = _safe_info_number(info, "dividendRate") / price

    return {
        "Current Share Price ($)": round(price, 2),
        "Market Cap ($B)": round(mkt_cap / 1e9, 2),
        "Enterprise Value ($B)": round(ev / 1e9, 2),
        "Trailing P/E (x)": round(trailing_pe, 2),
        "Forward P/E (x)": round(_safe_info_number(info, "forwardPE"), 2),
        "EV / EBITDA (x)": round(_safe_info_number(info, "enterpriseToEbitda") or (ev / latest_ebitda if latest_ebitda > 0 else 0.0), 2),
        "EV / Revenue (x)": round(_safe_info_number(info, "enterpriseToRevenue") or (ev / latest_rev if latest_rev > 0 else 0.0), 2),
        "Price / Book (x)": round(price_to_book, 2),
        "Price / FCF (x)": round(mkt_cap / latest_fcf if latest_fcf > 0 else 0.0, 2),
        "FCF Yield (%)": round((latest_fcf / mkt_cap) * 100 if mkt_cap > 0 else 0.0, 2),
        "Dividend Yield (%)": round(dividend_yield * 100, 2),
        "Beta (5Y Monthly)": round(_safe_info_number(info, "beta") or 1.25, 2),
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
    info = data.get("info") or {}
    latest = fin_df.iloc[-1]

    base_rev = latest["Revenue ($B)"] * 1e9
    total_debt = latest["Total Debt ($B)"] * 1e9
    cash = latest["Cash & Equivalents ($B)"] * 1e9
    int_exp = latest["Interest Expense ($B)"] * 1e9

    fast_info = data.get("fast_info") or {}
    current_price = _safe_info_number(info, "currentPrice", "regularMarketPrice") or _safe_info_number(fast_info, "last_price")
    if current_price <= 0:
        history = data.get("history")
        if history is not None and not history.empty and "Close" in history:
            prices = pd.to_numeric(history["Close"], errors="coerce").dropna()
            current_price = float(prices.iloc[-1]) if not prices.empty else 0.0

    shares_out = _safe_info_number(info, "sharesOutstanding") or _safe_info_number(fast_info, "shares")
    if shares_out <= 0:
        balance_sheet = data.get("balance_sheet", pd.DataFrame())
        if balance_sheet is not None and not balance_sheet.empty:
            shares_out = float(_safe_get(
                balance_sheet,
                ["Ordinary Shares Number", "Share Issued", "Common Stock Shares Outstanding", "Common Shares Outstanding"],
                list(balance_sheet.columns[-1:]),
            ).sum())

    mkt_cap = _safe_info_number(info, "marketCap") or _safe_info_number(fast_info, "market_cap")
    if mkt_cap <= 0 and shares_out > 0 and current_price > 0:
        mkt_cap = shares_out * current_price
    if mkt_cap <= 0:
        mkt_cap = latest["Total Equity ($B)"] * 1e9
    if shares_out <= 0 and mkt_cap > 0 and current_price > 0:
        shares_out = mkt_cap / current_price
    beta = _safe_info_number(info, "beta") or 1.25

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
    try:
        base_year = int(str(latest["Year"]))
    except (TypeError, ValueError):
        base_year = datetime.now().year

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
