# DARKTRACE API Conventions

All HTTP endpoints in the DARKTRACE platform must adhere to the conventions documented here to maintain predictable communication between clients and backend microservices.

---

## 1. Unified Response Envelope

Every endpoint in DARKTRACE returns a standardized JSON envelope. Clients can unconditionally inspect the `success` boolean to determine response status.

### Success Envelope
Returned on HTTP 2xx statuses:
```json
{
  "success": true,
  "data": { ... },
  "error": null,
  "meta": {}
}
```

- `success`: Always `true` for successful operations.
- `data`: Object, array, or primitive containing the requested payload.
- `error`: Always `null`.
- `meta`: Metadata dictionary (e.g. pagination offsets, query execution timestamps, filter counts). Empty object `{}` when no metadata is applicable.

### Error Envelope
Returned on HTTP 4xx and 5xx statuses:
```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "STRING_ERROR_CODE",
    "message": "Human-readable explanation of the error",
    "details": null
  },
  "meta": {}
}
```

- `success`: Always `false` for failed operations.
- `data`: Always `null`.
- `error.code`: Machine-readable, uppercase string with underscores (see Error Code Standards below).
- `error.message`: Clear description suitable for client logging or presentation.
- `error.details`: Additional context (e.g. validation error field mappings or exception diagnostics). May be `null`.
- `meta`: Metadata dictionary (or empty object `{}`).

---

## 2. Error Code Standards

Error codes must be concise, uppercase, underscore-separated strings representing the failure category:

| Error Code | HTTP Status | Meaning |
|---|---|---|
| `DATABASE_UNAVAILABLE` | 503 | PostgreSQL connection could not be established or query timed out. |
| `VALIDATION_ERROR` | 422 | Request body, query parameter, or path parameter failed schema validation. |
| `NOT_FOUND` / `HTTP_404` | 404 | Target resource or route was not found. |
| `UNAUTHORIZED` | 401 | Missing, malformed, or expired authentication token (future phases). |
| `FORBIDDEN` | 403 | Authenticated user lacks permission to access the resource (future phases). |
| `INTERNAL_SERVER_ERROR` | 500 | Unhandled server exception caught by global handler. |

---

## 3. URL Prefix & Versioning

- All API endpoints must be prefixed with `/api/v1`.
- Example:
  - Health check: `GET /api/v1/health`
  - Threat actors (future): `GET /api/v1/actors`
- Any future breaking changes to models or schemas will require a new major version prefix (e.g., `/api/v2`).

---

## 4. Rule for Future Phases

All future modules, routers, and background endpoints **must strictly implement this response envelope** via `app.core.responses.success` and `app.core.responses.error`. No endpoint may return raw un-enveloped dictionaries, bare arrays, or unhandled HTTP exceptions.

