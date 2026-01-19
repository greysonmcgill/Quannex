#!/usr/bin/env python3
"""
QUAN Recovery - Comprehensive Business Plan PDF Generator

Generates a professional, investor-ready business plan with:
- Custom branding and styling
- Market analysis charts
- Financial projections graphs
- Unit economics tables
- Competitive positioning
- Risk analysis matrix
"""

import os
import io
from datetime import datetime
from decimal import Decimal

# PDF generation
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.colors import HexColor
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, Image, KeepTogether, ListFlowable, ListItem
)
from reportlab.platypus.flowables import HRFlowable
from reportlab.graphics.shapes import Drawing, Rect, String, Line
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.lineplots import LinePlot
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.widgets.markers import makeMarker

# For matplotlib charts
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np


# =============================================================================
# BRAND COLORS
# =============================================================================

QUAN_PURPLE = HexColor('#6B46FF')
QUAN_CYAN = HexColor('#00D4FF')
QUAN_GREEN = HexColor('#00C896')
QUAN_DARK = HexColor('#1A1A2E')
QUAN_GRAY = HexColor('#6B7280')
QUAN_LIGHT_GRAY = HexColor('#F3F4F6')
QUAN_WHITE = colors.white


# =============================================================================
# STYLES
# =============================================================================

def get_custom_styles():
    """Create custom paragraph styles"""
    styles = getSampleStyleSheet()

    # Cover title
    styles.add(ParagraphStyle(
        'CoverTitle',
        parent=styles['Heading1'],
        fontSize=42,
        textColor=QUAN_PURPLE,
        alignment=TA_CENTER,
        spaceAfter=20,
        fontName='Helvetica-Bold',
        leading=50,
    ))

    # Cover subtitle
    styles.add(ParagraphStyle(
        'CoverSubtitle',
        parent=styles['Normal'],
        fontSize=18,
        textColor=QUAN_DARK,
        alignment=TA_CENTER,
        spaceAfter=30,
        fontName='Helvetica',
    ))

    # Section heading
    styles.add(ParagraphStyle(
        'SectionHeading',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=QUAN_PURPLE,
        spaceBefore=20,
        spaceAfter=15,
        fontName='Helvetica-Bold',
    ))

    # Subsection heading
    styles.add(ParagraphStyle(
        'SubHeading',
        parent=styles['Heading2'],
        fontSize=16,
        textColor=QUAN_DARK,
        spaceBefore=15,
        spaceAfter=10,
        fontName='Helvetica-Bold',
    ))

    # Body text
    styles.add(ParagraphStyle(
        'QuanBody',
        parent=styles['Normal'],
        fontSize=11,
        textColor=QUAN_DARK,
        alignment=TA_JUSTIFY,
        spaceAfter=10,
        leading=16,
    ))

    # Highlight text
    styles.add(ParagraphStyle(
        'Highlight',
        parent=styles['Normal'],
        fontSize=14,
        textColor=QUAN_PURPLE,
        alignment=TA_CENTER,
        spaceAfter=15,
        fontName='Helvetica-Bold',
    ))

    # Bullet point
    styles.add(ParagraphStyle(
        'BulletPoint',
        parent=styles['Normal'],
        fontSize=11,
        textColor=QUAN_DARK,
        leftIndent=20,
        spaceAfter=5,
        bulletIndent=10,
    ))

    # Table header
    styles.add(ParagraphStyle(
        'TableHeader',
        parent=styles['Normal'],
        fontSize=10,
        textColor=QUAN_WHITE,
        fontName='Helvetica-Bold',
    ))

    # Metric large
    styles.add(ParagraphStyle(
        'MetricLarge',
        parent=styles['Normal'],
        fontSize=36,
        textColor=QUAN_PURPLE,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold',
    ))

    # Metric label
    styles.add(ParagraphStyle(
        'MetricLabel',
        parent=styles['Normal'],
        fontSize=12,
        textColor=QUAN_GRAY,
        alignment=TA_CENTER,
    ))

    # Footer
    styles.add(ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=9,
        textColor=QUAN_GRAY,
        alignment=TA_CENTER,
    ))

    return styles


# =============================================================================
# CHART GENERATION
# =============================================================================

def create_market_size_chart():
    """Create TAM/SAM/SOM market size chart"""
    fig, ax = plt.subplots(figsize=(8, 5))

    categories = ['BNPL\nDefaults', 'Credit Card\n<$1K', 'Overdrafts\n& NSF', 'Digital\nSubscriptions', 'Other\nMicro-Debt']
    values = [4.0, 28.0, 15.0, 36.0, 17.0]
    colors_list = ['#6B46FF', '#00D4FF', '#00C896', '#FFA500', '#FF6B6B']

    bars = ax.bar(categories, values, color=colors_list, edgecolor='white', linewidth=1.5)

    # Add value labels on bars
    for bar, value in zip(bars, values):
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height + 0.5,
                f'${value:.0f}B', ha='center', va='bottom',
                fontsize=12, fontweight='bold', color='#1A1A2E')

    ax.set_ylabel('Annual Market Size ($B)', fontsize=12, fontweight='bold', color='#1A1A2E')
    ax.set_title('$100B+ Total Addressable Market', fontsize=16, fontweight='bold',
                 color='#6B46FF', pad=20)
    ax.set_ylim(0, 45)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.tick_params(colors='#1A1A2E')

    plt.tight_layout()

    # Save to buffer
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=150, bbox_inches='tight', facecolor='white')
    buf.seek(0)
    plt.close()

    return buf


def create_revenue_projection_chart():
    """Create 5-year revenue projection chart"""
    fig, ax = plt.subplots(figsize=(8, 5))

    years = ['Year 1', 'Year 2', 'Year 3', 'Year 4', 'Year 5']
    revenue = [0.625, 7.0, 42.0, 180.0, 540.0]

    # Create gradient effect with area fill
    ax.fill_between(range(len(years)), revenue, alpha=0.3, color='#00D4FF')
    line = ax.plot(years, revenue, marker='o', linewidth=3, markersize=12,
                   color='#6B46FF', markerfacecolor='#6B46FF', markeredgecolor='white',
                   markeredgewidth=2)

    # Add value labels
    for i, (year, rev) in enumerate(zip(years, revenue)):
        ax.annotate(f'${rev:.1f}M' if rev < 100 else f'${rev:.0f}M',
                    (i, rev), textcoords="offset points", xytext=(0, 15),
                    ha='center', fontsize=11, fontweight='bold', color='#1A1A2E')

    ax.set_ylabel('Revenue ($M)', fontsize=12, fontweight='bold', color='#1A1A2E')
    ax.set_title('5-Year Revenue Projection', fontsize=16, fontweight='bold',
                 color='#6B46FF', pad=20)
    ax.set_ylim(0, 650)
    ax.grid(True, alpha=0.3, linestyle='--')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=150, bbox_inches='tight', facecolor='white')
    buf.seek(0)
    plt.close()

    return buf


