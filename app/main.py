"""
Panama Papers Offshore Network Analysis API
============================================

FastAPI application for analyzing ICIJ Panama Papers offshore financial networks.

Features:
    - Neo4j graph database integration
    - Entity search and lookup
    - Beneficial ownership tracing
    - Network analysis (PageRank, communities)
    - Risk assessment and red flag detection

API Documentation:
    - Swagger UI: /docs
    - ReDoc: /redoc
    - OpenAPI Schema: /openapi.json

Usage:
    # Development
    uvicorn main:app --reload --host 0.0.0.0 --port 8000
    
    # Production
    gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000

Environment Variables:
    NEO4J_URI: Neo4j connection URI (default: bolt://localhost:7687)
    NEO4J_USER: Neo4j username (default: neo4j)
    NEO4J_PASSWORD: Neo4j password (required)
    NEO4J_DATABASE: Target database (default: neo4j)
    API_ENV: Environment (development/staging/production)
    CORS_ORIGINS: Comma-separated allowed origins

Python Version: 3.11+
FastAPI Version: 0.109+
"""

from __future__ import annotations

import logging
import os
import sys
import time
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, AsyncGenerator, Callable

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse, Response
from starlette.middleware.base import BaseHTTPMiddleware

# Load environment variables
load_dotenv()

# ============================================================================
# CONFIGURATION
# ============================================================================

# API Configuration
API_TITLE = "Panama Papers Offshore Network Analysis API"
API_DESCRIPTION = """
## Overview

Neo4j-powered API for analyzing ICIJ Panama Papers offshore financial networks.

### Features

* **Entity Search** - Full-text search across offshore entities
* **Ownership Tracing** - Trace beneficial ownership chains up to 6 hops
* **Network Analysis** - PageRank influence scoring, community detection
* **Risk Assessment** - Automated red flag detection and risk scoring

### Data Sources

This API analyzes data from the ICIJ Offshore Leaks Database, including:
- Panama Papers (2016)
- Paradise Papers (2017)
- Pandora Papers (2021)

### Authentication

Currently, this API does not require authentication for read operations.
Write operations may be restricted in production environments.

### Rate Limits

- Development: No limits
- Production: 100 requests/minute per IP

### Contact

For questions about this API, contact the development team.
"""

API_VERSION = "1.0.0"
API_ENV = os.getenv("API_ENV", "development")

# CORS Configuration
CORS_ORIGINS_STR = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:3000,http://localhost:8000,http://127.0.0.1:3000,http://127.0.0.1:8000"
)
CORS_ORIGINS = [origin.strip() for origin in CORS_ORIGINS_STR.split(",")]

# In development, allow all localhost origins
if API_ENV == "development":
    CORS_ORIGINS.extend([
        "http://localhost:*",
        "http://127.0.0.1:*",
    ])

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

# Configure logging format based on environment
if API_ENV == "production":
    log_format = '{"timestamp": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", "message": "%(message)s"}'
else:
    log_format = "%(asctime)s │ %(levelname)-8s │ %(name)s │ %(message)s"

logging.basicConfig(
    level=logging.INFO if API_ENV == "production" else logging.DEBUG,
    format=log_format,
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)

# Reduce noise from third-party loggers
logging.getLogger("neo4j").setLevel(logging.WARNING)
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger("panama_api")

# ============================================================================
# IMPORT APPLICATION MODULES
# ============================================================================

# Import database module
try:
    from database import Neo4jDatabase, health_check, HealthCheckResult
    DATABASE_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Database module not available: {e}")
    DATABASE_AVAILABLE = False

# Import routers
try:
    from entities import router as entities_router
    ENTITIES_ROUTER_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Entities router not available: {e}")
    ENTITIES_ROUTER_AVAILABLE = False

# Import models
try:
    from models import ErrorResponse, HealthCheckResponse, HealthStatus
    MODELS_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Models not available: {e}")
    MODELS_AVAILABLE = False

