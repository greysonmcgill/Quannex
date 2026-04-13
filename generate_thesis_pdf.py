#!/usr/bin/env python3
"""
Quannex Systemic Thesis PDF Generator

Generates a professional PDF of the foundational thesis document:
"Systemic Latency: The Structural Incompatibility of Legacy Collections
Architectures with High-Velocity Micro-Credit Portfolios"

Usage:
    python generate_thesis_pdf.py
    python generate_thesis_pdf.py --output ./output
"""

import sys
import os
from pathlib import Path
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib.colors import HexColor
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, KeepTogether,
)
from reportlab.platypus.flowables import HRFlowable


# Brand colors
QUAN_PURPLE = HexColor('#6B46FF')
QUAN_CYAN = HexColor('#00D4FF')
QUAN_GREEN = HexColor('#00C896')
QUAN_DARK = HexColor('#0A0B1E')
QUAN_GRAY = HexColor('#6B7280')
QUAN_LIGHT_GRAY = HexColor('#F3F4F6')
QUAN_RED = HexColor('#EF4444')


def create_styles():
    """Create all paragraph styles for the thesis PDF."""
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'ThesisTitle',
        parent=styles['Heading1'],
        fontSize=26,
        textColor=QUAN_PURPLE,
        spaceAfter=16,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold',
        leading=32,
    )

    subtitle_style = ParagraphStyle(
        'ThesisSubtitle',
        parent=styles['Normal'],
        fontSize=14,
        textColor=QUAN_DARK,
        spaceAfter=12,
        alignment=TA_CENTER,
        fontName='Helvetica-Oblique',
        leading=18,
    )

    heading1_style = ParagraphStyle(
        'SectionHeading',
        parent=styles['Heading2'],
        fontSize=17,
        textColor=QUAN_PURPLE,
        spaceAfter=10,
        spaceBefore=24,
        fontName='Helvetica-Bold',
        leading=22,
    )

    heading2_style = ParagraphStyle(
        'SubsectionHeading',
        parent=styles['Heading3'],
        fontSize=13,
        textColor=QUAN_DARK,
        spaceAfter=8,
        spaceBefore=14,
        fontName='Helvetica-Bold',
        leading=17,
    )

    heading3_style = ParagraphStyle(
        'SubsubHeading',
        parent=styles['Heading4'],
        fontSize=11,
        textColor=HexColor('#374151'),
        spaceAfter=6,
        spaceBefore=10,
        fontName='Helvetica-Bold',
        leading=14,
    )

    body_style = ParagraphStyle(
        'ThesisBody',
        parent=styles['Normal'],
        fontSize=10,
        textColor=QUAN_DARK,
        spaceAfter=6,
        alignment=TA_JUSTIFY,
        leading=14,
    )

    bullet_style = ParagraphStyle(
        'ThesisBullet',
        parent=body_style,
        leftIndent=20,
        bulletIndent=10,
        spaceAfter=4,
    )

    quote_style = ParagraphStyle(
        'ThesisQuote',
        parent=body_style,
        leftIndent=30,
        rightIndent=30,
        fontName='Helvetica-Oblique',
        textColor=QUAN_PURPLE,
        fontSize=11,
        alignment=TA_CENTER,
        spaceBefore=12,
        spaceAfter=12,
    )

    caption_style = ParagraphStyle(
        'TableCaption',
        parent=body_style,
        fontSize=9,
        textColor=QUAN_GRAY,
        fontName='Helvetica-Oblique',
        alignment=TA_LEFT,
        spaceAfter=10,
        spaceBefore=4,
    )

    code_style = ParagraphStyle(
        'CodeBlock',
        parent=body_style,
        fontName='Courier',
        fontSize=9,
        leftIndent=20,
        textColor=HexColor('#1F2937'),
        backColor=QUAN_LIGHT_GRAY,
        spaceBefore=6,
        spaceAfter=6,
        leading=12,
    )

    citation_style = ParagraphStyle(
        'Citation',
        parent=body_style,
        fontSize=8,
        textColor=QUAN_GRAY,
        leftIndent=15,
        spaceAfter=2,
        leading=10,
    )

    footer_style = ParagraphStyle(
        'FooterStyle',
        parent=body_style,
        fontSize=9,
        textColor=QUAN_GRAY,
        alignment=TA_CENTER,
    )

    return {
        'title': title_style,
        'subtitle': subtitle_style,
        'h1': heading1_style,
        'h2': heading2_style,
        'h3': heading3_style,
        'body': body_style,
        'bullet': bullet_style,
        'quote': quote_style,
        'caption': caption_style,
        'code': code_style,
        'citation': citation_style,
        'footer': footer_style,
    }


def divider():
    """Create a section divider."""
    return HRFlowable(
        width="100%", thickness=2, color=QUAN_PURPLE,
        spaceBefore=2, spaceAfter=12,
    )


def thin_divider():
    """Create a thin divider."""
    return HRFlowable(
        width="100%", thickness=0.5, color=QUAN_GRAY,
        spaceBefore=6, spaceAfter=6,
    )


def make_table(data, col_widths, caption=None, styles_dict=None):
    """Create a styled table with optional caption."""
    elements = []
    t = Table(data, colWidths=col_widths)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), QUAN_PURPLE),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 8),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('GRID', (0, 0), (-1, -1), 0.5, QUAN_GRAY),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, QUAN_LIGHT_GRAY]),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(t)
    if caption and styles_dict:
        elements.append(Paragraph(caption, styles_dict['caption']))
    return elements


