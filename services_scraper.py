import asyncio
import aiohttp
import time
from urllib.parse import urljoin, urlparse, robots
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
                    rp.read()
                    
                    # Parse robots.txt content manually since RobotFileParser doesn't support async
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
        
        # Use crawl-delay from robots.txt or default rate limit
        delay = self.domain_delays.get(domain, 1.0 / settings.REQUESTS_PER_SECOND)
        
        if domain in self.last_request_time:
            time_since_last = current_time - self.last_request_time[domain]
            if time_since_last < delay:
                sleep_time = delay - time_since_last
                await asyncio.sleep(sleep_time)
        
        self.last_request_time[domain] = time.time()
    
    def _extract_content(self, html: str, url: str) -> Dict[str, any]:
        """Extract useful content from HTML"""
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # Remove script and style elements
            for script in soup(["script", "style", "nav", "header", "footer"]):
                script.decompose()
            
            # Extract title
            title_tag = soup.find('title')
            title = title_tag.get_text().strip() if title_tag else ""
            
            # Extract meta description
            meta_desc_tag = soup.find('meta', attrs={'name': 'description'})
            meta_description = ""
            if meta_desc_tag:
                meta_description = meta_desc_tag.get('content', '').strip()
            
            # Extract main content
            content = ""
            
            # Try to find main content areas
            main_content_selectors = [
                'main', 'article', '[role="main"]', 
                '.content', '.post-content', '.entry-content',
                '#content', '#main-content'
            ]
            
            for selector in main_content_selectors:
                content_element = soup.select_one(selector)
                if content_element:
                    content = content_element.get_text(separator=' ', strip=True)
                    break
            
            # Fallback to body content
            if not content:
                body = soup.find('body')
                if body:
                    content = body.get_text(separator=' ', strip=True)
            
            # Extract keywords from meta tags
            keywords = []
            meta_keywords = soup.find('meta', attrs={'name': 'keywords'})
            if meta_keywords:
                keywords = [k.strip() for k in meta_keywords.get('content', '').split(',')]
            
            # Extract headings as potential keywords
            headings = []
            for heading in soup.find_all(['h1', 'h2', 'h3']):
                heading_text = heading.get_text().strip()
                if heading_text and len(heading_text) < 100:
                    headings.append(heading_text)
            
            return {
                'title': title,
                'meta_description': meta_description,
                'content': content[:5000],  # Limit content length
                'keywords': keywords,
                'headings': headings[:10]  # Top 10 headings
            }
            
        except Exception as e:
            logger.error(f"Error extracting content from {url}: {e}")
            return {
                'title': '',
                'meta_description': '',
                'content': '',
                'keywords': [],
                'headings': []
            }
    
    async def scrape_url(self, url: str) -> ScrapedPage:
        """Scrape a single URL"""
        domain = urlparse(url).netloc
        
        try:
            # Check robots.txt
            robots_parser = await self._get_robots_txt(domain)
            if not self._can_fetch(domain, url, robots_parser):
                return ScrapedPage(
                    url=url,
                    title="",
                    meta_description="",
                    content="",
                    keywords=[],
                    status_code=403,
                    error="Blocked by robots.txt"
                )
            
            # Respect rate limiting
            await self._respect_rate_limit(domain)
            
            # Make request
            if not self.session:
                raise Exception("Session not initialized")
                
            async with self.session.get(url) as response:
                if response.status == 200:
                    html = await response.text()
                    extracted = self._extract_content(html, url)
                    
                    return ScrapedPage(
                        url=url,
                        title=extracted['title'],
                        meta_description=extracted['meta_description'],
                        content=extracted['content'],
                        keywords=extracted['keywords'] + extracted['headings'],
                        status_code=response.status
                    )
                else:
                    return ScrapedPage(
                        url=url,
                        title="",
                        meta_description="",
                        content="",
                        keywords=[],
                        status_code=response.status,
                        error=f"HTTP {response.status}"
                    )
                    
        except Exception as e:
            logger.error(f"Error scraping {url}: {e}")
            return ScrapedPage(
                url=url,
                title="",
                meta_description="",
                content="",
                keywords=[],
                status_code=0,
                error=str(e)
            )
    
    async def scrape_domain_pages(self, domain: str, urls: List[str]) -> Dict[str, any]:
        """Scrape multiple pages from a domain"""
        if not self.session:
            async with self:
                return await self._scrape_pages_internal(domain, urls)
        else:
            return await self._scrape_pages_internal(domain, urls)
    
    async def _scrape_pages_internal(self, domain: str, urls: List[str]) -> Dict[str, any]:
        """Internal method to scrape pages"""
        # Limit number of pages
        urls = urls[:settings.MAX_PAGES_PER_DOMAIN]
        
        logger.info(f"Scraping {len(urls)} pages from {domain}")
        
        # Create semaphore to limit concurrent requests
        semaphore = asyncio.Semaphore(settings.MAX_CONCURRENT_REQUESTS)
        
        async def scrape_with_semaphore(url):
            async with semaphore:
                return await self.scrape_url(url)
        
        # Scrape all URLs concurrently (but with rate limiting)
        tasks = [scrape_with_semaphore(url) for url in urls]
        scraped_pages = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        successful_pages = []
        failed_pages = []
        all_content = []
        all_keywords = set()
        
        for i, result in enumerate(scraped_pages):
            if isinstance(result, Exception):
                failed_pages.append({
                    'url': urls[i],
                    'error': str(result)
                })
            elif isinstance(result, ScrapedPage):
                if result.status_code == 200 and result.content:
                    successful_pages.append({
                        'url': result.url,
                        'title': result.title,
                        'meta_description': result.meta_description,
                        'content_length': len(result.content)
                    })
                    all_content.append(result.content)
                    all_keywords.update(result.keywords)
                else:
                    failed_pages.append({
                        'url': result.url,
                        'error': result.error or f"Status {result.status_code}"
                    })
        
        logger.info(f"Successfully scraped {len(successful_pages)} pages, failed: {len(failed_pages)}")
        
        return {
            'domain': domain,
            'successful_pages': successful_pages,
            'failed_pages': failed_pages,
            'content': ' '.join(all_content),
            'extracted_keywords': list(all_keywords),
            'total_pages_scraped': len(successful_pages),
            'total_content_length': sum(len(content) for content in all_content)
        }

# Global scraper instance
scraper = WebScraper()

async def scrape_competitor_pages(domain: str, urls: List[str]) -> Dict[str, any]:
    """Convenience function to scrape competitor pages"""
    async with WebScraper() as scraper:
        return await scraper.scrape_domain_pages(domain, urls)