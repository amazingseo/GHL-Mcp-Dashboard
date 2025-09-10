from pydantic import BaseModel, Field, validator
from typing import List, Dict, Any, Optional
from datetime import datetime
from enum import Enum

class AnalysisRequest(BaseModel):
    """Request model for domain analysis"""
    domain: str = Field(..., min_length=3, max_length=255)
    include_content_gap: bool = Field(default=True)
    include_clustering: bool = Field(default=True)
    max_keywords: int = Field(default=50, ge=10, le=200)
    
    @validator('domain')
    def validate_domain(cls, v):
        # Remove protocol if present
        v = v.replace('https://', '').replace('http://', '')
        # Remove trailing slash
        v = v.rstrip('/')
        # Basic domain validation
        if not v or '.' not in v:
            raise ValueError('Invalid domain format')
        return v.lower()

class SearchIntent(str, Enum):
    """Search intent categories"""
    INFORMATIONAL = "informational"
    COMMERCIAL = "commercial"
    TRANSACTIONAL = "transactional"
    NAVIGATIONAL = "navigational"

class KeywordData(BaseModel):
    """Individual keyword information"""
    keyword: str
    position: Optional[int] = None
    search_volume: Optional[int] = None
    cpc: Optional[float] = None
    competition: Optional[float] = None
    intent: Optional[SearchIntent] = None
    url: Optional[str] = None

class TopicCluster(BaseModel):
    """Topic cluster information"""
    cluster_id: int
    topic_name: str
    keywords: List[str]
    keyword_count: int
    avg_search_volume: Optional[int] = None
    dominant_intent: Optional[SearchIntent] = None

class ContentGap(BaseModel):
    """Content gap analysis result"""
    missing_topics: List[str]
    opportunity_keywords: List[str]
    suggested_content: List[str]
    faq_questions: List[str]

class TrafficEstimate(BaseModel):
    """Traffic estimation data"""
    monthly_organic_traffic: Optional[int] = None
    confidence_score: float = Field(ge=0.0, le=1.0)
    estimation_method: str
    traffic_sources: Dict[str, int] = Field(default_factory=dict)

class CompetitorAnalysis(BaseModel):
    """Complete competitor analysis result"""
    domain: str
    analysis_date: datetime
    keywords: List[KeywordData]
    topic_clusters: List[TopicCluster]
    content_gaps: ContentGap
    traffic_estimate: TrafficEstimate
    top_pages: List[Dict[str, Any]] = Field(default_factory=list)
    people_also_ask: List[str] = Field(default_factory=list)
    analysis_summary: str = ""

class ReportResponse(BaseModel):
    """API response for analysis reports"""
    report_id: str
    domain: str
    status: str
    created_at: datetime
    expires_at: datetime
    report_url: str
    data: Optional[CompetitorAnalysis] = None

class AnalysisStatus(BaseModel):
    """Analysis status response"""
    report_id: str
    status: str
    progress: int = Field(ge=0, le=100)
    message: str = ""
    estimated_completion: Optional[datetime] = None