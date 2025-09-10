import asyncio
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
import json
from io import BytesIO
import base64

try:
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib.colors import HexColor
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.platypus import PageBreak, KeepTogether
    from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

logger = logging.getLogger(__name__)

class PDFGenerator:
    """Generate PDF reports for competitive analysis."""
    
    def __init__(self):
        self.styles = None
        self.custom_styles = {}
        if REPORTLAB_AVAILABLE:
            self._initialize_styles()
    
    def _initialize_styles(self):
        """Initialize PDF styles."""
        self.styles = getSampleStyleSheet()
        
        # Custom styles
        self.custom_styles = {
            'title': ParagraphStyle(
                'CustomTitle',
                parent=self.styles['Title'],
                fontSize=24,
                spaceAfter=30,
                textColor=HexColor('#2C3E50'),
                alignment=TA_CENTER
            ),
            'heading1': ParagraphStyle(
                'CustomHeading1',
                parent=self.styles['Heading1'],
                fontSize=18,
                spaceAfter=12,
                textColor=HexColor('#34495E')
            ),
            'heading2': ParagraphStyle(
                'CustomHeading2',
                parent=self.styles['Heading2'],
                fontSize=14,
                spaceAfter=8,
                textColor=HexColor('#7F8C8D')
            ),
            'body': ParagraphStyle(
                'CustomBody',
                parent=self.styles['Normal'],
                fontSize=10,
                spaceAfter=6,
                alignment=TA_LEFT
            ),
            'summary': ParagraphStyle(
                'CustomSummary',
                parent=self.styles['Normal'],
                fontSize=11,
                spaceAfter=8,
                leftIndent=20,
                rightIndent=20,
                borderColor=HexColor('#BDC3C7'),
                borderWidth=1,
                borderPadding=10
            )
        }
    
    async def generate_report_pdf(self, report_data: Any) -> bytes:
        """Generate PDF report from analysis data."""
        if not REPORTLAB_AVAILABLE:
            logger.error("ReportLab not available. Cannot generate PDF.")
            return self._generate_fallback_pdf(report_data)
        
        logger.info(f"Generating PDF report for {report_data.domain}")
        
        # Create PDF buffer
        buffer = BytesIO()
        
        # Create PDF document
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=18
        )
        
        # Build PDF content
        story = []
        
        # Title page
        story.extend(await self._create_title_page(report_data))
        story.append(PageBreak())
        
        # Executive summary
        story.extend(await self._create_executive_summary(report_data))
        story.append(PageBreak())
        
        # Traffic analysis
        story.extend(await self._create_traffic_section(report_data))
        story.append(PageBreak())
        
        # Keyword analysis
        story.extend(await self._create_keyword_section(report_data))
        story.append(PageBreak())
        
        # Content analysis
        story.extend(await self._create_content_section(report_data))
        story.append(PageBreak())
        
        # Gap analysis
        story.extend(await self._create_gap_section(report_data))
        story.append(PageBreak())
        
        # Recommendations
        story.extend(await self._create_recommendations_section(report_data))
        
        # Build PDF
        doc.build(story)
        
        # Get PDF bytes
        pdf_bytes = buffer.getvalue()
        buffer.close()
        
        logger.info(f"PDF generated successfully ({len(pdf_bytes)} bytes)")
        return pdf_bytes
    
    async def _create_title_page(self, report_data: Any) -> List:
        """Create title page content."""
        content = []
        
        # Main title
        title = f"Competitive Analysis Report<br/>{report_data.domain}"
        content.append(Paragraph(title, self.custom_styles['title']))
        content.append(Spacer(1, 0.5*inch))
        
        # Report details
        details = f"""
        <b>Analysis Date:</b> {report_data.analysis_date.strftime('%B %d, %Y')}<br/>
        <b>Generated by:</b> AI2Flows Competitive Analysis Tool<br/>
        <b>Report ID:</b> {getattr(report_data, 'id', 'N/A')}
        """
        content.append(Paragraph(details, self.custom_styles['body']))
        content.append(Spacer(1, 1*inch))
        
        # Summary stats
        stats_data = [
            ['Metric', 'Value'],
            ['Domain Analyzed', report_data.domain],
            ['Keywords Found', str(len(report_data.keywords))],
            ['Traffic Estimate', f"{report_data.traffic_estimate.get('monthly_organic_traffic', 'N/A'):,}" if report_data.traffic_estimate.get('monthly_organic_traffic') else 'N/A'],
            ['Analysis Confidence', f"{report_data.traffic_estimate.get('confidence_score', 0):.1%}"]
        ]
        
        stats_table = Table(stats_data, colWidths=[2*inch, 3*inch])
        stats_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), HexColor('#34495E')),
            ('TEXTCOLOR', (0, 0), (-1, 0), HexColor('#FFFFFF')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), HexColor('#ECF0F1')),
            ('GRID', (0, 0), (-1, -1), 1, HexColor('#BDC3C7'))
        ]))
        
        content.append(stats_table)
        
        return content
    
    async def _create_executive_summary(self, report_data: Any) -> List:
        """Create executive summary section."""
        content = []
        
        content.append(Paragraph("Executive Summary", self.custom_styles['heading1']))
        
        # Generate summary text
        domain = report_data.domain
        keyword_count = len(report_data.keywords)
        traffic_estimate = report_data.traffic_estimate.get('monthly_organic_traffic', 0)
        
        summary_text = f"""
        This report analyzes the competitive position of <b>{domain}</b> in the digital landscape. 
        Our analysis identified <b>{keyword_count}</b> keywords that the domain ranks for, with an 
        estimated monthly organic traffic of <b>{traffic_estimate:,} visitors</b>.
        <br/><br/>
        The analysis reveals key opportunities for AI2Flows to compete effectively in the workflow 
        automation and business process optimization space. Key findings include content gaps, 
        keyword opportunities, and strategic recommendations for improving market position.
        """
        
        content.append(Paragraph(summary_text, self.custom_styles['summary']))
        content.append(Spacer(1, 0.3*inch))
        
        # Key metrics
        content.append(Paragraph("Key Metrics", self.custom_styles['heading2']))
        
        metrics = [
            f"• Total Keywords Analyzed: {keyword_count}",
            f"• Estimated Monthly Traffic: {traffic_estimate:,}",
            f"• Analysis Confidence: {report_data.traffic_estimate.get('confidence_score', 0):.1%}",
            f"• Top Ranking Position: {min([kw.get('position', 10) for kw in report_data.keywords]) if report_data.keywords else 'N/A'}",
            f"• Content Gaps Identified: {len(report_data.content_gaps.get('missing_topics', []))}"
        ]
        
        for metric in metrics:
            content.append(Paragraph(metric, self.custom_styles['body']))
        
        return content
    
    async def _create_traffic_section(self, report_data: Any) -> List:
        """Create traffic analysis section."""
        content = []
        
        content.append(Paragraph("Traffic Analysis", self.custom_styles['heading1']))
        
        traffic_data = report_data.traffic_estimate
        
        # Traffic overview
        overview_text = f"""
        Based on our analysis using the {traffic_data.get('estimation_method', 'multi-method')} approach, 
        we estimate that <b>{report_data.domain}</b> receives approximately 
        <b>{traffic_data.get('monthly_organic_traffic', 0):,} monthly organic visitors</b>.
        <br/><br/>
        This estimate has a confidence score of <b>{traffic_data.get('confidence_score', 0):.1%}</b>, 
        indicating the reliability of our projection based on available keyword and ranking data.
        """
        
        content.append(Paragraph(overview_text, self.custom_styles['body']))
        content.append(Spacer(1, 0.2*inch))
        
        # Traffic breakdown table
        if 'traffic_breakdown' in traffic_data:
            content.append(Paragraph("Traffic Breakdown by Category", self.custom_styles['heading2']))
            
            breakdown = traffic_data['traffic_breakdown']
            breakdown_data = [
                ['Traffic Category', 'Estimated Monthly Visits', 'Percentage'],
            ]
            
            total_traffic = sum(breakdown.values()) if breakdown.values() else 1
            
            for category, visits in breakdown.items():
                category_name = category.replace('_', ' ').title()
                percentage = (visits / total_traffic) * 100 if total_traffic > 0 else 0
                breakdown_data.append([
                    category_name,
                    f"{visits:,}",
                    f"{percentage:.1f}%"
                ])
            
            breakdown_table = Table(breakdown_data, colWidths=[2*inch, 1.5*inch, 1*inch])
            breakdown_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), HexColor('#3498DB')),
                ('TEXTCOLOR', (0, 0), (-1, 0), HexColor('#FFFFFF')),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), HexColor('#EBF3FD')),
                ('GRID', (0, 0), (-1, -1), 1, HexColor('#BDC3C7'))
            ]))
            
            content.append(breakdown_table)
        
        return content
    
    async def _create_keyword_section(self, report_data: Any) -> List:
        """Create keyword analysis section."""
        content = []
        
        content.append(Paragraph("Keyword Analysis", self.custom_styles['heading1']))
        
        # Top keywords table
        content.append(Paragraph("Top Ranking Keywords", self.custom_styles['heading2']))
        
        keyword_data = [
            ['Keyword', 'Position', 'Search Volume', 'URL']
        ]
        
        top_keywords = sorted(
            report_data.keywords,
            key=lambda x: x.get('position', 999)
        )[:15]
        
        for kw in top_keywords:
            keyword_data.append([
                kw.get('keyword', 'N/A')[:30] + ('...' if len(kw.get('keyword', '')) > 30 else ''),
                str(kw.get('position', 'N/A')),
                f"{kw.get('search_volume', 0):,}" if kw.get('search_volume') else 'N/A',
                kw.get('url', 'N/A')[:40] + ('...' if len(kw.get('url', '')) > 40 else '')
            ])
        
        keyword_table = Table(keyword_data, colWidths=[2*inch, 0.8*inch, 1*inch, 2*inch])
        keyword_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), HexColor('#E74C3C')),
            ('TEXTCOLOR', (0, 0), (-1, 0), HexColor('#FFFFFF')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), HexColor('#FADBD8')),
            ('GRID', (0, 0), (-1, -1), 1, HexColor('#BDC3C7'))
        ]))
        
        content.append(keyword_table)
        
        return content
    
    async def _create_content_section(self, report_data: Any) -> List:
        """Create content analysis section."""
        content = []
        
        content.append(Paragraph("Content Analysis", self.custom_styles['heading1']))
        
        if hasattr(report_data, 'content_summary') and report_data.content_summary:
            summary = report_data.content_summary
            
            # Content overview
            overview_text = f"""
            Analysis of {report_data.domain}'s content reveals insights about their content strategy 
            and approach. The content appears to be primarily 
            <b>{summary.get('content_type', 'mixed')}</b> in nature.
            """
            
            content.append(Paragraph(overview_text, self.custom_styles['body']))
            content.append(Spacer(1, 0.2*inch))
            
            # Content metrics
            if 'word_count' in summary:
                content.append(Paragraph("Content Metrics", self.custom_styles['heading2']))
                
                metrics = [
                    f"• Total Word Count: {summary.get('word_count', 0):,}",
                    f"• Readability Score: {summary.get('readability_score', 0)}/100",
                    f"• Content Type: {summary.get('content_type', 'Unknown')}",
                    f"• Key Topics: {len(summary.get('topics', []))}"
                ]
                
                for metric in metrics:
                    content.append(Paragraph(metric, self.custom_styles['body']))
        
        return content
    
    async def _create_gap_section(self, report_data: Any) -> List:
        """Create gap analysis section."""
        content = []
        
        content.append(Paragraph("Content Gap Analysis", self.custom_styles['heading1']))
        
        gaps = report_data.content_gaps
        
        # Gap summary
        summary_text = gaps.get('gap_analysis_summary', 'No gap analysis summary available.')
        content.append(Paragraph(summary_text, self.custom_styles['summary']))
        content.append(Spacer(1, 0.2*inch))
        
        # Missing topics
        if gaps.get('missing_topics'):
            content.append(Paragraph("Missing Topic Opportunities", self.custom_styles['heading2']))
            
            for topic in gaps['missing_topics'][:10]:
                content.append(Paragraph(f"• {topic}", self.custom_styles['body']))
        
        content.append(Spacer(1, 0.2*inch))
        
        # Opportunity keywords
        if gaps.get('opportunity_keywords'):
            content.append(Paragraph("Keyword Opportunities", self.custom_styles['heading2']))
            
            for keyword in gaps['opportunity_keywords'][:10]:
                content.append(Paragraph(f"• {keyword}", self.custom_styles['body']))
        
        return content
    
    async def _create_recommendations_section(self, report_data: Any) -> List:
        """Create recommendations section."""
        content = []
        
        content.append(Paragraph("Strategic Recommendations", self.custom_styles['heading1']))
        
        # Generate recommendations based on analysis
        recommendations = [
            "Focus on workflow automation content to differentiate from competitors",
            "Target long-tail keywords in the business process optimization space",
            "Create comprehensive guides for identified content gaps",
            "Develop FAQ content to address common workflow automation questions",
            "Implement SEO best practices to improve keyword rankings",
            "Consider paid advertising for high-value commercial keywords",
            "Build authority through thought leadership content in automation",
            "Optimize existing content for better search visibility"
        ]
        
        content.append(Paragraph("Based on our analysis, we recommend the following strategic actions:", self.custom_styles['body']))
        content.append(Spacer(1, 0.1*inch))
        
        for i, rec in enumerate(recommendations, 1):
            content.append(Paragraph(f"{i}. {rec}", self.custom_styles['body']))
        
        return content
    
    def _generate_fallback_pdf(self, report_data: Any) -> bytes:
        """Generate a simple text-based PDF fallback."""
        logger.warning("Generating fallback PDF (ReportLab not available)")
        
        # Create a simple text report
        report_text = f"""
        COMPETITIVE ANALYSIS REPORT
        Domain: {report_data.domain}
        Date: {report_data.analysis_date.strftime('%Y-%m-%d')}
        
        SUMMARY:
        - Keywords analyzed: {len(report_data.keywords)}
        - Traffic estimate: {report_data.traffic_estimate.get('monthly_organic_traffic', 'N/A')}
        - Confidence: {report_data.traffic_estimate.get('confidence_score', 0):.1%}
        
        TOP KEYWORDS:
        """
        
        for i, kw in enumerate(report_data.keywords[:10], 1):
            report_text += f"{i}. {kw.get('keyword', 'N/A')} (Position: {kw.get('position', 'N/A')})\n"
        
        return report_text.encode('utf-8')