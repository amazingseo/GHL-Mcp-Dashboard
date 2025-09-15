import asyncio
import aiohttp
import time
from urllib.parse import urljoin, urlparse  # removed 'robots'
from urllib.robotparser import RobotFileParser
from bs4 import BeautifulSoup
from typing import List, Dict, Optional, Set
import logging
from dataclasses import dataclass
from config import settings

logger = logging.getLogger(__name__)

@dataclass
class ScrapedPage:
    """Data structure for scraped page content"""
    url: str
    title: str
    meta_description: str
    content: str
    keywords: List[str]
    status_code: int
    error: Optional[str] = None

class WebScraper:
    """Ethical web scraper with robots.txt compliance"""
    
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.robots_cache: Dict[str, RobotFileParser] = {}
        self.domain_delays: Dict[str, float] = {}
        self.last_request_time: Dict[str, float] = {}
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=settings.REQUEST_TIMEOUT),
            headers={'User-Agent': settings.USER_AGENT}
        )
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def _get_robots_txt(self, domain: str) -> Optional[RobotFileParser]:
        """Fetch and parse robots.txt for domain"""
        if domain in self.robots_cache:
            return self.robots_cache[domain]
        
        try:
            robots_url = f"https://{domain}/robots.txt"
            
            if not self.session:
                return None
                
            async with self.session.get(robots_url) as response:
                if response.status == 200:
                    robots_content = await response.text()
                    rp = RobotFileParser()
                    rp.set_url(robots_url)
                    # Previously: rp.read()  # This does blocking network I/O
                    # Use the content we already fetched asynchronously:
                    rp.parse(robots_content.splitlines())

                    # Parse crawl-delay for per-domain throttling
                    lines = robots_content.split('\n')
                    current_user_agent = None
                    
                    for line in lines:
                        line = line.strip()
                        if line.startswith('#') or not line:
                            continue
                            
                        if line.lower().startswith('user-agent:'):
                            current_user_agent = line.split(':', 1)[1].strip()
                        elif line.lower().startswith('crawl-delay:') and current_user_agent:
                            if current_user_agent == '*' or 'competitiveanalyzer' in current_user_agent.lower():
                                try:
                                    delay = float(line.split(':', 1)[1].strip())
                                    self.domain_delays[domain] = delay
                                except ValueError:
                                    pass
                    
                    self.robots_cache[domain] = rp
                    return rp
                    
        except Exception as e:
            logger.warning(f"Could not fetch robots.txt for {domain}: {e}")
        
        # Create permissive robots parser if fetch failed
        rp = RobotFileParser()
        self.robots_cache[domain] = rp
        return rp
    
    def _can_fetch(self, domain: str, url: str, robots_parser: Optional[RobotFileParser]) -> bool:
        """Check if URL can be fetched according to robots.txt"""
        if not robots_parser:
            return True
            
        try:
            return robots_parser.can_fetch(settings.USER_AGENT, url)
        except Exception:
            # If robots.txt parsing fails, be conservative and allow
            return True

    async def _respect_rate_limit(self, domain: str):
        """Implement rate limiting per domain"""
        current_time = time.time()
        # ...
