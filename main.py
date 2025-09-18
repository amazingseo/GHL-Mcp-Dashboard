# main.py - Debug Version
import os
import time
from urllib.parse import urlencode, urlparse
import logging

# Set up logging first
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# DEBUG: Check environment variables at startup
logger.info("=== ENVIRONMENT VARIABLES DEBUG ===")
logger.info(f"GHL_API_KEY exists: {bool(os.getenv('GHL_API_KEY'))}")
logger.info(f"GHL_LOCATION_ID exists: {bool(os.getenv('GHL_LOCATION_ID'))}")
logger.info(f"GOOGLE_API_KEY exists: {bool(os.getenv('GOOGLE_API_KEY'))}")
logger.info(f"GOOGLE_CSE_CX exists: {bool(os.getenv('GOOGLE_CSE_CX'))}")
logger.info("=====================================")

try:
    import httpx
    from fastapi import FastAPI, HTTPException, Request, Form
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import JSONResponse
    import jwt
    logger.info("All required packages imported successfully")
except ImportError as e:
    logger.error(f"Import error: {e}")
    raise

# Import config AFTER checking environment
try:
    from config import settings
    logger.info("Config imported successfully")
    logger.info(f"Settings GHL_API_KEY: {bool(settings.GHL_API_KEY)}")
    logger.info(f"Settings GHL_LOCATION_ID: {bool(settings.GHL_LOCATION_ID)}")
except Exception as e:
    logger.error(f"Config import error: {e}")
    raise

APP_NAME = "ai2flows-seo-api"

app = FastAPI(title=APP_NAME)