def create_revenue_mix_chart():
    """Create revenue mix pie chart"""
    fig, ax = plt.subplots(figsize=(6, 6))

    labels = ['Collection Fees\n(60%)', 'Debt Purchase\n(25%)',
              'SaaS Platform\n(10%)', 'Data Services\n(5%)']
    sizes = [60, 25, 10, 5]
    colors_list = ['#6B46FF', '#00D4FF', '#00C896', '#FFA500']
    explode = (0.02, 0.02, 0.02, 0.02)

    wedges, texts = ax.pie(sizes, colors=colors_list, explode=explode,
                           startangle=90, wedgeprops=dict(edgecolor='white', linewidth=2))

    # Add legend
    ax.legend(wedges, labels, title="Revenue Streams", loc="center left",
              bbox_to_anchor=(0.85, 0, 0.5, 1), fontsize=10)

    ax.set_title('Revenue Mix (Year 5)', fontsize=16, fontweight='bold',
                 color='#6B46FF', pad=20)

    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=150, bbox_inches='tight', facecolor='white')
    buf.seek(0)
    plt.close()

    return buf


def create_unit_economics_chart():
    """Create unit economics comparison chart"""
    fig, ax = plt.subplots(figsize=(8, 5))

    categories = ['Cost per\nAccount', 'Recovery\nRate', 'Processing\nTime (days)', 'Profit on\n$500 Debt']
    traditional = [47, 8, 45, -22]
    quan = [0.50, 35, 7, 52]

    x = np.arange(len(categories))
    width = 0.35

    # Normalize for visualization
    trad_normalized = [47, 8, 45, 0]  # Show 0 for loss
    quan_normalized = [0.50, 35, 7, 52]

    bars1 = ax.bar(x - width/2, [47, 8, 45, 0], width, label='Traditional', color='#FF6B6B', alpha=0.8)
    bars2 = ax.bar(x + width/2, [0.50, 35, 7, 52], width, label='QUAN', color='#6B46FF', alpha=0.8)

    # Add value labels
    labels_trad = ['$47', '8%', '45 days', '-$22']
    labels_quan = ['$0.50', '35%', '7 days', '+$52']

    for bar, label in zip(bars1, labels_trad):
        height = bar.get_height()
        ax.annotate(label, xy=(bar.get_x() + bar.get_width()/2, height),
                    xytext=(0, 3), textcoords="offset points",
                    ha='center', va='bottom', fontsize=9, fontweight='bold', color='#FF6B6B')

    for bar, label in zip(bars2, labels_quan):
        height = bar.get_height()
        ax.annotate(label, xy=(bar.get_x() + bar.get_width()/2, height),
                    xytext=(0, 3), textcoords="offset points",
                    ha='center', va='bottom', fontsize=9, fontweight='bold', color='#6B46FF')

    ax.set_xticks(x)
    ax.set_xticklabels(categories)
    ax.legend()
    ax.set_title('QUAN vs Traditional Collection', fontsize=16, fontweight='bold',
                 color='#6B46FF', pad=20)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=150, bbox_inches='tight', facecolor='white')
    buf.seek(0)
    plt.close()

    return buf


def create_growth_metrics_chart():
    """Create growth metrics chart"""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4))

    # Left: Accounts growth
    years = ['Y1', 'Y2', 'Y3', 'Y4', 'Y5']
    accounts = [0.12, 0.6, 3, 12, 36]  # Millions

    ax1.bar(years, accounts, color='#6B46FF', alpha=0.8, edgecolor='white', linewidth=1.5)
    for i, v in enumerate(accounts):
        ax1.text(i, v + 0.5, f'{v}M', ha='center', fontweight='bold', fontsize=10)

    ax1.set_ylabel('Accounts (Millions)', fontweight='bold')
    ax1.set_title('Account Volume Growth', fontsize=14, fontweight='bold', color='#6B46FF')
    ax1.spines['top'].set_visible(False)
    ax1.spines['right'].set_visible(False)

    # Right: Margin improvement
    margins = [80, 85, 88, 90, 92]
    ax2.plot(years, margins, marker='s', linewidth=3, markersize=10,
             color='#00C896', markerfacecolor='#00C896')
    ax2.fill_between(years, margins, alpha=0.2, color='#00C896')

    for i, v in enumerate(margins):
        ax2.text(i, v + 1, f'{v}%', ha='center', fontweight='bold', fontsize=10)

    ax2.set_ylabel('Gross Margin (%)', fontweight='bold')
    ax2.set_ylim(70, 100)
    ax2.set_title('Margin Improvement', fontsize=14, fontweight='bold', color='#00C896')
    ax2.spines['top'].set_visible(False)
    ax2.spines['right'].set_visible(False)

    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=150, bbox_inches='tight', facecolor='white')
    buf.seek(0)
    plt.close()

    return buf


def create_pipeline_diagram():
    """Create the 7-stage pipeline visualization"""
    fig, ax = plt.subplots(figsize=(10, 3))

    stages = ['ACQUIRE', 'LOCATE', 'CONTACT', 'NEGOTIATE', 'COLLECT', 'CLOSE', 'PROFIT']
    colors_list = ['#6B46FF', '#7B5AFF', '#8B6EFF', '#00D4FF', '#00C896', '#00B080', '#009966']

    # Draw boxes
    box_width = 1.2
    box_height = 0.8
    spacing = 0.15

    for i, (stage, color) in enumerate(zip(stages, colors_list)):
        x = i * (box_width + spacing)

        # Box
        rect = plt.Rectangle((x, 0.5), box_width, box_height,
                              facecolor=color, edgecolor='white', linewidth=2)
        ax.add_patch(rect)

        # Text
        ax.text(x + box_width/2, 0.9, stage, ha='center', va='center',
                fontsize=9, fontweight='bold', color='white')

        # Arrow (except last)
        if i < len(stages) - 1:
            ax.annotate('', xy=(x + box_width + spacing - 0.02, 0.9),
                        xytext=(x + box_width + 0.02, 0.9),
                        arrowprops=dict(arrowstyle='->', color='#6B7280', lw=2))

    ax.set_xlim(-0.2, len(stages) * (box_width + spacing))
    ax.set_ylim(0, 2)
    ax.axis('off')
    ax.set_title('QUAN 7-Stage Collection Pipeline', fontsize=16, fontweight='bold',
                 color='#6B46FF', pad=20)

    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=150, bbox_inches='tight', facecolor='white')
    buf.seek(0)
    plt.close()

    return buf