def build_cover_page(s):
    """Build the cover page."""
    elements = []
    elements.append(Spacer(1, 1.5 * inch))
    elements.append(Paragraph("Quannex", s['title']))
    elements.append(Spacer(1, 0.3 * inch))

    # Main title
    doc_title_style = ParagraphStyle(
        'DocTitle', parent=s['title'], fontSize=20, leading=26,
        textColor=QUAN_DARK, spaceAfter=20,
    )
    elements.append(Paragraph(
        "Systemic Latency: The Structural Incompatibility of "
        "Legacy Collections Architectures with High-Velocity "
        "Micro-Credit Portfolios",
        doc_title_style,
    ))

    elements.append(Spacer(1, 0.2 * inch))
    elements.append(Paragraph(
        "A Foundational Analysis for Quannex",
        s['subtitle'],
    ))

    elements.append(Spacer(1, 1.5 * inch))

    # Metadata table
    meta = [
        ["Author:", "Greyson McGill, Founder & CEO"],
        ["Organization:", "Quannex"],
        ["Contact:", "greyson@quannex.com"],
        ["Version:", "3.0"],
        ["Date:", datetime.now().strftime('%B %Y')],
        ["Classification:", "Strategic Foundation Document"],
    ]
    meta_table = Table(meta, colWidths=[1.5 * inch, 3.5 * inch])
    meta_table.setStyle(TableStyle([
        ('TEXTCOLOR', (0, 0), (0, -1), QUAN_PURPLE),
        ('TEXTCOLOR', (1, 0), (1, -1), QUAN_DARK),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(meta_table)

    elements.append(Spacer(1, 1.0 * inch))
    elements.append(Paragraph(
        f"Confidential - {datetime.now().strftime('%B %Y')}",
        s['footer'],
    ))
    elements.append(PageBreak())
    return elements


def build_table_of_contents(s):
    """Build table of contents page."""
    elements = []
    elements.append(Paragraph("Table of Contents", s['h1']))
    elements.append(divider())

    toc_style = ParagraphStyle(
        'TOC', parent=s['body'], fontSize=11, spaceAfter=8,
        leading=16,
    )
    toc_indent = ParagraphStyle(
        'TOCIndent', parent=toc_style, leftIndent=20, fontSize=10,
    )

    sections = [
        ("1.", "The Executive Thesis: A Crisis of Unit Economics and Structural Obsolescence"),
        ("2.", "The Historical and Structural Divergence of Debt Architectures"),
        ("3.", "The Unit Economics of Friction: Anatomy of a Broken P&L"),
        ("4.", "The Regulatory Moat: Compliance as a Barrier to Innovation"),
        ("5.", "The Data Infrastructure Void: Metro 2 and the \"Credit Invisible\""),
        ("6.", "Behavioral Economics: The Psychology of Micro-Debt"),
        ("7.", "The Technological Remediation: Agentic AI and the Compute-Centric Model"),
        ("8.", "The Financial Remediation: Tokenization and DeFi Liquidity"),
        ("9.", "Competitive Landscape: Why Incumbents Cannot Close the Gap"),
        ("10.", "Quannex Unit Economics: The Cost Advantage in Practice"),
        ("11.", "Conclusion: The Inevitable Transition"),
    ]

    for num, title in sections:
        elements.append(Paragraph(f"<b>{num}</b>  {title}", toc_style))

    elements.append(Spacer(1, 0.3 * inch))
    elements.append(Paragraph("<b>Appendix:</b>  Works Cited (51 Sources)", toc_style))

    elements.append(PageBreak())
    return elements


def build_section_1(s):
    """Section 1: Executive Thesis."""
    elements = []
    elements.append(Paragraph(
        "1. The Executive Thesis: A Crisis of Unit Economics and Structural Obsolescence",
        s['h1'],
    ))
    elements.append(divider())

    elements.append(Paragraph(
        "The United States credit and collections ecosystem stands at a precipice of functional "
        "obsolescence, driven by a fundamental architectural mismatch between the legacy "
        "infrastructure of debt recovery and the modern reality of consumer liability.",
        s['body'],
    ))

    elements.append(Paragraph(
        "<b>Core Thesis:</b> The prevailing U.S. credit and collections system was engineered for "
        "a macroeconomic environment that no longer exists--one defined by macro-debts such as "
        "30-year fixed-rate mortgages, automotive loans, and consolidated revolving credit lines. "
        "It was never designed, and remains structurally ill-equipped, to manage the explosion of "
        "small-balance, high-velocity consumer debts generated by Buy Now, Pay Later (BNPL) "
        "platforms, gig-economy services, subscription models, and micro-credit products.",
        s['body'],
    ))

    elements.append(Paragraph(
        "This incompatibility is not merely a friction point; it is a <b>systemic failure of unit "
        "economics</b>. The cost to recover a marginal dollar of debt using traditional human-centric "
        "methods now frequently exceeds the value of the dollar itself.",
        s['body'],
    ))

    elements.append(Paragraph("The Atomization Problem", s['h2']))
    elements.append(Paragraph(
        'We are witnessing the "atomization" of consumer debt, where a single individual\'s '
        "financial liabilities are fragmented across dozens of unregulated or semi-regulated "
        "platforms rather than concentrated in a few major banking relationships. This fragmentation "
        "destroys the economies of scale that traditional collection agencies rely upon, rendering "
        "the standard operating procedure--the human agent call center--<b>economically insolvent</b> "
        "for a vast and growing segment of the credit market.",
        s['body'],
    ))

    elements.append(Paragraph("Systemic Implications", s['h2']))
    elements.append(Paragraph(
        '<b>1. Sub-Prime Tax:</b> Vulnerable consumers face inflated costs for essential financial '
        'services to subsidize recovery system inefficiency', s['bullet'],
    ))
    elements.append(Paragraph(
        '<b>2. Regulatory Friction:</b> Compliance acts as a barrier to resolution rather than a '
        'safeguard', s['bullet'],
    ))
    elements.append(Paragraph(
        '<b>3. Market Failure:</b> Over $150B in total consumer debt charged off annually [45], of which '
        '$37.4B sits in a structural \"dead zone\" where recovery costs exceed the debt itself', s['bullet'],
    ))

    elements.append(Spacer(1, 0.15 * inch))
    elements.append(Paragraph(
        '<b>Required Response:</b> A radical paradigm shift toward autonomous, "Agentic AI" driven '
        "recovery models and the securitization of micro-debts via blockchain-based Real-World Asset "
        "(RWA) tokenization to restore liquidity and operational viability to the consumer credit market.",
        s['body'],
    ))

    elements.append(PageBreak())
    return elements


def build_section_2(s):
    """Section 2: Historical Divergence."""
    elements = []
    elements.append(Paragraph(
        "2. The Historical and Structural Divergence of Debt Architectures", s['h1'],
    ))
    elements.append(divider())

    elements.append(Paragraph(
        "To understand the magnitude of the current crisis, one must analyze the genealogy of the "
        "U.S. collections infrastructure. The system is operating on a chassis built in the mid-20th "
        "century, optimized for a completely different set of financial physics.",
        s['body'],
    ))

    elements.append(Paragraph("2.1 The Legacy Paradigm: Macro-Debt and Human Intervention", s['h2']))
    elements.append(Paragraph(
        'Post-World War II American consumer credit was characterized by "lumpy" debt. A typical '
        "household might have a mortgage, a car loan, and perhaps a department store credit line. "
        "These debts were substantial in principal, originated by regulated depository institutions, "
        "and underwritten with significant friction (paper applications, manual review).",
        s['body'],
    ))
    elements.append(Paragraph(
        "In this environment, the collections model was straightforward: human intervention. When a "
        "loan of $15,000 went into default, deploying a human agent to spend hours skip-tracing, "
        'calling, and negotiating was a rational allocation of resources. The "Cost to Collect" (CTC) '
        'was a fraction of the "Value at Risk" (VaR).',
        s['body'],
    ))
    elements.append(Paragraph(
        "The infrastructure that calcified around this model--large call centers, predictive dialers, "
        "and manual legal processing--was designed to amortize high fixed costs over high-value "
        "recovery targets.",
        s['body'],
    ))
    elements.append(Paragraph(
        "<b>Regulatory Framework (FDCPA, 1977):</b> The Fair Debt Collection Practices Act assumed "
        "a world where communication was synchronous and intrusive (the telephone). It built "
        "guardrails around harassment but did not anticipate a world where a consumer might have 20 "
        "concurrent distinct debt obligations, each requiring separate compliant communications.",
        s['body'],
    ))

    elements.append(Paragraph("2.2 The Modern Paradigm: The Atomization of Liability", s['h2']))
    elements.append(Paragraph(
        'The financialization of the digital economy has shattered the "lumpy" debt model. We have '
        'moved to a "granular" debt model defined by three key vectors:',
        s['body'],
    ))

    # Table 1: Structural Divergence
    t1_data = [
        ["Feature", "Legacy Debt Model\n(1970-2010)", "Modern Micro-Debt Model\n(2020-Present)"],
        ["Primary Debt\nVehicles", "Mortgages, Auto Loans,\nCredit Cards", "BNPL, Subscriptions,\nGig-Advances, Micro-loans"],
        ["Average Balance", "High ($5k - $300k)", "Low ($20 - $500)"],
        ["Underwriting\nSpeed", "Days / Weeks", "Milliseconds / Seconds"],
        ["Origination\nSource", "Banks, Credit Unions", "Fintechs, Merchants, Apps"],
        ["Data Visibility", "High (Centralized\nCredit Bureaus)", "Low (Fragmented /\nPhantom Debt)"],
        ["Recovery Method", "Human Agents,\nLitigation", "Digital Nudges, AI Agents,\nWrite-offs"],
    ]
    elements.extend(make_table(
        t1_data, [1.2 * inch, 2.2 * inch, 2.6 * inch],
        "Table 1: The Structural Divergence of Consumer Credit Architectures",
        s,
    ))

    elements.append(PageBreak())
    return elements


def build_section_3(s):
    """Section 3: Unit Economics."""
    elements = []
    elements.append(Paragraph(
        "3. The Unit Economics of Friction: Anatomy of a Broken P&L", s['h1'],
    ))
    elements.append(divider())

    elements.append(Paragraph(
        "The central failure point of the current system is mathematical. The operational cost of "
        "compliant human-centric collection has effectively imposed a \"floor\" on the size of debt "
        "that is economically recoverable.",
        s['body'],
    ))

    elements.append(Paragraph("3.1 The Insolvency of the Human Agent Model", s['h2']))
    elements.append(Paragraph(
        "Benchmarking data for 2024-2025 indicates that the fully burdened cost of a human agent in "
        "a specialized financial services role ranges between <b>$3.00 and $6.50 per minute</b> of "
        "active handle time. This includes:",
        s['body'],
    ))
    for item in [
        "<b>Direct Compensation:</b> Wages, commissions, and bonuses",
        "<b>Benefits &amp; Taxes:</b> Healthcare, insurance, payroll taxes (often 30% of base pay)",
        "<b>Infrastructure:</b> Seat licenses for dialers, CRM software, compliance tools",
        "<b>Management Overhead:</b> QA monitoring, team leads, training, and HR support",
    ]:
        elements.append(Paragraph(f"- {item}", s['bullet']))

    elements.append(Paragraph("The Micro-Debt Recovery Trap", s['h3']))
    elements.append(Paragraph(
        "Consider a typical BNPL default of $50. A human agent spends 15 minutes on the account "
        "(review, contact attempts, negotiation). At $4.00/min, the operational cost is <b>$60.00</b>--"
        "the agency has spent $60 to recover $50. This is a <b>guaranteed loss</b>. Even at 5 minutes "
        "($20), the cost represents 40% of principal. With a 5% Right Party Contact rate, 19 of every "
        "20 calls are wasted cost.",
        s['body'],
    ))

    elements.append(Paragraph("3.2 The Sub-Prime Tax", s['h2']))
    elements.append(Paragraph(
        "The inefficiency is passed to consumers as higher rates and fees. A borrower with a 620 "
        "credit score pays an average <b>\"tax\" of nearly $3,400 per year</b> in excess interest "
        "and insurance premiums compared to a prime borrower:",
        s['body'],
    ))
    for item in [
        "<b>Auto Loans:</b> ~$745 more per year in interest",
        "<b>Insurance:</b> ~$514 more annually (credit-based scoring)",
        "<b>Mortgages:</b> Over $1,300 annually in interest disparity",
    ]:
        elements.append(Paragraph(f"- {item}", s['bullet']))

    elements.append(Paragraph("3.3 The BNPL Delinquency Paradox", s['h2']))
    elements.append(Paragraph(
        "In 2025, delinquency rates for BNPL users spiked with <b>41% of users reporting a late "
        "payment</b>. Meanwhile, <b>63% of BNPL borrowers have multiple active loans simultaneously</b>, "
        "creating a liquidity crunch. In this \"stacked\" scenario, the creditor who gets paid is the "
        "one with the least friction--and the legacy system loses this race every time.",
        s['body'],
    ))

    elements.append(Paragraph("3.4 Break-Even Analysis", s['h2']))
    be_data = [
        ["Balance", "Required Recovery\nRate", "Industry Actual\nRate", "Economic\nViability"],
        ["$500", "9.4%", "22%", "Viable"],
        ["$200", "23.5%", "18%", "Marginal"],
        ["$100", "47%", "15%", "Insolvent"],
        ["$50", "94%", "12%", "Impossible"],
    ]
    elements.extend(make_table(be_data, [1.2 * inch, 1.5 * inch, 1.5 * inch, 1.3 * inch], None, s))
    elements.append(Paragraph(
        "<b>Conclusion:</b> Any debt under ~$250 is structurally uncollectible under the legacy model.",
        s['body'],
    ))

    elements.append(Paragraph('3.5 The Market Size of the "Dead Zone"', s['h2']))
    dz_data = [
        ["Debt Category", "Annual Default\nVolume", "Avg Balance", "% Under\n$250", "Dead Zone\nValue"],
        ["BNPL", "$7.2B", "$142", "78%", "$5.6B"],
        ["Subscriptions", "$4.8B", "$48", "100%", "$4.8B"],
        ["Gig Advances", "$1.2B", "$75", "95%", "$1.1B"],
        ["Overdraft/NSF", "$15B", "$35", "100%", "$15B"],
        ["Medical (<$500)", "$8B", "$180", "85%", "$6.8B"],
        ["Telecom", "$3.5B", "$220", "60%", "$2.1B"],
        ["Utilities", "$2.8B", "$165", "72%", "$2.0B"],
        ["TOTAL", "", "", "", "$37.4B"],
    ]
    elements.extend(make_table(
        dz_data, [1.2 * inch, 1.1 * inch, 0.9 * inch, 0.8 * inch, 1.0 * inch],
        "The $37.4B addressable market exists solely because of architectural obsolescence.",
        s,
    ))

    elements.append(PageBreak())
    return elements


def build_section_4(s):
    """Section 4: Regulatory Moat."""
    elements = []
    elements.append(Paragraph(
        "4. The Regulatory Moat: Compliance as a Barrier to Innovation", s['h1'],
    ))
    elements.append(divider())

    elements.append(Paragraph(
        "The rules governing debt collection were written for a different technological era and "
        "often criminalize the very efficiency needed to solve the micro-debt problem.",
        s['body'],
    ))

    elements.append(Paragraph("4.1 Regulation F and the 7/7/7 Rule", s['h2']))
    elements.append(Paragraph(
        "The CFPB's Regulation F introduced the <b>\"7/7/7\" rule</b>: a debt collector is presumed "
        "to be harassing a consumer if they place a telephone call more than seven times within a "
        "seven-day period or within seven days of engaging in a telephone conversation.",
        s['body'],
    ))
    for item in [
        "<b>Impact on Micro-Debt:</b> For a $30 BNPL installment tied to a bi-weekly paycheck, speed is essential--but legally throttled",
        "<b>Throughput Constraint:</b> For high-volume, low-balance portfolios, this throttle destroys the ability to find paying consumers",
        "<b>Channel Ambiguity:</b> SMS and email are unlimited with opt-out, but voicemail Limited Content Message rules create a compliance minefield",
    ]:
        elements.append(Paragraph(f"- {item}", s['bullet']))

    elements.append(Paragraph('4.2 The "Mini-Miranda" and AI Liability', s['h2']))
    elements.append(Paragraph(
        "The FDCPA mandates the Mini-Miranda warning in all communications. For AI systems, this "
        "creates unique risks:",
        s['body'],
    ))
    for item in [
        "<b>Omission Risk:</b> Failing to state the Mini-Miranda is strict liability",
        '<b>Hallucination Risk:</b> AI may fabricate threats ("We will garnish your wages") that are illegal under FDCPA',
        "<b>Impersonation Risk:</b> AI simulating a human creates UDAAP liability",
    ]:
        elements.append(Paragraph(f"- {item}", s['bullet']))
    elements.append(Paragraph(
        "This mandates a <b>\"Compliance-by-Design\"</b> approach: hard-coded guardrails that prevent "
        "non-compliant output regardless of conversation flow.",
        s['body'],
    ))

    elements.append(Paragraph("4.3 The 50-State Problem", s['h2']))
    elements.append(Paragraph(
        "The U.S. does not have a single debt collection market; it has 50. States like New York, "
        "California, and Massachusetts have enacted regulations far exceeding federal standards.",
        s['body'],
    ))

    # Table 3: Regulatory Friction
    rf_data = [
        ["Regulation", "Original Intent", "Friction in Micro-Debt Context"],
        ["FDCPA (1977)", "Prevent harassment\nvia phone", "Criminalizes efficient digital contact\nstrategies for high-volume accounts"],
        ["Reg F (7/7/7)", "Limit call\nfrequency", "Caps throughput for short-term debts\nwhere velocity is critical"],
        ["TCPA (1991)", "Stop robocalls", "Creates liability for AI-driven SMS/Voice\nwithout express consent"],
        ["Mini-Miranda", "Disclose collector\nidentity", "Hallucination risk for AI; strict\nliability trap for automated systems"],
        ["State Licensing", "Local oversight", "Administrative nightmare for national\nfintech apps; massive overhead per debt"],
    ]
    elements.extend(make_table(
        rf_data, [1.2 * inch, 1.5 * inch, 3.0 * inch],
        "Table 3: Regulatory Friction Points for Modern Debt",
        s,
    ))

    elements.append(PageBreak())
    return elements


def build_section_5(s):
    """Section 5: Data Infrastructure Void."""
    elements = []
    elements.append(Paragraph(
        '5. The Data Infrastructure Void: Metro 2 and the "Credit Invisible"', s['h1'],
    ))
    elements.append(divider())

    elements.append(Paragraph(
        "The industry standard data format, Metro 2, is a relic of the mainframe era, incapable of "
        "handling the nuance and velocity of modern micro-credit.",
        s['body'],
    ))

    elements.append(Paragraph("5.1 The Metro 2 Bottleneck", s['h2']))
    for item in [
        "<b>Latency:</b> A BNPL loan (4 payments over 6 weeks) moves faster than the Metro 2 monthly reporting cycle. A consumer could open, default, and cure before the file is processed",
        "<b>Categorization Failure:</b> Metro 2 has no native \"BNPL\" trade line code. Bureaus shoehorn these into \"unsecured installment\" categories, potentially harming consumer scores",
        "<b>Furnishing Friction:</b> Small fintechs choose not to report because dispute handling costs (e-OSCAR integration, dedicated staff) outweigh the benefit",
    ]:
        elements.append(Paragraph(f"- {item}", s['bullet']))

    elements.append(Paragraph("5.2 NCAP and Data Suppression", s['h2']))
    elements.append(Paragraph(
        "The National Consumer Assistance Plan has systematically scrubbed negative data from credit "
        "reports. Paid medical collections and medical debt under $500 are no longer reported. Civil "
        "judgments and tax liens have been largely removed. The result: a <b>\"Blind\" Lender</b> "
        "problem where underwriters cannot see a consumer's full obligation picture, forcing higher "
        "risk assumptions for everyone.",
        s['body'],
    ))

    elements.append(Paragraph("5.3 Alternative Data and Trigger Leads", s['h2']))
    elements.append(Paragraph(
        "To fill the void, the industry turns to alternative data: bank account cash flows, utility "
        "payments, rental history. While this helps \"credit invisible\" consumers, it effectively ends "
        "financial privacy. Meanwhile, bureaus monetize credit inquiries as \"trigger leads,\" selling "
        "consumer intent to competing lenders.",
        s['body'],
    ))

    elements.append(PageBreak())
    return elements


def build_section_6(s):
    """Section 6: Behavioral Economics."""
    elements = []
    elements.append(Paragraph(
        "6. Behavioral Economics: The Psychology of Micro-Debt", s['h1'],
    ))
    elements.append(divider())

    elements.append(Paragraph(
        'The collections system assumes a "Rational Economic Man" who prioritizes debts by interest '
        "rates and legal consequences. The modern consumer, overwhelmed by micro-transactions, "
        "behaves very differently.",
        s['body'],
    ))

    elements.append(Paragraph('6.1 Rational Inattention and the "Ostrich Effect"', s['h2']))
    elements.append(Paragraph(
        "Faced with the cognitive load of managing dozens of subscriptions, BNPL payments, and bills, "
        "consumers engage in <b>\"Rational Inattention\"</b>--the cost (in time and stress) of "
        "processing the information exceeds the benefit of resolving the $20 debt. Traditional "
        "collections, which increase frequency and urgency of contact, actually worsen this effect. "
        "In an attention economy, a collection email competes with hundreds of marketing emails and "
        "is easily filtered out.",
        s['body'],
    ))

    elements.append(Paragraph('6.2 The "Snowball" Preference', s['h2']))
    elements.append(Paragraph(
        "Behavioral research shows consumers overwhelmingly prefer the <b>Snowball Method</b>: paying "
        "off smallest balances first for a psychological \"win.\" Strategies that aggregate debt or "
        "offer lump sum settlements for multiple small items are more psychologically attractive than "
        "collecting each line item individually.",
        s['body'],
    ))

    elements.append(Paragraph("6.3 Gamification as Engagement", s['h2']))
    elements.append(Paragraph(
        "<b>Case Study -- Wandoo Finance:</b> Replaced threatening reminders with a gamified interface "
        "where users earned points for repayment behaviors, tapping into dopamine loops of mobile "
        "gaming. Significantly increased repayment rates.",
        s['body'],
    ))
    elements.append(Paragraph(
        "<b>Symend's Behavioral Engagement:</b> Instead of \"You owe $50,\" messages read \"Hi [Name], "
        "we know life gets busy. Here is a flexible way to get back on track.\" By reducing shame and "
        "pain of paying, they unlock payments from willing but stressed consumers.",
        s['body'],
    ))

    elements.append(PageBreak())
    return elements


def build_section_7(s):
    """Section 7: Technological Remediation."""
    elements = []
    elements.append(Paragraph(
        "7. The Technological Remediation: Agentic AI and the Compute-Centric Model", s['h1'],
    ))
    elements.append(divider())

    elements.append(Paragraph(
        "The only viable path to resolving the unit economics crisis is the complete removal of "
        "human labor from the micro-debt recovery chain through autonomous, cognitive "
        "<b>\"Agentic AI.\"</b>",
        s['body'],
    ))

    elements.append(Paragraph("7.1 The Economics of Agentic AI", s['h2']))
    elements.append(Paragraph(
        "While a human agent costs ~$4.00/minute, an AI voice agent costs between <b>$0.08 and "
        "$0.20 per minute</b>--a 95%+ reduction in marginal cost that makes high-touch negotiation "
        "viable for a $30 debt. AI scales from 100 concurrent calls to 100,000 instantly.",
        s['body'],
    ))

    # Table 2: Comparative Unit Economics
    ue_data = [
        ["Metric", "Human Agent\n(US)", "Offshore\nAgent", "Agentic AI\nVoice", "Digital/SMS\nNudge"],
        ["Cost Per\nMinute", "$3.00 - $6.50", "$0.50 - $1.00", "$0.08 - $0.20", "< $0.01"],
        ["Setup Cost", "High\n(Hiring/Training)", "Medium\n(Vendor Mgmt)", "Low\n(API Integration)", "Low\n(SaaS)"],
        ["Scalability", "Low\n(Weeks/Months)", "Medium\n(Days/Weeks)", "Instant", "Instant"],
        ["Compliance\nRisk", "High\n(Human Error)", "High\n(Script Adhere)", "Low\n(Code-Constrain)", "Low\n(Template)"],
        ["Min. Viable\nDebt", "$200 - $300", "$50 - $100", "$5", "$1"],
    ]
    elements.extend(make_table(
        ue_data, [1.0 * inch, 1.2 * inch, 1.1 * inch, 1.1 * inch, 1.1 * inch],
        "Table 2: Comparative Unit Economics of Recovery Channels",
        s,
    ))

    elements.append(Paragraph("7.2 The Architecture of Autonomy", s['h2']))
    for item in [
        "<b>Orchestrator LLM:</b> The \"brain\" that understands conversation context and decides strategy",
        "<b>RAG (Retrieval-Augmented Generation):</b> Pulls debtor details and compliance rules from a vector database in real-time",
        "<b>Voice Synthesis (TTS/STT):</b> Low-latency (sub-800ms) voice conversion for natural engagement",
        "<b>Compliance Monitor:</b> A separate \"Constitutional AI\" model acting as a real-time kill-switch for FDCPA violations",
    ]:
        elements.append(Paragraph(f"- {item}", s['bullet']))

    elements.append(Paragraph("7.3 Vertical vs. Horizontal AI", s['h2']))
    elements.append(Paragraph(
        "Generic AI models (Horizontal AI) lack domain expertise. The industry is moving toward "
        "<b>Vertical AI</b>--models fine-tuned on millions of debt collection conversations that "
        "understand the nuance of \"I can't pay until Friday\" vs. \"I refuse to pay.\"",
        s['body'],
    ))

    elements.append(PageBreak())
    return elements


def build_section_8(s):
    """Section 8: Tokenization and DeFi."""
    elements = []
    elements.append(Paragraph(
        "8. The Financial Remediation: Tokenization and DeFi Liquidity", s['h1'],
    ))
    elements.append(divider())

    elements.append(Paragraph(
        "While AI solves the recovery problem, it does not solve the liquidity problem for lenders "
        "holding millions in non-performing micro-loans. The solution: securitization via blockchain.",
        s['body'],
    ))

    elements.append(Paragraph("8.1 The Illiquidity of NPL Portfolios", s['h2']))
    elements.append(Paragraph(
        "Selling charged-off BNPL debt is slow and opaque. The bid-ask spread is massive because "
        "buyers don't trust data quality and can't easily verify assets.",
        s['body'],
    ))

    elements.append(Paragraph("8.2 Real-World Asset (RWA) Tokenization", s['h2']))
    elements.append(Paragraph(
        "Protocols like <b>Centrifuge</b> move securitization on-chain. Each debt (or batch) is "
        "minted as an NFT with immutable metadata (origination, payment history, risk score). "
        "Buyers can audit entire portfolio performance in real-time, eliminating the \"lemon market\" problem.",
        s['body'],
    ))

    elements.append(Paragraph("8.3 The Tinlake Tranche Model", s['h2']))
    for item in [
        "<b>DROP Token (Senior Tranche):</b> Paid first, lower yield (5-8%), protected against first-wave defaults",
        "<b>TIN Token (Junior Tranche):</b> First-loss position, upside yield (12-20%), paid after DROP holders satisfied",
        "<b>Algorithmic Waterfall:</b> Smart contract auto-routes repayments. No servicer fees or delays. The code is the servicer",
    ]:
        elements.append(Paragraph(f"- {item}", s['bullet']))

    # Table 4: Tokenized Debt Stack
    ts_data = [
        ["Layer", "Function", "Technology / Mechanism"],
        ["Asset Originator", "Originates the loan\n(BNPL, Invoice)", "Fintech App / Lender"],
        ["Tokenization", "Mints NFT representing\nasset/collateral", "Centrifuge P2P Protocol"],
        ["Pooling", "Aggregates NFTs into\nsmart contract pool", "Tinlake / Centrifuge Chain"],
        ["Tranching", "Splits risk into Senior\n(DROP) and Junior (TIN)", "Smart Contract Logic"],
        ["Liquidity", "Provides capital against\ntokens", "DeFi Protocols\n(MakerDAO, Aave)"],
        ["Servicing", "Collects payments,\ndistributes to tranches", "Automated Waterfall\nContract"],
    ]
    elements.extend(make_table(
        ts_data, [1.2 * inch, 2.0 * inch, 2.2 * inch],
        "Table 4: The Tokenized Debt Stack (Centrifuge/Tinlake Model)",
        s,
    ))

    elements.append(Paragraph("8.4 DeFi Integration", s['h2']))
    elements.append(Paragraph(
        "This infrastructure lets BNPL lenders access global DeFi liquidity. Originate loans, "
        "tokenize them, pledge as collateral to MakerDAO or Aave, and borrow stablecoins (USDC) "
        "instantly. This \"capital velocity\" recycles funds far faster than traditional bank facilities.",
        s['body'],
    ))

    elements.append(Paragraph("8.5 Regulatory Realism: The Path to Compliant Tokenization", s['h2']))
    elements.append(Paragraph(
        "Tokenized debt securities face real regulatory constraints that any credible implementation must address. "
        "Quannex's approach is pragmatic, not utopian:",
        s['body'],
    ))
    for item in [
        "<b>SEC Classification:</b> Tokenized debt tranches are securities under the Howey test. Quannex's model "
        "operates under Regulation D (506(c)) for accredited investors initially, with a Regulation A+ path "
        "for broader access as track record develops [46]",
        "<b>State Money Transmitter Licensing:</b> Smart contract payment flows trigger MTL requirements. "
        "Quannex partners with licensed payment processors (Stripe, Dwolla) rather than building custodial infrastructure",
        "<b>Bankruptcy Remoteness:</b> Assets must be legally isolated from the originator. Quannex uses "
        "Delaware statutory trusts (the same SPV structure used in traditional ABS) with on-chain record-keeping, "
        "not on-chain custody",
        "<b>CFPB Servicing Rules:</b> AI-driven servicing must still comply with FDCPA validation notices "
        "and dispute resolution timelines. Quannex's compliance engine (Section 7.2) is the critical enabler--code "
        "enforces what traditional servicers handle manually",
    ]:
        elements.append(Paragraph(f"- {item}", s['bullet']))

    elements.append(Spacer(1, 0.1 * inch))
    elements.append(Paragraph(
        "The key insight: Quannex does not need to revolutionize securities law. The legal frameworks for "
        "securitization already exist and are well-tested. What Quannex brings is the ability to make the "
        "underlying assets--micro-debts that are currently written off--economically viable through AI-driven "
        "recovery, thereby creating a performant asset class where none existed before.",
        s['body'],
    ))

    elements.append(PageBreak())
    return elements


def build_section_9_competitive(s):
    """Section 9: Competitive Landscape."""
    elements = []
    elements.append(Paragraph(
        "9. Competitive Landscape: Why Incumbents Cannot Close the Gap", s['h1'],
    ))
    elements.append(divider())

    elements.append(Paragraph(
        "Several companies are applying technology to debt collection. None are architected to solve "
        "the micro-debt unit economics problem that defines Quannex's addressable market.",
        s['body'],
    ))

    elements.append(Paragraph("9.1 The Current Players", s['h2']))

    comp_data = [
        ["Company", "Approach", "Limitation", "Min. Viable Debt"],
        ["TrueAccord\n(2013, $50M+)", "ML-optimized email/SMS\nsequencing for digital-first\ncollection", "Optimizes channel timing, not\ncost structure. Still charges\n15-40% contingency fees", "$200+"],
        ["Symend\n(2016, $100M+)", "Behavioral science SaaS\nfor pre-delinquency\nengagement", "Sells to banks as a retention\ntool, not a collector. Does not\nown the recovery P&L", "N/A\n(SaaS model)"],
        ["Indebted\n(2016, $47M)", "AI-powered digital\ncollection platform\n(Australia-first)", "Geographic focus on ANZ/UK.\nU.S. compliance engine not\nbuilt for 50-state complexity", "$100+"],
        ["Prodigal\n(2018, $30M+)", "AI call analytics and\ncompliance monitoring\nfor existing agencies", "Augments humans, does not\nreplace them. The human agent\ncost floor remains", "$200+"],
        ["Kredit (Skit.ai)\n(2021)", "AI voice agents for\noutbound collection\ncalls", "Voice-only channel. No\norchestration, no settlement\nengine, no tokenization layer", "$100+"],
    ]
    elements.extend(make_table(
        comp_data, [1.2 * inch, 1.6 * inch, 1.7 * inch, 0.9 * inch],
        "Table 5: Competitive Landscape -- AI Collections Entrants",
        s,
    ))

    elements.append(Paragraph("9.2 Why Quannex Is Structurally Different", s['h2']))
    elements.append(Paragraph(
        "The competitors above share a common limitation: they optimize within the existing collections "
        "architecture rather than replacing it. They make human agents more efficient, or automate a "
        "single channel, or reduce churn before charge-off. None of them address the fundamental "
        "question: <b>how do you profitably recover a $50 debt?</b>",
        s['body'],
    ))

    elements.append(Spacer(1, 0.1 * inch))
    elements.append(Paragraph("Quannex's moat is the integration of three layers that no competitor combines:", s['body']))
    for item in [
        "<b>Layer 1 -- Autonomous Full-Lifecycle Recovery:</b> Not just contact optimization, but end-to-end "
        "account management from ingestion through settlement, with zero human labor below $1,000. "
        "Multi-channel orchestration (voice, SMS, email, digital) with a compliance engine that enforces "
        "FDCPA/TCPA/Reg F and all 50 state laws programmatically",
        "<b>Layer 2 -- Vertical Intelligence:</b> ML models trained specifically on micro-debt behavioral "
        "patterns (payment willingness scoring, channel responsiveness, settlement threshold prediction). "
        "Not a generic LLM wrapper--a purpose-built recovery intelligence engine with 147-dimension "
        "feature space for debtor segmentation",
        "<b>Layer 3 -- Liquidity Infrastructure:</b> Tokenization of recovered and recovering portfolios "
        "into tradeable instruments, creating a secondary market for an asset class that currently has "
        "zero liquidity. This is the true platform play--Quannex becomes the exchange, not just the servicer",
    ]:
        elements.append(Paragraph(f"- {item}", s['bullet']))

    elements.append(Spacer(1, 0.1 * inch))
    elements.append(Paragraph(
        "The result: Quannex does not compete with TrueAccord for the same $5,000 credit card portfolio. "
        "Quannex operates in the $37.4B dead zone that every other player has written off as unrecoverable.",
        s['body'],
    ))

    elements.append(PageBreak())
    return elements


def build_section_10_unit_economics(s):
    """Section 10: Quannex Unit Economics."""
    elements = []
    elements.append(Paragraph(
        "10. Quannex Unit Economics: The Cost Advantage in Practice", s['h1'],
    ))
    elements.append(divider())

    elements.append(Paragraph(
        "Section 3 demonstrated that legacy collections break even only above ~$250. "
        "Quannex's architecture fundamentally reshapes this equation.",
        s['body'],
    ))

    elements.append(Paragraph("10.1 Quannex's Cost-to-Collect Per Account", s['h2']))
    elements.append(Paragraph(
        "Based on current API pricing for AI voice, SMS, and email channels, and our platform's "
        "orchestration efficiency, Quannex's projected fully-loaded cost per account is:",
        s['body'],
    ))

    cost_data = [
        ["Cost Component", "Per Account", "Notes"],
        ["AI Voice (avg 2.3 min)", "$0.35", "Retell/Vapi at $0.08-0.15/min\n+ TTS/STT overhead"],
        ["SMS Sequence (avg 4 msgs)", "$0.08", "Twilio at $0.02/msg"],
        ["Email Sequence (avg 3 msgs)", "$0.03", "SendGrid at $0.01/msg"],
        ["ML Scoring + Routing", "$0.02", "Amortized GPU inference"],
        ["Compliance Engine", "$0.01", "Per-account rule evaluation"],
        ["Payment Processing", "$0.45", "Stripe 2.9% on avg $15 recovery"],
        ["Infrastructure (amort.)", "$0.06", "Cloud compute per account"],
        ["TOTAL", "$1.00", "Fully loaded cost per account"],
    ]
    elements.extend(make_table(
        cost_data, [1.8 * inch, 1.0 * inch, 2.6 * inch],
        "Table 6: Quannex Projected Cost-to-Collect Per Account",
        s,
    ))

    elements.append(Paragraph("10.2 Break-Even Comparison: Legacy vs. Quannex", s['h2']))

    be_data = [
        ["Debt Balance", "Legacy Break-Even\nRecovery Rate", "Quannex Break-Even\nRecovery Rate", "Quannex Margin\nat 15% Recovery"],
        ["$500", "9.4%", "0.13%", "$74.00 (98.7%)"],
        ["$200", "23.5%", "0.33%", "$29.00 (96.7%)"],
        ["$100", "47.0%", "0.67%", "$14.00 (93.3%)"],
        ["$50", "94.0%", "1.33%", "$6.50 (86.7%)"],
        ["$25", "Impossible", "2.67%", "$2.75 (73.3%)"],
    ]
    elements.extend(make_table(
        be_data, [0.9 * inch, 1.4 * inch, 1.4 * inch, 1.6 * inch],
        "Table 7: Break-Even Analysis -- Legacy Model vs. Quannex at $1.00/account CTC",
        s,
    ))

    elements.append(Spacer(1, 0.1 * inch))
    elements.append(Paragraph(
        "At $1.00 per account, Quannex breaks even at a 1.33% recovery rate on a $50 debt--compared "
        "to the 94% required by legacy. Even conservative 15% recovery rates yield 87%+ gross margins "
        "on micro-debt, transforming a structurally impossible business into a high-margin one.",
        s['body'],
    ))

    elements.append(Paragraph("10.3 Portfolio-Level Projections", s['h2']))
    elements.append(Paragraph(
        "Modeled against the $37.4B dead zone market (Section 3.5), assuming Quannex captures "
        "1% of addressable volume in Year 1 with a blended 12% recovery rate:",
        s['body'],
    ))

    portfolio_data = [
        ["Metric", "Year 1 Projection", "Year 3 Projection"],
        ["Accounts Under Management", "2.5M", "25M"],
        ["Face Value of Portfolios", "$374M", "$3.74B"],
        ["Blended Recovery Rate", "12%", "18%"],
        ["Gross Recovery Revenue", "$44.9M", "$673M"],
        ["Total Operating Cost", "$2.5M", "$25M"],
        ["Gross Margin", "$42.4M (94.4%)", "$648M (96.3%)"],
        ["Revenue (30% contingency)", "$13.5M", "$202M"],
    ]
    elements.extend(make_table(
        portfolio_data, [1.8 * inch, 1.5 * inch, 1.5 * inch],
        "Table 8: Quannex Portfolio-Level Financial Projections",
        s,
    ))

    elements.append(Paragraph("10.4 Early Validation", s['h2']))
    elements.append(Paragraph(
        "Quannex's platform simulation environment has processed 1M+ synthetic accounts across "
        "10 debt categories, validating the core architecture:",
        s['body'],
    ))
    for item in [
        "<b>Simulation Results:</b> 6 consumer behavioral archetypes (Prompt Payer, Negotiator, "
        "Plan Keeper, Plan Breaker, Ghost, Hostile) modeled across BNPL, medical, telecom, "
        "subscription, utility, and other micro-debt categories",
        "<b>Platform Operational:</b> Full-stack application with FastAPI backend, Next.js dashboard, "
        "real-time analytics, and compliance-first account pipeline running in local and containerized "
        "environments",
        "<b>ML Pipeline Active:</b> Payment probability prediction, debtor segmentation (graph-based), "
        "channel optimization (multi-armed bandit), and settlement recommendation engines operational "
        "with synthetic data",
        "<b>Compliance Engine Built:</b> Programmatic FDCPA, TCPA, Regulation F, and 50-state "
        "rule enforcement with contact frequency governors and consent tracking",
    ]:
        elements.append(Paragraph(f"- {item}", s['bullet']))

    elements.append(Spacer(1, 0.1 * inch))
    elements.append(Paragraph(
        "<b>Next Milestone:</b> Live pilot with a single BNPL originator processing real charged-off "
        "accounts to validate recovery rates against simulation projections. Target: Q3 2026.",
        s['body'],
    ))

    elements.append(PageBreak())
    return elements


def build_section_11_conclusion(s):
    """Section 11: Conclusion."""
    elements = []
    elements.append(Paragraph(
        "11. Conclusion: The Inevitable Transition", s['h1'],
    ))
    elements.append(divider())

    elements.append(Paragraph(
        "The convergence of these forces--the collapse of unit economics, the rigor of regulation, "
        "the opacity of data, and the emergence of AI and Blockchain--points to a singular "
        "conclusion: <b>The legacy model of debt collection is dead.</b> It is not merely inefficient; "
        "it is structurally incapable of functioning in the modern economy.",
        s['body'],
    ))

    elements.append(Paragraph("The New Model", s['h2']))
    for item in [
        "<b>Fully Autonomous Recovery:</b> For debts under $1,000, human intervention will be eliminated. Agentic AI handles 100% of the lifecycle at cents per dollar",
        "<b>Programmatic Compliance:</b> Regulation codified into the software stack. Compliance becomes a software library, not a department",
        "<b>On-Chain Liquidity:</b> Debt tokenized at origination for fluid, transparent trading and instant lender liquidity",
        "<b>Behavioral-First Engagement:</b> Adversarial \"collections\" replaced by \"financial wellness\" approach, rehabilitating consumer LTV rather than extracting one-time payments",
    ]:
        elements.append(Paragraph(f"- {item}", s['bullet']))

    elements.append(Spacer(1, 0.15 * inch))
    elements.append(Paragraph(
        "The entities that cling to the call center model and Metro 2 batches will find themselves on "
        "the wrong side of history. The future belongs to those who treat debt not as a moral failing "
        "to be punished, but as a <b>data problem to be solved with compute, code, and cryptography</b>.",
        s['body'],
    ))

    elements.append(Paragraph("The Quannex Solution", s['h2']))
    elements.append(Paragraph(
        "Quannex is not disrupting an existing market. Quannex is <b>creating the infrastructure for a "
        "market that currently does not function</b>.",
        s['body'],
    ))
    elements.append(Paragraph(
        "The $37.4B annually stranded in the structural dead zone is not \"bad debt.\" It is "
        "<b>orphaned debt</b>--economically recoverable value that the existing system has "
        "structurally abandoned.",
        s['body'],
    ))
    elements.append(Paragraph(
        "<b>Quannex is the architecture that resurrects it.</b>",
        s['body'],
    ))

    elements.append(Spacer(1, 0.3 * inch))
    elements.append(thin_divider())
    elements.append(Paragraph(
        '"We don\'t just collect debt. We\'re building the parallel credit infrastructure '
        'for the modern economy."',
        s['quote'],
    ))

    elements.append(PageBreak())
    return elements


def build_works_cited(s):
    """Build the works cited section."""
    elements = []
    elements.append(Paragraph("Works Cited", s['h1']))
    elements.append(divider())

    citations = [
        "12 Statistics Detailing Cost-to-collect Benchmarks by Company Size - Resolve Pay",
        "FDCPA Guidelines for AI Voice Agents in Debt Collection - Smallest.ai",
        "Buy Now, Pay Later: Market trends and consumer impacts - CFPB (2022)",
        "The Debt Collection Market and Selected Policy Issues - Congress.gov",
        "Letter to Afterpay re BNPL - Senate Banking Committee (2025)",
        "Buy Now, Pay Later: Market Impact and Policy Considerations - Richmond Fed (2025)",
        "Consumer Use of Buy Now, Pay Later and Other Unsecured Debt - CFPB (2025)",
        "AI vs Human Agents: Cost Breakdown - Converso",
        "AI vs Live Agent Cost: The Complete 2025 Analysis and Comparison - Teneo.ai",
        "Average Recovery Rates for Collections: Industry Benchmark - Tratta.io",
        "True Cost of Subprime Credit Study - Bankrate",
        "Buy Now Pay Later (BNPL) Market 2025: Size, Growth, Stats & Risks - Chargeflow",
        "Navigating Regulation F With AI - Prodigal",
        "Meeting Debt Collection Compliance With AI-Powered Digital Voice Agents - Skit.ai",
        "Debt collection - Consumer Financial Protection Bureau",
        "AI Debt Collection in the US: Compliance Over Cost - Aiphoria",
        "Is It Legal to Use AI in Debt Collection? What You Need to Know - HealPay",
        "Statute of limitations for and credit reporting of debts - ABI",
        "Metro 2 Format for Credit Reporting - CDIA",
        "Buy Now, Pay Later and Credit Reporting - CFPB",
        "The Power of Data Mapping: Strengthening Compliance and Accuracy in Credit Reporting - BRG",
        "Equifax, Experian, and TransUnion: Changes to Medical Collection Debt Reporting - TransUnion",
        "Removal of public records has little effect on consumers' credit scores - CFPB",
        "How alternative credit data works alongside credit scores - Plaid",
        "Alternative Data in Financial Services - Congress.gov",
        "Understanding and Preventing Credit Trigger Lead Marketing - Sunflower Bank",
        "Rational inattention: a review - European Central Bank",
        "The Behavioral Science Behind Paying Your Debts - The Decision Lab",
        "How Do Individuals Repay Their Debt? The Balance-Matching Heuristic - NBER",
        "To Beat Debt, Consider Starting Small - Kellogg Insight",
        "Gamification in Debt Collection: Wandoo Finance - z3x tech care group",
        "AI Debt Collection for Banks & Lenders - Symend",
        "HI + AI: The key to better debt recovery outcomes - Symend",
        "What 10k Minutes Cost on the Top Voice-AI Platforms in Q3 2025 - Retell AI",
        "AI vs Human Agents: Cost Comparison - Converso",
        "The Hidden Economics of AI Agents: Managing Token Costs and Latency Trade-offs - Stevens",
        "COALESCE: Economic and Security Dynamics of Skill-Based Task Outsourcing - arXiv",
        "Why Horizontal AI Harms Debt Recovery - Symend (E-Book)",
        "Tackling non-performing loans (NPLs) in EU banks' books - European Parliament",
        "Centrifuge, Real-World Asset: Investor Guide - DIA Data",
        "Centrifuge V1 (aka Tinlake) - Centrifuge Docs",
        "Centrifuge RWA - IEEE Transmitter",
        "Centrifuge V2 - Centrifuge Docs",
        "DeFi Weekly: Centrifuge -- Real-World Assets On-Chain - Coinmonks / Medium",
        "Charge-Off and Delinquency Rates on Loans - Federal Reserve Board (2025)",
        "Regulation D -- Rules Governing the Limited Offer and Sale of Securities - SEC",
        "TrueAccord: Company Profile and Funding History - Crunchbase",
        "Symend: Company Profile and Funding History - Crunchbase",
        "InDebted: Company Profile and Funding History - Crunchbase",
        "Prodigal Technologies: Company Profile and Funding History - Crunchbase",
        "Retell AI: Voice AI Platform Pricing and Benchmarks - Retell AI (2025)",
    ]

    for i, cite in enumerate(citations, 1):
        elements.append(Paragraph(f"[{i}] {cite}", s['citation']))

    return elements


def generate_thesis_pdf(output_dir: str = "./output") -> str:
    """Generate the full thesis PDF."""
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    pdf_path = output_path / f"Quannex_Systemic_Thesis_{timestamp}.pdf"

    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=letter,
        rightMargin=65,
        leftMargin=65,
        topMargin=60,
        bottomMargin=40,
    )

    s = create_styles()
    elements = []

    # Build all sections
    elements.extend(build_cover_page(s))
    elements.extend(build_table_of_contents(s))
    elements.extend(build_section_1(s))
    elements.extend(build_section_2(s))
    elements.extend(build_section_3(s))
    elements.extend(build_section_4(s))
    elements.extend(build_section_5(s))
    elements.extend(build_section_6(s))
    elements.extend(build_section_7(s))
    elements.extend(build_section_8(s))
    elements.extend(build_section_9_competitive(s))
    elements.extend(build_section_10_unit_economics(s))
    elements.extend(build_section_11_conclusion(s))
    elements.extend(build_works_cited(s))

    doc.build(elements)
    return str(pdf_path)


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate Quannex Systemic Thesis PDF",
    )
    parser.add_argument(
        "--output", "-o", default="./output",
        help="Output directory (default: ./output)",
    )

    args = parser.parse_args()

    print("=" * 60)
    print("  Quannex SYSTEMIC THESIS PDF GENERATOR")
    print("=" * 60)
    print()
    print("Generating: Systemic Latency: The Structural Incompatibility")
    print("            of Legacy Collections Architectures with")
    print("            High-Velocity Micro-Credit Portfolios")
    print()

    pdf_path = generate_thesis_pdf(args.output)

    print(f"PDF generated: {pdf_path}")
    print()
    print("=" * 60)
    print("  COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
