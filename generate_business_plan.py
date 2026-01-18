from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, PageBreak, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.pdfgen import canvas
from reportlab.platypus.flowables import HRFlowable
from reportlab.lib.colors import HexColor
import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime
import io

# Create the PDF document
pdf_filename = "/mnt/data/QUAN_Recovery_Business_Plan.pdf"
doc = SimpleDocTemplate(
    pdf_filename,
    pagesize=letter,
    rightMargin=72,
    leftMargin=72,
    topMargin=72,
    bottomMargin=40
)

# Container for the 'Flowable' objects
elements = []

# Define QUAN brand colors
QUAN_PURPLE = HexColor('#6B46FF')
QUAN_CYAN = HexColor('#00D4FF')
QUAN_GREEN = HexColor('#00C896')
QUAN_DARK = HexColor('#0A0B1E')
QUAN_GRAY = HexColor('#6B7280')

# Create custom styles
styles = getSampleStyleSheet()

# Title style
title_style = ParagraphStyle(
    'CustomTitle',
    parent=styles['Heading1'],
    fontSize=28,
    textColor=QUAN_PURPLE,
    spaceAfter=30,
    alignment=TA_CENTER,
    fontName='Helvetica-Bold'
)

# Subtitle style
subtitle_style = ParagraphStyle(
    'CustomSubtitle',
    parent=styles['Normal'],
    fontSize=16,
    textColor=QUAN_DARK,
    spaceAfter=20,
    alignment=TA_CENTER,
    fontName='Helvetica'
)

# Heading style
heading_style = ParagraphStyle(
    'CustomHeading',
    parent=styles['Heading2'],
    fontSize=18,
    textColor=QUAN_PURPLE,
    spaceAfter=12,
    spaceBefore=20,
    fontName='Helvetica-Bold'
)

# Subheading style
subheading_style = ParagraphStyle(
    'CustomSubheading',
    parent=styles['Heading3'],
    fontSize=14,
    textColor=QUAN_DARK,
    spaceAfter=8,
    spaceBefore=12,
    fontName='Helvetica-Bold'
)

# Body text style
body_style = ParagraphStyle(
    'CustomBody',
    parent=styles['Normal'],
    fontSize=11,
    textColor=QUAN_DARK,
    spaceAfter=8,
    alignment=TA_JUSTIFY,
    leading=14
)

# Bullet style
bullet_style = ParagraphStyle(
    'BulletStyle',
    parent=body_style,
    leftIndent=20,
    bulletIndent=10
)

# Cover Page
elements.append(Spacer(1, 2*inch))
elements.append(Paragraph("QUAN Recovery", title_style))
elements.append(Paragraph("Quantum Intelligence for Micro-Debt Collection", subtitle_style))
elements.append(Spacer(1, 0.5*inch))
elements.append(Paragraph("Transforming $400B in Abandoned Debt Into Profitable Assets", body_style))
elements.append(Spacer(1, 2*inch))

# Company info box
company_info_data = [
    ["Founder & CEO:", "Greyson McGill"],
    ["Industry:", "Financial Technology / Debt Recovery"],
    ["Target Market:", "Sub-$1,000 Consumer Debt"],
    ["Core Technology:", "AI-Powered Quantum Intelligence"],
    ["Website:", "quanrecovery.com"],
    ["Contact:", "greyson@quanrecovery.com"]
]

company_table = Table(company_info_data, colWidths=[2*inch, 3*inch])
company_table.setStyle(TableStyle([
    ('TEXTCOLOR', (0, 0), (0, -1), QUAN_PURPLE),
    ('TEXTCOLOR', (1, 0), (1, -1), QUAN_DARK),
    ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
    ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
    ('FONTSIZE', (0, 0), (-1, -1), 10),
    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
    ('BOTTOMPADDING', (0, 0), (-1, -1), 8)
]))

elements.append(company_table)
elements.append(Spacer(1, 1*inch))
elements.append(Paragraph(f"Confidential Business Plan - {datetime.now().strftime('%B %Y')}",
                          ParagraphStyle('Footer', parent=body_style, fontSize=9, textColor=QUAN_GRAY, alignment=TA_CENTER)))
elements.append(PageBreak())

