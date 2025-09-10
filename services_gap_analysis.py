import asyncio
import logging
from typing import Dict, List, Any, Optional, Set
from collections import Counter
import re

from config import settings, SEED_TOPICS

logger = logging.getLogger(__name__)

class ContentGapAnalyzer:
    """Analyzes content gaps between competitor and ai2flows.com topics."""
    
    def __init__(self):
        self.seed_topics = SEED_TOPICS
        self.workflow_keywords = [
            'automation', 'workflow', 'process', 'efficiency', 'optimization',
            'productivity', 'integration', 'streamline', 'digital transformation',
            'business process', 'task management', 'workflow design'
        ]
    
    async def analyze_gaps(
        self, 
        competitor_topics: List[str], 
        competitor_keywords: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Analyze content gaps and opportunities."""
        logger.info("Analyzing content gaps")
        
        # Extract competitor keyword strings
        competitor_kw_strings = [kw.get('keyword', '') for kw in competitor_keywords]
        
        # Find missing topics
        missing_topics = await self._find_missing_topics(competitor_topics)
        
        # Find opportunity keywords
        opportunity_keywords = await self._find_opportunity_keywords(competitor_kw_strings)
        
        # Generate suggested content
        suggested_content = await self._generate_content_suggestions(
            missing_topics, opportunity_keywords
        )
        
        # Generate FAQ questions
        faq_questions = await self._generate_faq_questions(
            competitor_topics, competitor_kw_strings
        )
        
        return {
            'missing_topics': missing_topics,
            'opportunity_keywords': opportunity_keywords,
            'suggested_content': suggested_content,
            'faq_questions': faq_questions,
            'gap_analysis_summary': await self._create_gap_summary(
                missing_topics, opportunity_keywords
            ),
            'priority_score': await self._calculate_priority_score(
                missing_topics, opportunity_keywords
            )
        }
    
    async def _find_missing_topics(self, competitor_topics: List[str]) -> List[str]:
        """Find ai2flows topics not covered by competitor."""
        if not competitor_topics:
            return self.seed_topics[:10]  # Return top seed topics
        
        # Normalize topics for comparison
        competitor_topics_lower = [topic.lower() for topic in competitor_topics]
        
        missing_topics = []
        for seed_topic in self.seed_topics:
            is_covered = False
            seed_words = seed_topic.lower().split()
            
            # Check if any seed topic words appear in competitor topics
            for comp_topic in competitor_topics_lower:
                if any(word in comp_topic for word in seed_words):
                    is_covered = True
                    break
            
            if not is_covered:
                missing_topics.append(seed_topic)
        
        return missing_topics[:15]  # Return top 15 missing topics
    
    async def _find_opportunity_keywords(self, competitor_keywords: List[str]) -> List[str]:
        """Find workflow-related keywords not used by competitor."""
        if not competitor_keywords:
            return self.workflow_keywords[:10]
        
        # Combine all competitor keywords into one string
        all_competitor_text = ' '.join(competitor_keywords).lower()
        
        # Find workflow keywords not mentioned by competitor
        opportunity_keywords = []
        
        for workflow_kw in self.workflow_keywords:
            if workflow_kw not in all_competitor_text:
                opportunity_keywords.append(workflow_kw)
        
        # Add topic-specific opportunities
        topic_opportunities = [
            'workflow automation tools',
            'business process optimization',
            'automated workflow templates',
            'workflow management software',
            'process automation solutions',
            'digital workflow design',
            'workflow integration platforms',
            'automated business processes',
            'workflow efficiency tips',
            'process improvement strategies'
        ]
        
        for opp_kw in topic_opportunities:
            if not any(word in all_competitor_text for word in opp_kw.split()):
                opportunity_keywords.append(opp_kw)
        
        return opportunity_keywords[:20]
    
    async def _generate_content_suggestions(
        self, 
        missing_topics: List[str], 
        opportunity_keywords: List[str]
    ) -> List[str]:
        """Generate content suggestions based on gaps."""
        content_suggestions = []
        
        # Content based on missing topics
        for topic in missing_topics[:5]:
            suggestions = [
                f"The Ultimate Guide to {topic.title()}",
                f"How {topic.title()} Can Transform Your Business",
                f"Best Practices for {topic.title()} Implementation",
                f"{topic.title()}: Common Mistakes and How to Avoid Them"
            ]
            content_suggestions.extend(suggestions[:2])  # Add 2 per topic
        
        # Content based on opportunity keywords
        for keyword in opportunity_keywords[:5]:
            suggestions = [
                f"Complete Guide to {keyword.title()}",
                f"{keyword.title()}: Tips for Success",
                f"Why {keyword.title()} Matters for Your Business"
            ]
            content_suggestions.append(suggestions[0])  # Add 1 per keyword
        
        # Add ai2flows specific content ideas
        ai2flows_content = [
            "How to Build Effective Workflows with AI2Flows",
            "Workflow Templates for Common Business Processes",
            "Integrating AI2Flows with Your Existing Tools",
            "ROI Calculator: Measuring Workflow Automation Success",
            "Case Studies: Successful Workflow Implementations"
        ]
        
        content_suggestions.extend(ai2flows_content[:3])
        
        return content_suggestions[:15]
    
    async def _generate_faq_questions(
        self, 
        competitor_topics: List[str], 
        competitor_keywords: List[str]
    ) -> List[str]:
        """Generate FAQ questions based on analysis."""
        faq_questions = []
        
        # General workflow FAQs
        general_faqs = [
            "What is workflow automation and how does it work?",
            "How can workflow automation improve business efficiency?",
            "What are the best practices for implementing workflow automation?",
            "How do I choose the right workflow automation tools?",
            "What are the common challenges in workflow automation?",
            "How much does workflow automation typically cost?",
            "Can workflow automation integrate with existing systems?",
            "What ROI can I expect from workflow automation?",
            "How long does it take to implement workflow automation?",
            "Is workflow automation suitable for small businesses?"
        ]
        
        # Topic-specific FAQs
        for topic in competitor_topics[:3]:
            topic_faqs = [
                f"How does {topic.lower()} relate to workflow automation?",
                f"What are the benefits of automating {topic.lower()}?",
                f"Can AI2Flows help with {topic.lower()}?"
            ]
            faq_questions.extend(topic_faqs[:1])  # Add 1 per topic
        
        # Keyword-specific FAQs
        workflow_faqs = [
            "How do I create effective workflow templates?",
            "What's the difference between workflow automation and business process automation?",
            "How can I measure workflow efficiency?",
            "What are the key features to look for in workflow software?",
            "How do I handle exceptions in automated workflows?"
        ]
        
        faq_questions.extend(general_faqs[:5])
        faq_questions.extend(workflow_faqs[:5])
        
        return faq_questions[:15]
    
    async def _create_gap_summary(
        self, 
        missing_topics: List[str], 
        opportunity_keywords: List[str]
    ) -> str:
        """Create a summary of the gap analysis."""
        summary_parts = []
        
        if missing_topics:
            summary_parts.append(
                f"Found {len(missing_topics)} topic opportunities not covered by competitor, "
                f"including {', '.join(missing_topics[:3])}."
            )
        
        if opportunity_keywords:
            summary_parts.append(
                f"Identified {len(opportunity_keywords)} keyword opportunities for workflow automation content."
            )
        
        summary_parts.append(
            "AI2Flows has significant opportunities to create content around workflow automation, "
            "business process optimization, and digital transformation topics that competitors are not fully addressing."
        )
        
        return ' '.join(summary_parts)
    
    async def _calculate_priority_score(
        self, 
        missing_topics: List[str], 
        opportunity_keywords: List[str]
    ) -> float:
        """Calculate priority score for content gap opportunities."""
        base_score = 0.0
        
        # Score based on missing topics
        if missing_topics:
            topic_score = min(1.0, len(missing_topics) / 10) * 0.4
            base_score += topic_score
        
        # Score based on opportunity keywords
        if opportunity_keywords:
            keyword_score = min(1.0, len(opportunity_keywords) / 20) * 0.4
            base_score += keyword_score
        
        # Workflow automation bonus (AI2Flows specialty)
        workflow_bonus = 0.2
        base_score += workflow_bonus
        
        return round(min(1.0, base_score), 2)