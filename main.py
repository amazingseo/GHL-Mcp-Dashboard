import os
import sys
import logging
import pkgutil
from pathlib import Path

# -----------------------------------------------------------------------------
# Early startup diagnostics (unchanged)
# -----------------------------------------------------------------------------
DEBUG_STARTUP = os.getenv("DEBUG_STARTUP", "1") == "1"
if DEBUG_STARTUP:
    print("DEBUG: Python:", sys.version, flush=True)
    try:
        import pydantic  # noqa: F401
        from pydantic import __version__ as _pyd_ver  # type: ignore
        print("DEBUG: pydantic version:", _pyd_ver, flush=True)
    except Exception as _e:
        print("DEBUG: pydantic import failed:", _e, flush=True)
    try:
        _ps_installed = pkgutil.find_loader("pydantic_settings") is not None
        print("DEBUG: pydantic-settings installed?:", _ps_installed, flush=True)
    except Exception as _e:
        print("DEBUG: pydantic-settings check failed:", _e, flush=True)
    try:
        cfg_path = os.path.join(os.path.dirname(__file__), "config.py")
        with open(cfg_path, "r", encoding="utf-8") as _f:
            _head = "".join(_f.readlines()[:5])
        print("DEBUG: first lines of config.py:\n" + _head, flush=True)
    except Exception as _e:
        print("DEBUG: could not read config.py:", _e, flush=True)

# Import settings FIRST
try:
    from config import settings  # noqa: F401
except Exception:
    logging.exception(
        "Failed to import settings from config.py. "
        "If you see 'BaseSettings has moved', ensure the first line of config.py is:\n"
        "from pydantic_settings import BaseSettings"
    )
    raise

from fastapi import FastAPI, Request, Depends, HTTPException, Form  # noqa: E402
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from fastapi.templating import Jinja2Templates  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402
import uvicorn  # noqa: E402
from datetime import datetime  # noqa: E402
from typing import Optional
from models_db import init_db, get_db  # noqa: E402
from services_traffic_estimator import TrafficEstimator  # noqa: E402
from services_scraper import WebScraper  # noqa: E402
from services_nlp import NLPProcessor  # noqa: E402
from services_clustering import KeywordClusterer  # noqa: E402
from services_gap_analysis import ContentGapAnalyzer  # noqa: E402
from services_pdf import PDFGenerator  # noqa: E402
from services_speed_analyzer import WebSpeedAnalyzer, speed_analyzer  # noqa: E402
from services_seo_analyzer import SEOAnalyzer, seo_analyzer  # noqa: E402
from models_schemas import AnalysisRequest  # noqa: E402
from models_report import ReportRepository, CompetitorReport  # noqa: E402
from deps import rate_limiter, get_client_ip  # noqa: E402

logging.basicConfig(level=os.getenv("LOGLEVEL", "INFO").upper())
logger = logging.getLogger("ai2flows")

# Resolve absolute paths relative to this file
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"

app = FastAPI(
    title="AI2Flows SEO & Speed Analysis Tool",
    description="Comprehensive SEO analysis and website speed optimization tool by AI2Flows",
    version="2.0.0",
)

logger.info("Resolved BASE_DIR=%s", BASE_DIR)
logger.info("Resolved STATIC_DIR=%s exists=%s", STATIC_DIR, STATIC_DIR.is_dir())
logger.info("Resolved TEMPLATES_DIR=%s exists=%s", TEMPLATES_DIR, TEMPLATES_DIR.is_dir())

# Static and templates
if STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
else:
    logger.warning("Static directory not found at %s; skipping app.mount('/static', ...)", STATIC_DIR)

if TEMPLATES_DIR.is_dir():
    templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
else:
    logger.warning("Templates directory not found at %s; some pages may not render.", TEMPLATES_DIR)
    templates = Jinja2Templates(directory=str(BASE_DIR))

# ==== keep the rest of your main.py contents below unchanged ====
# services init, endpoints, etc.

