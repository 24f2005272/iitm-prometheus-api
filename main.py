
import json
import logging
import math
import time
import uuid
from collections import deque
from threading import Lock

from fastapi import FastAPI, Query, Request
from fastapi.responses import Response
from prometheus_client import (
    Counter,
    CONTENT_TYPE_LATEST,
    generate_latest,
)

app = FastAPI()

EMAIL = "24f2005272@ds.study.iitm.ac.in"
START_TIME = time.monotonic()

# Keep recent structured logs
recent_logs = deque(maxlen=1000)
logs_lock = Lock()

# Real Prometheus counter
http_requests = Counter(
    "http_requests_total",
    "Total number of HTTP requests",
)

logger = logging.getLogger("app")
logger.setLevel(logging.INFO)
logger.propagate = False

if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)


@app.middleware("http")
async def track_requests(request: Request, call_next):
    http_requests.inc()
    request_id = str(uuid.uuid4())

    try:
        response = await call_next(request)
    except Exception:
        logger.exception("Request failed")
        raise
    finally:
        entry = {
            "level": "INFO",
            "ts": time.time(),
            "path": request.url.path,
            "request_id": request_id,
        }

        with logs_lock:
            recent_logs.append(entry)

        logger.info(json.dumps(entry))

    response.headers["X-Request-ID"] = request_id
    return response


@app.get("/work")
def work(n: int = Query(default=1, ge=0, le=100000)):
    # Perform n units of simple computation
    value = 0
    for i in range(n):
        value += i * i

    return {"email": EMAIL, "done": n}


@app.get("/metrics")
def metrics():
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )


@app.get("/healthz")
def healthz():
    uptime = max(0.0, time.monotonic() - START_TIME)

    return {
        "status": "ok",
        "uptime_s": uptime,
    }


@app.get("/logs/tail")
def logs_tail(limit: int = Query(default=20, ge=0, le=1000)):
    with logs_lock:
        if limit == 0:
            return []
        return list(recent_logs)[-limit:]


@app.get("/")
def home():
    return {"status": "ok", "service": "Prometheus API"}