# ============================================================================
# APPLICATION LIFESPAN
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    FastAPI lifespan context manager.
    
    Handles startup and shutdown events:
    - Startup: Initialize Neo4j driver connection
    - Shutdown: Close driver and release resources
    """
    # ==================== STARTUP ====================
    logger.info("=" * 60)
    logger.info(f"Starting {API_TITLE}")
    logger.info(f"Version: {API_VERSION}")
    logger.info(f"Environment: {API_ENV}")
    logger.info("=" * 60)
    
    startup_success = True
    
    # Initialize Neo4j driver
    if DATABASE_AVAILABLE:
        try:
            await Neo4jDatabase.init()
            logger.info("✓ Neo4j database connection established")
        except Exception as e:
            logger.error(f"✗ Failed to connect to Neo4j: {e}")
            startup_success = False
            
            # In production, fail fast if database is unavailable
            if API_ENV == "production":
                logger.critical("Cannot start in production without database connection")
                sys.exit(1)
    else:
        logger.warning("⚠ Database module not available - running in limited mode")
    
    if startup_success:
        logger.info("✓ API startup complete")
    else:
        logger.warning("⚠ API started with warnings")
    
    logger.info("-" * 60)
    
    # ==================== YIELD ====================
    yield
    
    # ==================== SHUTDOWN ====================
    logger.info("-" * 60)
    logger.info("Shutting down API...")
    
    # Close Neo4j driver
    if DATABASE_AVAILABLE:
        try:
            await Neo4jDatabase.close()
            logger.info("✓ Neo4j connection closed")
        except Exception as e:
            logger.error(f"Error closing Neo4j connection: {e}")
    
    logger.info("✓ API shutdown complete")
    logger.info("=" * 60)


# ============================================================================
# FASTAPI APPLICATION
# ============================================================================

app = FastAPI(
    title=API_TITLE,
    description=API_DESCRIPTION,
    version=API_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
    license_info={
        "name": "MIT License",
        "url": "https://opensource.org/licenses/MIT",
    },
    contact={
        "name": "Panama Papers Analysis Team",
        "url": "https://github.com/example/panama-papers-api",
    },
    openapi_tags=[
        {
            "name": "health",
            "description": "Health check and status endpoints",
        },
        {
            "name": "entities",
            "description": "Entity search, lookup, and analysis",
        },
        {
            "name": "ownership",
            "description": "Beneficial ownership tracing",
        },
        {
            "name": "network",
            "description": "Network analysis and graph algorithms",
        },
        {
            "name": "risk",
            "description": "Risk assessment and red flag detection",
        },
    ],
)


# ============================================================================
# MIDDLEWARE
# ============================================================================

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID", "X-Response-Time"],
    max_age=600,  # Cache preflight requests for 10 minutes
)

# GZip Middleware for response compression
app.add_middleware(
    GZipMiddleware,
    minimum_size=1000,  # Only compress responses > 1KB
)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware for logging HTTP requests and responses.
    
    Logs:
    - Request method and path
    - Response status code
    - Request duration
    - Request ID (if provided)
    """
    
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Response],
    ) -> Response:
        # Generate request ID
        request_id = request.headers.get("X-Request-ID", f"req_{int(time.time() * 1000)}")
        
        # Start timer
        start_time = time.perf_counter()
        
        # Log request
        logger.info(
            f"→ {request.method} {request.url.path} "
            f"[{request_id}]"
        )
        
        # Process request
        try:
            response = await call_next(request)
        except Exception as e:
            # Log error
            duration = (time.perf_counter() - start_time) * 1000
            logger.error(
                f"✗ {request.method} {request.url.path} "
                f"[{request_id}] "
                f"ERROR: {str(e)[:100]} "
                f"({duration:.2f}ms)"
            )
            raise
        
        # Calculate duration
        duration = (time.perf_counter() - start_time) * 1000
        
        # Add headers
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time"] = f"{duration:.2f}ms"
        
        # Log response
        log_level = logging.INFO if response.status_code < 400 else logging.WARNING
        logger.log(
            log_level,
            f"← {request.method} {request.url.path} "
            f"[{request_id}] "
            f"{response.status_code} "
            f"({duration:.2f}ms)"
        )
        
        return response


# Add request logging middleware
app.add_middleware(RequestLoggingMiddleware)


