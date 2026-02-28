"""
Tech Signals — FastAPI Backend
Predictive Environmental Externality Engine
"""

import os
import time
import uuid
import logging
from collections import defaultdict, deque

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from routers.system import router as system_router
from routers.tech import router as tech_router
from routers.news import router as news_router
from routers.chat import router as chat_router

logger = logging.getLogger("tech-signals-api")
if not logger.handlers:
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO").upper())

is_production = os.getenv('APP_ENV', 'development').lower() == 'production'

app = FastAPI(
    title="Tech Signals API",
    description="Predictive Environmental Externality Engine — forecasts the environmental consequences of emerging technology adoption.",
    version="1.0.0",
    docs_url=None if is_production else "/docs",
    redoc_url=None if is_production else "/redoc",
    openapi_url=None if is_production else "/openapi.json",
)


def _csv_list(value: str, default: list[str]) -> list[str]:
    items = [item.strip() for item in str(value or '').split(',') if item.strip()]
    return items or default


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp):
        super().__init__(app)

    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers.setdefault('X-Content-Type-Options', 'nosniff')
        response.headers.setdefault('X-Frame-Options', 'DENY')
        response.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
        response.headers.setdefault('Permissions-Policy', 'geolocation=(), camera=(), microphone=()')
        response.headers.setdefault('Cross-Origin-Resource-Policy', 'same-site')
        response.headers.setdefault('Cross-Origin-Opener-Policy', 'same-origin')
        response.headers.setdefault('Cross-Origin-Embedder-Policy', 'require-corp')
        response.headers.setdefault('Content-Security-Policy', "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")

        if os.getenv('ENFORCE_HTTPS', 'false').lower() == 'true':
            response.headers.setdefault('Strict-Transport-Security', 'max-age=31536000; includeSubDomains; preload')

        return response


class AbuseProtectionMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.max_body_bytes = int(os.getenv('MAX_REQUEST_BODY_BYTES', '1048576'))
        self.window_seconds = int(os.getenv('RATE_LIMIT_WINDOW_SECONDS', '60'))
        self.max_requests = int(os.getenv('RATE_LIMIT_MAX_REQUESTS', '120'))
        self.strict_window_seconds = int(os.getenv('STRICT_RATE_LIMIT_WINDOW_SECONDS', '60'))
        self.strict_max_requests = int(os.getenv('STRICT_RATE_LIMIT_MAX_REQUESTS', '20'))
        self.strict_prefixes = _csv_list(
            os.getenv('STRICT_RATE_LIMIT_PATH_PREFIXES', ''),
            ['/api/chat', '/api/articles/generate', '/api/articles/'],
        )
        self.trust_proxy_headers = os.getenv('TRUST_PROXY_HEADERS', 'false').lower() == 'true'
        self._global_hits: defaultdict[str, deque[float]] = defaultdict(deque)
        self._strict_hits: defaultdict[str, deque[float]] = defaultdict(deque)

    def _client_ip(self, request: Request) -> str:
        if self.trust_proxy_headers:
            forwarded = request.headers.get('x-forwarded-for', '').strip()
            if forwarded:
                return forwarded.split(',')[0].strip() or 'unknown'
        client = request.client
        return client.host if client and client.host else 'unknown'

    @staticmethod
    def _is_strict_path(path: str, prefixes: list[str]) -> bool:
        return any(path.startswith(prefix) for prefix in prefixes)

    @staticmethod
    def _strict_bucket(path: str, prefixes: list[str]) -> str:
        for prefix in prefixes:
            if path.startswith(prefix):
                return prefix
        return path

    @staticmethod
    def _prune(queue: deque[float], now: float, window: int) -> None:
        cutoff = now - float(window)
        while queue and queue[0] < cutoff:
            queue.popleft()

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get('x-request-id') or str(uuid.uuid4())

        content_length = request.headers.get('content-length')
        if content_length and content_length.isdigit() and int(content_length) > self.max_body_bytes:
            return JSONResponse(
                status_code=413,
                content={'detail': 'Request body too large'},
                headers={'X-Request-ID': request_id},
            )

        if request.url.path.startswith('/api'):
            now = time.monotonic()
            ip = self._client_ip(request)

            global_key = ip
            global_queue = self._global_hits[global_key]
            self._prune(global_queue, now, self.window_seconds)
            if len(global_queue) >= self.max_requests:
                return JSONResponse(
                    status_code=429,
                    content={'detail': 'Rate limit exceeded'},
                    headers={
                        'Retry-After': str(self.window_seconds),
                        'X-Request-ID': request_id,
                    },
                )
            global_queue.append(now)

            if self._is_strict_path(request.url.path, self.strict_prefixes):
                strict_bucket = self._strict_bucket(request.url.path, self.strict_prefixes)
                strict_key = f'{ip}:{strict_bucket}'
                strict_queue = self._strict_hits[strict_key]
                self._prune(strict_queue, now, self.strict_window_seconds)
                if len(strict_queue) >= self.strict_max_requests:
                    return JSONResponse(
                        status_code=429,
                        content={'detail': 'Rate limit exceeded for sensitive endpoint'},
                        headers={
                            'Retry-After': str(self.strict_window_seconds),
                            'X-Request-ID': request_id,
                        },
                    )
                strict_queue.append(now)

        response = await call_next(request)
        response.headers.setdefault('X-Request-ID', request_id)
        return response


allow_origins = _csv_list(
    os.getenv('CORS_ALLOW_ORIGINS', ''),
    [
        'http://localhost:5173',
        'http://localhost:3000',
        'http://127.0.0.1:5173',
    ],
)

allowed_hosts = _csv_list(os.getenv('ALLOWED_HOSTS', ''), ['localhost', '127.0.0.1'])

if os.getenv('ENFORCE_HTTPS', 'false').lower() == 'true':
    app.add_middleware(HTTPSRedirectMiddleware)

app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(AbuseProtectionMiddleware)

# CORS — allow the React dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=False,
    allow_methods=['GET', 'POST', 'PUT', 'OPTIONS'],
    allow_headers=['Authorization', 'Content-Type'],
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.warning('Validation error on %s: %s', request.url.path, exc.errors())
    return JSONResponse(status_code=422, content={'detail': 'Invalid request payload'})


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception('Unhandled error on %s', request.url.path)
    return JSONResponse(status_code=500, content={'detail': 'Internal server error'})

# Router registration
app.include_router(system_router)
app.include_router(tech_router)
app.include_router(news_router)
app.include_router(chat_router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
