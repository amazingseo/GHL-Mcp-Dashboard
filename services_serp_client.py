import httpx
import asyncio
from typing import Dict, List, Optional, Any
import logging
from urllib.parse import quote_plus
import json
from datetime import datetime, timedelta

from config import settings
from deps import generate_cache_key
from models_db import APICache, AsyncSessionLocal

logger = logging.getLogger(__name__)

class SERPClient:
    """Client for SERP API interactions with multiple providers."""
    
    def __init__(self):
        self.providers = []
        
        # Initialize available providers
        if settings.GOOGLE_CSE_API_KEY and settings.GOOGLE_CSE_CX:
            self.providers.append('google_cse')
        
        if settings.SERPAPI_KEY:
            self.providers.append('serpapi')
        
        if not self.providers:
            logger.warning("No SERP API keys configured. Using mock data for development.")
            self.providers.append('mock')
    
    async def get_domain_keywords(self, domain: str) -> Dict[str, Any]:
        """Get keywords and rankings for a domain."""
        cache_key = generate_cache_key("domain_keywords", domain)
        
        # Check cache first
        cached_data = await self._get_cached_response(cache_key)
        if cached_data:
            logger.info(f"Using cached SERP data for {domain}")
            return cached_data
        
        # Try each provider until we get results
        for provider in self.providers:
            try:
                logger.info(f"Fetching SERP data for {domain} using {provider}")
                
                if provider == 'google_cse':
                    data = await self._fetch_google_cse(domain)
                elif provider == 'serpapi':
                    data = await self._fetch_serpapi(domain)
                else:  # mock
                    data = await self._fetch_mock_data(domain)
                
                if data and data.get('keywords'):
                    # Cache the response
                    await self._cache_response(cache_key, provider, data)
                    return data
                    
            except Exception as e:
                logger.error(f"Provider {provider} failed for {domain}: {str(e)}")
                continue
        
        raise Exception("All SERP providers failed or returned no data")
    
    async def _fetch_google_cse(self, domain: str) -> Dict[str, Any]:
        """Fetch data using Google Custom Search Engine API."""
        base_url = "https://www.googleapis.com/customsearch/v1"
        
        # Search for pages from this domain
        params = {
            'key': settings.GOOGLE_CSE_API_KEY,
            'cx': settings.GOOGLE_CSE_CX,
            'q': f'site:{domain}',
            'num': 10
        }
        
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(base_url, params=params)
            response.raise_for_status()
            
            data = response.json()
            
            # Process results
            keywords = []
            top_urls = []
            
            for idx, item in enumerate(data.get('items', []), 1):
                # Extract potential keywords from title and snippet
                title = item.get('title', '')
                snippet = item.get('snippet', '')
                url = item.get('link', '')
                
                # Simple keyword extraction (in production, use more sophisticated methods)
                potential_keywords = self._extract_keywords_from_text(f"{title} {snippet}")
                
                for keyword in potential_keywords[:5]:  # Top 5 keywords per result
                    keywords.append({
                        'keyword': keyword,
                        'position': idx,
                        'url': url,
                        'search_volume': None,  # Would need additional API calls
                        'cpc': None,
                        'competition': None
                    })
                
                top_urls.append({
                    'url': url,
                    'title': title,
                    'snippet': snippet,
                    'position': idx
                })
            
            return {
                'keywords': keywords,
                'top_urls': top_urls,
                'provider': 'google_cse'
            }
    
    async def _fetch_serpapi(self, domain: str) -> Dict[str, Any]:
        """Fetch data using SerpAPI."""
        base_url = "https://serpapi.com/search"
        
        params = {
            'api_key': settings.SERPAPI_KEY,
            'engine': 'google',
            'q': f'site:{domain}',
            'num': 20
        }
        
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(base_url, params=params)
            response.raise_for_status()
            
            data = response.json()
            
            keywords = []
            top_urls = []
            
            for idx, result in enumerate(data.get('organic_results', []), 1):
                title = result.get('title', '')
                snippet = result.get('snippet', '')
                url = result.get('link', '')
                
                # Extract keywords
                potential_keywords = self._extract_keywords_from_text(f"{title} {snippet}")
                
                for keyword in potential_keywords[:3]:
                    keywords.append({
                        'keyword': keyword,
                        'position': idx,
                        'url': url,
                        'search_volume': result.get('search_volume'),
                        'cpc': result.get('cpc'),
                        'competition': result.get('competition')
                    })
                
                top_urls.append({
                    'url': url,
                    'title': title,
                    'snippet': snippet,
                    'position': idx
                })
            
            return {
                'keywords': keywords,
                'top_urls': top_urls,
                'provider': 'serpapi'
            }
    
    async def _fetch_mock_data(self, domain: str) -> Dict[str, Any]:
        """Generate mock data for development/testing."""
        await asyncio.sleep(1)  # Simulate API delay
        
        mock_keywords = [
            {'keyword': f'{domain.split(".")[0]} services', 'position': 1, 'search_volume': 1000, 'cpc': 2.50},
            {'keyword': f'{domain.split(".")[0]} solutions', 'position': 2, 'search_volume': 800, 'cpc': 3.20},
            {'keyword': f'best {domain.split(".")[0]}', 'position': 3, 'search_volume': 600, 'cpc': 4.10},
            {'keyword': f'{domain.split(".")[0]} reviews', 'position': 4, 'search_volume': 400, 'cpc': 1.80},
            {'keyword': f'{domain.split(".")[0]} pricing', 'position': 5, 'search_volume': 350, 'cpc': 5.20},
        ]
        
        mock_urls = [
            {'url': f'https://{domain}/', 'title': f'{domain.capitalize()} - Home', 'position': 1},
            {'url': f'https://{domain}/about', 'title': f'About {domain.capitalize()}', 'position': 2},
            {'url': f'https://{domain}/services', 'title': f'{domain.capitalize()} Services', 'position': 3},
            {'url': f'https://{domain}/pricing', 'title': f'{domain.capitalize()} Pricing', 'position': 4},
            {'url': f'https://{domain}/contact', 'title': f'Contact {domain.capitalize()}', 'position': 5},
        ]
        
        return {
            'keywords': mock_keywords,
            'top_urls': mock_urls,
            'provider': 'mock'
        }
    
    def _extract_keywords_from_text(self, text: str) -> List[str]:
        """Extract potential keywords from text."""
        import re
        
        # Simple keyword extraction
        words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
        
        # Filter common stop words
        stop_words = {'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'}
        keywords = [word for word in words if word not in stop_words]
        
        # Return unique keywords
        return list(dict.fromkeys(keywords))[:10]
    
    async def _get_cached_response(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Get cached API response if available and not expired."""
        async with AsyncSessionLocal() as session:
            try:
                result = await session.execute(
                    "SELECT response_data FROM api_cache WHERE cache_key = :key AND expires_at > :now",
                    {"key": cache_key, "now": datetime.utcnow()}
                )
                row = result.fetchone()
                return row[0] if row else None
            except Exception:
                return None
    
    async def _cache_response(self, cache_key: str, provider: str, data: Dict[str, Any]):
        """Cache API response."""
        async with AsyncSessionLocal() as session:
            try:
                cache_entry = APICache(
                    cache_key=cache_key,
                    provider=provider,
                    response_data=data
                )
                session.add(cache_entry)
                await session.commit()
            except Exception as e:
                logger.error(f"Failed to cache response: {str(e)}")