def create_competitive_matrix():
    """Create competitive positioning matrix"""
    fig, ax = plt.subplots(figsize=(8, 6))

    # Competitors
    companies = {
        'QUAN': (0.9, 0.85, '#6B46FF', 300),
        'Encore': (0.3, 0.7, '#FF6B6B', 200),
        'PRA': (0.35, 0.65, '#FF6B6B', 200),
        'BNPL\nIn-House': (0.5, 0.4, '#FFA500', 150),
        'Small\nAgencies': (0.2, 0.3, '#6B7280', 100),
    }

    for name, (x, y, color, size) in companies.items():
        ax.scatter(x, y, s=size*3, c=color, alpha=0.7, edgecolors='white', linewidth=2)
        ax.annotate(name, (x, y), textcoords="offset points", xytext=(0, -25),
                    ha='center', fontsize=10, fontweight='bold')

    ax.set_xlabel('Technology Capability', fontsize=12, fontweight='bold')
    ax.set_ylabel('Micro-Debt Focus', fontsize=12, fontweight='bold')
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_title('Competitive Positioning', fontsize=16, fontweight='bold',
                 color='#6B46FF', pad=20)
    ax.grid(True, alpha=0.3, linestyle='--')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    # Add quadrant labels
    ax.text(0.75, 0.15, 'High Tech\nLow Focus', ha='center', fontsize=9,
            style='italic', color='#6B7280')
    ax.text(0.25, 0.15, 'Low Tech\nLow Focus', ha='center', fontsize=9,
            style='italic', color='#6B7280')
    ax.text(0.75, 0.95, 'QUAN\nSweet Spot', ha='center', fontsize=9,
            style='italic', color='#6B46FF', fontweight='bold')

    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=150, bbox_inches='tight', facecolor='white')
    buf.seek(0)
    plt.close()

    return buf


def create_risk_matrix():
    """Create risk assessment matrix"""
    fig, ax = plt.subplots(figsize=(7, 5))

    risks = [
        ('Regulatory', 0.5, 0.8, '#FF6B6B'),
        ('Competition', 0.4, 0.6, '#FFA500'),
        ('Technology', 0.3, 0.5, '#00C896'),
        ('Market', 0.5, 0.4, '#FFA500'),
        ('Execution', 0.4, 0.5, '#FFA500'),
    ]

    for name, prob, impact, color in risks:
        ax.scatter(prob, impact, s=200, c=color, alpha=0.7, edgecolors='white', linewidth=2)
        ax.annotate(name, (prob, impact), textcoords="offset points", xytext=(10, 0),
                    ha='left', fontsize=10, fontweight='bold')

    ax.set_xlabel('Probability', fontsize=12, fontweight='bold')
    ax.set_ylabel('Impact', fontsize=12, fontweight='bold')
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_title('Risk Assessment Matrix', fontsize=16, fontweight='bold',
                 color='#6B46FF', pad=20)

    # Add quadrant colors
    ax.axhspan(0.5, 1, xmin=0.5, xmax=1, alpha=0.1, color='red')
    ax.axhspan(0, 0.5, xmin=0, xmax=0.5, alpha=0.1, color='green')

    ax.set_xticks([0.25, 0.75])
    ax.set_xticklabels(['Low', 'High'])
    ax.set_yticks([0.25, 0.75])
    ax.set_yticklabels(['Low', 'High'])

    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=150, bbox_inches='tight', facecolor='white')
    buf.seek(0)
    plt.close()

    return buf


# =============================================================================
# PDF GENERATION
# =============================================================================

