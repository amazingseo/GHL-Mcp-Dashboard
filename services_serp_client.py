import os
import aiohttp
from urllib.parse import urlencode
from typing import Dict, List, Optional, Any
import logging

from config import settings

logger = logging.getLogger(__name__)

class SERPClient:
    """Google Programmable Search (CSE) client for competitor/domain discovery."""

    def __init__(self):
        # one key for both PSI + CSE (preferred), fallback to old var for compatibility
        self.api_key: Optional[str] = settings.GOOGLE_API_KEY or settings.GOOGLE_CSE_API_KEY
        self.cx: Optional[str] = settings.GOOGLE_CSE_CX
        self.session: Optional[aiohttp.ClientSession] = None

        if not self.api_key or not self.cx:
            logger.warning("CSE not configured; SERPClient will not return live results.")

    async def __aenter__(self):
        self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30))
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self.session:
            await self.session.close()

    async def _cse(self, q: str, num: int = 10, language: Optional[str] = None) -> Dict[str, Any]:
        if not self.session:
            raise RuntimeError("SERPClient session not initialized")
        if not self.api_key or not self.cx:
            return {}

        params = {
            "key": self.api_key,
            "cx": self.cx,
            "q": q,
            "num": num
        }
        if language:
            params["lr"] = f"lang_{language}"

        url = f"https://www.googleapis.com/customsearch/v1?{urlencode(params)}"
        async with self.session.get(url) as resp:
            if resp.status != 200:
                text = await resp.text()
                logger.error("CSE error %s: %s", resp.status, text[:300])
                return {}
            return await resp.json()

    def _extract_keywords(self, titles: List[str]) -> List[Dict[str, Any]]:
        # Very simple keyword extraction from titles/snippets
        words: Dict[str, int] = {}
        for t in titles:
            for w in t.lower().split():
                if len(w) >= 4 and w.isalpha():
                    words[w] = words.get(w, 0) + 1
        ranked = sorted(words.items(), key=lambda x: x[1], reverse=True)[:50]
        # shape into the structure your code expects
        return [{"keyword": w, "position": i + 1, "search_volume": 0} for i, (w, _) in enumerate(ranked)]

    async def get_domain_keywords(self, domain: str, country: str = "US", language: str = "en", location: Optional[str] = None) -> Dict[str, Any]:
        """Return top_urls and a naive 'keywords' list derived from CSE titles/snippets."""
        queries = [
            f"site:{domain}",
            f"site:{domain} blog",
            f"site:{domain} pricing",
            f"site:{domain} case study",
            f"site:{domain} services"
        ]
        titles: List[str] = []
        top_urls: List[Dict[str, str]] = []

        async with self:
            for q in queries:
                data = await self._cse(q, num=10, language=language)
                items = data.get("items", []) if data else []
                for it in items:
                    if it.get("link"):
                        top_urls.append({"url": it["link"], "title": it.get("title", "")})
                    if it.get("title"):
                        titles.append(it["title"])
                    if it.get("snippet"):
                        titles.append(it["snippet"])

        keywords = self._extract_keywords(titles)
        return {"keywords": keywords, "top_urls": top_urls, "provider": "google-cse"}
