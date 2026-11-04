"""API v1 router aggregating all v1 route endpoints."""

from fastapi import APIRouter
from app.api.v1.health import router as health_router

api_v1_router = APIRouter()

# Include health endpoints
api_v1_router.include_router(health_router, tags=["Health"])

