import os
import logging

logger = logging.getLogger(__name__)

class Settings:
    """Environment-backed settings with Railway-specific fixes."""
    
    def __init__(self) -> None:
        # Debug logging for Railway deployment
        self._log_environment_debug()
        
        # Auth / quotas
        self.JWT_SECRET = os.getenv("JWT_SECRET", "change-me")
        self.WINDOW_DAYS = int(os.getenv("WINDOW_DAYS", "30"))
        self.MAX_FREE = int(os.getenv("MAX_FREE", "6"))
        self.REQUESTS_PER_MINUTE = int(os.getenv("REQUESTS_PER_MINUTE", "30"))
        
        # GHL - Use exact variable names from Railway dashboard
        self.GHL_API_KEY = os.getenv("GHL_API_KEY")
        self.GHL_LOCATION_ID = os.getenv("GHL_LOCATION_ID")
        
        # Google APIs - Simplified single variable approach
        self.GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
        self.GOOGLE_CSE_CX = os.getenv("GOOGLE_CSE_CX")
        self.PSI_STRATEGY = os.getenv("PSI_STRATEGY", "mobile")
        
        # CORS
        self.ALLOWED_ORIGINS = os.getenv(
            "ALLOWED_ORIGINS",
            "https://ai2flows.com,https://www.ai2flows.com,http://localhost:5173,http://localhost:3000",
        )
        
        # Validate critical settings
        self._validate_configuration()
    
    def _log_environment_debug(self) -> None:
        """Debug logging for Railway deployment issues."""
        logger.info("=== RAILWAY ENVIRONMENT DEBUG ===")
        
        # Log Railway-specific variables
        railway_vars = [key for key in os.environ.keys() if key.startswith('RAILWAY_')]
        logger.info(f"Railway variables found: {railway_vars}")
        
        # Log critical app variables (without values for security)
        critical_vars = [
            "GHL_API_KEY", "GHL_LOCATION_ID", "GOOGLE_API_KEY", 
            "GOOGLE_CSE_CX", "JWT_SECRET"
        ]
        
        for var in critical_vars:
            value = os.getenv(var)
            if value:
                logger.info(f"{var}: SET (length: {len(value)})")
                # Log first/last few chars for debugging without exposing full key
                if len(value) > 8:
                    logger.info(f"{var} preview: {value[:4]}...{value[-4:]}")
            else:
                logger.error(f"{var}: NOT SET")
        
        logger.info("================================")
    
    def _validate_configuration(self) -> None:
        """Validate critical configuration and log issues."""
        issues = []
        
        # Check GHL configuration
        if not self.GHL_API_KEY:
            issues.append("GHL_API_KEY is missing")
        elif not self.GHL_API_KEY.startswith(('eyJ', 'pk_')):  # Common GHL token prefixes
            issues.append("GHL_API_KEY format looks incorrect")
            
        if not self.GHL_LOCATION_ID:
            issues.append("GHL_LOCATION_ID is missing")
        
        # Check Google API configuration
        if not self.GOOGLE_API_KEY:
            issues.append("GOOGLE_API_KEY is missing")
        elif not self.GOOGLE_API_KEY.startswith('AIza'):  # Google API keys start with AIza
            issues.append("GOOGLE_API_KEY format looks incorrect")
            
        if not self.GOOGLE_CSE_CX:
            issues.append("GOOGLE_CSE_CX is missing")
        
        # Log validation results
        if issues:
            logger.error(f"Configuration issues found: {issues}")
        else:
            logger.info("Configuration validation passed")

# Create singleton instance
settings = Settings()
