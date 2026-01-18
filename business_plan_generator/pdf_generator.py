"""
Business Plan PDF Generator

Generates professional PDF documents from BusinessPlan objects.
"""

from typing import List, Optional
from datetime import datetime
from decimal import Decimal
import io

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.colors import HexColor
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, KeepTogether, Image,
)
from reportlab.platypus.flowables import HRFlowable

from business_plan_generator.models import BusinessPlan


class PDFGenerator:
    """
    Generates professional PDF business plans.
    """

    def __init__(self, plan: BusinessPlan):
        self.plan = plan

        # Brand colors
        if plan.company:
            self.primary_color = HexColor(plan.company.primary_color)
            self.secondary_color = HexColor(plan.company.secondary_color)
        else:
            self.primary_color = HexColor("#6B46FF")
            self.secondary_color = HexColor("#00D4FF")

        self.dark_color = HexColor("#0A0B1E")
        self.gray_color = HexColor("#6B7280")

        # Initialize styles
        self._init_styles()

    def _init_styles(self):
        """Initialize paragraph styles"""
        self.styles = getSampleStyleSheet()

        self.title_style = ParagraphStyle(
            'CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=28,
            textColor=self.primary_color,
            spaceAfter=30,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        )

        self.subtitle_style = ParagraphStyle(
            'CustomSubtitle',
            parent=self.styles['Normal'],
            fontSize=16,
            textColor=self.dark_color,
            spaceAfter=20,
            alignment=TA_CENTER,
            fontName='Helvetica'
        )

        self.heading_style = ParagraphStyle(
            'CustomHeading',
            parent=self.styles['Heading2'],
            fontSize=18,
            textColor=self.primary_color,
            spaceAfter=12,
            spaceBefore=20,
            fontName='Helvetica-Bold'
        )

        self.subheading_style = ParagraphStyle(
            'CustomSubheading',
            parent=self.styles['Heading3'],
            fontSize=14,
            textColor=self.dark_color,
            spaceAfter=8,
            spaceBefore=12,
            fontName='Helvetica-Bold'
        )

        self.body_style = ParagraphStyle(
            'CustomBody',
            parent=self.styles['Normal'],
            fontSize=11,
            textColor=self.dark_color,
            spaceAfter=8,
            alignment=TA_JUSTIFY,
            leading=14
        )

        self.bullet_style = ParagraphStyle(
            'BulletStyle',
            parent=self.body_style,
            leftIndent=20,
            bulletIndent=10
        )

    def generate(self, output_path: str) -> str:
        """
        Generate PDF and save to file.

        Returns:
            Path to generated PDF
        """
        doc = SimpleDocTemplate(
            output_path,
            pagesize=letter,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=40
        )

        elements = []

        # Build sections
        elements.extend(self._build_cover_page())
        elements.extend(self._build_executive_summary())
        elements.extend(self._build_problem())
        elements.extend(self._build_solution())
        elements.extend(self._build_market())
        elements.extend(self._build_competition())
        elements.extend(self._build_business_model())
        elements.extend(self._build_financials())
        elements.extend(self._build_gtm())
        elements.extend(self._build_team())
        elements.extend(self._build_funding())
        elements.extend(self._build_risks())
        elements.extend(self._build_exit())
        elements.extend(self._build_contact())

        doc.build(elements)

        return output_path

    def _build_cover_page(self) -> List:
        """Build cover page"""
        elements = []

        if not self.plan.company:
            return elements

        company = self.plan.company

        elements.append(Spacer(1, 2*inch))
        elements.append(Paragraph(company.name, self.title_style))
        elements.append(Paragraph(company.tagline, self.subtitle_style))
        elements.append(Spacer(1, 0.5*inch))

        # Company info table
        info_data = [
            ["Founder & CEO:", company.founder_name or "TBD"],
            ["Industry:", company.industry.value],
            ["Stage:", company.stage.value.replace("_", " ").title()],
            ["Contact:", company.founder_email or ""],
        ]

        if company.website:
            info_data.append(["Website:", company.website])

        info_table = Table(info_data, colWidths=[2*inch, 3*inch])
        info_table.setStyle(TableStyle([
            ('TEXTCOLOR', (0, 0), (0, -1), self.primary_color),
            ('TEXTCOLOR', (1, 0), (1, -1), self.dark_color),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ]))

        elements.append(Spacer(1, 1*inch))
        elements.append(info_table)
        elements.append(Spacer(1, 1.5*inch))

        # Confidential notice
        elements.append(Paragraph(
            f"Confidential Business Plan - {datetime.now().strftime('%B %Y')}",
            ParagraphStyle('Footer', parent=self.body_style, fontSize=9,
                          textColor=self.gray_color, alignment=TA_CENTER)
        ))

        elements.append(PageBreak())

        return elements

    def _build_executive_summary(self) -> List:
        """Build executive summary"""
        elements = []

        elements.append(Paragraph("Executive Summary", self.heading_style))
        elements.append(self._divider())

        if self.plan.executive_summary:
            # Parse markdown-like formatting
            text = self.plan.executive_summary
            text = text.replace("**", "<b>").replace("**", "</b>")
            elements.append(Paragraph(text, self.body_style))
        elif self.plan.company:
            elements.append(Paragraph(
                self.plan.company.description,
                self.body_style
            ))

        elements.append(PageBreak())
        return elements

    def _build_problem(self) -> List:
        """Build problem section"""
        elements = []

        if not self.plan.problem:
            return elements

        problem = self.plan.problem

        elements.append(Paragraph("The Problem", self.heading_style))
        elements.append(self._divider())

        elements.append(Paragraph(f"<b>{problem.headline}</b>", self.body_style))
        elements.append(Spacer(1, 0.2*inch))
        elements.append(Paragraph(problem.description, self.body_style))

        # Pain points
        if problem.pain_points:
            elements.append(Paragraph("<b>Key Pain Points:</b>", self.subheading_style))
            for point in problem.pain_points:
                elements.append(Paragraph(f"• {point}", self.bullet_style))

        # Market impact
        if problem.market_impact:
            elements.append(Spacer(1, 0.2*inch))
            elements.append(Paragraph(
                f"<b>Market Impact:</b> {problem.market_impact}",
                self.body_style
            ))

        elements.append(PageBreak())
        return elements

    def _build_solution(self) -> List:
        """Build solution section"""
        elements = []

        if not self.plan.solution:
            return elements

        solution = self.plan.solution

        elements.append(Paragraph("Our Solution", self.heading_style))
        elements.append(self._divider())

        elements.append(Paragraph(f"<b>{solution.headline}</b>", self.body_style))
        elements.append(Spacer(1, 0.2*inch))
        elements.append(Paragraph(solution.description, self.body_style))

        # Key features
        if solution.key_features:
            elements.append(Paragraph("<b>Key Features:</b>", self.subheading_style))
            for feature in solution.key_features:
                elements.append(Paragraph(f"• {feature}", self.bullet_style))

        # Differentiators
        if solution.differentiators:
            elements.append(Paragraph("<b>What Makes Us Different:</b>", self.subheading_style))
            for diff in solution.differentiators:
                elements.append(Paragraph(f"• {diff}", self.bullet_style))

        # Technology
        if solution.technology:
            elements.append(Paragraph("<b>Core Technology:</b>", self.subheading_style))
            for tech in solution.technology:
                elements.append(Paragraph(f"• {tech}", self.bullet_style))

        elements.append(PageBreak())
        return elements

    def _build_market(self) -> List:
        """Build market analysis section"""
        elements = []

        if not self.plan.market:
            return elements

        market = self.plan.market

        elements.append(Paragraph("Market Opportunity", self.heading_style))
        elements.append(self._divider())

        # TAM/SAM/SOM table
        market_data = [
            ["Market", "Size", "Description"],
            ["TAM", f"${market.tam}B", market.tam_description],
            ["SAM", f"${market.sam}B", market.sam_description],
            ["SOM", f"${market.som}B", market.som_description],
        ]

        market_table = Table(market_data, colWidths=[1*inch, 1*inch, 4*inch])
        market_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), self.primary_color),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('GRID', (0, 0), (-1, -1), 0.5, self.gray_color),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, HexColor('#F3F4F6')]),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
        ]))

        elements.append(market_table)
        elements.append(Spacer(1, 0.3*inch))

        # Market segments
        if market.segments:
            elements.append(Paragraph("<b>Market Segments:</b>", self.subheading_style))

            seg_data = [["Segment", "Size", "Growth", "Description"]]
            for seg in market.segments:
                seg_data.append([
                    seg.name,
                    f"${seg.size_billions}B",
                    f"{seg.growth_rate}%",
                    seg.description[:50] + "..." if len(seg.description) > 50 else seg.description
                ])

            seg_table = Table(seg_data, colWidths=[1.5*inch, 0.8*inch, 0.8*inch, 3*inch])
            seg_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), self.primary_color),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('GRID', (0, 0), (-1, -1), 0.5, self.gray_color),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, HexColor('#F3F4F6')]),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ]))

            elements.append(seg_table)

        # Key statistics
        if market.key_statistics:
            elements.append(Spacer(1, 0.3*inch))
            elements.append(Paragraph("<b>Market Validation:</b>", self.subheading_style))
            for stat, value in market.key_statistics.items():
                elements.append(Paragraph(f"• <b>{stat}:</b> {value}", self.bullet_style))

        elements.append(PageBreak())
        return elements

    def _build_competition(self) -> List:
        """Build competitive analysis section"""
        elements = []

        if not self.plan.competition:
            return elements

        comp = self.plan.competition

        elements.append(Paragraph("Competitive Analysis", self.heading_style))
        elements.append(self._divider())

        # Competitors table
        if comp.direct_competitors:
            comp_data = [["Competitor", "Position", "Why We Win"]]
            for c in comp.direct_competitors:
                comp_data.append([c.name, c.market_position, c.why_we_win[:60]])

            comp_table = Table(comp_data, colWidths=[1.5*inch, 1.2*inch, 3.3*inch])
            comp_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), self.primary_color),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('GRID', (0, 0), (-1, -1), 0.5, self.gray_color),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ]))

            elements.append(comp_table)

        # Competitive advantages
        if comp.competitive_advantages:
            elements.append(Spacer(1, 0.3*inch))
            elements.append(Paragraph("<b>Competitive Advantages:</b>", self.subheading_style))
            for adv in comp.competitive_advantages:
                elements.append(Paragraph(f"• {adv}", self.bullet_style))

        # Moats
        if comp.moats:
            elements.append(Paragraph("<b>Defensible Moats:</b>", self.subheading_style))
            for moat in comp.moats:
                elements.append(Paragraph(f"• {moat}", self.bullet_style))

        elements.append(PageBreak())
        return elements

    def _build_business_model(self) -> List:
        """Build business model section"""
        elements = []

        if not self.plan.business_model:
            return elements

        bm = self.plan.business_model

        elements.append(Paragraph("Business Model", self.heading_style))
        elements.append(self._divider())

        elements.append(Paragraph(
            f"<b>Revenue Model:</b> {bm.revenue_model.value}",
            self.body_style
        ))

        # Revenue streams
        if bm.revenue_streams:
            elements.append(Paragraph("<b>Revenue Streams:</b>", self.subheading_style))

            stream_data = [["Stream", "% Revenue", "Pricing"]]
            for stream in bm.revenue_streams:
                stream_data.append([
                    stream.name,
                    f"{stream.percentage_of_total}%",
                    stream.pricing
                ])

            stream_table = Table(stream_data, colWidths=[2*inch, 1*inch, 3*inch])
            stream_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), self.primary_color),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('GRID', (0, 0), (-1, -1), 0.5, self.gray_color),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ]))

            elements.append(stream_table)

        # Unit economics
        if bm.unit_economics:
            elements.append(Spacer(1, 0.3*inch))
            elements.append(Paragraph("<b>Unit Economics:</b>", self.subheading_style))

            for metric, value in bm.unit_economics.items():
                formatted = metric.upper().replace("_", " ")
                if isinstance(value, (int, float)):
                    if "margin" in metric or "churn" in metric:
                        value = f"{value}%"
                    else:
                        value = f"${value:,.0f}"
                elements.append(Paragraph(f"• {formatted}: {value}", self.bullet_style))

        elements.append(PageBreak())
        return elements

    def _build_financials(self) -> List:
        """Build financial projections section"""
        elements = []

        if not self.plan.financials or not self.plan.financials.projections:
            return elements

        fin = self.plan.financials

        elements.append(Paragraph("Financial Projections", self.heading_style))
        elements.append(self._divider())

        # 5-year table
        headers = ["Metric"] + [f"Year {p.year}" for p in fin.projections]

        rows = [headers]

        # Revenue row
        revenue_row = ["Revenue"]
        for p in fin.projections:
            revenue_row.append(self._format_currency(p.revenue))
        rows.append(revenue_row)

        # EBITDA row
        ebitda_row = ["EBITDA"]
        for p in fin.projections:
            ebitda_row.append(self._format_currency(p.ebitda))
        rows.append(ebitda_row)

        # EBITDA Margin row
        margin_row = ["EBITDA Margin"]
        for p in fin.projections:
            margin = float(p.ebitda) / float(p.revenue) * 100 if p.revenue else 0
            margin_row.append(f"{margin:.0f}%")
        rows.append(margin_row)

        # Employees row
        emp_row = ["Employees"]
        for p in fin.projections:
            emp_row.append(str(p.employees))
        rows.append(emp_row)

        # Customers row
        cust_row = ["Customers"]
        for p in fin.projections:
            cust_row.append(f"{p.customers:,}")
        rows.append(cust_row)

        col_widths = [1.3*inch] + [1*inch] * len(fin.projections)
        fin_table = Table(rows, colWidths=col_widths)
        fin_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), self.primary_color),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
            ('GRID', (0, 0), (-1, -1), 0.5, self.gray_color),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, HexColor('#F3F4F6')]),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ]))

        elements.append(fin_table)

        # Assumptions
        if fin.assumptions:
            elements.append(Spacer(1, 0.3*inch))
            elements.append(Paragraph("<b>Key Assumptions:</b>", self.subheading_style))
            for assumption in fin.assumptions:
                elements.append(Paragraph(f"• {assumption}", self.bullet_style))

        elements.append(PageBreak())
        return elements

    def _build_gtm(self) -> List:
        """Build go-to-market section"""
        elements = []

        if not self.plan.gtm:
            return elements

        gtm = self.plan.gtm

        elements.append(Paragraph("Go-to-Market Strategy", self.heading_style))
        elements.append(self._divider())

        for phase in gtm.phases:
            elements.append(Paragraph(
                f"<b>{phase.name}</b> ({phase.timeline})",
                self.subheading_style
            ))

            if phase.target_customers:
                elements.append(Paragraph("Target Customers:", self.body_style))
                for cust in phase.target_customers:
                    elements.append(Paragraph(f"• {cust}", self.bullet_style))

            if phase.strategies:
                elements.append(Paragraph("Strategies:", self.body_style))
                for strat in phase.strategies:
                    elements.append(Paragraph(f"• {strat}", self.bullet_style))

            if phase.milestones:
                elements.append(Paragraph("Milestones:", self.body_style))
                for mile in phase.milestones:
                    elements.append(Paragraph(f"• {mile}", self.bullet_style))

        # Value propositions
        if gtm.key_value_propositions:
            elements.append(Spacer(1, 0.3*inch))
            elements.append(Paragraph("<b>Key Value Propositions:</b>", self.subheading_style))
            for prop in gtm.key_value_propositions:
                elements.append(Paragraph(f"• \"{prop}\"", self.bullet_style))

        elements.append(PageBreak())
        return elements

    def _build_team(self) -> List:
        """Build team section"""
        elements = []

        if not self.plan.team:
            return elements

        team = self.plan.team

        elements.append(Paragraph("Team", self.heading_style))
        elements.append(self._divider())

        # Founders
        if team.founders:
            elements.append(Paragraph("<b>Leadership:</b>", self.subheading_style))
            for founder in team.founders:
                elements.append(Paragraph(
                    f"<b>{founder.name}</b> - {founder.title}",
                    self.body_style
                ))
                elements.append(Paragraph(founder.bio, self.body_style))

        # Open positions
        if team.open_positions:
            elements.append(Spacer(1, 0.3*inch))
            elements.append(Paragraph("<b>Key Hires Needed:</b>", self.subheading_style))

            pos_data = [["Position", "Priority", "Timeline"]]
            for pos in team.open_positions:
                pos_data.append([pos.title, pos.priority, pos.timeline])

            pos_table = Table(pos_data, colWidths=[3*inch, 1.5*inch, 1.5*inch])
            pos_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), self.primary_color),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('GRID', (0, 0), (-1, -1), 0.5, self.gray_color),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ]))

            elements.append(pos_table)

        elements.append(PageBreak())
        return elements

    def _build_funding(self) -> List:
        """Build funding section"""
        elements = []

        if not self.plan.funding:
            return elements

        funding = self.plan.funding

        elements.append(Paragraph("Investment Opportunity", self.heading_style))
        elements.append(self._divider())

        # Current round
        curr = funding.current_round
        elements.append(Paragraph(
            f"<b>Current Round: {curr.round_name}</b>",
            self.subheading_style
        ))
        elements.append(Paragraph(
            f"Raising: ${float(curr.amount):,.0f}",
            self.body_style
        ))

        if curr.use_of_funds:
            elements.append(Paragraph("Use of Funds:", self.body_style))
            for use in curr.use_of_funds:
                elements.append(Paragraph(f"• {use}", self.bullet_style))

        if curr.milestones:
            elements.append(Paragraph("Milestones:", self.body_style))
            for mile in curr.milestones:
                elements.append(Paragraph(f"• {mile}", self.bullet_style))

        # Future rounds
        if funding.future_rounds:
            elements.append(Spacer(1, 0.3*inch))
            elements.append(Paragraph("<b>Funding Roadmap:</b>", self.subheading_style))

            round_data = [["Round", "Amount", "Timing"]]
            round_data.append([curr.round_name, self._format_currency(curr.amount), curr.timing])

            for fr in funding.future_rounds:
                round_data.append([fr.round_name, self._format_currency(fr.amount), fr.timing])

            round_table = Table(round_data, colWidths=[2*inch, 2*inch, 2*inch])
            round_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), self.primary_color),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('GRID', (0, 0), (-1, -1), 0.5, self.gray_color),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ]))

            elements.append(round_table)

        elements.append(PageBreak())
        return elements

    def _build_risks(self) -> List:
        """Build risk analysis section"""
        elements = []

        if not self.plan.risks or not self.plan.risks.risks:
            return elements

        elements.append(Paragraph("Risk Analysis", self.heading_style))
        elements.append(self._divider())

        risk_data = [["Category", "Risk", "Prob", "Impact", "Mitigation"]]
        for risk in self.plan.risks.risks:
            risk_data.append([
                risk.category,
                risk.description[:30] + "..." if len(risk.description) > 30 else risk.description,
                risk.probability,
                risk.impact,
                risk.mitigation[:30] + "..." if len(risk.mitigation) > 30 else risk.mitigation,
            ])

        risk_table = Table(risk_data, colWidths=[1*inch, 1.3*inch, 0.6*inch, 0.6*inch, 2.5*inch])
        risk_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), self.primary_color),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, self.gray_color),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))

        elements.append(risk_table)
        elements.append(PageBreak())
        return elements

    def _build_exit(self) -> List:
        """Build exit strategy section"""
        elements = []

        if not self.plan.exit_strategy or not self.plan.exit_strategy.scenarios:
            return elements

        elements.append(Paragraph("Exit Strategy", self.heading_style))
        elements.append(self._divider())

        for scenario in self.plan.exit_strategy.scenarios:
            elements.append(Paragraph(
                f"<b>{scenario.type}</b> ({scenario.probability:.0%} probability)",
                self.subheading_style
            ))
            elements.append(Paragraph(f"Timeline: {scenario.timeline}", self.body_style))
            elements.append(Paragraph(f"Valuation Range: {scenario.valuation_range}", self.body_style))

            if scenario.potential_acquirers:
                elements.append(Paragraph("Potential Acquirers:", self.body_style))
                for acq in scenario.potential_acquirers:
                    elements.append(Paragraph(f"• {acq}", self.bullet_style))

        elements.append(PageBreak())
        return elements

    def _build_contact(self) -> List:
        """Build contact page"""
        elements = []

        if not self.plan.company:
            return elements

        company = self.plan.company

        elements.append(Spacer(1, 2*inch))
        elements.append(Paragraph("Contact", self.heading_style))
        elements.append(self._divider())

        contact_style = ParagraphStyle(
            'Contact',
            parent=self.body_style,
            fontSize=14,
            alignment=TA_CENTER,
            spaceAfter=12
        )

        elements.append(Spacer(1, 0.5*inch))
        elements.append(Paragraph(f"<b>{company.name}</b>", contact_style))
        elements.append(Paragraph(company.tagline, contact_style))
        elements.append(Spacer(1, 0.5*inch))

        if company.founder_name:
            elements.append(Paragraph(f"<b>{company.founder_name}</b>", contact_style))
            elements.append(Paragraph(company.founder_title, contact_style))

        if company.founder_email:
            elements.append(Paragraph(f"Email: {company.founder_email}", contact_style))

        if company.website:
            elements.append(Paragraph(f"Website: {company.website}", contact_style))

        return elements

    def _divider(self) -> HRFlowable:
        """Create section divider"""
        return HRFlowable(
            width="100%",
            thickness=2,
            color=self.primary_color,
            spaceBefore=2,
            spaceAfter=12
        )

    def _format_currency(self, amount: Decimal) -> str:
        """Format currency for display"""
        num = float(amount)
        if num >= 1_000_000_000:
            return f"${num/1_000_000_000:.1f}B"
        elif num >= 1_000_000:
            return f"${num/1_000_000:.1f}M"
        elif num >= 1_000:
            return f"${num/1_000:.0f}K"
        else:
            return f"${num:,.0f}"
