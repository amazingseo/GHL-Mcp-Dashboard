from fastapi import FastAPI, Request, Depends, HTTPException, Form, Query
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
import uvicorn
import asyncio
from datetime import datetime
import logging
from typing import Optional

from config import settings
from models_db import init_db, get_db
from services_serp_client import SERPClient
from services_traffic_estimator import TrafficEstimator
from services_scraper import WebScraper
from services_nlp import NLPProcessor
from services_clustering import KeywordClusterer
from services_gap_analysis import ContentGapAnalyzer
from services_pdf import PDFGenerator
from services_speed_analyzer import WebSpeedAnalyzer, speed_analyzer
from services_seo_analyzer import SEOAnalyzer, seo_analyzer
from models_schemas import AnalysisRequest, CompetitorReport
from models_report import ReportRepository
from deps import rate_limiter, get_client_ip

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="AI2Flows SEO & Speed Analysis Tool",
    description="Comprehensive SEO analysis and website speed optimization tool by AI2Flows",
    version="2.0.0"
)

# Static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Initialize services
serp_client = SERPClient()
traffic_estimator = TrafficEstimator()
web_scraper = WebScraper()
nlp_processor = NLPProcessor()
clusterer = KeywordClusterer()
gap_analyzer = ContentGapAnalyzer()
pdf_generator = PDFGenerator()

@app.on_event("startup")
async def startup_event():
    """Initialize database and services on startup."""
    await init_db()
    logger.info("AI2Flows SEO & Speed Analysis Tool started successfully")

# API Endpoints for GHL Integration

