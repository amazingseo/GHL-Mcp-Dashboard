# main.py - Debug Version
import os
import time
from urllib.parse import urlencode, urlparse
import logging
from datetime import datetime
import sys

# Set up logging first
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# DEBUG: Check environment variables at startup
logger.info("=== ENVIRONMENT VARIABLES DEBUG ===")
logger.info(f"GHL_API_KEY exists: {bool(os.getenv('GHL_API_KEY'))}")
logger.info(f"GHL_LOCATION_ID exists: {bool(os.getenv('GHL_LOCATION_ID'))}")
from config import settings
logger.info(f"GOOGLE_API_KEY (from settings): {bool(settings.GOOGLE_API_KEY)}")
logger.info(f"GHL_API_KEY (from settings): {bool(settings.GHL_API_KEY)}")
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
# ADD THESE COMPLETE ENDPOINTS TO YOUR main.py

@app.get("/debug/railway")
def railway_debug():
    """Comprehensive Railway environment debugging endpoint."""
    debug_info = {
        "timestamp": datetime.utcnow().isoformat(),
        "python_version": sys.version,
        "environment": os.getenv("RAILWAY_ENVIRONMENT", "unknown"),
        "service_name": os.getenv("RAILWAY_SERVICE_NAME", "unknown"),
        "deployment_id": os.getenv("RAILWAY_DEPLOYMENT_ID", "unknown"),
        "port": os.getenv("PORT", "not set"),
        "variables": {
            "railway_vars": {},
            "app_vars": {},
            "api_keys": {}
        },
        "validation": {
            "ghl_configured": False,
            "google_configured": False,
            "issues": []
        }
    }
    
    # Collect Railway-specific variables
    for key, value in os.environ.items():
        if key.startswith('RAILWAY_'):
            debug_info["variables"]["railway_vars"][key] = value
    
    # Collect app-specific variables (masked for security)
    app_vars = [
        "JWT_SECRET", "WINDOW_DAYS", "MAX_FREE", "REQUESTS_PER_MINUTE",
        "PSI_STRATEGY", "ALLOWED_ORIGINS"
    ]
    
    for var in app_vars:
        value = os.getenv(var)
        if value:
            debug_info["variables"]["app_vars"][var] = f"SET (length: {len(value)})"
        else:
            debug_info["variables"]["app_vars"][var] = "NOT SET"
    
    # Collect and validate API keys
    api_keys = {
        "GHL_API_KEY": {"expected_prefix": ["eyJ", "pk_"], "required": True},
        "GHL_LOCATION_ID": {"expected_prefix": ["loc_", ""], "required": True},
        "GOOGLE_API_KEY": {"expected_prefix": ["AIza"], "required": True},
        "GOOGLE_CSE_CX": {"expected_prefix": [""], "required": True}
    }
    
    for key, config in api_keys.items():
        value = os.getenv(key)
        if value:
            # Mask the key for security
            masked_value = f"{value[:6]}...{value[-4:]}" if len(value) > 10 else "***"
            debug_info["variables"]["api_keys"][key] = {
                "status": "SET",
                "length": len(value),
                "preview": masked_value,
                "format_valid": any(value.startswith(prefix) for prefix in config["expected_prefix"]) if config["expected_prefix"] else True
            }
            
            # Validate format
            if config["expected_prefix"] and not any(value.startswith(prefix) for prefix in config["expected_prefix"]):
                debug_info["validation"]["issues"].append(f"{key} has incorrect format")
        else:
            debug_info["variables"]["api_keys"][key] = {
                "status": "NOT SET",
                "required": config["required"]
            }
            
            if config["required"]:
                debug_info["validation"]["issues"].append(f"{key} is required but not set")
    
    # Overall validation
    ghl_api = os.getenv("GHL_API_KEY")
    ghl_location = os.getenv("GHL_LOCATION_ID")
    debug_info["validation"]["ghl_configured"] = bool(ghl_api and ghl_location)
    
    google_api = os.getenv("GOOGLE_API_KEY")
    google_cse = os.getenv("GOOGLE_CSE_CX")
    debug_info["validation"]["google_configured"] = bool(google_api and google_cse)
    
    # Environment variable count
    debug_info["total_env_vars"] = len(os.environ)
    
    return debug_info


