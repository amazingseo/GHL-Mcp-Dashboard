import asyncio
import re
import logging
from typing import Dict, List, Any, Optional
from collections import Counter
import string

logger = logging.getLogger(__name__)

class NLPProcessor:
    """Natural Language Processing for content analysis."""
    
    def __init__(self):
        self.stop_words = {
            'a', 'an', 'and', 'are', 'as', 'at', 'be', 'by', 'for', 'from',
            'has', 'he', 'in', 'is', 'it', 'its', 'of', 'on', 'that', 'the',
            'to', 'was', 'were', 'will', 'with', 'the', 'this', 'but', 'they',
            'have', 'had', 'what', 'said', 'each', 'which', 'she', 'do',
            'how', 'their', 'if', 'up', 'out', 'many', 'then', 'them', 'these',
            'so', 'some', 'her', 'would', 'make', 'like', 'into', 'him', 'time',
            'two', 'more', 'go', 'no', 'way', 'could', 'my', 'than', 'first',
            'been', 'call', 'who', 'oil', 'sit', 'now', 'find', 'down', 'day',
            'did', 'get', 'come', 'made', 'may', 'part'
        }
        
        self.commercial_indicators = {
            'buy', 'purchase', 'order', 'price', 'cost', 'cheap', 'discount',
            'sale', 'deal', 'offer', 'shop', 'store', 'payment', 'shipping',
            'delivery', 'cart', 'checkout', 'subscribe', 'plan', 'pricing'
        }
        
        self.informational_indicators = {
            'how', 'what', 'why', 'when', 'where', 'guide', 'tutorial',
            'learn', 'understand', 'explain', 'definition', 'meaning',
            'tips', 'advice', 'help', 'information', 'knowledge', 'facts'
        }
    
    async def process_content(self, content: str) -> Dict[str, Any]:
        """Process scraped content and extract insights."""
        logger.info("Processing content with NLP")
        
        if not content:
            return self._empty_analysis()
        
        # Basic text preprocessing
        cleaned_content = self._preprocess_text(content)
        
        # Extract key information
        analysis = {
            'content_length': len(content),
            'word_count': len(cleaned_content.split()),
            'sentences': await self._extract_sentences(content),
            'keywords': await self._extract_keywords(cleaned_content),
            'topics': await self._extract_topics(cleaned_content),
            'readability_score': await self._calculate_readability(content),
            'content_type': await self._classify_content_type(cleaned_content),
            'key_phrases': await self._extract_key_phrases(cleaned_content),
            'entities': await self._extract_entities(content),
            'sentiment': await self._analyze_sentiment(content)
        }
        
        return analysis
    
    def _preprocess_text(self, text: str) -> str:
        """Clean and preprocess text."""
        # Remove HTML tags if any remain
        text = re.sub(r'<[^>]+>', '', text)
        
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove special characters but keep basic punctuation
        text = re.sub(r'[^\w\s\.\,\!\?\-]', '', text)
        
        return text.strip()
    
    async def _extract_sentences(self, content: str) -> List[str]:
        """Extract meaningful sentences from content."""
        # Simple sentence splitting
        sentences = re.split(r'[.!?]+', content)
        
        # Filter and clean sentences
        meaningful_sentences = []
        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) > 20 and len(sentence.split()) > 4:
                meaningful_sentences.append(sentence)
        
        return meaningful_sentences[:10]  # Top 10 sentences
    
    async def _extract_keywords(self, content: str) -> List[Dict[str, Any]]:
        """Extract and rank keywords from content."""
        words = content.lower().split()
        
        # Filter words
        filtered_words = []
        for word in words:
            word = word.strip(string.punctuation)
            if (len(word) >= 3 and 
                word not in self.stop_words and 
                word.isalpha()):
                filtered_words.append(word)
        
        # Count word frequency
        word_freq = Counter(filtered_words)
        
        # Create keyword list with scores
        keywords = []
        for word, freq in word_freq.most_common(20):
            # Simple scoring based on frequency and length
            score = freq * (len(word) / 10)
            
            keywords.append({
                'keyword': word,
                'frequency': freq,
                'score': round(score, 2)
            })
        
        return keywords
    
    async def _extract_topics(self, content: str) -> List[str]:
        """Extract main topics from content."""
        # Simple topic extraction based on keyword clustering
        keywords = await self._extract_keywords(content)
        
        if not keywords:
            return []
        
        # Group related keywords (simplified approach)
        topics = []
        top_keywords = [kw['keyword'] for kw in keywords[:10]]
        
        # Technology-related terms
        tech_terms = [kw for kw in top_keywords if any(tech in kw for tech in 
                     ['software', 'app', 'digital', 'online', 'tech', 'platform', 'tool'])]
        if tech_terms:
            topics.append('Technology & Software')
        
        # Business-related terms
        business_terms = [kw for kw in top_keywords if any(biz in kw for biz in 
                         ['business', 'company', 'service', 'solution', 'management', 'strategy'])]
        if business_terms:
            topics.append('Business & Services')
        
        # Marketing-related terms
        marketing_terms = [kw for kw in top_keywords if any(mkt in kw for mkt in 
                          ['marketing', 'seo', 'content', 'social', 'advertising', 'brand'])]
        if marketing_terms:
            topics.append('Marketing & Growth')
        
        # If no specific topics found, use top keywords as topics
        if not topics:
            topics = [kw.title() for kw in top_keywords[:3]]
        
        return topics[:5]
    
    async def _calculate_readability(self, content: str) -> float:
        """Calculate simple readability score."""
        sentences = len(re.findall(r'[.!?]+', content))
        words = len(content.split())
        
        if sentences == 0:
            return 0.0
        
        # Simplified Flesch Reading Ease approximation
        avg_sentence_length = words / sentences
        
        # Simple scoring: lower average sentence length = higher readability
        readability = max(0, min(100, 100 - (avg_sentence_length * 2)))
        
        return round(readability, 1)
    
    async def _classify_content_type(self, content: str) -> str:
        """Classify the type of content."""
        content_lower = content.lower()
        
        # Count indicators
        commercial_count = sum(1 for indicator in self.commercial_indicators 
                              if indicator in content_lower)
        
        informational_count = sum(1 for indicator in self.informational_indicators 
                                 if indicator in content_lower)
        
        # Classify based on indicators
        if commercial_count > informational_count * 2:
            return 'Commercial'
        elif informational_count > commercial_count * 2:
            return 'Informational'
        elif 'about' in content_lower or 'company' in content_lower:
            return 'About/Company'
        elif 'contact' in content_lower or 'phone' in content_lower:
            return 'Contact'
        else:
            return 'Mixed/Other'
    
    async def _extract_key_phrases(self, content: str) -> List[str]:
        """Extract key phrases (2-3 word combinations)."""
        words = content.lower().split()
        phrases = []
        
        # Extract 2-word phrases
        for i in range(len(words) - 1):
            phrase = f"{words[i]} {words[i+1]}"
            # Filter out phrases with stop words
            if not any(stop in phrase.split() for stop in self.stop_words):
                phrases.append(phrase)
        
        # Extract 3-word phrases
        for i in range(len(words) - 2):
            phrase = f"{words[i]} {words[i+1]} {words[i+2]}"
            if not any(stop in phrase.split() for stop in self.stop_words):
                phrases.append(phrase)
        
        # Count and return most common phrases
        phrase_counts = Counter(phrases)
        return [phrase for phrase, count in phrase_counts.most_common(10)]
    
    async def _extract_entities(self, content: str) -> List[Dict[str, str]]:
        """Extract named entities (simplified approach)."""
        entities = []
        
        # Find potential company names (capitalized words)
        company_pattern = r'\b[A-Z][a-zA-Z]+ (?:Inc|LLC|Ltd|Corp|Company|Solutions|Services|Group)\b'
        companies = re.findall(company_pattern, content)
        
        for company in set(companies):
            entities.append({
                'text': company,
                'type': 'Organization'
            })
        
        # Find potential product names (title case phrases)
        product_pattern = r'\b[A-Z][a-z]+ [A-Z][a-z]+\b'
        products = re.findall(product_pattern, content)
        
        for product in set(products[:5]):  # Limit to avoid noise
            entities.append({
                'text': product,
                'type': 'Product'
            })
        
        return entities[:10]
    
    async def _analyze_sentiment(self, content: str) -> Dict[str, Any]:
        """Analyze sentiment of content (simplified approach)."""
        positive_words = {
            'good', 'great', 'excellent', 'amazing', 'wonderful', 'fantastic',
            'best', 'perfect', 'outstanding', 'superb', 'brilliant', 'awesome',
            'love', 'like', 'enjoy', 'happy', 'satisfied', 'pleased'
        }
        
        negative_words = {
            'bad', 'terrible', 'awful', 'horrible', 'worst', 'hate', 'dislike',
            'poor', 'disappointing', 'frustrated', 'angry', 'sad', 'upset',
            'problem', 'issue', 'error', 'fail', 'broken', 'wrong'
        }
        
        words = content.lower().split()
        
        positive_count = sum(1 for word in words if word in positive_words)
        negative_count = sum(1 for word in words if word in negative_words)
        
        total_words = len(words)
        
        if total_words == 0:
            return {'sentiment': 'neutral', 'confidence': 0.0}
        
        # Calculate sentiment
        if positive_count > negative_count:
            sentiment = 'positive'
            confidence = min(0.9, (positive_count - negative_count) / total_words * 100)
        elif negative_count > positive_count:
            sentiment = 'negative'
            confidence = min(0.9, (negative_count - positive_count) / total_words * 100)
        else:
            sentiment = 'neutral'
            confidence = 0.5
        
        return {
            'sentiment': sentiment,
            'confidence': round(confidence, 2),
            'positive_indicators': positive_count,
            'negative_indicators': negative_count
        }
    
    def _empty_analysis(self) -> Dict[str, Any]:
        """Return empty analysis structure."""
        return {
            'content_length': 0,
            'word_count': 0,
            'sentences': [],
            'keywords': [],
            'topics': [],
            'readability_score': 0.0,
            'content_type': 'Unknown',
            'key_phrases': [],
            'entities': [],
            'sentiment': {'sentiment': 'neutral', 'confidence': 0.0}
        }