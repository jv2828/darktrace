"""Standardized API response envelopes for DARKTRACE.

All API responses strictly adhere to the unified envelope:
Success:
    {"success": true, "data": {...}, "error": null, "meta": {}}
Error:
    {"success": false, "data": null, "error": {"code": "...", "message": "...", "details": null}, "meta": {}}
"""

from typing import Any, Optional


def success(data: Any = None, meta: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    """Produce a standardized success response dictionary."""
    return {
        "success": True,
        "data": data,
        "error": None,
        "meta": meta if meta is not None else {},
    }


def error(
    code: str,
    message: str,
    details: Any = None,
    meta: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Produce a standardized error response dictionary."""
    return {
        "success": False,
        "data": None,
        "error": {
            "code": code,
            "message": message,
            "details": details,
        },
        "meta": meta if meta is not None else {},
    }

