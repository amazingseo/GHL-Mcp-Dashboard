from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    """Application configuration."""

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./competitive_analysis.db"

    # API Keys
    GOOGLE_CSE_API_KEY: Optional[str] = None
    GOOGLE_CSE_CX: Optional[str] = None
    SERPAPI_KEY: Optional[str] = None

    # Rate Limiting
    REQUESTS_PER_SECOND: float = 1.0
    MAX_CONCURRENT_REQUESTS: int = 5

    # Scraping
    USER_AGENT: str = "CompetitiveAnalyzer/1.0 (+https://ai2flows.com/contact)"
    REQUEST_TIMEOUT: int = 30
    MAX_PAGES_PER_DOMAIN: int = 20

    # Caching
    CACHE_EXPIRY_HOURS: int = 24
    MAX_CACHE_SIZE: int = 1000

    # Analysis
    MAX_KEYWORDS_TO_ANALYZE: int = 100
    MIN_CLUSTER_SIZE: int = 3
    MAX_CLUSTERS: int = 15

    # Reports
    REPORT_EXPIRY_DAYS: int = 30
    MAX_REPORTS_PER_USER: int = 50

    # PDF Generation
    PDF_TIMEOUT: int = 60
    INCLUDE_CHARTS_IN_PDF: bool = True

    # AI2Flows Topics (updated to match repo file)
    SEED_TOPICS_FILE: str = "config_seed_topics.txt"

    # Pydantic v2 settings config
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )


# Global settings instance
settings = Settings()


# Load seed topics
def load_seed_topics():
    """Load ai2flows.com seed topics from file."""
    try:
        with open(settings.SEED_TOPICS_FILE, "r", encoding="utf-8") as f:
            topics = [line.strip() for line in f if line.strip()]
        return topics
    except FileNotFoundError:
        # Default topics if file not found
        return [
            "automated workflows",
            "business automation",
            "workflow optimization",
            "process automation",
            "digital transformation",
            "productivity tools",
            "automation software",
            "workflow management",
            "business process improvement",
            "task automation",
            "workflow templates",
            "automation solutions",
            "workflow design",
            "process optimization",
            "business efficiency",
        ]


# Cache for seed topics
SEED_TOPICS = load_seed_topics()