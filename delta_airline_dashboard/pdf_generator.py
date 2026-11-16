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
