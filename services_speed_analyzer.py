import asyncio
import aiohttp
import time
import json
import logging
from typing import Dict, List, Any, Optional
from urllib.parse import urljoin, urlparse
from datetime import datetime
import re

from config import settings

logger = logging.getLogger(__name__)

class WebSpeedAnalyzer:
    """Comprehensive web speed and performance analyzer"""
    
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=60),
            headers={'User-Agent': settings.USER_AGENT}
        )
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def analyze_speed(self, url: str) -> Dict[str, Any]:
        """Comprehensive speed analysis of a website"""
        logger.info(f"Starting speed analysis for {url}")
        
        if not url.startswith(('http://', 'https://')):
            url = f'https://{url}'
        
        analysis_results = {
            'url': url,
            'analysis_date': datetime.utcnow().isoformat(),
            'loading_times': await self._measure_loading_times(url),
            'page_size_analysis': await self._analyze_page_size(url),
            'resource_analysis': await self._analyze_resources(url),
            'lighthouse_metrics': await self._get_lighthouse_metrics(url),
            'performance_issues': [],
            'recommendations': [],
            'score': 0
        }
        
        # Generate issues and recommendations
        analysis_results['performance_issues'] = await self._identify_issues(analysis_results)
        analysis_results['recommendations'] = await self._generate_recommendations(analysis_results)
        analysis_results['score'] = await self._calculate_performance_score(analysis_results)
        
        return analysis_results
    
    async def _measure_loading_times(self, url: str) -> Dict[str, Any]:
        """Measure various loading time metrics"""
        if not self.session:
            return {}
        
        try:
            start_time = time.time()
            
            async with self.session.get(url) as response:
                # Time to first byte
                ttfb = time.time() - start_time
                
                # Time to complete
                content = await response.text()
                total_time = time.time() - start_time
                
                return {
                    'ttfb': round(ttfb * 1000, 2),  # Time to First Byte in ms
                    'total_load_time': round(total_time * 1000, 2),  # Total load time in ms
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
                
                # Calculate sizes
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
        """Analyze page resources (images, CSS, JS, etc.)"""
        if not self.session:
            return {}
        
        try:
            async with self.session.get(url) as response:
                content = await response.text()
                
                # Parse HTML to find resources
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(content, 'html.parser')
                
                resources = {
                    'images': [],
                    'stylesheets': [],
                    'scripts': [],
                    'fonts': [],
                    'other': []
                }
                
                # Find images
                for img in soup.find_all('img'):
                    src = img.get('src')
                    if src:
                        resources['images'].append({
                            'url': urljoin(url, src),
                            'alt': img.get('alt', ''),
                            'loading': img.get('loading', 'eager')
                        })
                
                # Find stylesheets
                for link in soup.find_all('link', rel='stylesheet'):
                    href = link.get('href')
                    if href:
                        resources['stylesheets'].append({
                            'url': urljoin(url, href),
                            'media': link.get('media', 'all')
                        })
                
                # Find scripts
                for script in soup.find_all('script'):
                    src = script.get('src')
                    if src:
                        resources['scripts'].append({
                            'url': urljoin(url, src),
                            'async': script.has_attr('async'),
                            'defer': script.has_attr('defer')
                        })
                
                # Find fonts
                for link in soup.find_all('link'):
                    href = link.get('href', '')
                    if 'font' in href.lower() or link.get('rel') == 'preload' and 'font' in link.get('as', ''):
                        resources['fonts'].append({
                            'url': urljoin(url, href),
                            'preload': link.get('rel') == 'preload'
                        })
                
                # Calculate totals
                resource_summary = {
                    'total_images': len(resources['images']),
                    'total_stylesheets': len(resources['stylesheets']),
                    'total_scripts': len(resources['scripts']),
                    'total_fonts': len(resources['fonts']),
                    'resources': resources
                }
                
                return resource_summary
                
        except Exception as e:
            logger.error(f"Error analyzing resources: {e}")
            return {'error': str(e)}
    
    async def _get_lighthouse_metrics(self, url: str) -> Dict[str, Any]:
        """Simulate Lighthouse-like metrics"""
        # This is a simplified version. In production, you might use Google PageSpeed Insights API
        loading_times = await self._measure_loading_times(url)
        page_size = await self._analyze_page_size(url)
        
        # Calculate scores based on loading times and other factors
        ttfb = loading_times.get('ttfb', 0)
        total_time = loading_times.get('total_load_time', 0)
        
        # Performance scoring (0-100)
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
            'cumulative_layout_shift': 0.1,  # Placeholder
            'first_input_delay': 50,  # Placeholder
            'time_to_interactive': total_time * 1.2
        }
    
    async def _identify_issues(self, analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Identify performance issues based on analysis"""
        issues = []
        
        loading_times = analysis.get('loading_times', {})
        page_size = analysis.get('page_size_analysis', {})
        resources = analysis.get('resource_analysis', {})
        
        # TTFB issues
        ttfb = loading_times.get('ttfb', 0)
        if ttfb > 800:
            issues.append({
                'category': 'Server Response',
                'severity': 'high',
                'issue': 'Slow Time to First Byte',
                'description': f'Your server response time is {ttfb}ms, which is slower than recommended (< 200ms)',
                'impact': 'Users experience delays before any content starts loading'
            })
        elif ttfb > 200:
            issues.append({
                'category': 'Server Response',
                'severity': 'medium',
                'issue': 'Moderate Time to First Byte',
                'description': f'Your server response time is {ttfb}ms, consider optimization',
                'impact': 'Slight delays in initial page loading'
            })
        
        # Page size issues
        uncompressed_size = page_size.get('uncompressed_size', 0)
        if uncompressed_size > 3000000:  # 3MB
            issues.append({
                'category': 'Page Size',
                'severity': 'high',
                'issue': 'Large Page Size',
                'description': f'Page size is {uncompressed_size / 1024 / 1024:.2f}MB, which is very large',
                'impact': 'Slow loading on mobile and slower connections'
            })
        
        # Compression issues
        compression_ratio = page_size.get('compression_ratio', 0)
        if compression_ratio < 50:
            issues.append({
                'category': 'Compression',
                'severity': 'medium',
                'issue': 'Poor Compression',
                'description': f'Content compression is only {compression_ratio}%',
                'impact': 'Larger file transfers and slower loading'
            })
        
        # Resource issues
        total_images = resources.get('total_images', 0)
        if total_images > 50:
            issues.append({
                'category': 'Images',
                'severity': 'medium',
                'issue': 'Too Many Images',
                'description': f'Page contains {total_images} images',
                'impact': 'Multiple HTTP requests slow down page loading'
            })
        
        # Check for lazy loading
        images = resources.get('resources', {}).get('images', [])
        lazy_images = sum(1 for img in images if img.get('loading') == 'lazy')
        if len(images) > 10 and lazy_images == 0:
            issues.append({
                'category': 'Images',
                'severity': 'medium',
                'issue': 'No Lazy Loading',
                'description': 'Images are not using lazy loading',
                'impact': 'All images load immediately, slowing initial page load'
            })
        
        return issues
    
    async def _generate_recommendations(self, analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate actionable recommendations"""
        recommendations = []
        
        loading_times = analysis.get('loading_times', {})
        page_size = analysis.get('page_size_analysis', {})
        resources = analysis.get('resource_analysis', {})
        
        # Server optimization
        ttfb = loading_times.get('ttfb', 0)
        if ttfb > 200:
            recommendations.append({
                'category': 'Server Optimization',
                'priority': 'high' if ttfb > 800 else 'medium',
                'recommendation': 'Optimize server response time',
                'actions': [
                    'Use a Content Delivery Network (CDN)',
                    'Optimize database queries',
                    'Enable server-side caching',
                    'Upgrade hosting plan if necessary',
                    'Use faster web server (nginx vs Apache)'
                ]
            })
        
        # Compression
        if page_size.get('content_encoding') == 'none':
            recommendations.append({
                'category': 'Compression',
                'priority': 'high',
                'recommendation': 'Enable GZIP/Brotli compression',
                'actions': [
                    'Enable GZIP compression on your server',
                    'Consider Brotli compression for better results',
                    'Compress HTML, CSS, and JavaScript files',
                    'Set appropriate compression levels'
                ]
            })
        
        # Caching
        cache_control = page_size.get('cache_control', 'none')
        if cache_control == 'none' or 'no-cache' in cache_control:
            recommendations.append({
                'category': 'Caching',
                'priority': 'high',
                'recommendation': 'Implement browser caching',
                'actions': [
                    'Set appropriate Cache-Control headers',
                    'Use ETags for cache validation',
                    'Set expiration dates for static resources',
                    'Implement service worker for offline caching'
                ]
            })
        
        # Image optimization
        total_images = resources.get('total_images', 0)
        if total_images > 0:
            recommendations.append({
                'category': 'Image Optimization',
                'priority': 'medium',
                'recommendation': 'Optimize images for web',
                'actions': [
                    'Use modern image formats (WebP, AVIF)',
                    'Implement responsive images with srcset',
                    'Compress images without losing quality',
                    'Use lazy loading for below-the-fold images',
                    'Consider using image CDN services'
                ]
            })
        
        # JavaScript optimization
        scripts = resources.get('resources', {}).get('scripts', [])
        if scripts:
            async_scripts = sum(1 for script in scripts if script.get('async'))
            defer_scripts = sum(1 for script in scripts if script.get('defer'))
            
            if len(scripts) > async_scripts + defer_scripts:
                recommendations.append({
                    'category': 'JavaScript Optimization',
                    'priority': 'medium',
                    'recommendation': 'Optimize JavaScript loading',
                    'actions': [
                        'Use async or defer attributes on script tags',
                        'Minify JavaScript files',
                        'Bundle and compress JavaScript',
                        'Remove unused JavaScript code',
                        'Load critical JavaScript inline'
                    ]
                })
        
        # CSS optimization
        stylesheets = resources.get('total_stylesheets', 0)
        if stylesheets > 5:
            recommendations.append({
                'category': 'CSS Optimization',
                'priority': 'medium',
                'recommendation': 'Optimize CSS delivery',
                'actions': [
                    'Combine CSS files to reduce HTTP requests',
                    'Minify CSS files',
                    'Remove unused CSS',
                    'Inline critical CSS',
                    'Use media queries for conditional loading'
                ]
            })
        
        return recommendations
    
    async def _calculate_performance_score(self, analysis: Dict[str, Any]) -> int:
        """Calculate overall performance score (0-100)"""
        lighthouse_metrics = analysis.get('lighthouse_metrics', {})
        issues = analysis.get('performance_issues', [])
        
        base_score = lighthouse_metrics.get('performance', 100)
        
        # Deduct points for issues
        high_severity_issues = sum(1 for issue in issues if issue.get('severity') == 'high')
        medium_severity_issues = sum(1 for issue in issues if issue.get('severity') == 'medium')
        low_severity_issues = sum(1 for issue in issues if issue.get('severity') == 'low')
        
        penalty = (high_severity_issues * 15) + (medium_severity_issues * 8) + (low_severity_issues * 3)
        
        final_score = max(0, min(100, base_score - penalty))
        
        return int(final_score)

# Global instance

speed_analyzer = WebSpeedAnalyzer()
