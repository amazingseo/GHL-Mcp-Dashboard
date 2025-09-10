import asyncio
import logging
from typing import Dict, List, Optional, Any
import statistics
from datetime import datetime

logger = logging.getLogger(__name__)

class TrafficEstimator:
    """Estimates website traffic using multiple methodologies."""
    
    def __init__(self):
        self.estimation_methods = [
            'keyword_based',
            'position_based',
            'similarity_based'
        ]
    
    async def estimate_traffic(self, domain: str, serp_data: Dict[str, Any]) -> Dict[str, Any]:
        """Estimate monthly organic traffic for domain."""
        logger.info(f"Estimating traffic for {domain}")
        
        estimates = {}
        
        # Method 1: Keyword-based estimation
        keyword_estimate = await self._estimate_from_keywords(serp_data.get('keywords', []))
        estimates['keyword_based'] = keyword_estimate
        
        # Method 2: Position-based estimation
        position_estimate = await self._estimate_from_positions(serp_data.get('keywords', []))
        estimates['position_based'] = position_estimate
        
        # Method 3: Similarity-based estimation (simplified)
        similarity_estimate = await self._estimate_from_similarity(domain, serp_data)
        estimates['similarity_based'] = similarity_estimate
        
        # Calculate final estimate and confidence
        final_estimate, confidence = self._calculate_final_estimate(estimates)
        
        return {
            'monthly_organic_traffic': final_estimate,
            'confidence_score': confidence,
            'estimation_method': 'multi_method_average',
            'method_estimates': estimates,
            'traffic_breakdown': await self._calculate_traffic_breakdown(serp_data.get('keywords', []))
        }
    
    async def _estimate_from_keywords(self, keywords: List[Dict]) -> int:
        """Estimate traffic based on keyword search volumes and CTR."""
        if not keywords:
            return 0
        
        total_traffic = 0
        
        # CTR rates by position (industry averages)
        ctr_by_position = {
            1: 0.284, 2: 0.155, 3: 0.106, 4: 0.074, 5: 0.053,
            6: 0.040, 7: 0.031, 8: 0.025, 9: 0.020, 10: 0.016
        }
        
        for keyword_data in keywords:
            search_volume = keyword_data.get('search_volume', 0)
            position = keyword_data.get('position', 10)
            
            if search_volume and position:
                ctr = ctr_by_position.get(position, 0.01)  # Default 1% for positions > 10
                estimated_clicks = search_volume * ctr
                total_traffic += estimated_clicks
        
        return int(total_traffic)
    
    async def _estimate_from_positions(self, keywords: List[Dict]) -> int:
        """Estimate traffic based on ranking positions and average search volumes."""
        if not keywords:
            return 0
        
        # Position scoring (higher positions get higher traffic multipliers)
        position_scores = {
            1: 1000, 2: 600, 3: 400, 4: 250, 5: 180,
            6: 130, 7: 100, 8: 80, 9: 60, 10: 50
        }
        
        total_score = 0
        for keyword_data in keywords:
            position = keyword_data.get('position', 10)
            score = position_scores.get(position, 30)  # Default score for lower positions
            total_score += score
        
        # Convert score to traffic estimate (calibrated multiplier)
        estimated_traffic = total_score * 2.5
        return int(estimated_traffic)
    
    async def _estimate_from_similarity(self, domain: str, serp_data: Dict) -> int:
        """Estimate traffic based on similar domain patterns."""
        # Simplified similarity estimation
        # In production, this would use ML models trained on actual traffic data
        
        keyword_count = len(serp_data.get('keywords', []))
        avg_position = self._calculate_average_position(serp_data.get('keywords', []))
        
        # Base traffic estimate based on domain characteristics
        if '.' in domain:
            tld = domain.split('.')[-1]
            tld_multipliers = {
                'com': 1.2, 'org': 0.8, 'net': 0.9, 'edu': 0.7, 
                'gov': 0.6, 'io': 1.1, 'co': 1.0
            }
            multiplier = tld_multipliers.get(tld, 1.0)
        else:
            multiplier = 1.0
        
        # Estimate based on keyword count and average position
        base_estimate = keyword_count * 200 * multiplier
        position_adjustment = max(0.1, (11 - avg_position) / 10)
        
        final_estimate = base_estimate * position_adjustment
        return int(final_estimate)
    
    def _calculate_average_position(self, keywords: List[Dict]) -> float:
        """Calculate average ranking position."""
        positions = [kw.get('position', 10) for kw in keywords if kw.get('position')]
        return statistics.mean(positions) if positions else 10.0
    
    def _calculate_final_estimate(self, estimates: Dict[str, int]) -> tuple:
        """Calculate final estimate and confidence score."""
        valid_estimates = [v for v in estimates.values() if v > 0]
        
        if not valid_estimates:
            return 0, 0.0
        
        # Use median to reduce impact of outliers
        final_estimate = int(statistics.median(valid_estimates))
        
        # Calculate confidence based on agreement between methods
        if len(valid_estimates) == 1:
            confidence = 0.3
        else:
            # Calculate coefficient of variation
            mean_est = statistics.mean(valid_estimates)
            std_est = statistics.stdev(valid_estimates) if len(valid_estimates) > 1 else 0
            cv = std_est / mean_est if mean_est > 0 else 1
            
            # Higher agreement (lower CV) = higher confidence
            confidence = max(0.1, min(0.9, 1 - cv))
        
        return final_estimate, confidence
    
    async def _calculate_traffic_breakdown(self, keywords: List[Dict]) -> Dict[str, int]:
        """Break down traffic by different categories."""
        breakdown = {
            'branded_traffic': 0,
            'commercial_traffic': 0,
            'informational_traffic': 0,
            'long_tail_traffic': 0
        }
        
        for keyword_data in keywords:
            keyword = keyword_data.get('keyword', '').lower()
            search_volume = keyword_data.get('search_volume', 0)
            position = keyword_data.get('position', 10)
            
            # Simple CTR calculation
            ctr = max(0.01, (11 - position) * 0.03)
            estimated_clicks = search_volume * ctr if search_volume else 0
            
            # Categorize keyword
            if any(brand in keyword for brand in ['brand', 'company', 'official']):
                breakdown['branded_traffic'] += estimated_clicks
            elif any(comm in keyword for comm in ['buy', 'price', 'cost', 'cheap', 'best']):
                breakdown['commercial_traffic'] += estimated_clicks
            elif len(keyword.split()) >= 4:
                breakdown['long_tail_traffic'] += estimated_clicks
            else:
                breakdown['informational_traffic'] += estimated_clicks
        
        # Convert to integers
        return {k: int(v) for k, v in breakdown.items()}