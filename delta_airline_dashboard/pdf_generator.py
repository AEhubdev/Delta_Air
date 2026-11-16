import io
import re
from datetime import datetime
from urllib.parse import urlparse
from xml.sax.saxutils import escape, quoteattr
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    HRFlowable,
)


def generate_executive_pdf(
    data: dict,
    fin_df,
    multiples: dict,
    dcf_results: dict,
    executive_summary: str,
    hedging_recommendations: list,
    currency_symbol: str = "$",
    currency_code: str = "USD",
    company_name: str | None = None,
    exclude_years: tuple[str, ...] = (),
    ai_financial_summary: str = "",
    ai_news_summary: str = "",
    company_news: list[dict] | None = None,
    dcf_assumptions: dict | None = None,
    data_timestamp: str = "Not available",
) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=16 * mm,
        leftMargin=16 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
    )

    styles = getSampleStyleSheet()
    cgi_violet = colors.HexColor("#5236AB")
    cgi_red = colors.HexColor("#E31937")
    cgi_magenta = colors.HexColor("#9B185A")
    slate = colors.HexColor("#F7F7FA")
    dark_text = colors.HexColor("#1C1C1C")
    muted_text = colors.HexColor("#555566")

    title_style = ParagraphStyle("ReportTitle", parent=styles["Heading1"], fontSize=18, leading=22, textColor=cgi_violet, spaceAfter=4)
    subtitle_style = ParagraphStyle("ReportSubtitle", parent=styles["Normal"], fontSize=9.5, textColor=muted_text, spaceAfter=10)
    h2_style = ParagraphStyle("SectionHeader", parent=styles["Heading2"], fontSize=12, leading=15, textColor=cgi_magenta, spaceBefore=12, spaceAfter=6)
    h3_style = ParagraphStyle("AISectionHeader", parent=styles["Heading3"], fontSize=10, leading=13, textColor=cgi_violet, spaceBefore=5, spaceAfter=3)
    body_style = ParagraphStyle("BodyTextCustom", parent=styles["Normal"], fontSize=9.2, leading=13.5, textColor=dark_text, spaceAfter=6)
    bullet_style = ParagraphStyle("BulletCustom", parent=body_style, leftIndent=12, bulletIndent=4, spaceAfter=4)

    elements = []

    def pdf_text(value) -> str:
        return str(value).translate(str.maketrans({"\u2010": "-", "\u2011": "-", "\u2012": "-", "\u2013": "-", "\u2014": "-", "\u2212": "-"}))

    def append_ai_markdown(markdown_text: str, placeholder: str) -> None:
        if not markdown_text.strip():
            elements.append(Paragraph(escape(placeholder), body_style))
            return
        for source_line in markdown_text.splitlines():
            line = pdf_text(source_line.strip())
            if not line:
                continue
            heading = re.match(r"^#{1,3}\s+(.+)$", line)
            if heading:
                elements.append(Paragraph(escape(heading.group(1)), h3_style))
                continue
            if line.startswith(("- ", "* ", "• ")):
                line = line[2:].strip()
                safe_line = escape(line)
                safe_line = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", safe_line)
                elements.append(Paragraph(f"• {safe_line}", bullet_style))
                continue
            safe_line = escape(line)
            safe_line = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", safe_line)
            elements.append(Paragraph(safe_line, body_style))

    def add_table(table_data, widths, font_size=8):
        table = Table(table_data, colWidths=widths, repeatRows=1, hAlign="LEFT")
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), cgi_violet),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), font_size),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, slate]),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#DCD6E8")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("PADDING", (0, 0), (-1, -1), 5),
        ]))
        elements.append(table)

    info = data["info"]
    report_company = company_name or info.get("longName", "Selected company")
    excluded_note = f" | Excluded years: {', '.join(exclude_years)}" if exclude_years else ""

    elements.append(Paragraph("CGI ADVISORY - CORPORATE RISK MAPPING & HEDGING BRIEFING", subtitle_style))
    elements.append(Paragraph(escape(pdf_text(report_company)), title_style))
    elements.append(Paragraph(
        f"Sector: {escape(pdf_text(info.get('sector') or 'Not reported'))} | Industry: {escape(pdf_text(info.get('industry') or 'Not reported'))}"
        f"{pdf_text(excluded_note)} | Data updated: {escape(pdf_text(data_timestamp))} | Report generated: {datetime.now().strftime('%d %b %Y, %H:%M')}",
        subtitle_style,
    ))
    elements.append(HRFlowable(width="100%", thickness=2.0, color=cgi_red, spaceAfter=10))

    elements.append(Paragraph("1. Executive Performance & Risk Summary", h2_style))
    elements.append(Paragraph(escape(executive_summary), body_style))

    elements.append(Paragraph("2. AI Financial Analytics Summary", h2_style))
    append_ai_markdown(
        ai_financial_summary,
        "AI financial analysis was not generated in this session. Generate it from Tab 1 before exporting for the complete AI briefing.",
    )

    elements.append(Paragraph("3. Financial Trend Scorecard", h2_style))
    if not fin_df.empty:
        latest = fin_df.iloc[-1]
        prior = fin_df.iloc[-2] if len(fin_df) > 1 else None

        def show_value(row, column, suffix=""):
            return f"{float(row[column]):.2f}{suffix}" if row is not None else "n/a"

        def percent_change(current, previous):
            if previous is None or float(previous) <= 0:
                return "n/a"
            return f"{(float(current) / float(previous) - 1) * 100:+.1f}%"

        def point_change(current, previous):
            if current is None or previous is None:
                return "n/a"
            return f"{float(current) - float(previous):+.1f} pp"

        def multiple_change(current, previous):
            if previous is None:
                return "n/a"
            return f"{float(current) - float(previous):+.2f}x"

        latest_fcf_conversion = (
            latest["Free Cash Flow ($B)"] / latest["EBITDA ($B)"] * 100
            if latest["EBITDA ($B)"] > 0 else None
        )
        prior_fcf_conversion = (
            prior["Free Cash Flow ($B)"] / prior["EBITDA ($B)"] * 100
            if prior is not None and prior["EBITDA ($B)"] > 0 else None
        )
        scorecard = [
            ["Indicator", f"Latest ({latest['Year']})", f"Prior ({prior['Year'] if prior is not None else 'n/a'})", "Change / interpretation"],
            [f"Revenue ({currency_code}B)", show_value(latest, "Revenue ($B)"), show_value(prior, "Revenue ($B)"), percent_change(latest["Revenue ($B)"], prior["Revenue ($B)"] if prior is not None else None)],
            ["EBITDA margin", show_value(latest, "EBITDA Margin (%)", "%"), show_value(prior, "EBITDA Margin (%)", "%"), point_change(latest["EBITDA Margin (%)"], prior["EBITDA Margin (%)"] if prior is not None else None)],
            [f"Free cash flow ({currency_code}B)", show_value(latest, "Free Cash Flow ($B)"), show_value(prior, "Free Cash Flow ($B)"), "Positive" if latest["Free Cash Flow ($B)"] > 0 else "Negative"],
            ["FCF / EBITDA", f"{latest_fcf_conversion:.1f}%" if latest_fcf_conversion is not None else "n/a", f"{prior_fcf_conversion:.1f}%" if prior_fcf_conversion is not None else "n/a", point_change(latest_fcf_conversion, prior_fcf_conversion)],
            ["Net debt / EBITDA", show_value(latest, "Net Debt / EBITDA (x)", "x"), show_value(prior, "Net Debt / EBITDA (x)", "x"), multiple_change(latest["Net Debt / EBITDA (x)"], prior["Net Debt / EBITDA (x)"] if prior is not None else None)],
        ]
        add_table(scorecard, [43 * mm, 34 * mm, 34 * mm, 67 * mm], font_size=7.7)
        elements.append(Spacer(1, 7))

    elements.append(Paragraph("4. Market Multiples & DCF Valuation Summary", h2_style))
    bridge = dcf_results["valuation_bridge"]
    wacc_info = dcf_results["wacc_details"]

    val_table_data = [
        ["Market & Trading Multiples", "Value", "DCF Valuation Bridge", "Value"],
        ["Current Share Price", f"{currency_symbol}{multiples['Current Share Price ($)']:.2f}", "Implied Share Price (DCF)", f"{currency_symbol}{bridge['Implied Share Price ($)']:.2f}"],
        ["Market Capitalization", f"{currency_symbol}{multiples['Market Cap ($B)']:.2f}B", "Implied Upside / Downside", f"{bridge['Implied Upside / Downside (%)']:+.2f}%"],
        ["Enterprise Value (EV)", f"{currency_symbol}{multiples['Enterprise Value ($B)']:.2f}B", "Implied Enterprise Value", f"{currency_symbol}{bridge['Implied Enterprise Value ($B)']:.2f}B"],
        ["Trailing / Forward P/E", f"{multiples['Trailing P/E (x)']}x / {multiples['Forward P/E (x)']}x", "Calculated WACC", f"{wacc_info['Calculated WACC (%)']:.2f}%"],
        ["EV / EBITDA", f"{multiples['EV / EBITDA (x)']}x", "Terminal Growth Rate", f"{wacc_info['Terminal Growth Rate (%)']:.2f}%"],
        ["FCF Yield / Beta", f"{multiples['FCF Yield (%)']}% / {multiples['Beta (5Y Monthly)']}", f"Net Debt ({currency_code}B)", f"{currency_symbol}{fin_df.iloc[-1]['Net Debt ($B)']:.2f}B"],
    ]

    add_table(val_table_data, [52 * mm, 36 * mm, 54 * mm, 36 * mm], font_size=8)
    elements.append(Spacer(1, 8))

    elements.append(Paragraph("5. DCF Assumptions & Projection Detail", h2_style))
    if dcf_assumptions:
        assumption_items = list(dcf_assumptions.items())
        assumption_rows = [["Assumption", "Input", "Assumption", "Input"]]
        for index in range(0, len(assumption_items), 2):
            first_name, first_value = assumption_items[index]
            second_name, second_value = assumption_items[index + 1] if index + 1 < len(assumption_items) else ("", "")
            assumption_rows.append([first_name, first_value, second_name, second_value])
        add_table(assumption_rows, [50 * mm, 39 * mm, 50 * mm, 39 * mm], font_size=8)
        elements.append(Spacer(1, 6))

    projection_df = dcf_results.get("projections")
    if projection_df is not None and not projection_df.empty:
        projection_rows = [["Year", f"Revenue ({currency_code}B)", f"Unlevered FCF ({currency_code}B)", f"PV of FCF ({currency_code}B)"]]
        for _, projection in projection_df.iterrows():
            projection_rows.append([
                str(projection["Year"]),
                f"{projection['Revenue ($B)']:.2f}",
                f"{projection['Unlevered FCF ($B)']:.2f}",
                f"{projection['PV of FCF ($B)']:.2f}",
            ])
        add_table(projection_rows, [24 * mm, 52 * mm, 51 * mm, 51 * mm], font_size=8)
        elements.append(Spacer(1, 6))

    sensitivity_df = dcf_results.get("sensitivity")
    if sensitivity_df is not None and not sensitivity_df.empty:
        sensitivity_rows = [["WACC / TGR", *[str(column) for column in sensitivity_df.columns]]]
        for row_index, row in sensitivity_df.iterrows():
            sensitivity_rows.append([
                str(row_index),
                *["n/a" if value != value else f"{currency_symbol}{float(value):.2f}" for value in row],
            ])
        first_width = 34 * mm
        remaining_width = (178 * mm - first_width) / (len(sensitivity_df.columns) or 1)
        add_table(sensitivity_rows, [first_width] + [remaining_width] * len(sensitivity_df.columns), font_size=7)
        elements.append(Spacer(1, 8))

    elements.append(Paragraph(f"6. Historical Financial Performance ({currency_code} Billions{excluded_note})", h2_style))
    if not fin_df.empty:
        hist_headers = [f"Metric ({currency_code}B)"] + list(fin_df["Year"])
        metrics_to_show = [
            (f"Revenue ({currency_code}B)", "Revenue ($B)"),
            (f"EBIT ({currency_code}B)", "EBIT ($B)"),
            (f"EBITDA ({currency_code}B)", "EBITDA ($B)"),
            (f"Net Income ({currency_code}B)", "Net Income ($B)"),
            (f"Free Cash Flow ({currency_code}B)", "Free Cash Flow ($B)"),
            (f"Net Debt ({currency_code}B)", "Net Debt ($B)"),
            ("Operating Margin (%)", "Operating Margin (%)"),
        ]
        hist_rows = [hist_headers]
        for label, col_name in metrics_to_show:
            hist_rows.append([label] + [f"{val:.2f}" for val in fin_df[col_name]])

        col_w = [58 * mm] + [(120 / len(fin_df)) * mm] * len(fin_df)
        hist_table = Table(hist_rows, colWidths=col_w)
        hist_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), cgi_violet),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8.5),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, slate]),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#DCD6E8")),
            ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
            ("PADDING", (0, 0), (-1, -1), 5),
        ]))
        elements.append(hist_table)
        elements.append(Spacer(1, 8))

    elements.append(Paragraph("7. AI Recent Company News Summary", h2_style))
    append_ai_markdown(
        ai_news_summary,
        "No AI news summary was generated in this session. Generate the recent news summary from Tab 1 before exporting for AI news commentary.",
    )
    if company_news:
        elements.append(Paragraph("Recent source articles", h3_style))
        for article in company_news[:8]:
            title = escape(pdf_text(article.get("title") or "Untitled article"))
            publisher = escape(pdf_text(article.get("publisher") or "Publisher not listed"))
            published = escape(pdf_text(article.get("published_display") or "Date not provided"))
            url = str(article.get("url") or "")
            if urlparse(url).scheme in {"http", "https"}:
                title = f"<link href={quoteattr(url)} color=\"#5236AB\">{title}</link>"
            elements.append(Paragraph(f"• {title} <font color=\"#555566\">- {publisher} | {published}</font>", bullet_style))
    else:
        elements.append(Paragraph("No recent company articles were returned by the news feed.", body_style))

    elements.append(Paragraph("8. Treasury Discussion Points to Validate", h2_style))
    for rec in hedging_recommendations:
        elements.append(Paragraph(f"• <b>{escape(rec['title'])}:</b> {escape(rec['detail'])}", bullet_style))

    elements.append(Spacer(1, 10))
    elements.append(HRFlowable(width="100%", thickness=0.6, color=muted_text, spaceAfter=4))
    elements.append(Paragraph("Confidential - Prepared for CGI Client Engagement & Meeting Preparation.", subtitle_style))

    doc.build(elements)
    return buffer.getvalue()