@app.post("/api/speed-check")
async def api_speed_check(
    request: Request,
    url: str = Form(...),
    db: AsyncSession = Depends(get_db)
):
    """API endpoint for speed analysis - GHL compatible"""
    try:
        # Rate limiting
        await rate_limiter(request)
        
        logger.info(f"API Speed check requested for: {url}")
        
        async with speed_analyzer:
            speed_results = await speed_analyzer.analyze_speed(url)
        
        # Log analytics
        client_ip = get_client_ip(request)
        from deps import log_analytics_event
        await log_analytics_event(
            db, "speed_analysis", url, client_ip, 
            {"score": speed_results.get('score', 0)}
        )
        
        return JSONResponse({
            "success": True,
            "data": speed_results,
            "message": "Speed analysis completed successfully"
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"API Speed analysis failed for {url}: {str(e)}")
        return JSONResponse({
            "success": False,
            "error": str(e),
            "message": "Speed analysis failed"
        }, status_code=500)

@app.post("/api/seo-analysis")
async def api_seo_analysis(
    request: Request,
    url: str = Form(...),
    is_own_site: bool = Form(False),
    db: AsyncSession = Depends(get_db)
):
    """API endpoint for SEO analysis - GHL compatible"""
    try:
        # Rate limiting
        await rate_limiter(request)
        
        logger.info(f"API SEO analysis requested for: {url} (own_site: {is_own_site})")
        
        async with seo_analyzer:
            seo_results = await seo_analyzer.analyze_seo(url, is_own_site)
        
        # Log analytics
        client_ip = get_client_ip(request)
        from deps import log_analytics_event
        await log_analytics_event(
            db, "seo_analysis", url, client_ip,
            {"score": seo_results.get('seo_score', 0), "is_own_site": is_own_site}
        )
        
        return JSONResponse({
            "success": True,
            "data": seo_results,
            "message": "SEO analysis completed successfully"
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"API SEO analysis failed for {url}: {str(e)}")
        return JSONResponse({
            "success": False,
            "error": str(e),
            "message": "SEO analysis failed"
        }, status_code=500)

@app.post("/api/competitor-analysis")
async def api_competitor_analysis(
    request: Request,
    domain: str = Form(...),
    country: str = Form("US"),
    db: AsyncSession = Depends(get_db)
):
    """API endpoint for competitor analysis - GHL compatible"""
    try:
        # Rate limiting
        await rate_limiter(request)
        
        logger.info(f"API Competitor analysis requested for: {domain}")
        
        # Original competitor analysis logic
        serp_data = await serp_client.get_domain_keywords(domain)
        
        if not serp_data or not serp_data.get('keywords'):
            return JSONResponse({
                "success": False,
                "error": "No keyword data found for this domain",
                "message": "Unable to find ranking data"
            }, status_code=400)
        
        # Enhanced analysis with country-specific data
        scraped_data = await web_scraper.scrape_domain_pages(domain, serp_data['top_urls'][:10])
        traffic_estimate = await traffic_estimator.estimate_traffic(domain, serp_data)
        nlp_results = await nlp_processor.process_content(scraped_data['content'])
        clusters = await clusterer.cluster_keywords(serp_data['keywords'])
        gap_analysis = await gap_analyzer.analyze_gaps(
            competitor_topics=clusters['topics'],
            competitor_keywords=serp_data['keywords']
        )
        
        # Add country-specific insights
        analysis_data = {
            "domain": domain,
            "country": country,
            "analysis_date": datetime.utcnow().isoformat(),
            "traffic_estimate": traffic_estimate,
            "keywords": serp_data['keywords'][:50],
            "top_pages": serp_data['top_urls'][:10],
            "content_summary": nlp_results,
            "keyword_clusters": clusters,
            "content_gaps": gap_analysis,
            "competitor_insights": {
                "total_keywords": len(serp_data['keywords']),
                "avg_position": sum(kw.get('position', 0) for kw in serp_data['keywords']) / len(serp_data['keywords']) if serp_data['keywords'] else 0,
                "top_ranking_keywords": [kw for kw in serp_data['keywords'] if kw.get('position', 11) <= 3]
            }
        }
        
        # Log analytics
        client_ip = get_client_ip(request)
        from deps import log_analytics_event
        await log_analytics_event(
            db, "competitor_analysis", domain, client_ip,
            {"country": country, "keywords_found": len(serp_data['keywords'])}
        )
        
        return JSONResponse({
            "success": True,
            "data": analysis_data,
            "message": "Competitor analysis completed successfully"
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"API Competitor analysis failed for {domain}: {str(e)}")
        return JSONResponse({
            "success": False,
            "error": str(e),
            "message": "Competitor analysis failed"
        }, status_code=500)

# Web Interface Endpoints (for testing)

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Main page with analysis options."""
    return templates.TemplateResponse("index_new.html", {"request": request})

@app.get("/speed-test", response_class=HTMLResponse)
async def speed_test_page(request: Request):
    """Speed test page."""
    return templates.TemplateResponse("speed_test.html", {"request": request})

@app.get("/seo-analysis", response_class=HTMLResponse)
async def seo_analysis_page(request: Request):
    """SEO analysis page."""
    return templates.TemplateResponse("seo_analysis.html", {"request": request})

@app.get("/competitor-analysis", response_class=HTMLResponse)
async def competitor_analysis_page(request: Request):
    """Competitor analysis page."""
    return templates.TemplateResponse("competitor_analysis.html", {"request": request})

# Legacy endpoints (maintain compatibility)
@app.post("/analyze")
async def analyze_competitor(
    domain: str = Form(...),
    db: AsyncSession = Depends(get_db)
):
    """Legacy competitor analysis endpoint."""
    return RedirectResponse(url=f"/api/competitor-analysis", status_code=307)

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy", 
        "timestamp": datetime.utcnow(),
        "service": "AI2Flows SEO & Speed Analysis Tool",
        "version": "2.0.0"
    }

@app.get("/api/health")
async def api_health_check():
    """API Health check for GHL integration."""
    return JSONResponse({
        "success": True,
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "message": "AI2Flows SEO & Speed Analysis API is running"
    })

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )