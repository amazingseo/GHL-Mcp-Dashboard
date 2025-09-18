import os
import logging

logger = logging.getLogger(__name__)

class Settings:
    """Environment-backed settings - Railway compatible."""
    
    def __init__(self) -> None:
        logger.info("=== RAILWAY VARIABLE LOADING ===")
        
        # Load variables directly (no fallback logic)
        self.JWT_SECRET = os.getenv("JWT_SECRET", "change-me")
        self.WINDOW_DAYS = int(os.getenv("WINDOW_DAYS", "30"))
        self.MAX_FREE = int(os.getenv("MAX_FREE", "6"))
        self.REQUESTS_PER_MINUTE = int(os.getenv("REQUESTS_PER_MINUTE", "30"))
        
        # GHL Settings - direct mapping
        self.GHL_API_KEY = os.getenv("GHL_API_KEY")
        self.GHL_LOCATION_ID = os.getenv("GHL_LOCATION_ID")
        
        # Google Settings - direct mapping  
        self.GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
        self.GOOGLE_CSE_CX = os.getenv("GOOGLE_CSE_CX")
        self.PSI_STRATEGY = os.getenv("PSI_STRATEGY", "mobile")
        
        # CORS
        self.ALLOWED_ORIGINS = os.getenv(
            "ALLOWED_ORIGINS",
            "https://ai2flows.com,https://www.ai2flows.com,http://localhost:5173,http://localhost:3000",
        )
        
        # Log what we loaded
        self._log_loaded_variables()
    
    def _log_loaded_variables(self):
        """Log which variables were successfully loaded."""
        variables = {
            "GHL_API_KEY": self.GHL_API_KEY,
            "GHL_LOCATION_ID": self.GHL_LOCATION_ID,
            "GOOGLE_API_KEY": self.GOOGLE_API_KEY,
            "GOOGLE_CSE_CX": self.GOOGLE_CSE_CX,
            "JWT_SECRET": self.JWT_SECRET
        }
        
        for name, value in variables.items():
            if value:
                logger.info(f"✅ {name}: LOADED (length: {len(str(value))})")
                # Show first few chars for debugging
                if len(str(value)) > 8:
                    preview = f"{str(value)[:4]}...{str(value)[-4:]}"
                    logger.info(f"   Preview: {preview}")
            else:
                logger.error(f"❌ {name}: NOT LOADED")
        
        logger.info("================================")

settings = Settings()
