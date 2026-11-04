"""DARKTRACE API application entry point."""

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1.router import api_v1_router
from app.core.config import settings
from app.core.responses import error

# Create FastAPI application
app = FastAPI(
    title="DARKTRACE API",
    description="Dark web threat-intelligence and actor-correlation platform API.",
    version="0.1.0",
)

# Configure Cross-Origin Resource Sharing (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global Exception Handlers ensuring all responses match the standard envelope
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle request validation errors in standard error envelope."""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=error(
            code="VALIDATION_ERROR",
            message="Request parameter validation failed.",
            details=exc.errors(),
        ),
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Handle standard HTTP exceptions in standard error envelope."""
    return JSONResponse(
        status_code=exc.status_code,
        content=error(
            code=f"HTTP_{exc.status_code}",
            message=str(exc.detail),
            details=None,
        ),
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected server errors in standard error envelope."""
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error(
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected server error occurred.",
            details=str(exc),
        ),
    )


# Mount API v1 router
app.include_router(api_v1_router, prefix="/api/v1")

