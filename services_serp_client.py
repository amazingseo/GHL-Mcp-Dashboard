import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

import httpx
from sqlalchemy import select

from config import settings
from deps import generate_cache_key
from models_db import APICache, AsyncSessionLocal

logger = logging.getLogger(__name__)


class SERPClient:
    """Client for SERP API interactions with multiple providers."""

    def __init__(self):
        self.providers: List[str] = []

        # Initialize available providers
        if settings.GOOGLE_CSE_API_KEY and settings.GOOGLE_CSE_CX:
            self.providers.append("google_cse")

        if settings.SERPAPI_KEY:
            self.providers.append("serpapi")

        if not self.providers:
            logger.warning("No SERP API keys configured. Using mock data for development.")
            self.providers.append("mock")

    async def get_domain_keywords(
        self,
        domain: str,
        country: str = "US",
        language: str = "en",
        location: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get localized keywords and rankings for a domain."""
        cache_key = generate_cache_key("domain_keywords", domain, country, language, location or "")
        cached = await self._get_cached_response(cache_key)
        if cached:
            logger.info("Using cached SERP data for %s [%s/%s%s]", domain, country, language, f" | {location}" if location else "")
            return cached

        for provider in self.providers:
            try:
                logger.info(
                    "Fetching SERP data for %s using %s [%s/%s%s]",
                    domain,
                    provider,
                    country,
                    language,
                    f" | {location}" if location else "",
                )
                if provider == "google_cse":
                    data = await self._fetch_google_cse(domain, country, language)
                elif provider == "serpapi":
                    data = await self._fetch_serpapi(domain, country, language, location)
                else:
                    data = await self._fetch_mock_data(domain)

                if data and data.get("keywords"):
                    await self._cache_response(cache_key, provider, data)
                    return data
            except Exception as e:
                logger.error("Provider %s failed for %s: %s", provider, domain, e)
                continue

        raise Exception("All SERP providers failed or returned no data")

    async def _fetch_google_cse(self, domain: str, country: str, language: str) -> Dict[str, Any]:
        """Fetch data using Google Custom Search Engine API."""
        base_url = "https://www.googleapis.com/customsearch/v1"
        params = {
            "key": settings.GOOGLE_CSE_API_KEY,
            "cx": settings.GOOGLE_CSE_CX,
            "q": f"site:{domain}",
            "num": 10,
            # Localization hints (partial support)
            "hl": language,
            "gl": country.lower(),
        }

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(base_url, params=params)
            resp.raise_for_status()
            data = resp.json()

            keywords: List[Dict[str, Any]] = []
            top_urls: List[Dict[str, Any]] = []

            for idx, item in enumerate(data.get("items", []), 1):
                title = item.get("title", "")
                snippet = item.get("snippet", "")
                url = item.get("link", "")

                for kw in self._extract_keywords_from_text(f"{title} {snippet}")[:5]:
                    keywords.append(
                        {
                            "keyword": kw,
                            "position": idx,
                            "url": url,
                            "search_volume": None,
                            "cpc": None,
                            "competition": None,
                        }
                    )

                top_urls.append(
                    {
                        "url": url,
                        "title": title,
                        "snippet": snippet,
                        "position": idx,
                    }
                )

            return {"keywords": keywords, "top_urls": top_urls, "provider": "google_cse"}

    async def _fetch_serpapi(
        self, domain: str, country: str, language: str, location: Optional[str]
    ) -> Dict[str, Any]:
        """Fetch data using SerpAPI."""
        base_url = "https://serpapi.com/search"
        params: Dict[str, Any] = {
            "api_key": settings.SERPAPI_KEY,
            "engine": "google",
            "q": f"site:{domain}",
            "num": 20,
            "hl": language,
            "gl": country.lower(),
        }
        if location:
            params["location"] = location  # e.g., "Austin, Texas, United States"

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(base_url, params=params)
            resp.raise_for_status()
            data = resp.json()

            keywords: List[Dict[str, Any]] = []
            top_urls: List[Dict[str, Any]] = []

            for idx, result in enumerate(data.get("organic_results", []), 1):
                title = result.get("title", "")
                snippet = result.get("snippet", "")
                url = result.get("link", "")

                for kw in self._extract_keywords_from_text(f"{title} {snippet}")[:3]:
                    keywords.append(
                        {
                            "keyword": kw,
                            "position": idx,
                            "url": url,
                            "search_volume": result.get("search_volume"),
                            "cpc": result.get("cpc"),
                            "competition": result.get("competition"),
                        }
                    )

                top_urls.append(
                    {
                        "url": url,
                        "title": title,
                        "snippet": snippet,
                        "position": idx,
                    }
                )

            return {"keywords": keywords, "top_urls": top_urls, "provider": "serpapi"}

    async def _fetch_mock_data(self, domain: str) -> Dict[str, Any]:
        """Generate mock data for development/testing."""
        await asyncio.sleep(0.3)  # Simulate API latency

        head = domain.split(".")[0]
        mock_keywords = [
            {"keyword": f"{head} services", "position": 1, "search_volume": 1000, "cpc": 2.50},
            {"keyword": f"{head} solutions", "position": 2, "search_volume": 800, "cpc": 3.20},
            {"keyword": f"best {head}", "position": 3, "search_volume": 600, "cpc": 4.10},
            {"keyword": f"{head} reviews", "position": 4, "search_volume": 400, "cpc": 1.80},
            {"keyword": f"{head} pricing", "position": 5, "search_volume": 350, "cpc": 5.20},
        ]

        mock_urls = [
            {"url": f"https://{domain}/", "title": f"{domain} - Home", "position": 1},
            {"url": f"https://{domain}/about", "title": f"About {domain}", "position": 2},
            {"url": f"https://{domain}/services", "title": f"{domain} Services", "position": 3},
            {"url": f"https://{domain}/pricing", "title": f"{domain} Pricing", "position": 4},
            {"url": f"https://{domain}/contact", "title": f"Contact {domain}", "position": 5},
        ]

        return {"keywords": mock_keywords, "top_urls": mock_urls, "provider": "mock"}

    def _extract_keywords_from_text(self, text: str) -> List[str]:
        """Extract potential keywords from text."""
        import re

        words = re.findall(r"\b[a-zA-Z]{3,}\b", text.lower())
        stop_words = {"the", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with", "by"}
        return list(dict.fromkeys(w for w in words if w not in stop_words))[:10]

    async def _get_cached_response(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Get cached API response if available and not expired."""
        async with AsyncSessionLocal() as session:
            try:
                result = await session.execute(
                    select(APICache.response_data).where(
                        (APICache.cache_key == cache_key) & (APICache.expires_at > datetime.utcnow())
                    )
                )
                row = result.fetchone()
                return row[0] if row else None
            except Exception:
                return None

    async def _cache_response(self, cache_key: str, provider: str, data: Dict[str, Any]):
        """Cache API response."""
        async with AsyncSessionLocal() as session:
            try:
                session.add(APICache(cache_key=cache_key, provider=provider, response_data=data))
                await session.commit()
            except Exception as e:
                logger.error("Failed to cache response: %s", e)