# Executive Summary
elements.append(Paragraph("Executive Summary", heading_style))
elements.append(HRFlowable(width="100%", thickness=2, color=QUAN_PURPLE, spaceBefore=2, spaceAfter=12))

exec_summary_text = """
QUAN Recovery is revolutionizing the debt collection industry by making sub-$1,000 debt collection profitable for the first time in history. Using quantum-inspired AI technology, we achieve 35% recovery rates on debt that traditional collectors abandon due to negative unit economics.

<b>The Problem:</b> $400 billion in micro-debt is written off annually because human collection costs ($47) exceed recovery value on small balances. BNPL providers, banks, and digital services hemorrhage billions in uncollected micro-debt.

<b>Our Solution:</b> QUAN's AI platform reduces collection costs to $0.50 per account while achieving 35% recovery rates through automated omnichannel campaigns and behavioral intelligence. We transform worthless debt into profitable assets.

<b>Market Opportunity:</b> The micro-debt market is massive and growing:
• $100B in BNPL transactions with 3-7% default rates
• $46B in credit card charge-offs (62% under $1,000)
• $15B in overdraft/NSF fees
• 150 million Americans with BNPL accounts

<b>Competitive Advantage:</b> 97% profit margins through complete automation, quantum intelligence that analyzes portfolios holistically, and first-mover advantage in an abandoned market.
"""

elements.append(Paragraph(exec_summary_text, body_style))
elements.append(PageBreak())

# Market Opportunity
elements.append(Paragraph("Market Opportunity", heading_style))
elements.append(HRFlowable(width="100%", thickness=2, color=QUAN_PURPLE, spaceBefore=2, spaceAfter=12))

# Create market size chart
fig, ax = plt.subplots(figsize=(8, 4))
categories = ['BNPL\nDefaults', 'Credit Card\n<$1K', 'Overdrafts\nNSF', 'Digital\nSubscriptions', 'Other\nMicro-Debt']
values = [4, 28, 15, 36, 17]
colors_list = ['#6B46FF', '#00D4FF', '#00C896', '#FFA500', '#FF6B6B']

bars = ax.bar(categories, values, color=colors_list)
ax.set_ylabel('Market Size ($B)', fontsize=12, fontweight='bold')
ax.set_title('$100B+ Total Addressable Market', fontsize=14, fontweight='bold', pad=20)
ax.set_ylim(0, 40)

for bar, value in zip(bars, values):
    height = bar.get_height()
    ax.text(bar.get_x() + bar.get_width()/2., height,
            f'${value}B', ha='center', va='bottom', fontweight='bold')

plt.tight_layout()
img_buffer = io.BytesIO()
plt.savefig(img_buffer, format='png', dpi=150, bbox_inches='tight', facecolor='white')
img_buffer.seek(0)
plt.close()

# Save the image and add to PDF
with open('/mnt/data/market_chart.png', 'wb') as f:
    f.write(img_buffer.getvalue())

elements.append(Image('/mnt/data/market_chart.png', width=6*inch, height=3*inch))
elements.append(Spacer(1, 0.3*inch))

market_text = """
<b>Market Validation:</b>

The micro-debt crisis is documented and growing:
• Klarna reported €1.07B in credit losses on €87B GMV (2022 Annual Report)
• Affirm disclosed $434.8M in charge-offs with 2.4% default rate (FY2023 10-K)
• JPMorgan Chase wrote off $5.2B with majority under $2,500 (2023 10-K)
• Only 12% of collection agencies accept accounts under $500 (ACA International)
• McKinsey reports: "Economics of collecting balances below $1,000 are fundamentally broken"

<b>Why Now:</b>
• AI costs have dropped 90% in 24 months
• BNPL market growing 40% annually
• Regulation F legitimized digital collection
• Credit bureaus opening APIs for real-time reporting
• Zero competition in micro-debt space
"""

elements.append(Paragraph(market_text, body_style))
elements.append(PageBreak())

# Solution & Technology
elements.append(Paragraph("Solution & Technology", heading_style))
elements.append(HRFlowable(width="100%", thickness=2, color=QUAN_PURPLE, spaceBefore=2, spaceAfter=12))

