"""Main FastAPI application entrypoint."""
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes_actions import router as actions_router
from app.api.routes_advisor import router as advisor_router
from app.api.routes_auth import router as auth_router
from app.api.routes_eval import router as eval_router
from app.api.routes_policies import router as policies_router
from app.api.routes_receipts import router as receipts_router
from app.api.routes_reviews import router as reviews_router
from app.core.config import settings
from app.core.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application startup and shutdown lifecycle management."""
    # Enforce runtime security boundaries
    settings.validate_runtime_safety()
    # Initialize SQLite tables and seed data
    init_db()
    yield


app = FastAPI(
    title="AI Agent Human Approval Console",
    description="Role-based review, multi-factor risk scoring, and cryptographic receipts for autonomous agent actions.",
    version="1.2.0",
    lifespan=lifespan
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:3000",
        "http://localhost:3000",
        "http://127.0.0.1:8000",
        "http://localhost:8000"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    """Applies strict security and framing headers to all responses."""
    response: Response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


# Health check endpoint
@app.get("/api/health")
def health_check():
    """System health verification endpoint."""
    return {
        "status": "healthy",
        "environment": settings.environment,
        "demo_mode": settings.demo_mode,
        "llm_provider": settings.llm_provider,
        "llm_model": settings.llm_model
    }


# Include modular API routers
app.include_router(auth_router)
app.include_router(actions_router)
app.include_router(reviews_router)
app.include_router(receipts_router)
app.include_router(policies_router)
app.include_router(eval_router)
app.include_router(advisor_router)
