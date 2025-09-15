import asyncio
import aiohttp
import time
from urllib.parse import urljoin, urlparse  # removed 'robots'
from urllib.robotparser import RobotFileParser
from bs4 import BeautifulSoup
from typing import List, Dict, Optional, Set, Any
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
        """Implement simple rate limiting per domain"""
        min_delay = self.domain_delays.get(domain, 1.0)
        now = time.time()
        last = self.last_request_time.get(domain, 0)
        wait = min_delay - (now - last)
        if wait > 0:
            await asyncio.sleep(wait)
        self.last_request_time[domain] = time.time()

    async def _fetch_page(self, url: str) -> ScrapedPage:
        """Fetch a single page and extract basic content"""
        domain = urlparse(url).netloc
        robots_parser = await self._get_robots_txt(domain)

        if not self._can_fetch(domain, url, robots_parser):
            return ScrapedPage(url=url, title="", meta_description="", content="", keywords=[], status_code=0, error="Blocked by robots.txt")

        await self._respect_rate_limit(domain)

        if not self.session:
            return ScrapedPage(url=url, title="", meta_description="", content="", keywords=[], status_code=0, error="Session not initialized")

        try:
            async with self.session.get(url) as response:
                status = response.status
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')

                title_tag = soup.find('title')
                title = title_tag.get_text().strip() if title_tag else ""
                meta_desc_tag = soup.find('meta', attrs={'name': 'description'})
                meta_description = meta_desc_tag.get('content', '').strip() if meta_desc_tag else ""

                # Extract main text content
                for el in soup(['script', 'style', 'nav', 'header', 'footer']):
                    el.decompose()
                body = soup.find('body')
                text = body.get_text(separator=' ', strip=True) if body else soup.get_text(separator=' ', strip=True)

                # Very simple keywords (top frequent words > 3 chars)
                words = [w for w in text.lower().split() if len(w) > 3]
                freq = {}
                for w in words:
                    freq[w] = freq.get(w, 0) + 1
                top_keywords = [w for w, _ in sorted(freq.items(), key=lambda x: x[1], reverse=True)[:20]]

                return ScrapedPage(
                    url=url,
                    title=title,
                    meta_description=meta_description,
                    content=text,
                    keywords=top_keywords,
                    status_code=status,
                )
        except Exception as e:
            logger.error(f"Failed to fetch {url}: {e}")
            return ScrapedPage(url=url, title="", meta_description="", content="", keywords=[], status_code=0, error=str(e))

    async def scrape_domain_pages(self, domain: str, top_urls: List[Dict[str, str]]) -> Dict[str, Any]:
        """Fetch a subset of provided URLs and return combined content and per-page data.
        top_urls: list of dicts with 'url' keys
        """
        # Select up to MAX_PAGES_PER_DOMAIN URLs
        urls = [item.get('url') for item in top_urls if item.get('url')]
        urls = urls[: max(1, min(len(urls), settings.MAX_PAGES_PER_DOMAIN))]

        # Ensure session context
        close_after = False
        if not self.session:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=settings.REQUEST_TIMEOUT),
                headers={'User-Agent': settings.USER_AGENT}
            )
            close_after = True

        try:
            pages: List[ScrapedPage] = []
            for url in urls:
                page = await self._fetch_page(url)
                pages.append(page)

            combined_content = " \n".join(p.content for p in pages if p.content)
            return {
                'domain': domain,
                'page_count': len(pages),
                'pages': [p.__dict__ for p in pages],
                'content': combined_content
            }
        finally:
            if close_after and self.session:
                await self.session.close()
                self.session = None