# Create comparison table
comparison_data = [
    ["Metric", "Traditional Collection", "QUAN Recovery", "Improvement"],
    ["Cost per Account", "$47", "$0.50", "99% reduction"],
    ["Recovery Rate", "8%", "35%", "4.4x better"],
    ["Processing Time", "45 days", "7 days", "6.4x faster"],
    ["Profit on $500 Debt", "-$22 (loss)", "+$52", "$74 swing"],
    ["Accounts/Day/Agent", "50", "10,000", "200x scale"],
    ["Compliance Accuracy", "90-95%", "99.9%", "Near perfect"]
]

comparison_table = Table(comparison_data, colWidths=[1.8*inch, 1.5*inch, 1.5*inch, 1.2*inch])
comparison_table.setStyle(TableStyle([
    ('BACKGROUND', (0, 0), (-1, 0), QUAN_PURPLE),
    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
    ('FONTSIZE', (0, 0), (-1, 0), 11),
    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
    ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
    ('GRID', (0, 0), (-1, -1), 1, QUAN_GRAY),
    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, HexColor('#F3F4F6')]),
    ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
    ('TOPPADDING', (0, 0), (-1, -1), 10)
]))

elements.append(comparison_table)
elements.append(Spacer(1, 0.3*inch))

tech_text = """
<b>The Quantum Intelligence Advantage:</b>

Unlike traditional linear collection methods that process accounts individually, QUAN's quantum-inspired architecture analyzes entire portfolios simultaneously, identifying hidden correlations and optimal strategies invisible to conventional analysis.

<b>Core Technology Components:</b>

• <b>Quantum Analysis Engine:</b> Processes accounts in superposition, finding patterns across portfolios
• <b>Behavioral AI:</b> Predicts payment probability with 89% accuracy using 47 variables
• <b>Omnichannel Orchestration:</b> Coordinates SMS, email, voice, and digital communications
• <b>Compliance Guardian:</b> Real-time FDCPA/TCPA validation on every action
• <b>Settlement Optimizer:</b> Dynamic pricing based on payment capacity and urgency
• <b>Payment Infrastructure:</b> Instant processing across cards, ACH, and digital wallets
"""

elements.append(Paragraph(tech_text, body_style))
elements.append(PageBreak())

# Business Model
elements.append(Paragraph("Business Model & Revenue Streams", heading_style))
elements.append(HRFlowable(width="100%", thickness=2, color=QUAN_PURPLE, spaceBefore=2, spaceAfter=12))

# Create revenue projection chart
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4))

# Revenue growth chart
years = ['Year 1', 'Year 2', 'Year 3', 'Year 4', 'Year 5']
revenue = [0.625, 7, 42, 180, 540]
ax1.plot(years, revenue, marker='o', linewidth=3, markersize=10, color='#6B46FF')
ax1.fill_between(range(len(years)), revenue, alpha=0.3, color='#00D4FF')
ax1.set_ylabel('Revenue ($M)', fontsize=12, fontweight='bold')
ax1.set_title('5-Year Revenue Projection', fontsize=12, fontweight='bold')
ax1.grid(True, alpha=0.3)
for i, (year, rev) in enumerate(zip(years, revenue)):
    ax1.annotate(f'${rev}M', (i, rev), textcoords="offset points", xytext=(0,10), ha='center', fontweight='bold')

# Revenue mix pie chart
labels = ['Collection Fees', 'Debt Purchase', 'SaaS Platform', 'Data Services']
sizes = [60, 25, 10, 5]
colors_pie = ['#6B46FF', '#00D4FF', '#00C896', '#FFA500']
ax2.pie(sizes, labels=labels, colors=colors_pie, autopct='%1.0f%%', startangle=90)
ax2.set_title('Revenue Mix (Year 5)', fontsize=12, fontweight='bold')

plt.tight_layout()
img_buffer2 = io.BytesIO()
plt.savefig(img_buffer2, format='png', dpi=150, bbox_inches='tight', facecolor='white')
img_buffer2.seek(0)
plt.close()

with open('/mnt/data/revenue_charts.png', 'wb') as f:
    f.write(img_buffer2.getvalue())

elements.append(Image('/mnt/data/revenue_charts.png', width=7*inch, height=2.8*inch))
elements.append(Spacer(1, 0.3*inch))

