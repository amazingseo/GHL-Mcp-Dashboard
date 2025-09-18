# main.py
import time
from urllib.parse import urlencode, urlparse

import httpx
from fastapi import FastAPI, HTTPException, Request, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import jwt

from config import settings

APP_NAME = "ai2flows-seo-api"

app = FastAPI(title=APP_NAME)

# ---------- CORS (tight allowlist from env) ----------
ALLOWED = [o.strip() for o in settings.ALLOWED_ORIGINS.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED if ALLOWED else ["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

# ---------- Abuse controls (in-memory; swap to DB/Redis for prod) ----------
WINDOW_DAYS = settings.WINDOW_DAYS
MAX_FREE = settings.MAX_FREE
REQS_PER_MIN = settings.REQUESTS_PER_MINUTE

_usage: dict[str, dict] = {}        # { email: {count:int, windowStartISO:str} }
_ip_bucket: dict[str, list[float]] = {}  # { ip: [timestamps] }

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
    return (datetime.utcnow() - dt).days < WINDOW_DAYS

def enforce_quota(email: str) -> tuple[bool, str | None]:
    row = _usage.get(email, {"count": 0, "windowStartISO": _now_iso()})
    if not _within_window(row["windowStartISO"]):
        row["count"] = 0
        row["windowStartISO"] = _now_iso()
    if row["count"] >= MAX_FREE:
        return False, "Free analysis limit (6) reached. Please upgrade."
    row["count"] += 1
    _usage[email] = row
    return True, None

def throttle_ip(ip: str, limit: int = REQS_PER_MIN, window_sec: int = 60) -> bool:
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
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid/expired token")

# ---------- Utils ----------
def domain_from_url(url: str) -> str:
    try:
        host = urlparse(url).hostname or ""
    except Exception:
        host = ""
    return host.replace("www.", "")

# ---------- Routes ----------
@app.get("/health")
def health():
    return {"ok": True, "service": APP_NAME}

# ============== Lead capture -> creates GHL contact + returns JWT ==============
@app.post("/api/capture-lead")
async def capture_lead(payload: dict, request: Request):
    email = (payload.get("email") or "").strip().lower()
    name  = (payload.get("name") or "").strip()
    phone = (payload.get("phone") or "").strip()
    source = payload.get("source") or "seo_tool_free_trial"
    tags   = payload.get("tags") or ["SEO Tool lead"]

    if not email:
        raise HTTPException(status_code=400, detail="Email required")
    if not (settings.GHL_API_KEY and settings.GHL_LOCATION_ID):
        raise HTTPException(status_code=500, detail="GHL not configured on server")

    first, last = (name.split(" ", 1) + [""])[:2]

    # Create/Upsert contact in GHL (server-side; keep PIT secret)
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            "https://services.leadconnectorhq.com/contacts/",
            headers={
                "Authorization": f"Bearer {settings.GHL_API_KEY}",
                "Content-Type": "application/json",
                "Version": "2021-07-28",
            },
            json={
                "firstName": first or email,
                "lastName": last,
                "email": email,
                "phone": phone,
                "locationId": settings.GHL_LOCATION_ID,
                "source": source,
                "tags": tags,
            },
        )
        if resp.status_code >= 300:
            detail = (resp.text or "")[:300]
            raise HTTPException(status_code=502, detail=f"GHL contact create failed: {detail}")

    # init quota window if first time and issue token
    _usage.setdefault(email, {"count": 0, "windowStartISO": _now_iso()})
    return {"success": True, "token": issue_token(email)}

# ================== PageSpeed Insights (REAL data) ==================
@app.post("/api/speed-check")
async def speed_check(
    request: Request,
    url: str = Form(...)
):
    email = auth_user(request)
    ip = get_client_ip(request)
    if not throttle_ip(ip):
        return JSONResponse(status_code=429, content={"success": False, "message": "Too many requests. Slow down."})

    ok, msg = enforce_quota(email)
    if not ok:
        return JSONResponse(status_code=429, content={"success": False, "message": msg})

    if not url.lower().startswith("http"):
        raise HTTPException(status_code=400, detail="Valid https:// URL required")

    # PSI v5
    qs = {"url": url, "strategy": settings.PSI_STRATEGY}
    if settings.GOOGLE_API_KEY:
        qs["key"] = settings.GOOGLE_API_KEY

    psi_url = f"https://pagespeedonline.googleapis.com/pagespeedonline/v5/runPagespeed?{urlencode(qs)}"

    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.get(psi_url)
        if r.status_code >= 300:
            raise HTTPException(status_code=502, detail=f"PSI error {r.status_code}")
        j = r.json()

    lr = j.get("lighthouseResult", {}) or {}
    audits = lr.get("audits", {}) or {}
    perf = lr.get("categories", {}).get("performance", {}).get("score")

    score100 = int(round(perf * 100)) if isinstance(perf, (int, float)) else None

    def audit_val(key: str):
        v = audits.get(key) or {}
        return v.get("numericValue")

    # Shape response expected by your frontend
    data = {
        "score": score100,
        "loading_times": {
            "ttfb": audit_val("server-response-time"),
            "total_load_time": audit_val("speed-index"),
            "response_code": 200
        },
        "lighthouse_metrics": {
            "performance": score100,
            "first_contentful_paint": audit_val("first-contentful-paint"),
            "largest_contentful_paint": audit_val("largest-contentful-paint"),
        },
        "performance_issues": []
    }

    for key in ["render-blocking-resources", "uses-text-compression", "unminified-css", "unminified-javascript"]:
        a = audits.get(key)
        if not a:
            continue
        s = a.get("score", 0) or 0
        if s < 1:
            data["performance_issues"].append({
                "severity": "high" if s < 0.5 else "medium",
                "issue": a.get("title", key),
                "description": a.get("description", "")
            })

    return {"success": True, "data": data}

# ================== SEO Analysis (CSE) ==================
@app.post("/api/seo-analysis")
async def seo_analysis(
    request: Request,
    url: str = Form(...)
):
    email = auth_user(request)
    ip = get_client_ip(request)
    if not throttle_ip(ip):
        return JSONResponse(status_code=429, content={"success": False, "message": "Too many requests. Slow down."})

    ok, msg = enforce_quota(email)
    if not ok:
        return JSONResponse(status_code=429, content={"success": False, "message": msg})

    if not (settings.GOOGLE_API_KEY and settings.GOOGLE_CSE_CX):
        raise HTTPException(status_code=500, detail="CSE key/cx missing on server")
    if not url.lower().startswith("http"):
        raise HTTPException(status_code=400, detail="Valid https:// URL required")

    domain = domain_from_url(url)
    q = f"site:{domain}"

    params = {"key": settings.GOOGLE_API_KEY, "cx": settings.GOOGLE_CSE_CX, "q": q, "num": 10}
    cse_url = f"https://www.googleapis.com/customsearch/v1?{urlencode(params)}"

    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(cse_url)
        j = r.json()

    idx = int(j.get("searchInformation", {}).get("totalResults", "0") or 0)
    titles = [i.get("title") for i in (j.get("items") or [])][:5]

    return {"success": True, "data": {"domain": domain, "indexedCount": idx, "sampleTitles": titles}}

# ================== Competitor Analysis (CSE) ==================
@app.post("/api/competitor-analysis")
async def competitor_analysis(
    request: Request,
    domain: str = Form(...),
    country: str = Form("US"),
    language: str = Form("en"),
    location: str | None = Form(None),
):
    email = auth_user(request)
    ip = get_client_ip(request)
    if not throttle_ip(ip):
        return JSONResponse(status_code=429, content={"success": False, "message": "Too many requests. Slow down."})

    ok, msg = enforce_quota(email)
    if not ok:
        return JSONResponse(status_code=429, content={"success": False, "message": msg})

    if not (settings.GOOGLE_API_KEY and settings.GOOGLE_CSE_CX):
        raise HTTPException(status_code=500, detail="CSE key/cx missing on server")

    d = domain.replace("https://", "").replace("http://", "").split("/")[0]

    queries = [
        f"site:{d}",
        f"site:{d} blog",
        f"site:{d} pricing",
        f"site:{d} case study",
        f"site:{d} services",
    ]

    out = []
    async with httpx.AsyncClient(timeout=30.0) as client:
        for q in queries:
            params = {"key": settings.GOOGLE_API_KEY, "cx": settings.GOOGLE_CSE_CX, "q": q, "num": 5}
            # language restriction (optional)
            if language:
                params["lr"] = f"lang_{language}"
            url = f"https://www.googleapis.com/customsearch/v1?{urlencode(params)}"
            r = await client.get(url)
            j = r.json()
            items = [
                {"title": i.get("title"), "link": i.get("link"), "snippet": i.get("snippet")}
                for i in (j.get("items") or [])
            ]
            out.append({"query": q, "items": items})

    return {"success": True, "data": {"domain": d, "results": out}}

# ================== Optional analytics ==================
@app.post("/api/track-event")
async def track_event(payload: dict):
    # No-op placeholder. Wire to your logs/analytics if needed.
    return {"ok": True}

# ================== Run hint (Railway) ==================
# Start command: uvicorn main:app --host 0.0.0.0 --port $PORT
