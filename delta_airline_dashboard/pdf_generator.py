import io
from datetime import datetime
from xml.sax.saxutils import escape
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
    body_style = ParagraphStyle("BodyTextCustom", parent=styles["Normal"], fontSize=9.2, leading=13.5, textColor=dark_text, spaceAfter=6)
    bullet_style = ParagraphStyle("BulletCustom", parent=body_style, leftIndent=12, bulletIndent=4, spaceAfter=4)

    elements = []
    info = data["info"]
    report_company = company_name or info.get("longName", "Selected company")
    excluded_note = f" | Excluded years: {', '.join(exclude_years)}" if exclude_years else ""

    elements.append(Paragraph("CGI ADVISORY – CORPORATE RISK MAPPING & HEDGING BRIEFING", subtitle_style))
    elements.append(Paragraph(escape(report_company), title_style))
    elements.append(Paragraph(f"Sector: {escape(str(info.get('sector') or 'Not reported'))} | Industry: {escape(str(info.get('industry') or 'Not reported'))}{excluded_note} | Generated: {datetime.now().strftime('%d %b %Y, %H:%M')}", subtitle_style))
    elements.append(HRFlowable(width="100%", thickness=2.0, color=cgi_red, spaceAfter=10))

    elements.append(Paragraph("1. Executive Performance & Risk Summary", h2_style))
    elements.append(Paragraph(escape(executive_summary), body_style))

    elements.append(Paragraph("2. Market Multiples & DCF Valuation Summary", h2_style))
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

    val_table = Table(val_table_data, colWidths=[52 * mm, 36 * mm, 54 * mm, 36 * mm])
    val_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), cgi_violet),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, slate]),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#DCD6E8")),
        ("PADDING", (0, 0), (-1, -1), 5),
    ]))
    elements.append(val_table)
    elements.append(Spacer(1, 8))

    elements.append(Paragraph(f"3. Historical Financial Performance ({currency_code} Billions{excluded_note})", h2_style))
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

    elements.append(Paragraph("4. Treasury Hedging Scheme Design & Recommendations", h2_style))
    for rec in hedging_recommendations:
        elements.append(Paragraph(f"• <b>{escape(rec['title'])}:</b> {escape(rec['detail'])}", bullet_style))

    elements.append(Spacer(1, 10))
    elements.append(HRFlowable(width="100%", thickness=0.6, color=muted_text, spaceAfter=4))
    elements.append(Paragraph("Confidential – Prepared for CGI Client Engagement & Meeting Preparation.", subtitle_style))

    doc.build(elements)
    return buffer.getvalue()