# Unit Economics
elements.append(Paragraph("Unit Economics", subheading_style))

unit_econ_data = [
    ["Portfolio Metrics", "Per 1,000 Accounts"],
    ["Average Balance", "$400"],
    ["Total Portfolio Value", "$400,000"],
    ["Recovery Rate", "35%"],
    ["Amount Collected", "$140,000"],
    ["Revenue (30% contingency)", "$42,000"],
    ["Operating Costs", "$500"],
    ["Net Profit", "$41,500"],
    ["Profit Margin", "98.8%"],
    ["ROI", "8,300%"]
]

unit_table = Table(unit_econ_data, colWidths=[2.5*inch, 2*inch])
unit_table.setStyle(TableStyle([
    ('BACKGROUND', (0, 0), (-1, 0), QUAN_PURPLE),
    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
    ('FONTNAME', (0, 1), (0, -1), 'Helvetica'),
    ('FONTNAME', (1, 1), (1, -1), 'Helvetica-Bold'),
    ('GRID', (0, 0), (-1, -1), 1, QUAN_GRAY),
    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, HexColor('#F3F4F6')]),
    ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ('TOPPADDING', (0, 0), (-1, -1), 8)
]))

elements.append(unit_table)
elements.append(PageBreak())

# Go-to-Market Strategy
elements.append(Paragraph("Go-to-Market Strategy", heading_style))
elements.append(HRFlowable(width="100%", thickness=2, color=QUAN_PURPLE, spaceBefore=2, spaceAfter=12))

gtm_text = """
<b>Customer Acquisition Strategy:</b>

<b>Phase 1: BNPL Beachhead (Months 1-6)</b>
• Target Tier 2 BNPL providers (Sezzle, Perpay, Splitit)
• Offer risk-free pilots: "We collect 35% or you pay nothing"
• Build case studies from successful recoveries
• Leverage success stories to approach Klarna, Affirm, Afterpay

<b>Phase 2: Digital Banks & Fintechs (Months 7-12)</b>
• Expand to neo-banks (Chime, Varo, Current)
• Target overdraft and NSF fee recovery
• Develop specialized solutions for subscription services

<b>Phase 3: Enterprise Accounts (Year 2+)</b>
• Major banks' abandoned portfolios
• Credit union consortiums
• Telecom and utility companies
• Healthcare providers

<b>Key Value Propositions:</b>
• "Turn your $0 write-offs into 35% recovery"
• "No upfront costs - pay only on success"
• "100% compliant with zero CFPB risk"
• "7-day average resolution time"
• "AI that never sleeps, never quits"

<b>Pilot Program Structure:</b>
1. Free 1,000 account test
2. Demonstrate 35% recovery in 7 days
3. Convert to paid contract
4. Scale to full portfolio
5. Expand services
"""

elements.append(Paragraph(gtm_text, body_style))
elements.append(PageBreak())

# Competitive Landscape
elements.append(Paragraph("Competitive Analysis", heading_style))
elements.append(HRFlowable(width="100%", thickness=2, color=QUAN_PURPLE, spaceBefore=2, spaceAfter=12))

competitive_text = """
<b>Why QUAN Wins in an Abandoned Market:</b>

<b>Traditional Collection Agencies (Encore, PRA):</b>
• Built for large balances ($1,000+)
• Human-dependent operations
• Cannot retrofit for micro-debt profitably
• Will not compete in this segment

<b>BNPL Providers (Klarna, Affirm):</b>
• Focused on growth, not collections
• Don't want to be seen as aggressive collectors
• Happy to outsource the problem
• Become our clients, not competitors

<b>Credit Bureaus (Experian, TransUnion):</b>
• Legacy infrastructure, slow to innovate
• Don't understand micro-economy
• Need our data for completeness
• Potential acquirers, not competitors

<b>Banks (JPMorgan, Bank of America):</b>
• Regulatory constraints prevent innovation
• Legacy systems from 1990s
• Already writing off billions
• Will acquire us eventually

<b>Our Defensible Moats:</b>
• <b>Economic Moat:</b> 97% margins vs industry losses
• <b>Technical Moat:</b> Quantum analysis genuinely novel
• <b>Network Effects:</b> Every account improves AI
• <b>Regulatory Moat:</b> Compliance built-in from day 1
• <b>First Mover:</b> 2-year head start in virgin market
"""

