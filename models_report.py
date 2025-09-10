import asyncio
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import json
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
import uuid

from models_db import CachedReport
from models_schemas import CompetitorAnalysis, ReportResponse

logger = logging.getLogger(__name__)

class CompetitorReport:
    """Data class for competitor analysis report."""
    
    def __init__(
        self,
        domain: str,
        analysis_date: datetime,
        traffic_estimate: Dict[str, Any],
        keywords: List[Dict[str, Any]],
        top_pages: List[Dict[str, Any]],
        content_summary: Dict[str, Any],
        keyword_clusters: Dict[str, Any],
        content_gaps: Dict[str, Any],
        scraped_content: Dict[str, Any]
    ):
        self.id = str(uuid.uuid4())
        self.domain = domain
        self.analysis_date = analysis_date
        self.traffic_estimate = traffic_estimate
        self.keywords = keywords
        self.top_pages = top_pages
        self.content_summary = content_summary
        self.keyword_clusters = keyword_clusters
        self.content_gaps = content_gaps
        self.scraped_content = scraped_content

class ReportRepository:
    """Repository for managing analysis reports."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create_report(self, report_data: CompetitorReport) -> CachedReport:
        """Save analysis report to database."""
        try:
            # Calculate metadata
            analysis_duration = 0.0  # Would be calculated from actual timing
            keyword_count = len(report_data.keywords)
            page_count = len(report_data.top_pages)
            cluster_count = len(report_data.keyword_clusters.get('clusters', []))
            
            # Create database record
            cached_report = CachedReport(
                id=report_data.id,
                domain=report_data.domain,
                created_at=report_data.analysis_date,
                traffic_estimate=report_data.traffic_estimate,
                keywords=report_data.keywords,
                top_pages=report_data.top_pages,
                content_summary=report_data.content_summary,
                keyword_clusters=report_data.keyword_clusters,
                content_gaps=report_data.content_gaps,
                scraped_content=report_data.scraped_content,
                analysis_duration=analysis_duration,
                keyword_count=keyword_count,
                page_count=page_count,
                cluster_count=cluster_count
            )
            
            self.db.add(cached_report)
            await self.db.commit()
            await self.db.refresh(cached_report)
            
            logger.info(f"Report saved: {cached_report.id} for domain {cached_report.domain}")
            return cached_report
            
        except Exception as e:
            logger.error(f"Failed to save report: {str(e)}")
            await self.db.rollback()
            raise
    
    async def get_report(self, report_id: str) -> Optional[CachedReport]:
        """Retrieve analysis report by ID."""
        try:
            result = await self.db.execute(
                select(CachedReport).where(CachedReport.id == report_id)
            )
            report = result.scalar_one_or_none()
            
            if report and report.expires_at < datetime.utcnow():
                # Report has expired
                await self.delete_report(report_id)
                return None
            
            return report
            
        except Exception as e:
            logger.error(f"Failed to retrieve report {report_id}: {str(e)}")
            return None
    
    async def get_reports_by_domain(
        self, 
        domain: str, 
        limit: int = 10
    ) -> List[CachedReport]:
        """Get recent reports for a domain."""
        try:
            result = await self.db.execute(
                select(CachedReport)
                .where(CachedReport.domain == domain)
                .where(CachedReport.expires_at > datetime.utcnow())
                .order_by(CachedReport.created_at.desc())
                .limit(limit)
            )
            
            return result.scalars().all()
            
        except Exception as e:
            logger.error(f"Failed to retrieve reports for domain {domain}: {str(e)}")
            return []
    
    async def delete_report(self, report_id: str) -> bool:
        """Delete analysis report."""
        try:
            result = await self.db.execute(
                delete(CachedReport).where(CachedReport.id == report_id)
            )
            await self.db.commit()
            
            return result.rowcount > 0
            
        except Exception as e:
            logger.error(f"Failed to delete report {report_id}: {str(e)}")
            await self.db.rollback()
            return False
    
    async def cleanup_expired_reports(self) -> int:
        """Clean up expired reports."""
        try:
            result = await self.db.execute(
                delete(CachedReport).where(CachedReport.expires_at < datetime.utcnow())
            )
            await self.db.commit()
            
            deleted_count = result.rowcount
            logger.info(f"Cleaned up {deleted_count} expired reports")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Failed to cleanup expired reports: {str(e)}")
            await self.db.rollback()
            return 0
    
    async def get_report_statistics(self) -> Dict[str, Any]:
        """Get statistics about stored reports."""
        try:
            # Total reports
            total_result = await self.db.execute(
                select(CachedReport.id).where(CachedReport.expires_at > datetime.utcnow())
            )
            total_reports = len(total_result.scalars().all())
            
            # Reports by domain
            domain_result = await self.db.execute(
                select(CachedReport.domain, CachedReport.id)
                .where(CachedReport.expires_at > datetime.utcnow())
            )
            
            domains = {}
            for domain, report_id in domain_result:
                domains[domain] = domains.get(domain, 0) + 1
            
            # Recent activity (last 7 days)
            week_ago = datetime.utcnow() - timedelta(days=7)
            recent_result = await self.db.execute(
                select(CachedReport.id)
                .where(CachedReport.created_at > week_ago)
                .where(CachedReport.expires_at > datetime.utcnow())
            )
            recent_reports = len(recent_result.scalars().all())
            
            return {
                'total_reports': total_reports,
                'domains_analyzed': len(domains),
                'reports_by_domain': domains,
                'recent_reports_7d': recent_reports
            }
            
        except Exception as e:
            logger.error(f"Failed to get report statistics: {str(e)}")
            return {
                'total_reports': 0,
                'domains_analyzed': 0,
                'reports_by_domain': {},
                'recent_reports_7d': 0
            }

    def to_competitor_analysis(self, cached_report: CachedReport) -> CompetitorAnalysis:
        """Convert cached report to CompetitorAnalysis model."""
        return CompetitorAnalysis(
            domain=cached_report.domain,
            analysis_date=cached_report.created_at,
            keywords=[],  # Would need to convert from JSON
            topic_clusters=[],  # Would need to convert from JSON
            content_gaps=cached_report.content_gaps or {},
            traffic_estimate=cached_report.traffic_estimate or {},
            top_pages=cached_report.top_pages or [],
            analysis_summary=self._generate_analysis_summary(cached_report)
        )
    
    def _generate_analysis_summary(self, report: CachedReport) -> str:
        """Generate analysis summary from report data."""
        summary_parts = []
        
        summary_parts.append(f"Analysis of {report.domain} completed on {report.created_at.strftime('%B %d, %Y')}.")
        
        if report.keyword_count:
            summary_parts.append(f"Found {report.keyword_count} ranking keywords.")
        
        if report.traffic_estimate and report.traffic_estimate.get('monthly_organic_traffic'):
            traffic = report.traffic_estimate['monthly_organic_traffic']
            summary_parts.append(f"Estimated monthly organic traffic: {traffic:,} visitors.")
        
        if report.cluster_count:
            summary_parts.append(f"Keywords grouped into {report.cluster_count} topic clusters.")
        
        return ' '.join(summary_parts)