from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy import Column, String, Text, DateTime, Integer, Float, JSON
from datetime import datetime, timedelta
import uuid
from config import settings

Base = declarative_base()

class CachedReport(Base):
    """Stored analysis reports."""
    __tablename__ = "cached_reports"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    domain = Column(String, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, default=lambda: datetime.utcnow() + timedelta(days=settings.REPORT_EXPIRY_DAYS))
    
    # Analysis results
    traffic_estimate = Column(JSON)
    keywords = Column(JSON)
    top_pages = Column(JSON)
    content_summary = Column(JSON)
    keyword_clusters = Column(JSON)
    content_gaps = Column(JSON)
    scraped_content = Column(JSON)
    
    # Metadata
    analysis_duration = Column(Float)  # seconds
    keyword_count = Column(Integer)
    page_count = Column(Integer)
    cluster_count = Column(Integer)

class APICache(Base):
    """Cache for external API responses."""
    __tablename__ = "api_cache"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    cache_key = Column(String, unique=True, nullable=False, index=True)
    provider = Column(String, nullable=False)  # 'google_cse', 'serpapi', etc.
    response_data = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, default=lambda: datetime.utcnow() + timedelta(hours=settings.CACHE_EXPIRY_HOURS))

class AnalyticsEvent(Base):
    """Basic analytics tracking."""
    __tablename__ = "analytics_events"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    event_type = Column(String, nullable=False)  # 'analysis_started', 'report_viewed', etc.
    domain = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)
    metadata = Column(JSON)

# Database engine and session
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    future=True
)

AsyncSessionLocal = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

async def init_db():
    """Initialize database tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def get_db() -> AsyncSession:
    """Dependency to get database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

async def cleanup_expired_data():
    """Clean up expired cache entries and reports."""
    async with AsyncSessionLocal() as session:
        now = datetime.utcnow()
        
        # Clean expired reports
        await session.execute(
            "DELETE FROM cached_reports WHERE expires_at < :now",
            {"now": now}
        )
        
        # Clean expired cache entries
        await session.execute(
            "DELETE FROM api_cache WHERE expires_at < :now",
            {"now": now}
        )
        
        await session.commit()