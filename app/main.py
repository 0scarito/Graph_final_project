"""FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import entities, networks
from app.database import get_database

app = FastAPI(
    title="Graph-Backed Analysis API",
    description="API for analyzing offshore financial data using Neo4j",
    version="0.1.0",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(entities.router, prefix="/api/entities", tags=["entities"])
app.include_router(networks.router, prefix="/api/networks", tags=["networks"])


@app.on_event("startup")
async def startup_event():
    """Initialize database connection on startup."""
    try:
        db = get_database()
        db.verify_connectivity()
        print("✓ Connected to Neo4j")
    except Exception as e:
        print(f"✗ Failed to connect to Neo4j: {e}")


@app.on_event("shutdown")
async def shutdown_event():
    """Close database connection on shutdown."""
    db = get_database()
    db.close()
    print("✓ Disconnected from Neo4j")


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Graph-Backed Analysis API",
        "version": "0.1.0",
        "docs": "/docs",
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    try:
        db = get_database()
        db.verify_connectivity()
        return {"status": "healthy", "neo4j": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "neo4j": "disconnected", "error": str(e)}