# -----------------------------------------------------------------------------
# Initialize services (lightweight constructors)
# -----------------------------------------------------------------------------
serp_client = None
traffic_estimator = TrafficEstimator()
web_scraper = WebScraper()
nlp_processor = NLPProcessor()
clusterer = KeywordClusterer()
gap_analyzer = ContentGapAnalyzer()
pdf_generator = PDFGenerator()


def get_serp_client():
    """Lazy-load the SERP client to avoid import-time crashes."""
    global serp_client
    if serp_client is not None:
        return serp_client
    try:
        from services_serp_client import SERPClient  # lazy import here
        serp_client = SERPClient()
        logger.info("Initialized SERPClient successfully")
    except Exception as e:
        logger.exception("Failed to import/initialize SERPClient; falling back to mock client: %s", e)

        class _MockSERPClient:
            async def get_domain_keywords(
                self, domain: str, country: str = "US", language: str = "en", location: Optional[str] = None
            ):
                head = domain.split(".")[0]
                return {
                    "keywords": [
                        {"keyword": f"{head} services", "position": 1, "search_volume": 1000},
                        {"keyword": f"{head} pricing", "position": 2, "search_volume": 350},
                    ],
                    "top_urls": [
                        {"url": f"https://{domain}/", "title": f"{domain} - Home", "position": 1},
                        {"url": f"https://{domain}/about", "title": f"About {domain}", "position": 2},
                    ],
                    "provider": "mock-fallback",
                }

        serp_client = _MockSERPClient()
    return serp_client


# -----------------------------------------------------------------------------
# Lifecycle
# -----------------------------------------------------------------------------
@app.on_event("startup")
async def startup_event():
    """Initialize database and services on startup."""
    try:
        await init_db()
        logger.info("AI2Flows SEO & Speed Analysis Tool started successfully")
    except Exception as e:
        logger.exception("Database initialization failed: %s", e)
        raise