@app.get("/debug/test-apis")
async def test_api_connections():
    """Test API connections with current environment variables."""
    results = {
        "timestamp": datetime.utcnow().isoformat(),
        "tests": {}
    }
    
    # Test Google PageSpeed API
    google_api_key = os.getenv("GOOGLE_API_KEY")
    if google_api_key:
        try:
            test_url = "https://pagespeedonline.googleapis.com/pagespeedonline/v5/runPagespeed"
            params = {
                "url": "https://example.com",
                "key": google_api_key,
                "strategy": "mobile"
            }
            
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(test_url, params=params)
                results["tests"]["google_pagespeed"] = {
                    "status": "success" if response.status_code == 200 else "failed",
                    "status_code": response.status_code,
                    "api_key_format": "valid" if google_api_key.startswith("AIza") else "invalid"
                }
        except Exception as e:
            results["tests"]["google_pagespeed"] = {
                "status": "error",
                "error": str(e)
            }
    else:
        results["tests"]["google_pagespeed"] = {
            "status": "skipped",
            "reason": "GOOGLE_API_KEY not set"
        }
    
    # Test Google Custom Search API
    google_cse_cx = os.getenv("GOOGLE_CSE_CX")
    if google_api_key and google_cse_cx:
        try:
            test_url = "https://www.googleapis.com/customsearch/v1"
            params = {
                "key": google_api_key,
                "cx": google_cse_cx,
                "q": "test",
                "num": 1
            }
            
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(test_url, params=params)
                results["tests"]["google_cse"] = {
                    "status": "success" if response.status_code == 200 else "failed",
                    "status_code": response.status_code
                }
        except Exception as e:
            results["tests"]["google_cse"] = {
                "status": "error",
                "error": str(e)
            }
    else:
        results["tests"]["google_cse"] = {
            "status": "skipped",
            "reason": "GOOGLE_API_KEY or GOOGLE_CSE_CX not set"
        }
    
    # Test GHL API (just connection test, no actual API call)
    ghl_api_key = os.getenv("GHL_API_KEY")
    if ghl_api_key:
        results["tests"]["ghl_format"] = {
            "status": "valid" if ghl_api_key.startswith(("pit", "f4b_")) else "invalid_format",
            "format_check": "passed" if ghl_api_key.startswith(("pit", "f4b")) else "failed - should start with 'eyJ' or 'pk_'"
        }
    else:
        results["tests"]["ghl_format"] = {
            "status": "skipped",
            "reason": "GHL_API_KEY not set"
        }
    
    return results
# Your existing main.py structure...

@app.get("/debug/test-apis")
async def test_api_connections():
    # ... your existing test-apis code ...
    return results

# ADD THE NEW DEBUG ENDPOINTS HERE (between test-apis and capture-lead):

@app.get("/debug/env-raw")
def debug_env_raw():
    """Check raw environment variables"""
    import os
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "railway_info": {
            "environment": os.getenv("RAILWAY_ENVIRONMENT", "NOT_SET"),
            "service": os.getenv("RAILWAY_SERVICE_NAME", "NOT_SET"), 
            "deployment": os.getenv("RAILWAY_DEPLOYMENT_ID", "NOT_SET"),
        },
        "raw_env_vars": {
            "GHL_API_KEY": {
                "exists": "GHL_API_KEY" in os.environ,
                "length": len(os.getenv("GHL_API_KEY", "")),
                "preview": os.getenv("GHL_API_KEY", "")[:8] + "..." if os.getenv("GHL_API_KEY") else "NOT_SET",
                "type": type(os.getenv("GHL_API_KEY")).__name__
            },
            "GHL_LOCATION_ID": {
                "exists": "GHL_LOCATION_ID" in os.environ,
                "length": len(os.getenv("GHL_LOCATION_ID", "")),
                "preview": os.getenv("GHL_LOCATION_ID", "")[:8] + "..." if os.getenv("GHL_LOCATION_ID") else "NOT_SET",
                "type": type(os.getenv("GHL_LOCATION_ID")).__name__
            },
            "GOOGLE_API_KEY": {
                "exists": "GOOGLE_API_KEY" in os.environ,
                "length": len(os.getenv("GOOGLE_API_KEY", "")),
                "preview": os.getenv("GOOGLE_API_KEY", "")[:8] + "..." if os.getenv("GOOGLE_API_KEY") else "NOT_SET",
                "type": type(os.getenv("GOOGLE_API_KEY")).__name__
            }
        },
        "settings_vars": {
            "GHL_API_KEY": {
                "exists": bool(settings.GHL_API_KEY),
                "length": len(settings.GHL_API_KEY) if settings.GHL_API_KEY else 0,
                "preview": settings.GHL_API_KEY[:8] + "..." if settings.GHL_API_KEY else "NOT_SET"
            },
            "GHL_LOCATION_ID": {
                "exists": bool(settings.GHL_LOCATION_ID),
                "length": len(settings.GHL_LOCATION_ID) if settings.GHL_LOCATION_ID else 0,
                "preview": settings.GHL_LOCATION_ID[:8] + "..." if settings.GHL_LOCATION_ID else "NOT_SET"
            }
        },
        "all_env_vars_count": len(os.environ),
        "env_vars_starting_with": {
            "GHL_": [k for k in os.environ.keys() if k.startswith("GHL_")],
            "GOOGLE_": [k for k in os.environ.keys() if k.startswith("GOOGLE_")],
            "RAILWAY_": [k for k in os.environ.keys() if k.startswith("RAILWAY_")]
        }
    }

