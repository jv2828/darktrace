"""API v1 router aggregating all v1 route endpoints."""

from fastapi import APIRouter
from app.api.v1.auth import router as auth_router
from app.api.v1.dashboard import router as dashboard_router
from app.api.v1.datasets import router as datasets_router
from app.api.v1.health import router as health_router
from app.api.v1.investigations import router as investigations_router
from app.api.v1.system import router as system_router
from app.api.v1.users import router as users_router

api_v1_router = APIRouter()

# Include health endpoints
api_v1_router.include_router(health_router, tags=["Health"])

# Include system diagnostics endpoints
api_v1_router.include_router(system_router, tags=["System"])

# Include auth endpoints
api_v1_router.include_router(auth_router)

# Include users endpoints
api_v1_router.include_router(users_router)

# Include datasets endpoints
api_v1_router.include_router(datasets_router)

# Include investigations endpoints
api_v1_router.include_router(investigations_router)

# Include dashboard endpoints
api_v1_router.include_router(dashboard_router)