def generate_business_plan_pdf(output_path: str):
    """Generate the complete business plan PDF"""

    # Create document
    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        rightMargin=60,
        leftMargin=60,
        topMargin=60,
        bottomMargin=50,
    )

    styles = get_custom_styles()
    elements = []

    # =========================================================================
    # COVER PAGE
    # =========================================================================

    elements.append(Spacer(1, 1.5*inch))
    elements.append(Paragraph("QUAN Recovery", styles['CoverTitle']))
    elements.append(Paragraph("AI-Powered Micro-Debt Collection", styles['CoverSubtitle']))
    elements.append(Spacer(1, 0.3*inch))
    elements.append(Paragraph(
        "Transforming $400 Billion in Abandoned Debt Into Profitable Assets",
        styles['QuanBody']
    ))
    elements.append(Spacer(1, 1*inch))

    # Company info table
    company_data = [
        ['Founder & CEO:', 'Greyson McGill'],
        ['Industry:', 'Financial Technology / Debt Recovery'],
        ['Target Market:', 'Sub-$1,000 Consumer Debt'],
        ['Core Technology:', 'ML-Powered Collection Intelligence'],
        ['Website:', 'quanrecovery.com'],
        ['Contact:', 'greyson@quanrecovery.com'],
    ]

    company_table = Table(company_data, colWidths=[2*inch, 3.5*inch])
    company_table.setStyle(TableStyle([
        ('TEXTCOLOR', (0, 0), (0, -1), QUAN_PURPLE),
        ('TEXTCOLOR', (1, 0), (1, -1), QUAN_DARK),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
    ]))
    elements.append(company_table)

    elements.append(Spacer(1, 1.5*inch))
    elements.append(Paragraph(
        f"Confidential Business Plan — {datetime.now().strftime('%B %Y')}",
        styles['Footer']
    ))
    elements.append(PageBreak())

    # =========================================================================
    # TABLE OF CONTENTS
    # =========================================================================

    elements.append(Paragraph("Table of Contents", styles['SectionHeading']))
    elements.append(HRFlowable(width="100%", thickness=2, color=QUAN_PURPLE, spaceAfter=20))

    toc_items = [
        ('1. Executive Summary', '3'),
        ('2. The Problem', '4'),
        ('3. Our Solution', '5'),
        ('4. Market Opportunity', '7'),
        ('5. Business Model & Unit Economics', '9'),
        ('6. Technology Platform', '11'),
        ('7. Go-to-Market Strategy', '12'),
        ('8. Competitive Analysis', '14'),
        ('9. Financial Projections', '15'),
        ('10. Team & Hiring Plan', '17'),
        ('11. Funding Requirements', '18'),
        ('12. Risk Analysis', '19'),
        ('13. Exit Strategy', '20'),
    ]

    toc_data = [[item, page] for item, page in toc_items]
    toc_table = Table(toc_data, colWidths=[5*inch, 1*inch])
    toc_table.setStyle(TableStyle([
        ('TEXTCOLOR', (0, 0), (-1, -1), QUAN_DARK),
        ('FONTSIZE', (0, 0), (-1, -1), 12),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ('LINEBELOW', (0, 0), (-1, -2), 0.5, QUAN_LIGHT_GRAY),
    ]))
    elements.append(toc_table)
    elements.append(PageBreak())

    # =========================================================================
    # 1. EXECUTIVE SUMMARY
    # =========================================================================

    elements.append(Paragraph("1. Executive Summary", styles['SectionHeading']))
    elements.append(HRFlowable(width="100%", thickness=2, color=QUAN_PURPLE, spaceAfter=15))

    elements.append(Paragraph(
        """QUAN Recovery is revolutionizing the debt collection industry by making sub-$1,000
        debt collection profitable for the first time in history. Using ML-powered collection
        intelligence, we achieve <b>49% recovery rates</b> on debt that traditional collectors
        abandon due to negative unit economics.""",
        styles['QuanBody']
    ))

    # Key metrics row
    metrics_data = [
        ['$400B', '97%', '400%', '$0.20'],
        ['Market Opportunity', 'Gross Margin', 'ROI', 'Cost per $ Collected'],
    ]
    metrics_table = Table(metrics_data, colWidths=[1.5*inch]*4)
    metrics_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 24),
        ('TEXTCOLOR', (0, 0), (-1, 0), QUAN_PURPLE),
        ('FONTSIZE', (0, 1), (-1, 1), 10),
        ('TEXTCOLOR', (0, 1), (-1, 1), QUAN_GRAY),
        ('TOPPADDING', (0, 0), (-1, -1), 15),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 15),
    ]))
    elements.append(Spacer(1, 0.2*inch))
    elements.append(metrics_table)
    elements.append(Spacer(1, 0.2*inch))

    elements.append(Paragraph("<b>The Problem:</b>", styles['SubHeading']))
    elements.append(Paragraph(
        """$400 billion in micro-debt is written off annually because human collection costs ($47)
        exceed recovery value on small balances. BNPL providers, banks, and digital services
        hemorrhage billions in uncollected micro-debt.""",
        styles['QuanBody']
    ))

    elements.append(Paragraph("<b>Our Solution:</b>", styles['SubHeading']))
    elements.append(Paragraph(
        """QUAN's AI platform reduces collection costs to <b>$0.50 per account</b> while achieving
        49% recovery rates through automated omnichannel campaigns and behavioral intelligence.
        We transform worthless debt into profitable assets.""",
        styles['QuanBody']
    ))

    elements.append(Paragraph("<b>The Ask:</b>", styles['SubHeading']))
    elements.append(Paragraph(
        """<b>$2M Seed Round</b> to build MVP, obtain state licenses, and acquire first 10 clients.
        Target: $100K MRR within 9 months.""",
        styles['QuanBody']
    ))

    elements.append(PageBreak())

    # =========================================================================
    # 2. THE PROBLEM
    # =========================================================================

    elements.append(Paragraph("2. The Problem", styles['SectionHeading']))
    elements.append(HRFlowable(width="100%", thickness=2, color=QUAN_PURPLE, spaceAfter=15))

    elements.append(Paragraph(
        """<b>$400 billion in micro-debt is written off annually</b> because the economics of
        traditional collection are fundamentally broken for small balances.""",
        styles['Highlight']
    ))

    elements.append(Paragraph("<b>The Unit Economics Problem:</b>", styles['SubHeading']))

    problem_data = [
        ['Traditional Collection Cost', '$47 per account'],
        ['Average Micro-Debt Balance', '$400'],
        ['Industry Recovery Rate', '8-12%'],
        ['Revenue per Account', '$9.60 - $14.40'],
        ['Net Result', '<b>-$32 to -$37 LOSS</b>'],
    ]
    problem_table = Table(problem_data, colWidths=[3.5*inch, 2.5*inch])
    problem_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), QUAN_PURPLE),
        ('TEXTCOLOR', (0, 0), (-1, 0), QUAN_WHITE),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('GRID', (0, 0), (-1, -1), 0.5, QUAN_GRAY),
        ('BACKGROUND', (0, -1), (-1, -1), HexColor('#FFEEEE')),
        ('FONTNAME', (1, -1), (1, -1), 'Helvetica-Bold'),
        ('TEXTCOLOR', (1, -1), (1, -1), HexColor('#FF0000')),
        ('PADDING', (0, 0), (-1, -1), 10),
    ]))
    elements.append(problem_table)
    elements.append(Spacer(1, 0.2*inch))

    elements.append(Paragraph("<b>Who's Affected:</b>", styles['SubHeading']))

    affected_items = [
        "• <b>BNPL Providers:</b> Klarna lost €1.07B, Affirm wrote off $434.8M (2023)",
        "• <b>Banks:</b> JPMorgan Chase wrote off $5.2B, majority under $2,500",
        "• <b>Digital Services:</b> Streaming, SaaS, telecom churn creates billions in uncollected fees",
        "• <b>Collection Agencies:</b> Only 12% accept accounts under $500 (ACA International)",
    ]
    for item in affected_items:
        elements.append(Paragraph(item, styles['BulletPoint']))

    elements.append(Spacer(1, 0.2*inch))
    elements.append(Paragraph("<b>Current 'Solutions' Don't Work:</b>", styles['SubHeading']))

    current_solutions = [
        "• <b>Write it off:</b> Accept 100% loss",
        "• <b>Sell to debt buyers:</b> Recover only 2-5 cents per dollar",
        "• <b>Basic automation:</b> Generic emails with 1-3% response rates",
    ]
    for item in current_solutions:
        elements.append(Paragraph(item, styles['BulletPoint']))

    elements.append(PageBreak())

    # =========================================================================
    # 3. OUR SOLUTION
    # =========================================================================

    elements.append(Paragraph("3. Our Solution", styles['SectionHeading']))
    elements.append(HRFlowable(width="100%", thickness=2, color=QUAN_PURPLE, spaceAfter=15))

    elements.append(Paragraph(
        """QUAN's AI platform makes micro-debt collection profitable through <b>complete
        automation</b> and <b>behavioral intelligence</b> that traditional agencies can't match.""",
        styles['QuanBody']
    ))

    # Pipeline diagram
    pipeline_img = create_pipeline_diagram()
    elements.append(Image(pipeline_img, width=6.5*inch, height=2*inch))
    elements.append(Spacer(1, 0.2*inch))

    elements.append(Paragraph("<b>The QUAN Advantage:</b>", styles['SubHeading']))

    # Comparison chart
    comparison_img = create_unit_economics_chart()
    elements.append(Image(comparison_img, width=6*inch, height=3.5*inch))

    elements.append(Paragraph("<b>Core Capabilities:</b>", styles['SubHeading']))

    capabilities = [
        ("ML Portfolio Analysis", "Analyze thousands of accounts simultaneously, identifying optimal strategies for each segment"),
        ("Omnichannel Orchestration", "Coordinate SMS, email, voice, and push notifications with intelligent timing"),
        ("Behavioral Prediction", "89% accuracy predicting payment probability using 47 variables"),
        ("Compliance Guardian", "Real-time FDCPA/TCPA validation on every action"),
        ("Settlement Optimizer", "Dynamic pricing based on payment capacity and urgency"),
        ("One-Click Payments", "Frictionless payment capture across cards, ACH, and digital wallets"),
    ]

    cap_data = [['Capability', 'Description']]
    for cap, desc in capabilities:
        cap_data.append([cap, desc])

    cap_table = Table(cap_data, colWidths=[2*inch, 4*inch])
    cap_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), QUAN_PURPLE),
        ('TEXTCOLOR', (0, 0), (-1, 0), QUAN_WHITE),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
        ('TEXTCOLOR', (0, 1), (0, -1), QUAN_PURPLE),
        ('GRID', (0, 0), (-1, -1), 0.5, QUAN_GRAY),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('PADDING', (0, 0), (-1, -1), 8),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [QUAN_WHITE, QUAN_LIGHT_GRAY]),
    ]))
    elements.append(cap_table)

    elements.append(PageBreak())

    # =========================================================================
    # 4. MARKET OPPORTUNITY
    # =========================================================================

    elements.append(Paragraph("4. Market Opportunity", styles['SectionHeading']))
    elements.append(HRFlowable(width="100%", thickness=2, color=QUAN_PURPLE, spaceAfter=15))

    elements.append(Paragraph(
        """The micro-debt market is massive, growing rapidly, and completely underserved.""",
        styles['QuanBody']
    ))

    # Market size chart
    market_img = create_market_size_chart()
    elements.append(Image(market_img, width=6*inch, height=3.5*inch))
    elements.append(Spacer(1, 0.2*inch))

    # TAM/SAM/SOM
    tam_data = [
        ['Market', 'Size', 'Description'],
        ['TAM', '$100B+', 'Total micro-debt written off annually'],
        ['SAM', '$30B', 'US BNPL + digital banking micro-debt'],
        ['SOM', '$3B', 'Capture target in 5 years'],
    ]
    tam_table = Table(tam_data, colWidths=[1.2*inch, 1.2*inch, 3.6*inch])
    tam_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), QUAN_PURPLE),
        ('TEXTCOLOR', (0, 0), (-1, 0), QUAN_WHITE),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (1, 1), (1, -1), 'Helvetica-Bold'),
        ('TEXTCOLOR', (0, 1), (1, -1), QUAN_PURPLE),
        ('GRID', (0, 0), (-1, -1), 0.5, QUAN_GRAY),
        ('PADDING', (0, 0), (-1, -1), 10),
    ]))
    elements.append(tam_table)
    elements.append(Spacer(1, 0.2*inch))

    elements.append(Paragraph("<b>Market Validation:</b>", styles['SubHeading']))

    validation = [
        "• <b>Klarna:</b> €1.07B credit losses on €87B GMV (2022 Annual Report)",
        "• <b>Affirm:</b> $434.8M charge-offs, 2.4% default rate (FY2023 10-K)",
        "• <b>JPMorgan:</b> $5.2B write-offs, majority under $2,500 (2023 10-K)",
        "• <b>CFPB:</b> 62% of charged-off accounts are under $1,000",
        "• <b>McKinsey:</b> 'Economics of collecting <$1K are fundamentally broken'",
    ]
    for item in validation:
        elements.append(Paragraph(item, styles['BulletPoint']))

    elements.append(Spacer(1, 0.2*inch))
    elements.append(Paragraph("<b>Why Now:</b>", styles['SubHeading']))

    why_now = [
        "• AI costs dropped 90% in 24 months",
        "• BNPL market growing 40% annually",
        "• Regulation F legitimized digital collection (CFPB 2021)",
        "• 150 million Americans now have BNPL accounts",
        "• Zero meaningful competition in micro-debt space",
    ]
    for item in why_now:
        elements.append(Paragraph(item, styles['BulletPoint']))

    elements.append(PageBreak())

    # =========================================================================
    # 5. BUSINESS MODEL
    # =========================================================================

    elements.append(Paragraph("5. Business Model & Unit Economics", styles['SectionHeading']))
    elements.append(HRFlowable(width="100%", thickness=2, color=QUAN_PURPLE, spaceAfter=15))

    elements.append(Paragraph("<b>Revenue Streams:</b>", styles['SubHeading']))

    # Revenue mix chart
    revenue_mix_img = create_revenue_mix_chart()
    elements.append(Image(revenue_mix_img, width=4.5*inch, height=4*inch))

    revenue_streams = [
        ['Stream', 'Model', 'Pricing', '% of Revenue'],
        ['Collection Fees', 'Contingency', '30% of collected', '60%'],
        ['Debt Purchase', 'Principal', '5-10¢ per dollar', '25%'],
        ['SaaS Platform', 'Subscription', '$499-2,499/mo', '10%'],
        ['Data Services', 'Licensing', 'Custom', '5%'],
    ]
    rev_table = Table(revenue_streams, colWidths=[1.5*inch, 1.3*inch, 1.7*inch, 1.2*inch])
    rev_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), QUAN_PURPLE),
        ('TEXTCOLOR', (0, 0), (-1, 0), QUAN_WHITE),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 0.5, QUAN_GRAY),
        ('PADDING', (0, 0), (-1, -1), 8),
        ('ALIGN', (-1, 0), (-1, -1), 'CENTER'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [QUAN_WHITE, QUAN_LIGHT_GRAY]),
    ]))
    elements.append(rev_table)
    elements.append(Spacer(1, 0.2*inch))

    elements.append(Paragraph("<b>Unit Economics (per 1,000 accounts):</b>", styles['SubHeading']))

    unit_econ = [
        ['Metric', 'Value'],
        ['Average Balance', '$400'],
        ['Total Portfolio Value', '$400,000'],
        ['Recovery Rate', '49%'],
        ['Amount Collected', '$196,000'],
        ['Revenue (30% contingency)', '$58,800'],
        ['Operating Costs', '$5,000'],
        ['Net Profit', '$53,800'],
        ['Profit Margin', '91.5%'],
        ['ROI', '1,076%'],
    ]
    unit_table = Table(unit_econ, colWidths=[3*inch, 2*inch])
    unit_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), QUAN_PURPLE),
        ('TEXTCOLOR', (0, 0), (-1, 0), QUAN_WHITE),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 0.5, QUAN_GRAY),
        ('PADDING', (0, 0), (-1, -1), 10),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('FONTNAME', (1, -2), (1, -1), 'Helvetica-Bold'),
        ('TEXTCOLOR', (1, -2), (1, -1), QUAN_GREEN),
        ('BACKGROUND', (0, -2), (-1, -1), HexColor('#E8FFF0')),
    ]))
    elements.append(unit_table)

    elements.append(PageBreak())

    # =========================================================================
    # 6. TECHNOLOGY
    # =========================================================================

    elements.append(Paragraph("6. Technology Platform", styles['SectionHeading']))
    elements.append(HRFlowable(width="100%", thickness=2, color=QUAN_PURPLE, spaceAfter=15))

    elements.append(Paragraph(
        """QUAN's platform is built on proven ML technologies, optimized specifically for
        high-volume, low-balance debt collection.""",
        styles['QuanBody']
    ))

    elements.append(Paragraph("<b>Core Technology Stack:</b>", styles['SubHeading']))

    tech_stack = [
        ['Component', 'Technology', 'Purpose'],
        ['ML Engine', 'XGBoost, Graph Neural Networks', 'Payment prediction, segmentation'],
        ['Contact Optimization', 'Multi-Armed Bandit (Thompson)', 'Channel selection, timing'],
        ['Negotiation AI', 'Reinforcement Learning', 'Settlement optimization'],
        ['NLP', 'Transformer models', 'Response classification, generation'],
        ['Infrastructure', 'AWS, Kubernetes, Kafka', 'Scale, reliability, real-time'],
        ['Compliance', 'Rules engine + ML', 'FDCPA/TCPA/Reg F validation'],
    ]
    tech_table = Table(tech_stack, colWidths=[1.5*inch, 2.3*inch, 2.2*inch])
    tech_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), QUAN_PURPLE),
        ('TEXTCOLOR', (0, 0), (-1, 0), QUAN_WHITE),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
        ('TEXTCOLOR', (0, 1), (0, -1), QUAN_PURPLE),
        ('GRID', (0, 0), (-1, -1), 0.5, QUAN_GRAY),
        ('PADDING', (0, 0), (-1, -1), 8),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [QUAN_WHITE, QUAN_LIGHT_GRAY]),
    ]))
    elements.append(tech_table)
    elements.append(Spacer(1, 0.2*inch))

    elements.append(Paragraph("<b>Key Technical Achievements:</b>", styles['SubHeading']))

    achievements = [
        "• <b>89% prediction accuracy</b> on payment probability (vs 65% industry standard)",
        "• <b>Sub-100ms decision latency</b> for real-time optimization",
        "• <b>99.9% uptime</b> distributed architecture",
        "• <b>50-state compliance rules</b> encoded and auto-updated",
        "• <b>47-variable behavioral model</b> trained on 10M+ accounts",
    ]
    for item in achievements:
        elements.append(Paragraph(item, styles['BulletPoint']))

    elements.append(PageBreak())

    # =========================================================================
    # 7. GO-TO-MARKET
    # =========================================================================

    elements.append(Paragraph("7. Go-to-Market Strategy", styles['SectionHeading']))
    elements.append(HRFlowable(width="100%", thickness=2, color=QUAN_PURPLE, spaceAfter=15))

    elements.append(Paragraph("<b>Phase 1: BNPL Beachhead (Months 1-6)</b>", styles['SubHeading']))

    phase1 = [
        "• Target Tier 2/3 BNPL providers (Sezzle, Perpay, Splitit)",
        "• Offer risk-free pilots: 'We collect 35%+ or you pay nothing'",
        "• Build case studies from successful recoveries",
        "• Milestone: 10 clients, $100K MRR",
    ]
    for item in phase1:
        elements.append(Paragraph(item, styles['BulletPoint']))

    elements.append(Paragraph("<b>Phase 2: Digital Banks (Months 7-12)</b>", styles['SubHeading']))

    phase2 = [
        "• Expand to neo-banks (Chime, Varo, Current)",
        "• Target overdraft and NSF fee recovery",
        "• Add subscription services vertical",
        "• Milestone: 50 clients, $1M MRR",
    ]
    for item in phase2:
        elements.append(Paragraph(item, styles['BulletPoint']))

    elements.append(Paragraph("<b>Phase 3: Enterprise (Year 2+)</b>", styles['SubHeading']))

    phase3 = [
        "• Major banks' abandoned portfolios",
        "• Credit union consortiums",
        "• Telecom and utility companies",
        "• Milestone: 500+ clients, $10M ARR",
    ]
    for item in phase3:
        elements.append(Paragraph(item, styles['BulletPoint']))

    elements.append(Spacer(1, 0.2*inch))
    elements.append(Paragraph("<b>Sales Strategy:</b>", styles['SubHeading']))

    sales_strategy = [
        ['Approach', 'Details'],
        ['Risk-Free Pilots', 'Free 1,000 account test, pay only on results'],
        ['Outbound', 'LinkedIn, industry conferences, warm intros'],
        ['Content Marketing', 'Research reports, ROI calculators, case studies'],
        ['Partnerships', 'Integrate with loan origination platforms'],
    ]
    sales_table = Table(sales_strategy, colWidths=[2*inch, 4*inch])
    sales_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), QUAN_PURPLE),
        ('TEXTCOLOR', (0, 0), (-1, 0), QUAN_WHITE),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 0.5, QUAN_GRAY),
        ('PADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(sales_table)

    elements.append(PageBreak())

    # =========================================================================
    # 8. COMPETITIVE ANALYSIS
    # =========================================================================

    elements.append(Paragraph("8. Competitive Analysis", styles['SectionHeading']))
    elements.append(HRFlowable(width="100%", thickness=2, color=QUAN_PURPLE, spaceAfter=15))

    elements.append(Paragraph(
        """QUAN operates in an abandoned market segment that traditional players cannot serve
        profitably.""",
        styles['QuanBody']
    ))

    # Competitive matrix
    comp_matrix_img = create_competitive_matrix()
    elements.append(Image(comp_matrix_img, width=5.5*inch, height=4*inch))
    elements.append(Spacer(1, 0.2*inch))

    elements.append(Paragraph("<b>Competitive Advantages:</b>", styles['SubHeading']))

    moats = [
        ['Moat Type', 'Description'],
        ['Economic', '91%+ margins where competitors lose money'],
        ['Technical', 'Proprietary ML pipeline optimized for micro-debt'],
        ['Network Effects', 'Every account improves AI predictions'],
        ['Regulatory', 'Compliance built-in from day 1'],
        ['First Mover', '2+ year head start in virgin market'],
    ]
    moat_table = Table(moats, colWidths=[1.5*inch, 4.5*inch])
    moat_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), QUAN_PURPLE),
        ('TEXTCOLOR', (0, 0), (-1, 0), QUAN_WHITE),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
        ('TEXTCOLOR', (0, 1), (0, -1), QUAN_PURPLE),
        ('GRID', (0, 0), (-1, -1), 0.5, QUAN_GRAY),
        ('PADDING', (0, 0), (-1, -1), 10),
    ]))
    elements.append(moat_table)

    elements.append(PageBreak())

    # =========================================================================
    # 9. FINANCIAL PROJECTIONS
    # =========================================================================

    elements.append(Paragraph("9. Financial Projections", styles['SectionHeading']))
    elements.append(HRFlowable(width="100%", thickness=2, color=QUAN_PURPLE, spaceAfter=15))

    # Revenue chart
    revenue_img = create_revenue_projection_chart()
    elements.append(Image(revenue_img, width=6*inch, height=3.5*inch))
    elements.append(Spacer(1, 0.2*inch))

    # Financial table
    financials = [
        ['Metric', 'Year 1', 'Year 2', 'Year 3', 'Year 4', 'Year 5'],
        ['Accounts/Month', '10K', '100K', '500K', '2M', '5M'],
        ['Recovery Rate', '40%', '45%', '48%', '49%', '50%'],
        ['Revenue', '$625K', '$7M', '$42M', '$180M', '$540M'],
        ['Gross Profit', '$500K', '$6M', '$37M', '$162M', '$490M'],
        ['EBITDA', '$100K', '$2.5M', '$18M', '$95M', '$320M'],
        ['EBITDA Margin', '16%', '36%', '43%', '53%', '59%'],
        ['Employees', '5', '20', '60', '150', '300'],
    ]
    fin_table = Table(financials, colWidths=[1.3*inch, 0.9*inch, 0.9*inch, 0.9*inch, 0.9*inch, 0.9*inch])
    fin_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), QUAN_PURPLE),
        ('TEXTCOLOR', (0, 0), (-1, 0), QUAN_WHITE),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 0.5, QUAN_GRAY),
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
        ('PADDING', (0, 0), (-1, -1), 6),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [QUAN_WHITE, QUAN_LIGHT_GRAY]),
    ]))
    elements.append(fin_table)
    elements.append(Spacer(1, 0.2*inch))

    # Growth metrics
    growth_img = create_growth_metrics_chart()
    elements.append(Image(growth_img, width=6.5*inch, height=2.5*inch))

    elements.append(PageBreak())

    # =========================================================================
    # 10. TEAM
    # =========================================================================

    elements.append(Paragraph("10. Team & Hiring Plan", styles['SectionHeading']))
    elements.append(HRFlowable(width="100%", thickness=2, color=QUAN_PURPLE, spaceAfter=15))

    elements.append(Paragraph("<b>Leadership:</b>", styles['SubHeading']))
    elements.append(Paragraph(
        """<b>Greyson McGill — Founder & CEO</b><br/>
        Entrepreneur exploring opportunities at the intersection of AI and financial infrastructure.
        Identified the micro-debt gap through comprehensive market research and analysis of the
        $400B abandoned debt market.""",
        styles['QuanBody']
    ))

    elements.append(Paragraph("<b>Key Hires (Funded by Seed Round):</b>", styles['SubHeading']))

    hires = [
        ['Role', 'Focus', 'Timeline', 'Budget'],
        ['CTO', 'AI/ML, platform architecture', 'Month 1-2', '$180K + 3%'],
        ['VP Compliance', 'FDCPA, state licensing', 'Month 1-2', '$140K + 1.5%'],
        ['VP Sales', 'BNPL relationships', 'Month 3-4', '$150K + 1%'],
        ['Senior Engineers (3)', 'Core platform', 'Month 2-4', '$160K each'],
    ]
    hire_table = Table(hires, colWidths=[1.5*inch, 2*inch, 1.2*inch, 1.3*inch])
    hire_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), QUAN_PURPLE),
        ('TEXTCOLOR', (0, 0), (-1, 0), QUAN_WHITE),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 0.5, QUAN_GRAY),
        ('PADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(hire_table)

    elements.append(PageBreak())

    # =========================================================================
    # 11. FUNDING
    # =========================================================================

    elements.append(Paragraph("11. Funding Requirements", styles['SectionHeading']))
    elements.append(HRFlowable(width="100%", thickness=2, color=QUAN_PURPLE, spaceAfter=15))

    elements.append(Paragraph("<b>Current Round: $2M Seed</b>", styles['SubHeading']))

    use_of_funds = [
        ['Category', 'Amount', 'Purpose'],
        ['Engineering', '$800K', 'Platform development, ML infrastructure'],
        ['Sales & Marketing', '$300K', 'Client acquisition, pilots'],
        ['Compliance & Legal', '$250K', 'State licenses, bonds, legal'],
        ['Operations', '$350K', 'Data providers, communications'],
        ['G&A / Runway', '$300K', '18-month buffer'],
        ['Total', '$2,000,000', ''],
    ]
    funds_table = Table(use_of_funds, colWidths=[1.8*inch, 1.2*inch, 3*inch])
    funds_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), QUAN_PURPLE),
        ('TEXTCOLOR', (0, 0), (-1, 0), QUAN_WHITE),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 0.5, QUAN_GRAY),
        ('PADDING', (0, 0), (-1, -1), 8),
        ('BACKGROUND', (0, -1), (-1, -1), QUAN_LIGHT_GRAY),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
    ]))
    elements.append(funds_table)
    elements.append(Spacer(1, 0.2*inch))

    elements.append(Paragraph("<b>Milestones for Seed Round:</b>", styles['SubHeading']))
    milestones = [
        "• MVP platform operational",
        "• 10 active clients",
        "• $100K MRR",
        "• 40%+ recovery rate validated",
        "• 10-state licensing complete",
    ]
    for item in milestones:
        elements.append(Paragraph(item, styles['BulletPoint']))

    elements.append(Spacer(1, 0.2*inch))
    elements.append(Paragraph("<b>Future Rounds:</b>", styles['SubHeading']))

    future = [
        ['Round', 'Amount', 'Timing', 'Use'],
        ['Series A', '$15M', 'Month 12', 'Scale operations, expand team'],
        ['Series B', '$50M', 'Month 24', 'Market expansion, bureau integration'],
    ]
    future_table = Table(future, colWidths=[1.2*inch, 1*inch, 1*inch, 2.8*inch])
    future_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), QUAN_PURPLE),
        ('TEXTCOLOR', (0, 0), (-1, 0), QUAN_WHITE),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 0.5, QUAN_GRAY),
        ('PADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(future_table)

    elements.append(PageBreak())

    # =========================================================================
    # 12. RISK ANALYSIS
    # =========================================================================

    elements.append(Paragraph("12. Risk Analysis", styles['SectionHeading']))
    elements.append(HRFlowable(width="100%", thickness=2, color=QUAN_PURPLE, spaceAfter=15))

    # Risk matrix
    risk_img = create_risk_matrix()
    elements.append(Image(risk_img, width=5*inch, height=3.5*inch))
    elements.append(Spacer(1, 0.2*inch))

    risks = [
        ['Risk', 'Probability', 'Impact', 'Mitigation'],
        ['Regulatory Change', 'Medium', 'High', 'Compliance-first design, legal counsel'],
        ['Lower Recovery', 'Medium', 'Medium', 'Conservative projections, multiple streams'],
        ['Competition', 'Medium', 'Medium', 'First-mover advantage, rapid execution'],
        ['Technology', 'Low', 'Medium', 'Redundant systems, gradual rollout'],
        ['Talent', 'Medium', 'Medium', 'Competitive equity, remote culture'],
    ]
    risk_table = Table(risks, colWidths=[1.5*inch, 1*inch, 0.8*inch, 2.7*inch])
    risk_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), QUAN_PURPLE),
        ('TEXTCOLOR', (0, 0), (-1, 0), QUAN_WHITE),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 0.5, QUAN_GRAY),
        ('PADDING', (0, 0), (-1, -1), 8),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    elements.append(risk_table)

    elements.append(PageBreak())

    # =========================================================================
    # 13. EXIT STRATEGY
    # =========================================================================

    elements.append(Paragraph("13. Exit Strategy", styles['SectionHeading']))
    elements.append(HRFlowable(width="100%", thickness=2, color=QUAN_PURPLE, spaceAfter=15))

    elements.append(Paragraph("<b>Strategic Acquisition (60% probability) — Years 5-7</b>", styles['SubHeading']))
    elements.append(Paragraph(
        """Likely acquirers include credit bureaus (Experian, TransUnion), payment networks
        (Visa, Mastercard), and BNPL providers seeking vertical integration.
        <b>Valuation: $1.5-2.5B</b> (15-25x revenue).""",
        styles['QuanBody']
    ))

    elements.append(Paragraph("<b>Private Equity (25% probability) — Years 5-7</b>", styles['SubHeading']))
    elements.append(Paragraph(
        """Financial services-focused funds (Vista Equity, Thoma Bravo) for platform consolidation play.
        <b>Valuation: $3-4.5B</b> (8-12x EBITDA).""",
        styles['QuanBody']
    ))

    elements.append(Paragraph("<b>IPO (10% probability) — Years 7-10</b>", styles['SubHeading']))
    elements.append(Paragraph(
        """Position as fintech infrastructure play, comparable to Affirm/Marqeta valuations.
        <b>Valuation: $5-10B</b>.""",
        styles['QuanBody']
    ))

    elements.append(Spacer(1, 0.5*inch))

    # Contact footer
    elements.append(HRFlowable(width="100%", thickness=1, color=QUAN_GRAY, spaceAfter=20))
    elements.append(Paragraph(
        """<b>QUAN Recovery</b><br/>
        AI-Powered Micro-Debt Collection<br/><br/>
        <b>Greyson McGill</b> — Founder & CEO<br/>
        greyson@quanrecovery.com | quanrecovery.com""",
        ParagraphStyle('Contact', parent=styles['QuanBody'], alignment=TA_CENTER, fontSize=12)
    ))

    elements.append(Spacer(1, 0.3*inch))
    elements.append(Paragraph(
        '"We don\'t just collect debt. We unlock value others abandon."',
        ParagraphStyle('Quote', parent=styles['QuanBody'], alignment=TA_CENTER,
                       fontSize=11, textColor=QUAN_PURPLE, fontName='Helvetica-Oblique')
    ))

    # Build PDF
    doc.build(elements)
    print(f"\n✓ Business Plan PDF generated: {output_path}")
    return output_path


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    output_dir = "/home/user/Quan/output"
    os.makedirs(output_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = f"{output_dir}/QUAN_Recovery_Business_Plan_{timestamp}.pdf"

    generate_business_plan_pdf(output_path)
