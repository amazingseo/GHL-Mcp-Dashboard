# config.py
import os

class Settings:
    """Environment-backed settings (no extra deps)."""

    # --- Auth / Security ---
    JWT_SECRET: str
    WINDOW_DAYS: int
    MAX_FREE: int
    REQUESTS_PER_MINUTE: int

    # --- GoHighLevel (server-side only) ---
    GHL_API_KEY: str | None
    GHL_LOCATION_ID: str | None

    # --- Google APIs (single key for PSI + CSE) ---
    GOOGLE_API_KEY: str | None
    GOOGLE_CSE_CX: str | None
    PSI_STRATEGY: str  # "mobile" or "desktop"

    # --- CORS ---
    ALLOWED_ORIGINS: str  # comma-separated

    def __init__(self) -> None:
        # Auth / quotas
        self.JWT_SECRET           = os.getenv("JWT_SECRET", "change-me")  # change in Railway
        self.WINDOW_DAYS          = int(os.getenv("WINDOW_DAYS", "30"))
        self.MAX_FREE             = int(os.getenv("MAX_FREE", "6"))
        self.REQUESTS_PER_MINUTE  = int(os.getenv("REQUESTS_PER_MINUTE", "30"))

        # GHL
        self.GHL_API_KEY          = os.getenv("GHL_API_KEY")              # PIT (Private Integration Token)
        self.GHL_LOCATION_ID      = os.getenv("GHL_LOCATION_ID")          # Subaccount / Location ID

        # Google
        # In config.py, change this line:
self.GOOGLE_API_KEY = os.getenv("GOOGLE_CSE_API_KEY")  # Changed name

# Or add fallback logic:
self.GOOGLE_API_KEY = (
    os.getenv("GOOGLE_API_KEY") or 
    os.getenv("GOOGLE_CSE_API_KEY") or 
    os.getenv("GOOGLE_PAGESPEED_API_KEY")
)
        self.GOOGLE_CSE_CX        = os.getenv("GOOGLE_CSE_CX")            # CSE "cx"
        self.PSI_STRATEGY         = os.getenv("PSI_STRATEGY", "mobile")   # or "desktop"

        # CORS
        self.ALLOWED_ORIGINS      = os.getenv(
            "ALLOWED_ORIGINS",
            "https://ai2flows.com,https://www.ai2flows.com,http://localhost:5173,http://localhost:3000",
        )

settings = Settings()

