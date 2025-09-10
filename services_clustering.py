import asyncio
import logging
from typing import Dict, List, Any, Optional, Tuple
import numpy as np
from collections import Counter, defaultdict
import re
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
import warnings

# Suppress sklearn warnings
warnings.filterwarnings('ignore')

logger = logging.getLogger(__name__)

class KeywordClusterer:
    """Advanced keyword clustering using TF-IDF and KMeans."""
    
    def __init__(self):
        self.min_cluster_size = 3
        self.max_clusters = 15
        self.vectorizer = None
        self.cluster_model = None
    
    async def cluster_keywords(self, keywords: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Cluster keywords into topic groups."""
        logger.info(f"Clustering {len(keywords)} keywords")
        
        if not keywords or len(keywords) < self.min_cluster_size:
            return self._create_single_cluster(keywords)
        
        # Extract keyword text
        keyword_texts = [kw.get('keyword', '') for kw in keywords if kw.get('keyword')]
        
        if len(keyword_texts) < self.min_cluster_size:
            return self._create_single_cluster(keywords)
        
        try:
            # Preprocess keywords
            processed_keywords = [self._preprocess_keyword(kw) for kw in keyword_texts]
            
            # Create TF-IDF vectors
            tfidf_matrix = await self._create_tfidf_vectors(processed_keywords)
            
            if tfidf_matrix is None:
                return self._create_single_cluster(keywords)
            
            # Find optimal number of clusters
            optimal_k = await self._find_optimal_clusters(tfidf_matrix)
            
            # Perform clustering
            cluster_labels = await self._perform_clustering(tfidf_matrix, optimal_k)
            
            # Create cluster analysis
            clusters = await self._analyze_clusters(keywords, cluster_labels)
            
            return {
                'clusters': clusters,
                'cluster_count': len(clusters),
                'total_keywords': len(keywords),
                'clustering_method': 'kmeans_tfidf',
                'topics': [cluster['topic_name'] for cluster in clusters]
            }
            
        except Exception as e:
            logger.error(f"Clustering failed: {str(e)}")
            return self._create_single_cluster(keywords)
    
    def _preprocess_keyword(self, keyword: str) -> str:
        """Preprocess keyword for clustering."""
        # Convert to lowercase
        keyword = keyword.lower()
        
        # Remove special characters except spaces and hyphens
        keyword = re.sub(r'[^\w\s\-]', ' ', keyword)
        
        # Replace multiple spaces with single space
        keyword = re.sub(r'\s+', ' ', keyword)
        
        return keyword.strip()
    
    async def _create_tfidf_vectors(self, keywords: List[str]) -> Optional[np.ndarray]:
        """Create TF-IDF vectors from keywords."""
        try:
            # Configure TF-IDF vectorizer
            self.vectorizer = TfidfVectorizer(
                max_features=1000,
                stop_words='english',
                ngram_range=(1, 3),  # Include 1-3 gram phrases
                max_df=0.8,  # Ignore terms in >80% of documents
                min_df=1,    # Include terms in at least 1 document
                lowercase=True,
                token_pattern=r'\b[a-zA-Z]{2,}\b'  # Only alphabetic tokens
            )
            
            # Fit and transform keywords
            tfidf_matrix = self.vectorizer.fit_transform(keywords)
            
            if tfidf_matrix.shape[1] == 0:
                return None
                
            return tfidf_matrix.toarray()
            
        except Exception as e:
            logger.error(f"TF-IDF vectorization failed: {str(e)}")
            return None
    
    async def _find_optimal_clusters(self, tfidf_matrix: np.ndarray) -> int:
        """Find optimal number of clusters using silhouette analysis."""
        n_samples = tfidf_matrix.shape[0]
        
        # Determine range of k values to test
        max_k = min(self.max_clusters, n_samples - 1)
        min_k = min(2, n_samples - 1)
        
        if min_k >= max_k:
            return 2
        
        best_k = min_k
        best_score = -1
        
        for k in range(min_k, max_k + 1):
            try:
                kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
                cluster_labels = kmeans.fit_predict(tfidf_matrix)
                
                # Skip if all points in one cluster
                if len(set(cluster_labels)) < 2:
                    continue
                
                # Calculate silhouette score
                score = silhouette_score(tfidf_matrix, cluster_labels)
                
                if score > best_score:
                    best_score = score
                    best_k = k
                    
            except Exception as e:
                logger.warning(f"Silhouette analysis failed for k={k}: {str(e)}")
                continue
        
        return best_k
    
    async def _perform_clustering(self, tfidf_matrix: np.ndarray, n_clusters: int) -> np.ndarray:
        """Perform KMeans clustering."""
        self.cluster_model = KMeans(
            n_clusters=n_clusters,
            random_state=42,
            n_init=10,
            max_iter=300
        )
        
        cluster_labels = self.cluster_model.fit_predict(tfidf_matrix)
        return cluster_labels
    
    async def _analyze_clusters(self, keywords: List[Dict], cluster_labels: np.ndarray) -> List[Dict[str, Any]]:
        """Analyze and label clusters."""
        clusters = []
        
        # Group keywords by cluster
        cluster_groups = defaultdict(list)
        for i, label in enumerate(cluster_labels):
            if i < len(keywords):
                cluster_groups[label].append(keywords[i])
        
        # Analyze each cluster
        for cluster_id, cluster_keywords in cluster_groups.items():
            if len(cluster_keywords) < 2:  # Skip tiny clusters
                continue
            
            # Generate topic name
            topic_name = await self._generate_topic_name(cluster_keywords)
            
            # Calculate cluster statistics
            search_volumes = [kw.get('search_volume', 0) for kw in cluster_keywords if kw.get('search_volume')]
            avg_search_volume = int(np.mean(search_volumes)) if search_volumes else None
            
            positions = [kw.get('position', 0) for kw in cluster_keywords if kw.get('position')]
            avg_position = round(np.mean(positions), 1) if positions else None
            
            # Determine dominant intent
            dominant_intent = await self._determine_cluster_intent(cluster_keywords)
            
            cluster_info = {
                'cluster_id': int(cluster_id),
                'topic_name': topic_name,
                'keywords': [kw.get('keyword', '') for kw in cluster_keywords],
                'keyword_count': len(cluster_keywords),
                'avg_search_volume': avg_search_volume,
                'avg_position': avg_position,
                'dominant_intent': dominant_intent,
                'top_keywords': sorted(
                    cluster_keywords,
                    key=lambda x: x.get('search_volume', 0),
                    reverse=True
                )[:5]
            }
            
            clusters.append(cluster_info)
        
        # Sort clusters by keyword count (largest first)
        clusters.sort(key=lambda x: x['keyword_count'], reverse=True)
        
        return clusters
    
    async def _generate_topic_name(self, cluster_keywords: List[Dict]) -> str:
        """Generate a topic name for the cluster."""
        # Extract keyword texts
        keyword_texts = [kw.get('keyword', '') for kw in cluster_keywords]
        
        # Find common words
        all_words = []
        for keyword in keyword_texts:
            words = keyword.lower().split()
            all_words.extend([word for word in words if len(word) > 2])
        
        # Count word frequency
        word_counts = Counter(all_words)
        
        # Get most common meaningful words
        stop_words = {'the', 'and', 'or', 'for', 'to', 'in', 'on', 'at', 'by', 'with'}
        common_words = [
            word for word, count in word_counts.most_common(10)
            if word not in stop_words and count > 1
        ]
        
        if common_words:
            # Create topic name from most common words
            if len(common_words) >= 2:
                topic_name = f"{common_words[0].title()} & {common_words[1].title()}"
            else:
                topic_name = f"{common_words[0].title()} Related"
        else:
            # Fallback: use first keyword
            first_keyword = keyword_texts[0] if keyword_texts else "Mixed Topics"
            topic_name = first_keyword.title()
        
        return topic_name
    
    async def _determine_cluster_intent(self, cluster_keywords: List[Dict]) -> str:
        """Determine the dominant search intent for the cluster."""
        intent_indicators = {
            'informational': ['how', 'what', 'why', 'guide', 'tutorial', 'tips', 'learn'],
            'commercial': ['best', 'top', 'review', 'compare', 'vs', 'alternative'],
            'transactional': ['buy', 'price', 'cost', 'cheap', 'discount', 'deal', 'shop'],
            'navigational': ['login', 'sign', 'account', 'dashboard', 'app']
        }
        
        intent_scores = defaultdict(int)
        
        for keyword_data in cluster_keywords:
            keyword = keyword_data.get('keyword', '').lower()
            
            for intent, indicators in intent_indicators.items():
                for indicator in indicators:
                    if indicator in keyword:
                        intent_scores[intent] += 1
        
        if intent_scores:
            dominant_intent = max(intent_scores, key=intent_scores.get)
            return dominant_intent
        
        return 'informational'  # Default intent
    
    def _create_single_cluster(self, keywords: List[Dict]) -> Dict[str, Any]:
        """Create a single cluster when clustering is not possible."""
        if not keywords:
            return {
                'clusters': [],
                'cluster_count': 0,
                'total_keywords': 0,
                'clustering_method': 'single_cluster',
                'topics': []
            }
        
        # Create one cluster with all keywords
        cluster = {
            'cluster_id': 0,
            'topic_name': 'General Keywords',
            'keywords': [kw.get('keyword', '') for kw in keywords],
            'keyword_count': len(keywords),
            'avg_search_volume': None,
            'avg_position': None,
            'dominant_intent': 'mixed',
            'top_keywords': keywords[:5]
        }
        
        return {
            'clusters': [cluster],
            'cluster_count': 1,
            'total_keywords': len(keywords),
            'clustering_method': 'single_cluster',
            'topics': ['General Keywords']
        }