# ---------- CORS ----------
ALLOWED = [o.strip() for o in settings.ALLOWED_ORIGINS.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED if ALLOWED else ["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

# ---------- In-memory storage ----------
_usage: dict[str, dict] = {}
_ip_bucket: dict[str, list[float]] = {}

def _now_iso() -> str:
    from datetime import datetime
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")

def _within_window(start_iso: str) -> bool:
    from datetime import datetime
    if not start_iso:
        return False
    try:
        dt = datetime.fromisoformat(start_iso)
    except Exception:
        return False
    return (datetime.utcnow() - dt).days < settings.WINDOW_DAYS

def enforce_quota(email: str) -> tuple[bool, str | None]:
    row = _usage.get(email, {"count": 0, "windowStartISO": _now_iso()})
    if not _within_window(row["windowStartISO"]):
        row["count"] = 0
        row["windowStartISO"] = _now_iso()
    if row["count"] >= settings.MAX_FREE:
        return False, f"Free analysis limit ({settings.MAX_FREE}) reached. Please upgrade."
    row["count"] += 1
    _usage[email] = row
    return True, None

def throttle_ip(ip: str, limit: int = None, window_sec: int = 60) -> bool:
    if limit is None:
        limit = settings.REQUESTS_PER_MINUTE
    now = time.time()
    bucket = _ip_bucket.get(ip, [])
    bucket = [t for t in bucket if now - t < window_sec]
    if len(bucket) >= limit:
        return False
    bucket.append(now)
    _ip_bucket[ip] = bucket
    return True

def get_client_ip(request: Request) -> str:
    xf = request.headers.get("x-forwarded-for")
    if xf:
        return xf.split(",")[0].strip()
    return request.client.host

# ---------- JWT helpers ----------
def issue_token(email: str, days: int = 7) -> str:
    return jwt.encode(
        {"email": email, "iat": int(time.time()), "exp": int(time.time()) + days * 86400},
        settings.JWT_SECRET,
        algorithm="HS256",
    )

def auth_user(request: Request) -> str:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")
    token = auth.split(" ", 1)[1]
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
        email = payload.get("email")
        if not email:
            raise HTTPException(status_code=401, detail="Invalid token payload")
        return email
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except Exception as e:
        logger.error(f"JWT decode error: {e}")
        raise HTTPException(status_code=401, detail="Invalid/expired token")

def domain_from_url(url: str) -> str:
    try:
        host = urlparse(url).hostname or ""
    except Exception:
        host = ""
    return host.replace("www.", "")

# ---------- Routes ----------
@app.get("/health")
def health():
    return {
        "ok": True, 
        "service": APP_NAME,
        "config_check": {
            "ghl_configured": bool(settings.GHL_API_KEY and settings.GHL_LOCATION_ID),
            "google_configured": bool(settings.GOOGLE_API_KEY and settings.GOOGLE_CSE_CX)
        }
    }

@app.get("/debug/env")
def debug_env():
    """Debug endpoint to check environment variables"""
    return {
        "environment_variables": {
            "GHL_API_KEY": "SET" if settings.GHL_API_KEY else "MISSING",
            "GHL_LOCATION_ID": "SET" if settings.GHL_LOCATION_ID else "MISSING", 
            "GOOGLE_API_KEY": "SET" if settings.GOOGLE_API_KEY else "MISSING",
            "GOOGLE_CSE_CX": "SET" if settings.GOOGLE_CSE_CX else "MISSING",
            "JWT_SECRET": "SET" if settings.JWT_SECRET else "MISSING"
        },
        "env_var_lengths": {
            "GHL_API_KEY": len(settings.GHL_API_KEY) if settings.GHL_API_KEY else 0,
            "GHL_LOCATION_ID": len(settings.GHL_LOCATION_ID) if settings.GHL_LOCATION_ID else 0,
        }
    }

# ============== Lead capture ==============
@app.post("/api/capture-lead")
async def capture_lead(request: Request):
    try:
        # Get JSON payload
        payload = await request.json()
        logger.info(f"Received lead capture request: {payload}")
        
    except Exception as e:
        logger.error(f"Failed to parse request JSON: {e}")
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    email = (payload.get("email") or "").strip().lower()
    name = (payload.get("name") or "").strip()
    phone = (payload.get("phone") or "").strip()
    source = payload.get("source") or "seo_tool_free_trial"
    tags = payload.get("tags") or ["SEO Tool lead"]

    logger.info(f"Processing lead: email={email}, name={name}")

    if not email:
        raise HTTPException(status_code=400, detail="Email required")

    # DETAILED GHL CONFIGURATION CHECK
    logger.info(f"GHL_API_KEY present: {bool(settings.GHL_API_KEY)}")
    logger.info(f"GHL_LOCATION_ID present: {bool(settings.GHL_LOCATION_ID)}")
    
    if not settings.GHL_API_KEY:
        logger.error("GHL_API_KEY is missing or empty")
        raise HTTPException(status_code=500, detail="GHL API key not configured")
        
    if not settings.GHL_LOCATION_ID:
        logger.error("GHL_LOCATION_ID is missing or empty") 
        raise HTTPException(status_code=500, detail="GHL Location ID not configured")

    first, last = (name.split(" ", 1) + [""])[:2]

    # Create GHL contact
    ghl_payload = {
        "firstName": first or email.split("@")[0],
        "lastName": last,
        "email": email,
        "phone": phone,
        "locationId": settings.GHL_LOCATION_ID,
        "source": source,
        "tags": tags,
    }

    logger.info(f"Sending to GHL: {ghl_payload}")

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            logger.info("Making request to GHL API...")
            
            resp = await client.post(
                "https://services.leadconnectorhq.com/contacts/",
                headers={
                    "Authorization": f"Bearer {settings.GHL_API_KEY}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "Version": "2021-07-28",
                },
                json=ghl_payload,
            )

            logger.info(f"GHL Response Status: {resp.status_code}")
            logger.info(f"GHL Response Headers: {dict(resp.headers)}")
            
            response_text = await resp.atext()
            logger.info(f"GHL Response Body: {response_text}")

            if resp.status_code >= 300:
                logger.error(f"GHL API failed: {resp.status_code} - {response_text}")
                raise HTTPException(
                    status_code=502,
                    detail=f"Contact creation failed: {resp.status_code} - {response_text[:200]}"
                )

            logger.info("GHL contact created successfully")

    except httpx.TimeoutException:
        logger.error("GHL API timeout")
        raise HTTPException(status_code=502, detail="Contact service timeout")
    except Exception as e:
        logger.error(f"GHL API error: {str(e)}")
        raise HTTPException(status_code=502, detail=f"Contact creation failed: {str(e)}")

    # Initialize quota and issue token
    _usage.setdefault(email, {"count": 0, "windowStartISO": _now_iso()})
    token = issue_token(email)

    return {"success": True, "token": token}

# ================== Speed Analysis ==================
@app.post("/api/speed-check")
async def speed_check(request: Request, url: str = Form(...)):
    email = auth_user(request)
    ip = get_client_ip(request)

    if not throttle_ip(ip):
        return JSONResponse(status_code=429, content={"success": False, "message": "Too many requests"})

    ok, msg = enforce_quota(email)
    if not ok:
        return JSONResponse(status_code=429, content={"success": False, "message": msg})

    if not url.lower().startswith("http"):
        raise HTTPException(status_code=400, detail="Valid https:// URL required")

    try:
        qs = {"url": url, "strategy": settings.PSI_STRATEGY}
        if settings.GOOGLE_API_KEY:
            qs["key"] = settings.GOOGLE_API_KEY

        psi_url = f"https://pagespeedonline.googleapis.com/pagespeedonline/v5/runPagespeed?{urlencode(qs)}"

        async with httpx.AsyncClient(timeout=90.0) as client:
            r = await client.get(psi_url)
            
            if r.status_code >= 300:
                if r.status_code == 429:
                    return JSONResponse(status_code=429, content={"success": False, "message": "API rate limit reached"})
                raise HTTPException(status_code=502, detail=f"PageSpeed API error: {r.status_code}")
            
            j = r.json()

        # Extract data
        lr = j.get("lighthouseResult", {}) or {}
        categories = lr.get("categories", {}) or {}
        perf = categories.get("performance", {}).get("score", 0)
        score100 = int(round(perf * 100)) if perf else 0

        data = {
            "score": score100,
            "analysis_date": lr.get("fetchTime"),
            "loading_times": {"ttfb": 0, "total_load_time": 0, "response_code": 200},
            "lighthouse_metrics": {"performance": score100},
            "performance_issues": [],
            "data_source": "Google PageSpeed Insights"
        }

        return {"success": True, "data": data}

    except Exception as e:
        logger.error(f"Speed analysis error: {str(e)}")
        raise HTTPException(status_code=500, detail="Speed analysis failed")

# ================== SEO Analysis ==================  
@app.post("/api/seo-analysis")
async def seo_analysis(request: Request, url: str = Form(...)):
    email = auth_user(request)
    ip = get_client_ip(request)

    if not throttle_ip(ip):
        return JSONResponse(status_code=429, content={"success": False, "message": "Too many requests"})

    ok, msg = enforce_quota(email)
    if not ok:
        return JSONResponse(status_code=429, content={"success": False, "message": msg})

    if not (settings.GOOGLE_API_KEY and settings.GOOGLE_CSE_CX):
        raise HTTPException(status_code=500, detail="SEO analysis not configured")

    try:
        domain = domain_from_url(url)
        params = {"key": settings.GOOGLE_API_KEY, "cx": settings.GOOGLE_CSE_CX, "q": f"site:{domain}", "num": 10}
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.get(f"https://www.googleapis.com/customsearch/v1?{urlencode(params)}")
            if r.status_code >= 300:
                raise HTTPException(status_code=502, detail="SEO API error")
            j = r.json()

        idx = int(j.get("searchInformation", {}).get("totalResults", "0") or 0)
        titles = [i.get("title", "") for i in j.get("items", [])][:5]

        return {"success": True, "data": {"domain": domain, "indexedCount": idx, "sampleTitles": titles}}

    except Exception as e:
        logger.error(f"SEO analysis error: {str(e)}")
        raise HTTPException(status_code=500, detail="SEO analysis failed")

# ================== Competitor Analysis ==================
@app.post("/api/competitor-analysis")
async def competitor_analysis(
    request: Request,
    domain: str = Form(...),
    country: str = Form("US"), 
    language: str = Form("en"),
    location: str = Form(None)
):
    email = auth_user(request)
    ip = get_client_ip(request)

    if not throttle_ip(ip):
        return JSONResponse(status_code=429, content={"success": False, "message": "Too many requests"})

    ok, msg = enforce_quota(email)
    if not ok:
        return JSONResponse(status_code=429, content={"success": False, "message": msg})

    if not (settings.GOOGLE_API_KEY and settings.GOOGLE_CSE_CX):
        raise HTTPException(status_code=500, detail="Competitor analysis not configured")

    try:
        d = domain.replace("https://", "").replace("http://", "").split("/")[0]
        queries = [f"site:{d}", f"site:{d} blog", f"site:{d} pricing"]
        results = []

        async with httpx.AsyncClient(timeout=30.0) as client:
            for q in queries:
                params = {"key": settings.GOOGLE_API_KEY, "cx": settings.GOOGLE_CSE_CX, "q": q, "num": 5}
                r = await client.get(f"https://www.googleapis.com/customsearch/v1?{urlencode(params)}")
                
                if r.status_code == 200:
                    j = r.json()
                    items = [{"title": i.get("title", ""), "link": i.get("link", ""), "snippet": i.get("snippet", "")} for i in j.get("items", [])]
                    results.append({"query": q, "items": items})

        return {"success": True, "data": {"domain": d, "results": results}}

    except Exception as e:
        logger.error(f"Competitor analysis error: {str(e)}")
        raise HTTPException(status_code=500, detail="Competitor analysis failed")

# ================== Analytics ==================
@app.post("/api/track-event")
async def track_event(payload: dict):
    logger.info(f"Analytics: {payload}")
    return {"ok": True}

# Start the app
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