def generate_custom_client_pdf(
    company_name: str,
    sector: str,
    industry: str,
    fin_df,
    multiples: dict,
    dcf_results: dict,
    executive_summary: str,
    ai_financial_summary: str,
    ai_news_summary: str,
    company_news: list[dict],
    discussion_points: list[dict],
    dcf_assumptions: dict,
    currency_symbol: str,
    currency_code: str,
    data_timestamp: str,
) -> bytes:
    """Create a concise, company-specific client meeting report."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=16 * mm,
        leftMargin=16 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
    )
    styles = getSampleStyleSheet()
    violet = colors.HexColor("#5236AB")
    red = colors.HexColor("#E31937")
    magenta = colors.HexColor("#9B185A")
    light = colors.HexColor("#F7F7FA")
    text_color = colors.HexColor("#1C1C1C")
    muted = colors.HexColor("#555566")
    title_style = ParagraphStyle(
        "CustomClientTitle", parent=styles["Heading1"], fontSize=20, leading=24,
        textColor=colors.white, spaceAfter=2,
    )
    subtitle_style = ParagraphStyle(
        "CustomClientSubtitle", parent=styles["Normal"], fontSize=9, leading=12,
        textColor=muted, spaceAfter=8,
    )
    section_style = ParagraphStyle(
        "CustomClientSection", parent=styles["Heading2"], fontSize=12, leading=15,
        textColor=magenta, spaceBefore=10, spaceAfter=5,
    )
    subheading_style = ParagraphStyle(
        "CustomClientSubheading", parent=styles["Heading3"], fontSize=9.5, leading=12,
        textColor=violet, spaceBefore=4, spaceAfter=3,
    )
    body_style = ParagraphStyle(
        "CustomClientBody", parent=styles["Normal"], fontSize=9, leading=12.5,
        textColor=text_color, spaceAfter=5,
    )
    bullet_style = ParagraphStyle(
        "CustomClientBullet", parent=body_style, leftIndent=12, bulletIndent=4, spaceAfter=3,
    )

    elements = []

    def safe_pdf_text(value) -> str:
        text = str(value)
        return text.translate(str.maketrans({"\u2010": "-", "\u2011": "-", "\u2012": "-", "\u2013": "-", "\u2014": "-", "\u2212": "-"}))

    def add_markdown(markdown_text: str, placeholder: str) -> None:
        if not markdown_text.strip():
            elements.append(Paragraph(escape(placeholder), body_style))
            return
        for source_line in markdown_text.splitlines():
            line = safe_pdf_text(source_line.strip())
            if not line:
                continue
            heading = re.match(r"^#{1,3}\s+(.+)$", line)
            if heading:
                elements.append(Paragraph(escape(heading.group(1)), subheading_style))
                continue
            is_bullet = line.startswith(("- ", "* ", "• "))
            if is_bullet:
                line = line[2:].strip()
            rendered = escape(line)
            rendered = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", rendered)
            elements.append(Paragraph(f"• {rendered}" if is_bullet else rendered, bullet_style if is_bullet else body_style))

    def add_table(rows, widths, font_size=8):
        table = Table(rows, colWidths=widths, repeatRows=1, hAlign="LEFT")
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), violet),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), font_size),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, light]),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#DCD6E8")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("PADDING", (0, 0), (-1, -1), 5),
        ]))
        elements.append(table)

    banner = Table(
        [[Paragraph("CUSTOM CLIENT MEETING BRIEF", title_style),
          Paragraph(escape(safe_pdf_text(company_name)), ParagraphStyle(
              "CustomClientName", parent=styles["Heading2"], fontSize=13, leading=16,
              textColor=colors.white, alignment=2,
          ))]],
        colWidths=[105 * mm, 73 * mm],
    )
    banner.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), violet),
        ("LINEBEFORE", (1, 0), (1, 0), 3, red),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]))
    elements.append(banner)
    elements.append(Spacer(1, 6))
    elements.append(Paragraph(
        f"{escape(safe_pdf_text(sector or 'Sector not reported'))} | "
        f"{escape(safe_pdf_text(industry or 'Industry not reported'))} | Reporting currency: {escape(currency_code)} | "
        f"Financial data updated: {escape(safe_pdf_text(data_timestamp))} | Prepared: {datetime.now().strftime('%d %b %Y, %H:%M')}",
        subtitle_style,
    ))
    elements.append(HRFlowable(width="100%", thickness=2, color=red, spaceAfter=6))

    elements.append(Paragraph("Meeting Brief", section_style))
    elements.append(Paragraph(escape(safe_pdf_text(executive_summary)), body_style))

    elements.append(Paragraph("Financial Snapshot", section_style))
    if fin_df is not None and not fin_df.empty:
        latest = fin_df.iloc[-1]
        prior = fin_df.iloc[-2] if len(fin_df) > 1 else None
        revenue_growth = None
        if prior is not None and float(prior["Revenue ($B)"]) > 0:
            revenue_growth = (float(latest["Revenue ($B)"]) / float(prior["Revenue ($B)"]) - 1) * 100
        latest_fcf_conversion = (
            float(latest["Free Cash Flow ($B)"]) / float(latest["EBITDA ($B)"]) * 100
            if float(latest["EBITDA ($B)"]) > 0 else None
        )
        snapshot_rows = [
            ["Measure", f"Latest period: {latest['Year']}", "Prior period / context"],
            [f"Revenue ({currency_code}B)", f"{latest['Revenue ($B)']:.2f}", f"{revenue_growth:+.1f}% growth" if revenue_growth is not None else "No comparable period"],
            [f"EBITDA ({currency_code}B)", f"{latest['EBITDA ($B)']:.2f}", f"{latest['EBITDA Margin (%)']:.1f}% margin"],
            [f"Free cash flow ({currency_code}B)", f"{latest['Free Cash Flow ($B)']:.2f}", f"{latest_fcf_conversion:.1f}% of EBITDA" if latest_fcf_conversion is not None else "FCF conversion n/a"],
            [f"Net debt ({currency_code}B)", f"{latest['Net Debt ($B)']:.2f}", f"{latest['Net Debt / EBITDA (x)']:.2f}x net debt / EBITDA"],
        ]
        add_table(snapshot_rows, [50 * mm, 55 * mm, 73 * mm], font_size=8)
    else:
        elements.append(Paragraph("No usable financial summary was available for this report.", body_style))

    elements.append(Paragraph("AI Financial Analysis", section_style))
    add_markdown(
        ai_financial_summary,
        "No AI financial summary was generated in this session. Generate it from Tab 1 before downloading the custom report.",
    )

    bridge = dcf_results["valuation_bridge"]
    wacc = dcf_results["wacc_details"]
    elements.append(Paragraph("Valuation Scenario", section_style))
    valuation_rows = [
        ["Market measure", "Current", "DCF scenario"],
        ["Share value", f"{currency_symbol}{multiples['Current Share Price ($)']:.2f}", f"{currency_symbol}{bridge['Implied Share Price ($)']:.2f}"],
        ["Enterprise value", f"{currency_symbol}{multiples['Enterprise Value ($B)']:.2f}B", f"{currency_symbol}{bridge['Implied Enterprise Value ($B)']:.2f}B"],
        ["Scenario change", "-", f"{bridge['Implied Upside / Downside (%)']:+.1f}%"],
        ["EV / EBITDA", f"{multiples['EV / EBITDA (x)']}x", f"WACC {wacc['Calculated WACC (%)']:.2f}%"],
    ]
    add_table(valuation_rows, [55 * mm, 55 * mm, 68 * mm], font_size=8)
    assumption_text = " | ".join(f"{name}: {value}" for name, value in dcf_assumptions.items())
    elements.append(Paragraph(f"Scenario assumptions: {escape(safe_pdf_text(assumption_text))}", subtitle_style))
    elements.append(Paragraph("DCF outputs are assumption-driven scenarios, not forecasts or investment recommendations.", subtitle_style))

    elements.append(Paragraph("Recent News and AI Synthesis", section_style))
    add_markdown(
        ai_news_summary,
        "No AI news summary was generated in this session. Generate it from Tab 1 before downloading the custom report.",
    )
    if company_news:
        elements.append(Paragraph("Source articles", subheading_style))
        for article in company_news[:6]:
            title = escape(safe_pdf_text(article.get("title") or "Untitled article"))
            publisher = escape(safe_pdf_text(article.get("publisher") or "Publisher not listed"))
            published = escape(safe_pdf_text(article.get("published_display") or "Date not provided"))
            url = str(article.get("url") or "")
            if urlparse(url).scheme in {"http", "https"}:
                title = f"<link href={quoteattr(url)} color=\"#5236AB\">{title}</link>"
            elements.append(Paragraph(f"• {title} <font color=\"#555566\">- {publisher} | {published}</font>", bullet_style))
    else:
        elements.append(Paragraph("No recent company news was returned by the news feed.", body_style))

    elements.append(Paragraph("Questions to Explore", section_style))
    for point in discussion_points:
        elements.append(Paragraph(
            f"• <b>{escape(safe_pdf_text(point.get('title') or 'Discussion point'))}:</b> "
            f"{escape(safe_pdf_text(point.get('detail') or ''))}",
            bullet_style,
        ))

    elements.append(Spacer(1, 8))
    elements.append(HRFlowable(width="100%", thickness=0.6, color=muted, spaceAfter=4))
    elements.append(Paragraph(
        "Prepared for client discussion using company financials, market data, and linked news sources available at the time shown above. "
        "News commentary is based on article headlines and available excerpts; confirm source details before relying on them.",
        subtitle_style,
    ))
    doc.build(elements)
    return buffer.getvalue()