# -----------------------------------------------------------------------------
# API Endpoints for GHL Integration
# -----------------------------------------------------------------------------
@app.post("/api/speed-check")
async def api_speed_check(
    request: Request,
    url: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    """API endpoint for speed analysis - GHL compatible"""
    try:
        await rate_limiter(request)
        logger.info("API Speed check requested for: %s", url)

        async with speed_analyzer:
            speed_results = await speed_analyzer.analyze_speed(url)

        client_ip = get_client_ip(request)
        from deps import log_analytics_event

        await log_analytics_event(
            db, "speed_analysis", url, client_ip, {"score": speed_results.get("score", 0)}
        )

        return JSONResponse(
            {"success": True, "data": speed_results, "message": "Speed analysis completed successfully"}
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("API Speed analysis failed for %s: %s", url, e)
        return JSONResponse(
            {"success": False, "error": str(e), "message": "Speed analysis failed"}, status_code=500
        )


@app.post("/api/seo-analysis")
async def api_seo_analysis(
    request: Request,
    url: str = Form(...),
    is_own_site: bool = Form(False),
    db: AsyncSession = Depends(get_db),
):
    """API endpoint for SEO analysis - GHL compatible"""
    try:
        await rate_limiter(request)
        logger.info("API SEO analysis requested for: %s (own_site: %s)", url, is_own_site)

        async with seo_analyzer:
            seo_results = await seo_analyzer.analyze_seo(url, is_own_site)

        client_ip = get_client_ip(request)
        from deps import log_analytics_event

        await log_analytics_event(
            db,
            "seo_analysis",
            url,
            client_ip,
            {"score": seo_results.get("seo_score", 0), "is_own_site": is_own_site},
        )

        return JSONResponse(
            {"success": True, "data": seo_results, "message": "SEO analysis completed successfully"}
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("API SEO analysis failed for %s: %s", url, e)
        return JSONResponse(
            {"success": False, "error": str(e), "message": "SEO analysis failed"}, status_code=500
        )


@app.post("/api/competitor-analysis")
async def api_competitor_analysis(
    request: Request,
    domain: str = Form(...),
    country: str = Form("US"),
    language: str = Form("en"),
    location: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
):
    """API endpoint for competitor analysis - GHL compatible"""
    try:
        await rate_limiter(request)
        logger.info(
            "API Competitor analysis requested for: %s [%s/%s%s]",
            domain,
            country,
            language,
            f" | {location}" if location else "",
        )

        serp_data = await get_serp_client().get_domain_keywords(
            domain, country=country, language=language, location=location
        )

        if not serp_data or not serp_data.get("keywords"):
            return JSONResponse(
                {
                    "success": False,
                    "error": "No keyword data found for this domain",
                    "message": "Unable to find ranking data",
                },
                status_code=400,
            )

        scraped_data = await web_scraper.scrape_domain_pages(domain, serp_data.get("top_urls", [])[:10])
        traffic_estimate = await traffic_estimator.estimate_traffic(domain, serp_data)
        nlp_results = await nlp_processor.process_content(scraped_data.get("content", ""))
        clusters = await clusterer.cluster_keywords(serp_data["keywords"])
        gap_analysis = await gap_analyzer.analyze_gaps(
            competitor_topics=clusters.get("topics", []),
            competitor_keywords=serp_data["keywords"],
        )

        analysis_data = {
            "domain": domain,
            "country": country,
            "language": language,
            "location": location,
            "analysis_date": datetime.utcnow().isoformat(),
            "traffic_estimate": traffic_estimate,
            "keywords": serp_data["keywords"][:50],
            "top_pages": serp_data.get("top_urls", [])[:10],
            "content_summary": nlp_results,
            "keyword_clusters": clusters,
            "content_gaps": gap_analysis,
            "competitor_insights": {
                "total_keywords": len(serp_data["keywords"]),
                "avg_position": (
                    sum(kw.get("position", 0) for kw in serp_data["keywords"]) / len(serp_data["keywords"])
                    if serp_data["keywords"]
                    else 0
                ),
                "top_ranking_keywords": [kw for kw in serp_data["keywords"] if kw.get("position", 11) <= 3],
            },
        }

        client_ip = get_client_ip(request)
        from deps import log_analytics_event

        await log_analytics_event(
            db,
            "competitor_analysis",
            domain,
            client_ip,
            {"country": country, "language": language, "location": location, "keywords_found": len(serp_data["keywords"])},
        )

        return JSONResponse(
            {"success": True, "data": analysis_data, "message": "Competitor analysis completed successfully"}
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("API Competitor analysis failed for %s: %s", domain, e)
        return JSONResponse(
            {"success": False, "error": str(e), "message": "Competitor analysis failed"}, status_code=500
        )


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    # Render existing file at repository root (now moved to templates/)
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/speed-test", response_class=HTMLResponse)
async def speed_test_page(request: Request):
    return templates.TemplateResponse("speed_test_embed.html", {"request": request})


@app.get("/seo-analysis", response_class=HTMLResponse)
async def seo_analysis_page(request: Request):
    # Use existing informational page for now
    return templates.TemplateResponse("report.html", {"request": request})


@app.get("/competitor-analysis", response_class=HTMLResponse)
async def competitor_analysis_page(request: Request):
    # Reuse the home page form
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/analyze")
async def analyze_competitor(domain: str = Form(...), db: AsyncSession = Depends(get_db)):
    return RedirectResponse(url="/api/competitor-analysis", status_code=307)


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow(),
        "service": "AI2Flows SEO & Speed Analysis Tool",
        "version": "2.0.0",
    }


@app.get("/api/health")
async def api_health_check():
    return JSONResponse(
        {
            "success": True,
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "message": "AI2Flows SEO & Speed Analysis API is running",
        }
    )


if __name__ == "__main__":
    # IMPORTANT: if you run this file directly, point uvicorn at THIS module (not "main")
    uvicorn.run(
        "main:app",  # Change from "seo_speed_analysis:app"
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        reload=os.getenv("RELOAD", "0") == "1",
        log_level=os.getenv("LOG_LEVEL", "info"),
    )



