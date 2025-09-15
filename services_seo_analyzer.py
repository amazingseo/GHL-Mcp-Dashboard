import asyncio
import aiohttp
import logging
from typing import Dict, List, Any, Optional
from urllib.parse import urljoin, urlparse
from datetime import datetime
import re
from bs4 import BeautifulSoup

from config import settings, SEED_TOPICS

logger = logging.getLogger(__name__)

class SEOAnalyzer:
    """Comprehensive SEO analysis for websites"""
    
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
    
    async def analyze_seo(self, url: str, is_own_site: bool = False) -> Dict[str, Any]:
        """Comprehensive SEO analysis"""
        logger.info(f"Starting SEO analysis for {url}")
        
        if not url.startswith(('http://', 'https://')):
            url = f'https://{url}'
        
        analysis_results = {
            'url': url,
            'is_own_site': is_own_site,
            'analysis_date': datetime.utcnow().isoformat(),
            'on_page_seo': await self._analyze_on_page_seo(url),
            'technical_seo': await self._analyze_technical_seo(url),
            'content_analysis': await self._analyze_content_quality(url),
            'meta_analysis': await self._analyze_meta_tags(url),
            'heading_structure': await self._analyze_heading_structure(url),
            'image_optimization': await self._analyze_images(url),
            'internal_linking': await self._analyze_internal_links(url),
            'seo_issues': [],
            'recommendations': [],
            'seo_score': 0
        }
        
        # Generate issues and recommendations
        analysis_results['seo_issues'] = await self._identify_seo_issues(analysis_results)
        analysis_results['recommendations'] = await self._generate_seo_recommendations(analysis_results, is_own_site)
        analysis_results['seo_score'] = await self._calculate_seo_score(analysis_results)
        
        return analysis_results
    
    async def _analyze_on_page_seo(self, url: str) -> Dict[str, Any]:
        """Analyze on-page SEO factors"""
        if not self.session:
            return {}
        
        try:
            async with self.session.get(url) as response:
                content = await response.text()
                soup = BeautifulSoup(content, 'html.parser')
                
                # Title tag analysis
                title_tag = soup.find('title')
                title = title_tag.get_text().strip() if title_tag else ""
                
                # Meta description
                meta_desc = soup.find('meta', attrs={'name': 'description'})
                meta_description = meta_desc.get('content', '').strip() if meta_desc else ""
                
                # URL structure
                parsed_url = urlparse(url)
                
                return {
                    'title': title,
                    'title_length': len(title),
                    'meta_description': meta_description,
                    'meta_description_length': len(meta_description),
                    'url_structure': {
                        'length': len(url),
                        'has_https': parsed_url.scheme == 'https',
                        'subdomain': parsed_url.hostname.split('.')[0] if '.' in parsed_url.hostname else '',
                        'path_depth': len([p for p in parsed_url.path.split('/') if p]),
                        'has_parameters': bool(parsed_url.query),
                        'readable': self._is_url_readable(parsed_url.path)
                    }
                }
                
        except Exception as e:
            logger.error(f"Error analyzing on-page SEO: {e}")
            return {'error': str(e)}
    
    async def _analyze_technical_seo(self, url: str) -> Dict[str, Any]:
        """Analyze technical SEO factors"""
        if not self.session:
            return {}
        
        try:
            # Check robots.txt
            robots_url = urljoin(url, '/robots.txt')
            robots_exists = False
            robots_content = ""
            
            try:
                async with self.session.get(robots_url) as response:
                    if response.status == 200:
                        robots_exists = True
                        robots_content = await response.text()
            except:
                pass
            
            # Check sitemap
            sitemap_url = urljoin(url, '/sitemap.xml')
            sitemap_exists = False
            sitemap_urls = 0
            
            try:
                async with self.session.get(sitemap_url) as response:
                    if response.status == 200:
                        sitemap_exists = True
                        sitemap_content = await response.text()
                        sitemap_urls = sitemap_content.count('<url>')
            except:
                pass
            
            # Analyze main page
            async with self.session.get(url) as response:
                content = await response.text()
                soup = BeautifulSoup(content, 'html.parser')
                headers = dict(response.headers)
                
                # Check for canonical tag
                canonical = soup.find('link', rel='canonical')
                canonical_url = canonical.get('href') if canonical else ""
                
                # Check for meta robots
                meta_robots = soup.find('meta', attrs={'name': 'robots'})
                robots_directives = meta_robots.get('content', '') if meta_robots else ""
                
                # Check schema markup
                schema_scripts = soup.find_all('script', type='application/ld+json')
                has_schema = len(schema_scripts) > 0
                
                # Check Open Graph tags
                og_tags = soup.find_all('meta', attrs={'property': lambda x: x and x.startswith('og:')})
                has_og_tags = len(og_tags) > 0
                
                # Check Twitter Card tags
                twitter_tags = soup.find_all('meta', attrs={'name': lambda x: x and x.startswith('twitter:')})
                has_twitter_cards = len(twitter_tags) > 0
                
                return {
                    'robots_txt': {
                        'exists': robots_exists,
                        'content_preview': robots_content[:200] if robots_content else ""
                    },
                    'sitemap': {
                        'exists': sitemap_exists,
                        'url_count': sitemap_urls
                    },
                    'canonical_url': canonical_url,
                    'meta_robots': robots_directives,
                    'schema_markup': {
                        'present': has_schema,
                        'count': len(schema_scripts)
                    },
                    'social_tags': {
                        'open_graph': has_og_tags,
                        'twitter_cards': has_twitter_cards
                    },
                    'https_enabled': url.startswith('https://'),
                    'response_headers': {
                        'content_type': headers.get('Content-Type', ''),
                        'x_robots_tag': headers.get('X-Robots-Tag', ''),
                        'cache_control': headers.get('Cache-Control', '')
                    }
                }
                
        except Exception as e:
            logger.error(f"Error analyzing technical SEO: {e}")
            return {'error': str(e)}
    
    async def _analyze_content_quality(self, url: str) -> Dict[str, Any]:
        """Analyze content quality and relevance"""
        if not self.session:
            return {}
        
        try:
            async with self.session.get(url) as response:
                content = await response.text()
                soup = BeautifulSoup(content, 'html.parser')
                
                # Remove script, style, nav, header, footer
                for element in soup(['script', 'style', 'nav', 'header', 'footer']):
                    element.decompose()
                
                # Extract main content
                main_content = ""
                content_selectors = ['main', 'article', '[role="main"]', '.content', '#content']
                
                for selector in content_selectors:
                    content_element = soup.select_one(selector)
                    if content_element:
                        main_content = content_element.get_text(separator=' ', strip=True)
                        break
                
                if not main_content:
                    body = soup.find('body')
                    main_content = body.get_text(separator=' ', strip=True) if body else ""
                
                # Analyze content
                words = main_content.split()
                sentences = re.split(r'[.!?]+', main_content)
                paragraphs = main_content.split('\n\n')
                
                # Calculate readability (simplified Flesch score)
                if len(sentences) > 0 and len(words) > 0:
                    avg_sentence_length = len(words) / len(sentences)
                    readability_score = max(0, min(100, 206.835 - (1.015 * avg_sentence_length)))
                else:
                    readability_score = 0
                
                # Keyword density analysis
                word_freq = {}
                for word in words:
                    word = word.lower().strip('.,!?";()[]{}')
                    if len(word) > 3:
                        word_freq[word] = word_freq.get(word, 0) + 1
                
                top_keywords = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:10]
                
                return {
                    'word_count': len(words),
                    'sentence_count': len([s for s in sentences if s.strip()]),
                    'paragraph_count': len([p for p in paragraphs if p.strip()]),
                    'readability_score': round(readability_score, 1),
                    'avg_words_per_sentence': round(len(words) / max(len(sentences), 1), 1),
                    'content_length_category': self._categorize_content_length(len(words)),
                    'top_keywords': [{'keyword': kw, 'frequency': freq} for kw, freq in top_keywords],
                    'content_preview': main_content[:200] + '...' if len(main_content) > 200 else main_content
                }
                
        except Exception as e:
            logger.error(f"Error analyzing content quality: {e}")
            return {'error': str(e)}
    
    async def _analyze_meta_tags(self, url: str) -> Dict[str, Any]:
        """Analyze all meta tags"""
        if not self.session:
            return {}
        
        try:
            async with self.session.get(url) as response:
                content = await response.text()
                soup = BeautifulSoup(content, 'html.parser')
                
                meta_tags = {}
                
                # Find all meta tags
                for meta in soup.find_all('meta'):
                    name = meta.get('name') or meta.get('property') or meta.get('http-equiv')
                    content_attr = meta.get('content', '')
                    
                    if name:
                        meta_tags[name] = content_attr
                
                # Specific analysis
                return {
                    'total_meta_tags': len(meta_tags),
                    'essential_tags': {
                        'description': meta_tags.get('description', ''),
                        'keywords': meta_tags.get('keywords', ''),
                        'author': meta_tags.get('author', ''),
                        'viewport': meta_tags.get('viewport', ''),
                        'robots': meta_tags.get('robots', '')
                    },
                    'og_tags': {k: v for k, v in meta_tags.items() if k.startswith('og:')},
                    'twitter_tags': {k: v for k, v in meta_tags.items() if k.startswith('twitter:')},
                    'all_tags': meta_tags
                }
                
        except Exception as e:
            logger.error(f"Error analyzing meta tags: {e}")
            return {'error': str(e)}
    
    async def _analyze_heading_structure(self, url: str) -> Dict[str, Any]:
        """Analyze heading structure (H1-H6)"""
        if not self.session:
            return {}
        
        try:
            async with self.session.get(url) as response:
                content = await response.text()
                soup = BeautifulSoup(content, 'html.parser')
                
                headings = {f'h{i}': [] for i in range(1, 7)}
                
                for level in range(1, 7):
                    for heading in soup.find_all(f'h{level}'):
                        text = heading.get_text().strip()
                        if text:
                            headings[f'h{level}'].append({
                                'text': text,
                                'length': len(text)
                            })
                
                # Analysis
                h1_count = len(headings['h1'])
                total_headings = sum(len(headings[f'h{i}']) for i in range(1, 7))
                
                return {
                    'headings': headings,
                    'h1_count': h1_count,
                    'total_headings': total_headings,
                    'structure_score': self._calculate_heading_score(headings),
                    'has_proper_hierarchy': self._check_heading_hierarchy(headings)
                }
                
        except Exception as e:
            logger.error(f"Error analyzing heading structure: {e}")
            return {'error': str(e)}
    
    async def _analyze_images(self, url: str) -> Dict[str, Any]:
        """Analyze image optimization"""
        if not self.session:
            return {}
        
        try:
            async with self.session.get(url) as response:
                content = await response.text()
                soup = BeautifulSoup(content, 'html.parser')
                
                images = soup.find_all('img')
                
                image_analysis = {
                    'total_images': len(images),
                    'images_with_alt': 0,
                    'images_without_alt': 0,
                    'images_with_title': 0,
                    'lazy_loaded_images': 0,
                    'responsive_images': 0,
                    'issues': []
                }
                
                for img in images:
                    alt = img.get('alt')
                    title = img.get('title')
                    loading = img.get('loading')
                    srcset = img.get('srcset')
                    src = img.get('src', '')
                    
                    if alt:
                        image_analysis['images_with_alt'] += 1
                    else:
                        image_analysis['images_without_alt'] += 1
                        image_analysis['issues'].append(f"Image missing alt text: {src}")
                    
                    if title:
                        image_analysis['images_with_title'] += 1
                    
                    if loading == 'lazy':
                        image_analysis['lazy_loaded_images'] += 1
                    
                    if srcset:
                        image_analysis['responsive_images'] += 1
                
                return image_analysis
                
        except Exception as e:
            logger.error(f"Error analyzing images: {e}")
            return {'error': str(e)}
    
    async def _analyze_internal_links(self, url: str) -> Dict[str, Any]:
        """Analyze internal linking structure"""
        if not self.session:
            return {}
        
        try:
            async with self.session.get(url) as response:
                content = await response.text()
                soup = BeautifulSoup(content, 'html.parser')
                
                parsed_base_url = urlparse(url)
                base_domain = parsed_base_url.netloc
                
                all_links = soup.find_all('a', href=True)
                
                internal_links = []
                external_links = []
                
                for link in all_links:
                    href = link['href']
                    text = link.get_text().strip()
                    
                    # Convert relative URLs to absolute
                    absolute_url = urljoin(url, href)
                    parsed_link = urlparse(absolute_url)
                    
                    link_data = {
                        'url': absolute_url,
                        'text': text,
                        'title': link.get('title', ''),
                        'rel': link.get('rel', [])
                    }
                    
                    if parsed_link.netloc == base_domain:
                        internal_links.append(link_data)
                    else:
                        external_links.append(link_data)
                
                return {
                    'total_links': len(all_links),
                    'internal_links': len(internal_links),
                    'external_links': len(external_links),
                    'internal_link_list': internal_links[:20],  # First 20 for review
                    'external_link_list': external_links[:10],  # First 10 for review
                    'nofollow_links': len([link for link in all_links if 'nofollow' in link.get('rel', [])])
                }
                
        except Exception as e:
            logger.error(f"Error analyzing internal links: {e}")
            return {'error': str(e)}
    
    def _is_url_readable(self, path: str) -> bool:
        """Check if URL path is human-readable"""
        # Remove leading/trailing slashes and split
        parts = path.strip('/').split('/')
        
        for part in parts:
            # Check for overly long parts or cryptic IDs
            if len(part) > 50 or re.match(r'^[0-9a-f]{8,}$', part):
                return False
            
            # Check for meaningful words (simplified)
            if len(part) > 0 and not re.match(r'^[a-zA-Z0-9-_]+$', part):
                return False
        
        return True
    
    def _categorize_content_length(self, word_count: int) -> str:
        """Categorize content length"""
        if word_count < 300:
            return "thin"
        elif word_count < 600:
            return "short"
        elif word_count < 1500:
            return "medium"
        elif word_count < 2500:
            return "long"
        else:
            return "very_long"
    
    def _calculate_heading_score(self, headings: Dict[str, List]) -> int:
        """Calculate heading structure score"""
        score = 100
        
        # Check H1
        h1_count = len(headings['h1'])
        if h1_count == 0:
            score -= 20
        elif h1_count > 1:
            score -= 10
        
        # Check if there are headings at all
        total_headings = sum(len(headings[f'h{i}']) for i in range(1, 7))
        if total_headings == 0:
            score -= 30
        elif total_headings < 3:
            score -= 10
        
        return max(0, score)
    
    def _check_heading_hierarchy(self, headings: Dict[str, List]) -> bool:
        """Check if heading hierarchy is proper"""
        has_h1 = len(headings['h1']) > 0
        
        # Simple check: if there's content, there should be at least H1
        return has_h1
    
    async def _identify_seo_issues(self, analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Identify SEO issues"""
        issues = []
        
        on_page = analysis.get('on_page_seo', {})
        technical = analysis.get('technical_seo', {})
        content = analysis.get('content_analysis', {})
        meta = analysis.get('meta_analysis', {})
        headings = analysis.get('heading_structure', {})
        images = analysis.get('image_optimization', {})
        
        # Title issues
        title_length = on_page.get('title_length', 0)
        if title_length == 0:
            issues.append({
                'category': 'Title Tag',
                'severity': 'high',
                'issue': 'Missing Title Tag',
                'description': 'Page has no title tag',
                'impact': 'Critical for search engine rankings and click-through rates'
            })
        elif title_length < 30:
            issues.append({
                'category': 'Title Tag',
                'severity': 'medium',
                'issue': 'Title Too Short',
                'description': f'Title is only {title_length} characters',
                'impact': 'May not fully describe page content'
            })
        elif title_length > 60:
            issues.append({
                'category': 'Title Tag',
                'severity': 'medium',
                'issue': 'Title Too Long',
                'description': f'Title is {title_length} characters (may be truncated)',
                'impact': 'Title may be cut off in search results'
            })
        
        # Meta description issues
        meta_desc_length = on_page.get('meta_description_length', 0)
        if meta_desc_length == 0:
            issues.append({
                'category': 'Meta Description',
                'severity': 'high',
                'issue': 'Missing Meta Description',
                'description': 'Page has no meta description',
                'impact': 'Search engines will generate their own snippet'
            })
        elif meta_desc_length < 120:
            issues.append({
                'category': 'Meta Description',
                'severity': 'medium',
                'issue': 'Meta Description Too Short',
                'description': f'Meta description is only {meta_desc_length} characters',
                'impact': 'Not utilizing full snippet space in search results'
            })
        elif meta_desc_length > 160:
            issues.append({
                'category': 'Meta Description',
                'severity': 'medium',
                'issue': 'Meta Description Too Long',
                'description': f'Meta description is {meta_desc_length} characters',
                'impact': 'Description may be truncated in search results'
            })
        
        # HTTPS issues
        if not technical.get('https_enabled', False):
            issues.append({
                'category': 'Security',
                'severity': 'high',
                'issue': 'No HTTPS',
                'description': 'Site is not using HTTPS encryption',
                'impact': 'Negative ranking factor and security concerns'
            })
        
        # Robots.txt issues
        if not technical.get('robots_txt', {}).get('exists', False):
            issues.append({
                'category': 'Technical SEO',
                'severity': 'medium',
                'issue': 'Missing Robots.txt',
                'description': 'No robots.txt file found',
                'impact': 'Cannot guide search engine crawlers'
            })
        
        # Sitemap issues
        if not technical.get('sitemap', {}).get('exists', False):
            issues.append({
                'category': 'Technical SEO',
                'severity': 'medium',
                'issue': 'Missing XML Sitemap',
                'description': 'No XML sitemap found',
                'impact': 'Harder for search engines to discover all pages'
            })
        
        # Content issues
        word_count = content.get('word_count', 0)
        if word_count < 300:
            issues.append({
                'category': 'Content',
                'severity': 'medium',
                'issue': 'Thin Content',
                'description': f'Page has only {word_count} words',
                'impact': 'May be considered low-quality by search engines'
            })
        
        # Heading issues
        h1_count = headings.get('h1_count', 0)
        if h1_count == 0:
            issues.append({
                'category': 'Content Structure',
                'severity': 'high',
                'issue': 'Missing H1 Tag',
                'description': 'Page has no H1 heading',
                'impact': 'Important for content hierarchy and SEO'
            })
        elif h1_count > 1:
            issues.append({
                'category': 'Content Structure',
                'severity': 'medium',
                'issue': 'Multiple H1 Tags',
                'description': f'Page has {h1_count} H1 tags',
                'impact': 'Can confuse search engines about main topic'
            })
        
        # Image issues
        images_without_alt = images.get('images_without_alt', 0)
        if images_without_alt > 0:
            issues.append({
                'category': 'Image Optimization',
                'severity': 'medium',
                'issue': 'Images Missing Alt Text',
                'description': f'{images_without_alt} images missing alt attributes',
                'impact': 'Poor accessibility and missed SEO opportunities'
            })
        
        return issues
    
    async def _generate_seo_recommendations(self, analysis: Dict[str, Any], is_own_site: bool) -> List[Dict[str, Any]]:
        """Generate SEO recommendations"""
        recommendations = []
        
        on_page = analysis.get('on_page_seo', {})
        technical = analysis.get('technical_seo', {})
        content = analysis.get('content_analysis', {})
        
        # Basic optimizations
        if on_page.get('title_length', 0) == 0:
            recommendations.append({
                'category': 'Title Optimization',
                'priority': 'high',
                'recommendation': 'Add a compelling title tag',
                'actions': [
                    'Create a unique title for this page (30-60 characters)',
                    'Include your primary keyword near the beginning',
                    'Make it compelling for users to click',
                    'Avoid keyword stuffing'
                ]
            })
        
        if on_page.get('meta_description_length', 0) == 0:
            recommendations.append({
                'category': 'Meta Description',
                'priority': 'high',
                'recommendation': 'Add meta description',
                'actions': [
                    'Write a compelling meta description (120-160 characters)',
                    'Include your primary keyword naturally',
                    'Make it actionable with a call-to-action',
                    'Accurately describe the page content'
                ]
            })
        
        # Technical improvements
        if not technical.get('https_enabled', False):
            recommendations.append({
                'category': 'Security & Trust',
                'priority': 'high',
                'recommendation': 'Implement HTTPS',
                'actions': [
                    'Install an SSL certificate',
                    'Redirect all HTTP traffic to HTTPS',
                    'Update internal links to use HTTPS',
                    'Update canonical URLs to HTTPS'
                ]
            })
        
        # Content improvements
        word_count = content.get('word_count', 0)
        if word_count < 600:
            recommendations.append({
                'category': 'Content Enhancement',
                'priority': 'medium',
                'recommendation': 'Expand content depth',
                'actions': [
                    'Add more comprehensive information about your topic',
                    'Include relevant subtopics and related information',
                    'Add FAQ sections to address common questions',
                    'Include examples, case studies, or tutorials',
                    'Ensure content provides real value to users'
                ]
            })
        
        # Schema markup
        if not technical.get('schema_markup', {}).get('present', False):
            recommendations.append({
                'category': 'Structured Data',
                'priority': 'medium',
                'recommendation': 'Implement Schema markup',
                'actions': [
                    'Add appropriate Schema.org markup for your content type',
                    'Include Organization schema for business information',
                    'Add Product schema if selling products',
                    'Implement FAQ schema for question/answer content',
                    'Test markup with Google\'s Rich Results Test'
                ]
            })
        
        # Site-specific recommendations for own sites
        if is_own_site:
            recommendations.extend([
                {
                    'category': 'AI2Flows Integration',
                    'priority': 'high',
                    'recommendation': 'Optimize for workflow automation keywords',
                    'actions': [
                        'Target "workflow automation" and related terms',
                        'Create content around business process optimization',
                        'Add case studies showing automation results',
                        'Include workflow templates and guides',
                        'Optimize for "digital transformation" keywords'
                    ]
                },
                {
                    'category': 'Local SEO',
                    'priority': 'medium',
                    'recommendation': 'Implement local SEO if applicable',
                    'actions': [
                        'Add location-based keywords if serving local markets',
                        'Create location-specific landing pages',
                        'Claim and optimize Google My Business listing',
                        'Encourage customer reviews',
                        'Add local structured data markup'
                    ]
                }
            ])
        
        return recommendations
    
    async def _calculate_seo_score(self, analysis: Dict[str, Any]) -> int:
        """Calculate overall SEO score"""
        score = 100
        issues = analysis.get('seo_issues', [])
        
        # Deduct points based on issue severity
        for issue in issues:
            severity = issue.get('severity', 'low')
            if severity == 'high':
                score -= 15
            elif severity == 'medium':
                score -= 8
            elif severity == 'low':
                score -= 3
        
        # Bonus points for good practices
        technical = analysis.get('technical_seo', {})
        
        if technical.get('https_enabled', False):
            score += 5
        
        if technical.get('schema_markup', {}).get('present', False):
            score += 5
        
        if technical.get('robots_txt', {}).get('exists', False):
            score += 3
        
        if technical.get('sitemap', {}).get('exists', False):
            score += 3
        
        return max(0, min(100, score))

# Global instance

seo_analyzer = SEOAnalyzer()