# ============================================================================
# EXCEPTION HANDLERS
# ============================================================================

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """
    Handle HTTPException with consistent error format.
    """
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "status_code": exc.status_code,
            "error": exc.detail if isinstance(exc.detail, str) else "Error",
            "detail": exc.detail,
            "timestamp": datetime.utcnow().isoformat(),
            "path": str(request.url.path),
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """
    Handle request validation errors with detailed error messages.
    """
    errors = []
    for error in exc.errors():
        errors.append({
            "field": ".".join(str(loc) for loc in error["loc"]),
            "message": error["msg"],
            "type": error["type"],
        })
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "status_code": 422,
            "error": "Validation Error",
            "detail": "Request validation failed",
            "errors": errors,
            "timestamp": datetime.utcnow().isoformat(),
            "path": str(request.url.path),
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Handle unexpected exceptions.
    
    In production, hide internal error details.
    In development, include exception message.
    """
    logger.exception(f"Unhandled exception on {request.url.path}: {exc}")
    
    detail = "An internal error occurred"
    if API_ENV == "development":
        detail = f"{type(exc).__name__}: {str(exc)}"
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "status_code": 500,
            "error": "Internal Server Error",
            "detail": detail,
            "timestamp": datetime.utcnow().isoformat(),
            "path": str(request.url.path),
        },
    )


# ============================================================================
# ROOT ENDPOINTS
# ============================================================================

@app.get(
    "/",
    tags=["health"],
    summary="API Information",
    response_model=None,
)
async def root() -> dict[str, Any]:
    """
    API welcome endpoint with service information.
    
    Returns:
        API metadata including version, environment, and documentation links
    """
    return {
        "service": API_TITLE,
        "version": API_VERSION,
        "environment": API_ENV,
        "status": "running",
        "timestamp": datetime.utcnow().isoformat(),
        "documentation": {
            "swagger_ui": "/docs",
            "redoc": "/redoc",
            "openapi_schema": "/openapi.json",
        },
        "endpoints": {
            "health": "/health",
            "entities": "/entities",
            "search": "/entities/search",
            "ownership": "/entities/{entity_id}/ownership-path",
            "network": "/entities/{entity_id}/network",
            "influential": "/entities/top/influential",
        },
        "data_source": "ICIJ Offshore Leaks Database",
    }


@app.get(
    "/health",
    tags=["health"],
    summary="Health Check",
    response_model=None,
    responses={
        200: {"description": "Service is healthy"},
        503: {"description": "Service is unhealthy"},
    },
)
async def health_check_endpoint() -> JSONResponse:
    """
    System health check endpoint.
    
    Verifies:
    - API is running
    - Neo4j database connectivity
    - GDS plugin availability (if applicable)
    
    Returns:
        Health status with component details
    """
    health_response: dict[str, Any] = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": API_VERSION,
        "environment": API_ENV,
        "checks": {
            "api": True,
        },
    }
    
    status_code = status.HTTP_200_OK
    
    # Check database if available
    if DATABASE_AVAILABLE:
        try:
            db_health: HealthCheckResult = await health_check(detailed=True)
            
            health_response["checks"]["neo4j"] = db_health.neo4j_connected
            health_response["neo4j"] = {
                "connected": db_health.neo4j_connected,
                "version": db_health.neo4j_version,
                "edition": db_health.neo4j_edition,
                "database": db_health.database,
                "latency_ms": db_health.latency_ms,
                "gds_available": db_health.gds_available,
                "gds_version": db_health.gds_version,
            }
            
            if db_health.uptime_seconds:
                health_response["uptime_seconds"] = round(db_health.uptime_seconds, 2)
            
            if not db_health.neo4j_connected:
                health_response["status"] = "unhealthy"
                health_response["error"] = db_health.error
                status_code = status.HTTP_503_SERVICE_UNAVAILABLE
                
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            health_response["status"] = "unhealthy"
            health_response["checks"]["neo4j"] = False
            health_response["error"] = str(e)
            status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    else:
        health_response["checks"]["neo4j"] = None
        health_response["status"] = "degraded"
        health_response["warning"] = "Database module not available"
    
    return JSONResponse(status_code=status_code, content=health_response)


@app.get(
    "/ready",
    tags=["health"],
    summary="Readiness Check",
    response_model=None,
)
async def readiness_check() -> dict[str, Any]:
    """
    Kubernetes-style readiness probe.
    
    Returns 200 if the service is ready to accept traffic.
    """
    ready = True
    
    if DATABASE_AVAILABLE:
        try:
            db_health = await health_check(detailed=False)
            ready = db_health.neo4j_connected
        except Exception:
            ready = False
    
    if not ready:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"ready": False},
        )
    
    return {"ready": True}


@app.get(
    "/live",
    tags=["health"],
    summary="Liveness Check",
    response_model=None,
)
async def liveness_check() -> dict[str, Any]:
    """
    Kubernetes-style liveness probe.
    
    Returns 200 if the service process is alive.
    """
    return {"alive": True}


# ============================================================================
# API INFO ENDPOINTS
# ============================================================================

@app.get(
    "/info",
    tags=["health"],
    summary="API Statistics",
    response_model=None,
)
async def api_info() -> dict[str, Any]:
    """
    Get API runtime information and statistics.
    """
    info: dict[str, Any] = {
        "api": {
            "title": API_TITLE,
            "version": API_VERSION,
            "environment": API_ENV,
        },
        "python_version": sys.version,
        "timestamp": datetime.utcnow().isoformat(),
    }
    
    # Add database info if available
    if DATABASE_AVAILABLE and Neo4jDatabase.is_initialized():
        uptime = Neo4jDatabase.get_uptime()
        if uptime:
            info["database"] = {
                "connected": True,
                "uptime_seconds": round(uptime, 2),
            }
    
    return info


# ============================================================================
# INCLUDE ROUTERS
# ============================================================================

# Entity routes
if ENTITIES_ROUTER_AVAILABLE:
    app.include_router(
        entities_router,
        prefix="/entities",
        tags=["entities"],
    )
    logger.info("✓ Entities router loaded")
else:
    logger.warning("⚠ Entities router not available")

# Network routes (placeholder - create if needed)
# if NETWORK_ROUTER_AVAILABLE:
#     app.include_router(
#         network_router,
#         prefix="/network",
#         tags=["network"],
#     )
#     logger.info("✓ Network router loaded")


# ============================================================================
# DEVELOPMENT SERVER
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    
    # Development server configuration
    uvicorn_config = {
        "app": "main:app",
        "host": os.getenv("API_HOST", "0.0.0.0"),
        "port": int(os.getenv("API_PORT", "8000")),
        "reload": API_ENV == "development",
        "reload_dirs": ["app"] if API_ENV == "development" else None,
        "log_level": "debug" if API_ENV == "development" else "info",
        "access_log": API_ENV == "development",
    }
    
    logger.info(f"Starting development server on {uvicorn_config['host']}:{uvicorn_config['port']}")
    
    uvicorn.run(**uvicorn_config)