@app.get("/debug/config-reload")
def debug_config_reload():
    """Force reload configuration"""
    try:
        # Import fresh config
        import importlib
        import config
        importlib.reload(config)
        
        # Create new settings instance
        new_settings = config.Settings()
        
        return {
            "status": "reloaded",
            "old_settings": {
                "GHL_API_KEY": bool(settings.GHL_API_KEY),
                "GHL_LOCATION_ID": bool(settings.GHL_LOCATION_ID)
            },
            "new_settings": {
                "GHL_API_KEY": bool(new_settings.GHL_API_KEY),
                "GHL_LOCATION_ID": bool(new_settings.GHL_LOCATION_ID)
            }
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}

# ============== Lead capture ============== (your existing code continues here)
# Replace your existing @app.post("/api/capture-lead") function with this enhanced version:

@app.post("/api/capture-lead")
async def capture_lead(request: Request):
    try:
        # Enhanced logging for debugging
        logger.info("=== CAPTURE LEAD DEBUG START ===")
        logger.info(f"Request received at: {datetime.utcnow().isoformat()}")
        
        # Check environment variables step by step
        logger.info("Checking environment variables...")
        
        # Raw environment check
        raw_ghl_key = os.getenv("GHL_API_KEY")
        raw_ghl_location = os.getenv("GHL_LOCATION_ID")
        
        logger.info(f"Raw GHL_API_KEY: {'SET' if raw_ghl_key else 'NOT_SET'} (length: {len(raw_ghl_key) if raw_ghl_key else 0})")
        logger.info(f"Raw GHL_LOCATION_ID: {'SET' if raw_ghl_location else 'NOT_SET'} (length: {len(raw_ghl_location) if raw_ghl_location else 0})")
        
        # Settings check
        logger.info(f"Settings GHL_API_KEY: {'SET' if settings.GHL_API_KEY else 'NOT_SET'} (length: {len(settings.GHL_API_KEY) if settings.GHL_API_KEY else 0})")
        logger.info(f"Settings GHL_LOCATION_ID: {'SET' if settings.GHL_LOCATION_ID else 'NOT_SET'} (length: {len(settings.GHL_LOCATION_ID) if settings.GHL_LOCATION_ID else 0})")
        
        # Get JSON payload
        payload = await request.json()
        logger.info(f"Received payload keys: {list(payload.keys())}")
        
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

    # More detailed GHL configuration check
    logger.info("=== GHL CONFIGURATION CHECK ===")
    
    # Use raw environment variables if settings are not working
    ghl_api_key = settings.GHL_API_KEY or os.getenv("GHL_API_KEY")
    ghl_location_id = settings.GHL_LOCATION_ID or os.getenv("GHL_LOCATION_ID")
    
    logger.info(f"Final GHL_API_KEY: {'SET' if ghl_api_key else 'NOT_SET'}")
    logger.info(f"Final GHL_LOCATION_ID: {'SET' if ghl_location_id else 'NOT_SET'}")
    
    if not ghl_api_key:
        logger.error("GHL_API_KEY is missing or empty")
        # Return detailed debug info in error
        debug_info = {
            "raw_env": os.getenv("GHL_API_KEY", "NOT_SET")[:10] + "..." if os.getenv("GHL_API_KEY") else "NOT_SET",
            "settings": settings.GHL_API_KEY[:10] + "..." if settings.GHL_API_KEY else "NOT_SET",
            "env_var_exists": "GHL_API_KEY" in os.environ,
            "all_ghl_vars": [k for k in os.environ.keys() if "GHL" in k.upper()]
        }
        raise HTTPException(status_code=500, detail=f"GHL API key not configured. Debug: {debug_info}")
        
    if not ghl_location_id:
        logger.error("GHL_LOCATION_ID is missing or empty")
        debug_info = {
            "raw_env": os.getenv("GHL_LOCATION_ID", "NOT_SET"),
            "settings": settings.GHL_LOCATION_ID or "NOT_SET",
            "env_var_exists": "GHL_LOCATION_ID" in os.environ
        }
        raise HTTPException(status_code=500, detail=f"GHL Location ID not configured. Debug: {debug_info}")

    first, last = (name.split(" ", 1) + [""])[:2]

    # Create GHL contact using the resolved variables
    ghl_payload = {
        "firstName": first or email.split("@")[0],
        "lastName": last,
        "email": email,
        "phone": phone,
        "locationId": ghl_location_id,
        "source": source,
        "tags": tags,
    }

    logger.info(f"Sending to GHL: {ghl_payload}")
    logger.info(f"Using API Key: {ghl_api_key[:10]}...{ghl_api_key[-4:] if len(ghl_api_key) > 14 else ''}")

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            logger.info("Making request to GHL API...")
            
            resp = await client.post(
                "https://services.leadconnectorhq.com/contacts/",
                headers={
                    "Authorization": f"Bearer {ghl_api_key}",
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
            logger.info("=== CAPTURE LEAD DEBUG END ===")

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