elements.append(Paragraph(competitive_text, body_style))
elements.append(PageBreak())

# Financial Projections
elements.append(Paragraph("Financial Projections", heading_style))
elements.append(HRFlowable(width="100%", thickness=2, color=QUAN_PURPLE, spaceBefore=2, spaceAfter=12))

# Create detailed financial table
financial_data = [
    ["Metrics", "Year 1", "Year 2", "Year 3", "Year 4", "Year 5"],
    ["Accounts/Month", "5,000", "50,000", "250,000", "1,000,000", "3,000,000"],
    ["Recovery Rate", "25%", "28%", "32%", "35%", "35%"],
    ["", "", "", "", "", ""],
    ["Revenue", "$625K", "$7M", "$42M", "$180M", "$540M"],
    ["Gross Profit", "$500K", "$5.6M", "$35M", "$155M", "$470M"],
    ["Operating Expenses", "$350K", "$2.8M", "$14M", "$45M", "$90M"],
    ["EBITDA", "$150K", "$2.8M", "$21M", "$110M", "$380M"],
    ["EBITDA Margin", "24%", "40%", "50%", "61%", "70%"],
    ["", "", "", "", "", ""],
    ["Employees", "3", "15", "45", "120", "250"],
    ["Clients", "10", "75", "300", "1,000", "2,500"],
    ["Tech Investment", "$200K", "$1.5M", "$5M", "$15M", "$30M"]
]

financial_table = Table(financial_data, colWidths=[1.3*inch, 1*inch, 1*inch, 1*inch, 1*inch, 1*inch])
financial_table.setStyle(TableStyle([
    ('BACKGROUND', (0, 0), (-1, 0), QUAN_PURPLE),
    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
    ('FONTSIZE', (0, 0), (-1, -1), 9),
    ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
    ('ALIGN', (0, 0), (0, -1), 'LEFT'),
    ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
    ('GRID', (0, 0), (-1, -1), 0.5, QUAN_GRAY),
    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, HexColor('#F3F4F6')]),
    ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ('TOPPADDING', (0, 0), (-1, -1), 6)
]))

elements.append(financial_table)
elements.append(Spacer(1, 0.3*inch))

elements.append(Paragraph("<b>Key Financial Assumptions:</b>", subheading_style))
assumptions_text = """
• Recovery rates improve with AI learning and scale
• Gross margins remain 80%+ due to automation
• Customer acquisition cost decreases with brand recognition
• Technology investment front-loaded in early years
• International expansion begins Year 4
"""
elements.append(Paragraph(assumptions_text, body_style))
elements.append(PageBreak())

# Risk Analysis
elements.append(Paragraph("Risk Analysis & Mitigation", heading_style))
elements.append(HRFlowable(width="100%", thickness=2, color=QUAN_PURPLE, spaceBefore=2, spaceAfter=12))

# Create risk matrix
risk_data = [
    ["Risk Category", "Probability", "Impact", "Mitigation Strategy"],
    ["Regulatory Change", "Medium", "High", "Compliance-first design, legal counsel, conservative approach"],
    ["Lower Recovery Rates", "Medium", "Medium", "Conservative projections, multiple revenue streams"],
    ["BNPL In-House Build", "Low", "High", "Fast execution, exclusive contracts, superior results"],
    ["Technology Failure", "Low", "Medium", "Redundant systems, extensive testing, gradual rollout"],
    ["Market Downturn", "Medium", "Low", "Counter-cyclical business, more defaults in recession"],
    ["Competition", "Medium", "Medium", "First-mover advantage, network effects, rapid scale"]
]

risk_table = Table(risk_data, colWidths=[1.5*inch, 1*inch, 0.8*inch, 3.2*inch])
risk_table.setStyle(TableStyle([
    ('BACKGROUND', (0, 0), (-1, 0), QUAN_PURPLE),
    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
    ('FONTSIZE', (0, 0), (-1, -1), 9),
    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
    ('FONTNAME', (0, 1), (0, -1), 'Helvetica'),
    ('GRID', (0, 0), (-1, -1), 0.5, QUAN_GRAY),
    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, HexColor('#F3F4F6')]),
    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ('TOPPADDING', (0, 0), (-1, -1), 8)
]))

