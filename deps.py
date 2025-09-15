from fastapi import Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
import time
import hashlib
from collections import defaultdict

from models_db import get_db
from config import settings

# Rate limiting storage (in production, use Redis)
rate_limit_storage = defaultdict(list)

async def get_database() -> AsyncSession:
    """Get database session"""
    return Depends(get_db)

def get_client_ip(request: Request) -> str:
    """Extract client IP from request"""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host

async def rate_limiter(request: Request) -> bool:
    """Simple rate limiter based on IP"""
    client_ip = get_client_ip(request)
    current_time = time.time()
    
    # Clean old entries (1 hour window)
    cutoff_time = current_time - 3600  # 1 hour
    rate_limit_storage[client_ip] = [
        timestamp for timestamp in rate_limit_storage[client_ip] 
        if timestamp > cutoff_time
    ]
    
    # Check if rate limit exceeded (max 10 requests per hour)
    if len(rate_limit_storage[client_ip]) >= 10:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Maximum 10 requests per hour."
        )
    
    # Add current request
    rate_limit_storage[client_ip].append(current_time)
    return True

def generate_cache_key(prefix: str, *args) -> str:
    """Generate cache key from arguments"""
    key_string = f"{prefix}:" + ":".join(str(arg) for arg in args)
    return hashlib.md5(key_string.encode()).hexdigest()

class ServiceDependency:
    """Base class for service dependencies"""
    
    def __init__(self):
        self._initialized = False
    
    async def initialize(self):
        """Initialize service if not already done"""
        if not self._initialized:
            await self._setup()
            self._initialized = True
    
    async def _setup(self):
        """Override in subclasses"""
        pass

def get_current_user(request: Request) -> Optional[str]:
    """Extract user information from request (placeholder)"""
    # In production, implement proper authentication
    return None

async def log_analytics_event(
    db: AsyncSession,
    event_type: str,
    domain: str = None,
    user_ip: str = None,
    metadata: dict = None
):
    """Log analytics event"""
    from models_db import AnalyticsEvent
    import json
    
    event = AnalyticsEvent(
        event_type=event_type,
        domain=domain,
        event_metadata=json.dumps(metadata) if metadata else None
    )
    
    db.add(event)
    await db.commit()