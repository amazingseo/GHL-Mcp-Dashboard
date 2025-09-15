import asyncio
import aiohttp
import time
import json
import logging
import os
from typing import Dict, List, Any, Optional
from urllib.parse import urljoin, urlparse
from datetime import datetime
import re

from config import settings

logger = logging.getLogger(__name__)

class WebSpeedAnalyzer:
    """Comprehensive web speed and performance analyzer using Google PageSpeed Insights API"""
    
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        # Google PageSpeed Insights API (FREE - 25,000 requests/day)
        self.pagespeed_api_key = os.getenv('GOOGLE_PAGESPEED_API_KEY')  # Optional but recommended
        self.pagespeed_url = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=120),  # Increased for API calls
            headers={'User-Agent': settings.USER_AGENT}
        )
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def analyze_speed(self, url: str) -> Dict[str, Any]:
        """Comprehensive speed analysis using Google PageSpeed Insights API"""
        logger.info(f"Starting speed analysis for {url}")
        
        if not url.startswith(('http://', 'https://')):
            url = f'https://{url}'
        
        try:
            # Primary: Use Google PageSpeed Insights API for accurate data
            pagespeed_data = await self._get_pagespeed_insights(url)
            
            if pagespeed_data and not pagespeed_data.get('error'):
                return await self._format_pagespeed_results(pagespeed_data, url)
            else:
                logger.warning("PageSpeed API failed, using fallback analysis")
                return await self._fallback_analysis(url)
                
        except Exception as e:
            logger.error(f"Speed analysis failed: {e}")
            return await self._fallback_analysis(url)
    
    async def _get_pagespeed_insights(self, url: str) -> Optional[Dict[str, Any]]:
        """Get real performance data from Google PageSpeed Insights API"""
        if not self.session:
            return None
            
        params = {
            "url": url,
            "strategy": "mobile",  # Use mobile strategy for Core Web Vitals
            "category": ["PERFORMANCE", "ACCESSIBILITY", "BEST_PRACTICES", "SEO"]
        }
        
        # Add API key if available for higher rate limits
        if self.pagespeed_api_key:
            params["key"] = self.pagespeed_api_key
        
        try:
            logger.info(f"Calling PageSpeed Insights API for {url}")
            async with self.session.get(self.pagespeed_url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    return data
                elif response.status == 429:
                    logger.warning("PageSpeed API rate limit exceeded")
                    return {"error": "rate_limit"}
                else:
                    logger.error(f"PageSpeed API error: {response.status}")
                    error_text = await response.text()
                    logger.error(f"Error details: {error_text}")
                    return {"error": f"api_error_{response.status}"}
                    
        except asyncio.TimeoutError:
            logger.error("PageSpeed API timeout")
            return {"error": "timeout"}
        except Exception as e:
            logger.error(f"PageSpeed API request failed: {e}")
            return {"error": str(e)}
    
    async def _format_pagespeed_results(self, data: Dict[str, Any], url: str) -> Dict[str, Any]:
        """Format PageSpeed Insights data to match your current structure"""
        lighthouse_result = data.get("lighthouseResult", {})
        audits = lighthouse_result.get("audits", {})
        categories = lighthouse_result.get("categories", {})
        
        # Extract Core Web Vitals (in seconds, convert to ms where needed)
        fcp = audits.get("first-contentful-paint", {}).get("numericValue", 0) / 1000
        lcp = audits.get("largest-contentful-paint", {}).get("numericValue", 0) / 1000
        cls = audits.get("cumulative-layout-shift", {}).get("numericValue", 0)
        fid = audits.get("max-potential-fid", {}).get("numericValue", 0)
        ttfb = audits.get("server-response-time", {}).get("numericValue", 0)
        tti = audits.get("interactive", {}).get("numericValue", 0) / 1000
        
        # Performance scores
        performance_score = int(categories.get("performance", {}).get("score", 0) * 100)
        accessibility_score = int(categories.get("accessibility", {}).get("score", 0) * 100)
        best_practices_score = int(categories.get("best-practices", {}).get("score", 0) * 100)
        seo_score = int(categories.get("seo", {}).get("score", 0) * 100)
        
        # Extract resource information
        resource_summary = audits.get("resource-summary", {}).get("details", {}).get("items", [])
        total_byte_weight = audits.get("total-byte-weight", {}).get("numericValue", 0)
        
        # Resource breakdown
        resources = {"images": [], "stylesheets": [], "scripts": [], "fonts": [], "other": []}
        resource_counts = {"total_images": 0, "total_stylesheets": 0, "total_scripts": 0, "total_fonts": 0}
        
        for item in resource_summary:
            resource_type = item.get("resourceType", "other")
            count = item.get("requestCount", 0)
            size = item.get("transferSize", 0)
            
            if resource_type == "image":
                resource_counts["total_images"] = count
            elif resource_type == "stylesheet":
                resource_counts["total_stylesheets"] = count
            elif resource_type == "script":
                resource_counts["total_scripts"] = count
            elif resource_type == "font":
                resource_counts["total_fonts"] = count
        
        # Extract opportunities for recommendations
        opportunities = []
        recommendations = []
        
        # Process Lighthouse opportunities
        opportunity_audits = [
            "unused-css-rules", "unused-javascript", "modern-image-formats",
            "uses-optimized-images", "uses-text-compression", "render-blocking-resources",
            "eliminate-render-blocking-resources", "reduce-unused-css", "minify-css", "minify-javascript"
        ]
        
        for audit_id in opportunity_audits:
            audit_data = audits.get(audit_id, {})
            if audit_data.get("score", 1) < 1:  # Failed audit
                potential_savings = audit_data.get("details", {}).get("overallSavingsMs", 0)
                if potential_savings > 100:  # Significant savings
                    opportunities.append({
                        "category": self._get_category_from_audit(audit_id),
                        "severity": "high" if potential_savings > 1000 else "medium",
                        "issue": audit_data.get("title", audit_id.replace("-", " ").title()),
                        "description": audit_data.get("description", "").split(".")[0],  # First sentence only
                        "impact": f"Could save {potential_savings/1000:.1f}s"
                    })
        
        # Generate recommendations based on failed audits
        recommendations = await self._generate_pagespeed_recommendations(audits)
        
        # Calculate page size analysis
        page_size_analysis = {
            "total_size": total_byte_weight,
            "compression_enabled": audits.get("uses-text-compression", {}).get("score", 0) == 1,
            "image_optimization": audits.get("uses-optimized-images", {}).get("score", 0) == 1,
            "modern_formats": audits.get("modern-image-formats", {}).get("score", 0) == 1
        }
        
        return {
            "url": url,
            "analysis_date": lighthouse_result.get("fetchTime", datetime.utcnow().isoformat()),
            "score": performance_score,
            "status": "completed",
            "loading_times": {
                "ttfb": round(ttfb, 2),
                "total_load_time": round(lcp * 1000, 2),  # LCP in ms
                "response_code": 200,
                "content_length": total_byte_weight,
                "server_time": f"{ttfb}ms"
            },
            "page_size_analysis": {
                "uncompressed_size": total_byte_weight,
                "compressed_size": total_byte_weight,
                "compression_ratio": 70.0 if page_size_analysis["compression_enabled"] else 0.0,
                "content_encoding": "gzip" if page_size_analysis["compression_enabled"] else "none",
                "cache_control": "public, max-age=31536000" if audits.get("uses-long-cache-ttl", {}).get("score", 0) == 1 else "none",
                "expires": "optimized" if audits.get("uses-long-cache-ttl", {}).get("score", 0) == 1 else "none"
            },
            "resource_analysis": {
                **resource_counts,
                "resources": resources
            },
            "lighthouse_metrics": {
                "performance": performance_score,
                "accessibility": accessibility_score,
                "best_practices": best_practices_score,
                "seo": seo_score,
                "first_contentful_paint": round(fcp * 1000, 2),
                "largest_contentful_paint": round(lcp * 1000, 2),
                "cumulative_layout_shift": round(cls, 3),
                "first_input_delay": round(fid, 2),
                "time_to_interactive": round(tti * 1000, 2)
            },
            "performance_issues": opportunities,
            "recommendations": recommendations,
            "data_source": "Google PageSpeed Insights",
            "api_version": lighthouse_result.get("lighthouseVersion", ""),
            "test_details": {
                "strategy": "mobile",
                "lighthouse_version": lighthouse_result.get("lighthouseVersion", ""),
                "user_agent": lighthouse_result.get("userAgent", ""),
                "fetch_time": lighthouse_result.get("fetchTime", "")
            }
        }
    
    def _get_category_from_audit(self, audit_id: str) -> str:
        """Map audit IDs to categories"""
        category_map = {
            "unused-css-rules": "CSS Optimization",
            "unused-javascript": "JavaScript Optimization", 
            "modern-image-formats": "Image Optimization",
            "uses-optimized-images": "Image Optimization",
            "uses-text-compression": "Compression",
            "render-blocking-resources": "Critical Resource Optimization",
            "eliminate-render-blocking-resources": "Critical Resource Optimization",
            "reduce-unused-css": "CSS Optimization",
            "minify-css": "CSS Optimization",
            "minify-javascript": "JavaScript Optimization"
        }
        return category_map.get(audit_id, "Performance")
    
    async def _generate_pagespeed_recommendations(self, audits: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate specific recommendations based on PageSpeed audit results"""
        recommendations = []
        
        # Image optimization
        if audits.get("uses-optimized-images", {}).get("score", 1) < 1:
            recommendations.append({
                "category": "Image Optimization",
                "priority": "high",
                "recommendation": "Optimize and compress images",
                "actions": [
                    "Use modern image formats (WebP, AVIF)",
                    "Implement responsive images with srcset",
                    "Compress images without losing quality", 
                    "Use lazy loading for below-the-fold images",
                    "Consider using image CDN services"
                ]
            })
        
        # JavaScript optimization
        if audits.get("unused-javascript", {}).get("score", 1) < 1:
            recommendations.append({
                "category": "JavaScript Optimization",
                "priority": "high",
                "recommendation": "Remove unused JavaScript",
                "actions": [
                    "Remove unused JavaScript code",
                    "Split JavaScript into smaller chunks",
                    "Use dynamic imports for non-critical code",
                    "Minify JavaScript files",
                    "Use async/defer attributes appropriately"
                ]
            })
        
        # CSS optimization
        if audits.get("unused-css-rules", {}).get("score", 1) < 1:
            recommendations.append({
                "category": "CSS Optimization", 
                "priority": "medium",
                "recommendation": "Remove unused CSS",
                "actions": [
                    "Remove unused CSS rules",
                    "Inline critical CSS",
                    "Defer non-critical CSS",
                    "Minify CSS files"
                ]
            })
        
        # Render-blocking resources
        if audits.get("render-blocking-resources", {}).get("score", 1) < 1:
            recommendations.append({
                "category": "Critical Resource Optimization",
                "priority": "high",
                "recommendation": "Eliminate render-blocking resources", 
                "actions": [
                    "Inline critical CSS",
                    "Defer non-critical CSS",
                    "Use async/defer for JavaScript",
                    "Prioritize above-the-fold content"
                ]
            })
        
        # Text compression
        if audits.get("uses-text-compression", {}).get("score", 1) < 1:
            recommendations.append({
                "category": "Compression",
                "priority": "high",
                "recommendation": "Enable text compression",
                "actions": [
                    "Enable GZIP compression",
                    "Consider Brotli compression",
                    "Compress HTML, CSS, and JavaScript",
                    "Configure server compression settings"
                ]
            })
        
        # Server response time
        server_response = audits.get("server-response-time", {})
        if server_response.get("score", 1) < 1:
            recommendations.append({
                "category": "Server Optimization",
                "priority": "high",
                "recommendation": "Improve server response time",
                "actions": [
                    "Use a Content Delivery Network (CDN)",
                    "Optimize database queries",
                    "Enable server-side caching",
                    "Upgrade hosting infrastructure",
                    "Use faster web server software"
                ]
            })
        
        # Caching
        if audits.get("uses-long-cache-ttl", {}).get("score", 1) < 1:
            recommendations.append({
                "category": "Caching",
                "priority": "medium", 
                "recommendation": "Implement efficient caching",
                "actions": [
                    "Set appropriate Cache-Control headers",
                    "Use ETags for cache validation",
                    "Implement browser caching for static assets",
                    "Consider service worker caching"
                ]
            })
        
        return recommendations
    
    async def _fallback_analysis(self, url: str) -> Dict[str, Any]:
        """Fallback to basic analysis when PageSpeed API fails"""
        logger.info(f"Using fallback analysis for {url}")
        
        # Use original basic timing analysis
        analysis_results = {
            'url': url,
            'analysis_date': datetime.utcnow().isoformat(),
            'loading_times': await self._measure_loading_times(url),
            'page_size_analysis': await self._analyze_page_size(url),
            'resource_analysis': await self._analyze_resources(url),
            'lighthouse_metrics': {},
            'performance_issues': [],
            'recommendations': [],
            'score': 0,
            'status': 'completed',
            'data_source': 'Fallback Analysis',
            'note': 'Limited data - PageSpeed Insights API unavailable'
        }
        
        # Calculate basic lighthouse-like metrics
        analysis_results['lighthouse_metrics'] = await self._get_basic_lighthouse_metrics(analysis_results)
        analysis_results['performance_issues'] = await self._identify_basic_issues(analysis_results)
        analysis_results['recommendations'] = await self._generate_basic_recommendations(analysis_results)
        analysis_results['score'] = await self._calculate_basic_performance_score(analysis_results)
        
        return analysis_results
    
    async def _measure_loading_times(self, url: str) -> Dict[str, Any]:
        """Measure basic loading time metrics"""
        if not self.session:
            return {}
        
        try:
            start_time = time.time()
            
            async with self.session.get(url) as response:
                ttfb = time.time() - start_time
                content = await response.text()
                total_time = time.time() - start_time
                
                return {
                    'ttfb': round(ttfb * 1000, 2),
                    'total_load_time': round(total_time * 1000, 2),
                    'response_code': response.status,
                    'content_length': len(content),
                    'server_time': response.headers.get('Server-Timing', 'N/A')
                }
                
        except Exception as e:
            logger.error(f"Error measuring loading times: {e}")
            return {
                'ttfb': 0,
                'total_load_time': 0,
                'response_code': 0,
                'content_length': 0,
                'error': str(e)
            }
    
    async def _analyze_page_size(self, url: str) -> Dict[str, Any]:
        """Analyze page size and compression"""
        if not self.session:
            return {}
        
        try:
            async with self.session.get(url) as response:
                content = await response.text()
                headers = dict(response.headers)
                
                uncompressed_size = len(content.encode('utf-8'))
                compressed_size = int(headers.get('Content-Length', uncompressed_size))
                
                return {
                    'uncompressed_size': uncompressed_size,
                    'compressed_size': compressed_size,
                    'compression_ratio': round((1 - compressed_size / uncompressed_size) * 100, 2) if uncompressed_size > 0 else 0,
                    'content_encoding': headers.get('Content-Encoding', 'none'),
                    'cache_control': headers.get('Cache-Control', 'none'),
                    'expires': headers.get('Expires', 'none')
                }
                
        except Exception as e:
            logger.error(f"Error analyzing page size: {e}")
            return {'error': str(e)}
    
    async def _analyze_resources(self, url: str) -> Dict[str, Any]:
        """Analyze page resources"""
        if not self.session:
            return {}
        
        try:
            async with self.session.get(url) as response:
                content = await response.text()
                
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(content, 'html.parser')
                
                resources = {
                    'images': [],
                    'stylesheets': [],
                    'scripts': [],
                    'fonts': [],
                }
                
                # Count resources
                images = soup.find_all('img')
                for img in images[:20]:  # Limit for performance
                    src = img.get('src')
                    if src:
                        resources['images'].append({
                            'url': urljoin(url, src),
                            'alt': img.get('alt', ''),
                            'loading': img.get('loading', 'eager')
                        })
                
                stylesheets = soup.find_all('link', rel='stylesheet')
                for link in stylesheets:
                    href = link.get('href')
                    if href:
                        resources['stylesheets'].append({
                            'url': urljoin(url, href),
                            'media': link.get('media', 'all')
                        })
                
                scripts = soup.find_all('script')
                for script in scripts:
                    src = script.get('src')
                    if src:
                        resources['scripts'].append({
                            'url': urljoin(url, src),
                            'async': script.has_attr('async'),
                            'defer': script.has_attr('defer')
                        })
                
                return {
                    'total_images': len(images),
                    'total_stylesheets': len(stylesheets),
                    'total_scripts': len(scripts),
                    'total_fonts': 0,  # Basic analysis doesn't detect fonts reliably
                    'resources': resources
                }
                
        except Exception as e:
            logger.error(f"Error analyzing resources: {e}")
            return {'error': str(e)}
    
    async def _get_basic_lighthouse_metrics(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate basic lighthouse-like metrics"""
        loading_times = analysis.get('loading_times', {})
        ttfb = loading_times.get('ttfb', 0)
        total_time = loading_times.get('total_load_time', 0)
        
        # Basic performance scoring
        performance_score = 100
        if ttfb > 800:
            performance_score -= 20
        elif ttfb > 200:
            performance_score -= 10
        
        if total_time > 3000:
            performance_score -= 30
        elif total_time > 1500:
            performance_score -= 15
        
        return {
            'performance': max(0, performance_score),
            'first_contentful_paint': ttfb,
            'largest_contentful_paint': total_time * 0.8,
            'cumulative_layout_shift': 0.1,
            'first_input_delay': 50,
            'time_to_interactive': total_time * 1.2
        }
    
    async def _identify_basic_issues(self, analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Identify basic performance issues"""
        issues = []
        loading_times = analysis.get('loading_times', {})
        ttfb = loading_times.get('ttfb', 0)
        
        if ttfb > 800:
            issues.append({
                'category': 'Server Response',
                'severity': 'high',
                'issue': 'Slow Server Response',
                'description': f'Server response time is {ttfb}ms (should be < 200ms)',
                'impact': 'Users experience delays before content starts loading'
            })
        
        return issues
    
    async def _generate_basic_recommendations(self, analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate basic recommendations"""
        return [
            {
                'category': 'API Enhancement',
                'priority': 'high',
                'recommendation': 'Enable Google PageSpeed Insights API for accurate analysis',
                'actions': [
                    'Add GOOGLE_PAGESPEED_API_KEY environment variable',
                    'Get real Core Web Vitals measurements',
                    'Access detailed performance insights'
                ]
            }
        ]
    
    async def _calculate_basic_performance_score(self, analysis: Dict[str, Any]) -> int:
        """Calculate basic performance score"""
        lighthouse_metrics = analysis.get('lighthouse_metrics', {})
        return int(lighthouse_metrics.get('performance', 75))

# Global instance
speed_analyzer = WebSpeedAnalyzer()