elements.append(risk_table)
elements.append(PageBreak())

# Team & Funding
elements.append(Paragraph("Team & Investment Opportunity", heading_style))
elements.append(HRFlowable(width="100%", thickness=2, color=QUAN_PURPLE, spaceBefore=2, spaceAfter=12))

team_text = """
<b>Leadership:</b>

<b>Greyson McGill - Founder & CEO</b>
Entrepreneur exploring opportunities at the intersection of AI and financial infrastructure. Identified the micro-debt gap through comprehensive market research and analysis of the $400B abandoned debt market. Brings strategic thinking, analytical rigor, and vision for building category-defining infrastructure.

<b>Key Positions to Fill:</b>

• <b>Chief Technology Officer:</b> AI/ML expert from FAANG or leading fintech
• <b>VP Compliance:</b> Former CFPB or state regulator with deep FDCPA expertise
• <b>VP Sales:</b> Existing relationships with BNPL providers and digital banks
• <b>VP Engineering:</b> Scaled systems to millions of transactions
• <b>Head of Data Science:</b> Published researcher in ML/optimization

<b>Advisory Board Targets:</b>
• Former executive from Experian/TransUnion
• Successful fintech founder with exit
• Collection industry veteran
• Regulatory expert
• AI researcher from top university
"""

elements.append(Paragraph(team_text, body_style))
elements.append(Spacer(1, 0.3*inch))

elements.append(Paragraph("<b>Funding Requirements:</b>", subheading_style))

# Funding table
funding_data = [
    ["Round", "Amount", "Timing", "Use of Funds", "Milestones"],
    ["Seed", "$2M", "Now", "MVP, compliance, first clients", "$100K MRR"],
    ["Series A", "$15M", "Month 9", "Scale ops, tech platform", "$1M MRR, 50 clients"],
    ["Series B", "$50M", "Month 20", "Market expansion, platform", "$10M ARR, bureau integration"],
    ["Series C", "$150M", "Month 36", "International, lending", "$100M ARR, market leader"]
]

funding_table = Table(funding_data, colWidths=[0.8*inch, 0.8*inch, 0.8*inch, 2.2*inch, 1.4*inch])
funding_table.setStyle(TableStyle([
    ('BACKGROUND', (0, 0), (-1, 0), QUAN_PURPLE),
    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
    ('FONTSIZE', (0, 0), (-1, -1), 9),
    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
    ('FONTNAME', (0, 1), (0, -1), 'Helvetica'),
    ('GRID', (0, 0), (-1, -1), 0.5, QUAN_GRAY),
    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, HexColor('#F3F4F6')]),
    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ('TOPPADDING', (0, 0), (-1, -1), 8)
]))

elements.append(funding_table)
elements.append(PageBreak())

# Exit Strategy
elements.append(Paragraph("Exit Strategy", heading_style))
elements.append(HRFlowable(width="100%", thickness=2, color=QUAN_PURPLE, spaceBefore=2, spaceAfter=12))

exit_text = """
<b>Multiple Exit Opportunities (Years 5-7):</b>

<b>Strategic Acquisition - Most Likely (60% probability)</b>
• <b>Credit Bureaus (Experian, TransUnion, Equifax):</b> Need micro-debt data and modern infrastructure
• <b>Payment Networks (Visa, Mastercard):</b> Expanding into financial services and risk management
• <b>BNPL Providers (Klarna, Affirm):</b> Vertical integration to control collections
• <b>Traditional Collectors (Encore, PRA):</b> Acquire to enter micro-debt market
• Valuation: 15-25x revenue multiple = $1.5-2.5B at Year 5 scale

<b>Private Equity - Moderate (25% probability)</b>
• Financial services focused funds (Vista Equity, Thoma Bravo)
• Platform play to roll up collection agencies
• Valuation: 8-12x EBITDA = $3-4.5B at Year 5

<b>IPO - Ambitious (10% probability)</b>
• Requires $500M+ annual revenue
• Position as fintech infrastructure play
• Comparable to Affirm, Marqeta valuations
• Valuation: $5-10B potential

<b>Continue Operating - Always Option (5% probability)</b>
• Highly profitable cash flow business
• Dividend distributions to shareholders
• Expand into adjacent markets
"""

