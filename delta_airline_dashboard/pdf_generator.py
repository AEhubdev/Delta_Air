import io
from datetime import datetime
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
    cgi_navy = colors.HexColor("#002B49")
    cgi_red = colors.HexColor("#E00034")
    slate = colors.HexColor("#F8FAFC")
    dark_text = colors.HexColor("#1E293B")
    muted_text = colors.HexColor("#64748B")

    title_style = ParagraphStyle("ReportTitle", parent=styles["Heading1"], fontSize=18, leading=22, textColor=cgi_navy, spaceAfter=4)
    subtitle_style = ParagraphStyle("ReportSubtitle", parent=styles["Normal"], fontSize=9.5, textColor=muted_text, spaceAfter=10)
    h2_style = ParagraphStyle("SectionHeader", parent=styles["Heading2"], fontSize=12, leading=15, textColor=cgi_navy, spaceBefore=12, spaceAfter=6)
    body_style = ParagraphStyle("BodyTextCustom", parent=styles["Normal"], fontSize=9.2, leading=13.5, textColor=dark_text, spaceAfter=6)
    bullet_style = ParagraphStyle("BulletCustom", parent=body_style, leftIndent=12, bulletIndent=4, spaceAfter=4)

    elements = []
    info = data["info"]

    elements.append(Paragraph("CGI CONSULTING – CORPORATE RISK MAPPING & HEDGING BRIEFING", subtitle_style))
    elements.append(Paragraph(f"{info.get('longName', 'Delta Air Lines, Inc.')} (NYSE: DAL)", title_style))
    elements.append(Paragraph(f"Sector: {info.get('sector', 'Industrials')} | Industry: {info.get('industry', 'Airlines')} | Generated: {datetime.now().strftime('%d %b %Y, %H:%M')}", subtitle_style))
    elements.append(HRFlowable(width="100%", thickness=1.5, color=cgi_red, spaceAfter=10))

    elements.append(Paragraph("1. Executive Performance & Risk Summary", h2_style))
    elements.append(Paragraph(executive_summary, body_style))

    elements.append(Paragraph("2. Market Multiples & DCF Valuation Summary", h2_style))
    bridge = dcf_results["valuation_bridge"]
    wacc_info = dcf_results["wacc_details"]

    val_table_data = [
        ["Market & Trading Multiples", "Value", "DCF Valuation Bridge", "Value"],
        ["Current Share Price", f"${multiples['Current Share Price ($)']:.2f}", "Implied Share Price (DCF)", f"${bridge['Implied Share Price ($)']:.2f}"],
        ["Market Capitalization", f"${multiples['Market Cap ($B)']:.2f}B", "Implied Upside / Downside", f"{bridge['Implied Upside / Downside (%)']:+.2f}%"],
        ["Enterprise Value (EV)", f"${multiples['Enterprise Value ($B)']:.2f}B", "Implied Enterprise Value", f"${bridge['Implied Enterprise Value ($B)']:.2f}B"],
        ["Trailing / Forward P/E", f"{multiples['Trailing P/E (x)']}x / {multiples['Forward P/E (x)']}x", "Calculated WACC", f"{wacc_info['Calculated WACC (%)']:.2f}%"],
        ["EV / EBITDA", f"{multiples['EV / EBITDA (x)']}x", "Terminal Growth Rate", f"{wacc_info['Terminal Growth Rate (%)']:.2f}%"],
        ["FCF Yield / Beta", f"{multiples['FCF Yield (%)']}% / {multiples['Beta (5Y Monthly)']}", "Net Debt ($B)", f"${fin_df.iloc[-1]['Net Debt ($B)']:.2f}B"],
    ]

    val_table = Table(val_table_data, colWidths=[52 * mm, 36 * mm, 54 * mm, 36 * mm])
    val_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), cgi_navy),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, slate]),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD5E1")),
        ("PADDING", (0, 0), (-1, -1), 5),
    ]))
    elements.append(val_table)
    elements.append(Spacer(1, 8))

    elements.append(Paragraph("3. Historical Financial Performance (USD Billions - Excl. 2021)", h2_style))
    if not fin_df.empty:
        hist_headers = ["Metric ($B)"] + list(fin_df["Year"])
        metrics_to_show = [
            ("Revenue ($B)", "Revenue ($B)"),
            ("EBIT ($B)", "EBIT ($B)"),
            ("EBITDA ($B)", "EBITDA ($B)"),
            ("Net Income ($B)", "Net Income ($B)"),
            ("Free Cash Flow ($B)", "Free Cash Flow ($B)"),
            ("Net Debt ($B)", "Net Debt ($B)"),
            ("Operating Margin (%)", "Operating Margin (%)"),
        ]
        hist_rows = [hist_headers]
        for label, col_name in metrics_to_show:
            hist_rows.append([label] + [f"{val:.2f}" for val in fin_df[col_name]])

        col_w = [58 * mm] + [(120 / len(fin_df)) * mm] * len(fin_df)
        hist_table = Table(hist_rows, colWidths=col_w)
        hist_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), cgi_navy),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8.5),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, slate]),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD5E1")),
            ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
            ("PADDING", (0, 0), (-1, -1), 5),
        ]))
        elements.append(hist_table)
        elements.append(Spacer(1, 8))

    elements.append(Paragraph("4. Treasury Hedging Scheme Design & Recommendations", h2_style))
    for rec in hedging_recommendations:
        elements.append(Paragraph(f"• <b>{rec['title']}:</b> {rec['detail']}", bullet_style))

    elements.append(Spacer(1, 10))
    elements.append(HRFlowable(width="100%", thickness=0.6, color=muted_text, spaceAfter=4))
    elements.append(Paragraph("Confidential – Prepared for CGI Client Engagement & Meeting Preparation.", subtitle_style))

    doc.build(elements)
    return buffer.getvalue()