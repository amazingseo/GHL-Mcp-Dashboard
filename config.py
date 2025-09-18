import os
import logging

logger = logging.getLogger(__name__)

# Load seed topics from file or define inline
SEED_TOPICS = [
    "automated workflows", "business automation", "workflow optimization",
    "process automation", "digital transformation", "productivity tools",
    "automation software", "workflow management", "business process improvement",
    "task automation", "workflow templates", "automation solutions",
    "workflow design", "process optimization", "business efficiency",
    "robotic process automation", "workflow integration", "business process automation",
    "automated reporting", "workflow orchestration", "intelligent automation",
    "process digitization", "workflow analytics", "automation consulting",
    "business process redesign"
]

class Settings:
    """Environment-backed settings - Railway compatible."""
    
    def __init__(self) -> None:
        logger.info("=== RAILWAY VARIABLE LOADING ===")
        
        # Basic app settings
        self.JWT_SECRET = os.getenv("JWT_SECRET", "change-me")
        self.WINDOW_DAYS = int(os.getenv("WINDOW_DAYS", "30"))
        self.MAX_FREE = int(os.getenv("MAX_FREE", "6"))
        self.REQUESTS_PER_MINUTE = int(os.getenv("REQUESTS_PER_MINUTE", "30"))
        
        # GHL Settings
        self.GHL_API_KEY = os.getenv("GHL_API_KEY")
        self.GHL_LOCATION_ID = os.getenv("GHL_LOCATION_ID")
        
        # Google Settings
        self.GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
        self.GOOGLE_CSE_CX = os.getenv("GOOGLE_CSE_CX")
        self.GOOGLE_CSE_API_KEY = os.getenv("GOOGLE_CSE_API_KEY")  # Legacy compatibility
        self.PSI_STRATEGY = os.getenv("PSI_STRATEGY", "mobile")
        
        # CORS
        self.ALLOWED_ORIGINS = os.getenv(
            "ALLOWED_ORIGINS",
            "https://ai2flows.com,https://www.ai2flows.com,http://localhost:5173,http://localhost:3000",
        )
        
        # Database settings
        self.DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./app.db")
        
        # Cache settings
        self.CACHE_EXPIRY_HOURS = int(os.getenv("CACHE_EXPIRY_HOURS", "24"))
        self.REPORT_EXPIRY_DAYS = int(os.getenv("REPORT_EXPIRY_DAYS", "7"))
        
        # Scraper settings
        self.REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "30"))
        self.USER_AGENT = os.getenv("USER_AGENT", "AI2Flows-CompetitiveAnalyzer/1.0")
        self.MAX_PAGES_PER_DOMAIN = int(os.getenv("MAX_PAGES_PER_DOMAIN", "5"))
        
        # Analysis settings
        self.MAX_KEYWORDS_TO_ANALYZE = int(os.getenv("MAX_KEYWORDS_TO_ANALYZE", "100"))
        self.MAX_CLUSTERS = int(os.getenv("MAX_CLUSTERS", "15"))
        self.MIN_CLUSTER_SIZE = int(os.getenv("MIN_CLUSTER_SIZE", "3"))
        
        # Log what we loaded
        self._log_loaded_variables()
    
    def _log_loaded_variables(self):
        """Log which variables were successfully loaded."""
        variables = {
            "GHL_API_KEY": self.GHL_API_KEY,
            "GHL_LOCATION_ID": self.GHL_LOCATION_ID,
            "GOOGLE_API_KEY": self.GOOGLE_API_KEY,
            "GOOGLE_CSE_CX": self.GOOGLE_CSE_CX,
            "JWT_SECRET": self.JWT_SECRET,
            "DATABASE_URL": self.DATABASE_URL
        }
        
        for name, value in variables.items():
            if value and name not in ["DATABASE_URL"]:  # Don't show DB URL preview
                logger.info(f"✅ {name}: LOADED (length: {len(str(value))})")
                # Show first few chars for debugging (except sensitive ones)
                if name not in ["JWT_SECRET"] and len(str(value)) > 8:
                    preview = f"{str(value)[:4]}...{str(value)[-4:]}"
                    logger.info(f"   Preview: {preview}")
            elif value:
                logger.info(f"✅ {name}: LOADED (length: {len(str(value))})")
            else:
                logger.error(f"❌ {name}: NOT LOADED")
        
        logger.info("================================")

settings = Settings()