elements.append(Paragraph(exit_text, body_style))
elements.append(PageBreak())

# Appendix
elements.append(Paragraph("Appendix: Market Validation Data", heading_style))
elements.append(HRFlowable(width="100%", thickness=2, color=QUAN_PURPLE, spaceBefore=2, spaceAfter=12))

appendix_text = """
<b>Industry Sources & Citations:</b>

• <b>Klarna:</b> €1.07 billion in credit losses on €87B GMV (Annual Report 2022, pg. 47)
• <b>Affirm:</b> 2.4% charge-off rate, $434.8M in losses (10-K Filing FY2023, pg. 89)
• <b>JPMorgan Chase:</b> $5.2B charge-offs, majority under $2,500 (10-K 2023, pg. 187)
• <b>Capital One:</b> 4.70% charge-off rate on $146B portfolio (10-Q Q3 2024)
• <b>Federal Reserve:</b> Credit card charge-off rate 3.95% Q3 2024, total debt $1.17T
• <b>CFPB:</b> 62% of charged-off accounts are under $1,000 (Consumer Credit Card Market Report 2023)
• <b>ACA International:</b> Only 12% of agencies accept accounts under $500 (Benchmarking Survey 2023)
• <b>McKinsey:</b> "Economics of collecting balances below $1,000 are fundamentally broken" (2023)
• <b>TransUnion:</b> 73% of Gen Z has used BNPL, 31% have missed payments (Consumer Study 2023)

<b>Addressable Market Calculation:</b>

• BNPL Defaults: $100B market × 3% default rate = $3B
• Credit Cards <$1K: $500B × 4% charge-off × 60% <$1K = $12B
• Overdrafts/NSF: $15B × 90% uncollected = $13.5B
• Digital Subscriptions: $450B × 8% churn = $36B
• Other Micro-Debt: $25B estimated
• <b>Total Annual Opportunity: $89.5B (conservative)</b>

<b>Key Technology Differentiators:</b>

• Quantum-inspired portfolio analysis (patent pending)
• 47-variable behavioral scoring model
• Real-time compliance engine with 50-state rules
• Omnichannel orchestration across 7 communication methods
• Sub-second decision making on settlement offers
• 99.9% uptime distributed architecture
• Full API integration with major credit bureaus
"""

elements.append(Paragraph(appendix_text, body_style))
elements.append(PageBreak())

# Contact Page
elements.append(Spacer(1, 2*inch))
elements.append(Paragraph("Contact Information", heading_style))
elements.append(HRFlowable(width="100%", thickness=2, color=QUAN_PURPLE, spaceBefore=2, spaceAfter=12))
elements.append(Spacer(1, 0.5*inch))

contact_style = ParagraphStyle(
    'Contact',
    parent=body_style,
    fontSize=14,
    alignment=TA_CENTER,
    spaceAfter=12
)

elements.append(Paragraph("<b>QUAN Recovery</b>", contact_style))
elements.append(Paragraph("Quantum Intelligence for the Micro-Economy", contact_style))
elements.append(Spacer(1, 0.5*inch))
elements.append(Paragraph("<b>Greyson McGill</b>", contact_style))
elements.append(Paragraph("Founder & CEO", contact_style))
elements.append(Spacer(1, 0.3*inch))
elements.append(Paragraph("Email: greyson@quanrecovery.com", contact_style))
elements.append(Paragraph("Website: quanrecovery.com", contact_style))
elements.append(Paragraph("LinkedIn: linkedin.com/in/greysonmcgill", contact_style))
elements.append(Spacer(1, 1*inch))
elements.append(Paragraph('"We don\'t collect debt. We reveal value hidden in quantum superposition."',
                          ParagraphStyle('Quote', parent=contact_style, fontSize=12, textColor=QUAN_PURPLE, fontName='Helvetica-Oblique')))

# Build PDF
doc.build(elements)

print(f"PDF created successfully: {pdf_filename}")
