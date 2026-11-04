"""Normalisation and validation service for ingested darknet records.

Handles Unicode NFKC normalisation, deduplication hashing, field constraint
validation, timestamp parsing, structured indicator checks, and warning tracking.
"""

from datetime import datetime, timedelta, timezone
import hashlib
import ipaddress
import re
from typing import Any, Dict, List, Optional, Tuple, Union
import unicodedata

# Maximum characters when echoing user content in errors/warnings
MAX_ECHO_LEN = 100

PGP_HEX_PATTERN = re.compile(r"^[0-9a-fA-F]{40}$|^[0-9a-fA-F]{64}$")
SHA256_HEX_PATTERN = re.compile(r"^[0-9a-fA-F]{64}$")


def truncate_echo(val: Any) -> str:
    """Safely truncate echoed user input to 100 characters."""
    s = str(val) if val is not None else ""
    if len(s) > MAX_ECHO_LEN:
        return s[:MAX_ECHO_LEN] + "..."
    return s


def normalise_username(username: str) -> str:
    """Normalise username: Unicode NFKC, strip whitespace, casefold.

    Example: "  Ädmin_User  " -> "ädmin_user"
    """
    if not username:
        return ""
    return unicodedata.normalize("NFKC", username).strip().casefold()


def normalise_marketplace(marketplace: str) -> str:
    """Normalise marketplace identifier for case-insensitive lookup.

    Unicode NFKC, strip, collapse internal whitespace, and casefold.
    """
    if not marketplace:
        return ""
    cleaned = unicodedata.normalize("NFKC", marketplace).strip()
    collapsed = " ".join(cleaned.split())
    return collapsed.casefold()


def compute_dedupe_hash(
    marketplace: str,
    username: str,
    timestamp_iso_utc: Optional[str],
    content: str,
) -> str:
    """Compute deterministic SHA-256 dedupe hash as defined in schema design.

    Formula:
        sha256(marketplace(normalised)|username(normalised)|timestamp ISO UTC (or empty)|content with whitespace collapsed)
    """
    norm_mkt = normalise_marketplace(marketplace)
    norm_user = normalise_username(username)
    ts_str = timestamp_iso_utc or ""
    collapsed_content = " ".join(content.split()) if content else ""

    raw = f"{norm_mkt}|{norm_user}|{ts_str}|{collapsed_content}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def parse_and_validate_timestamp(
    raw_ts: Optional[Union[str, datetime]],
) -> Tuple[Optional[datetime], Optional[str], List[str], List[str]]:
    """Parse timestamp string into timezone-aware UTC datetime and ISO string.

    Returns:
        (datetime_utc, iso_string, errors, warnings)
    """
    errors: List[str] = []
    warnings: List[str] = []

    if raw_ts is None or (isinstance(raw_ts, str) and not raw_ts.strip()):
        return None, None, errors, warnings

    dt: Optional[datetime] = None

    if isinstance(raw_ts, datetime):
        dt = raw_ts
    else:
        ts_str = raw_ts.strip()
        # 1. Standard ISO formats
        try:
            # Handle trailing Z
            if ts_str.endswith("Z"):
                ts_iso = ts_str[:-1] + "+00:00"
                dt = datetime.fromisoformat(ts_iso)
            else:
                dt = datetime.fromisoformat(ts_str)
        except ValueError:
            # 2. Try common formats: "YYYY-MM-DD HH:MM:SS" or "YYYY-MM-DD HH:MM" or "YYYY-MM-DD"
            formats = [
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d %H:%M",
                "%Y-%m-%d",
                "%Y/%m/%d %H:%M:%S",
                "%Y/%m/%d %H:%M",
                "%Y/%m/%d",
            ]
            for fmt in formats:
                try:
                    dt = datetime.strptime(ts_str, fmt)
                    break
                except ValueError:
                    continue

        if dt is None:
            errors.append(f"Unparseable timestamp: '{truncate_echo(ts_str)}'")
            return None, None, errors, warnings

    # Check timezone awareness
    if dt.tzinfo is None:
        warnings.append("timezone assumed UTC")
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        # Convert to UTC
        dt = dt.astimezone(timezone.utc)

    # Validate range
    now_utc = datetime.now(timezone.utc)
    one_day_future = now_utc + timedelta(days=1)
    min_date = datetime(2000, 1, 1, tzinfo=timezone.utc)

    if dt > one_day_future:
        warnings.append(
            f"Timestamp '{truncate_echo(dt.isoformat())}' is more than 1 day in the future."
        )
    elif dt < min_date:
        warnings.append(
            f"Timestamp '{truncate_echo(dt.isoformat())}' is before 2000-01-01."
        )

    iso_str = dt.isoformat()
    return dt, iso_str, errors, warnings


def validate_structured_indicators(
    raw_indicators: Optional[Dict[str, Any]],
) -> Tuple[Dict[str, Any], Dict[str, Any], List[str]]:
    """Validate optional structured indicator fields.

    Returns:
        (valid_indicators, unparsed_indicators, warnings)
    """
    valid: Dict[str, Any] = {}
    unparsed: Dict[str, Any] = {}
    warnings: List[str] = []

    if not raw_indicators or not isinstance(raw_indicators, dict):
        return valid, unparsed, warnings

    for key, val in raw_indicators.items():
        if val is None or val == "":
            continue

        str_val = str(val).strip()
        if not str_val:
            continue

        if key == "ip_address":
            try:
                ipaddress.ip_address(str_val)
                valid["ip_address"] = str_val
            except ValueError:
                warnings.append(f"Invalid IP address format: '{truncate_echo(str_val)}'")
                unparsed["ip_address"] = str_val

        elif key == "port":
            try:
                port_int = int(str_val)
                if 1 <= port_int <= 65535:
                    valid["port"] = port_int
                else:
                    warnings.append(f"Port out of range 1-65535: '{truncate_echo(str_val)}'")
                    unparsed["port"] = str_val
            except ValueError:
                warnings.append(f"Invalid non-integer port: '{truncate_echo(str_val)}'")
                unparsed["port"] = str_val

        elif key == "pgp_fingerprint":
            # Clean spaces, colons, leading 0x/0X
            cleaned = str_val.replace(" ", "").replace(":", "")
            if cleaned.lower().startswith("0x"):
                cleaned = cleaned[2:]
            if PGP_HEX_PATTERN.fullmatch(cleaned):
                valid["pgp_fingerprint"] = str_val
            else:
                warnings.append(
                    f"PGP fingerprint must be 40 or 64 hex characters: '{truncate_echo(str_val)}'"
                )
                unparsed["pgp_fingerprint"] = str_val

        elif key == "ssl_cert_fingerprint":
            cleaned = str_val.replace(":", "").replace(" ", "")
            if SHA256_HEX_PATTERN.fullmatch(cleaned):
                valid["ssl_cert_fingerprint"] = str_val
            else:
                warnings.append(
                    f"SSL certificate fingerprint must be 64 hex characters: '{truncate_echo(str_val)}'"
                )
                unparsed["ssl_cert_fingerprint"] = str_val

        elif key in {"wallet", "domain", "server_banner", "source_reference"}:
            valid[key] = str_val

        else:
            # Other arbitrary fields passed through
            valid[key] = val

    return valid, unparsed, warnings


def validate_post_row(
    row: Dict[str, Any],
    row_number: int = 1,
    existing_hashes_in_batch: Optional[set[str]] = None,
    existing_hashes_in_db: Optional[set[str]] = None,
) -> Dict[str, Any]:
    """Validate a single post record and determine its ingestion status.

    Status is one of:
      - "invalid" (has fatal validation errors)
      - "duplicate" (dedupe hash collision in upload or DB)
      - "valid_with_warnings" (valid but contains non-fatal warnings)
      - "valid" (fully valid with no errors or warnings)
    """
    errors: List[str] = []
    warnings: List[str] = []

    # 1. Marketplace
    mkt = row.get("marketplace")
    mkt_str = str(mkt).strip() if mkt is not None else ""
    if not mkt_str:
        errors.append("Marketplace is required.")
    elif len(mkt_str) < 2 or len(mkt_str) > 100:
        errors.append(
            f"Marketplace name must be between 2 and 100 characters (got {len(mkt_str)}): '{truncate_echo(mkt_str)}'"
        )

    # 2. Username
    username = row.get("username")
    if username is None:
        username = row.get("author_username") or row.get("author")
    user_str = str(username).strip() if username is not None else ""
    if not user_str:
        errors.append("Username is required.")
    elif len(user_str) < 2 or len(user_str) > 64:
        errors.append(
            f"Username must be between 2 and 64 characters (got {len(user_str)}): '{truncate_echo(user_str)}'"
        )
    else:
        # Check for control characters
        has_control = any(
            unicodedata.category(c).startswith("C") for c in user_str
        )
        if has_control:
            errors.append(f"Username contains disallowed control characters: '{truncate_echo(user_str)}'")

    # 3. Content
    content = row.get("content")
    content_str = str(content) if content is not None else ""
    if not content_str or not content_str.strip():
        errors.append("Content cannot be empty or whitespace-only.")
    elif len(content_str) > 20000:
        errors.append(
            f"Content length exceeds 20,000 characters (got {len(content_str)})."
        )
    elif "\x00" in content_str:
        errors.append("Content contains prohibited NUL bytes.")

    # 4. Timestamp
    raw_ts = row.get("timestamp")
    if raw_ts is None:
        raw_ts = row.get("posted_at")
    dt_utc, ts_iso, ts_errors, ts_warnings = parse_and_validate_timestamp(raw_ts)
    errors.extend(ts_errors)
    warnings.extend(ts_warnings)

    # 5. Optional Structured Indicators
    raw_structured = row.get("structured_indicators")
    if raw_structured is None:
        raw_structured = row.get("raw_indicators")
    # If flat indicators in row (e.g. from CSV)
    flat_indicators = {}
    for k in ["pgp_fingerprint", "wallet", "domain", "ip_address", "ssl_cert_fingerprint", "server_banner", "port"]:
        if k in row and row[k] is not None and str(row[k]).strip():
            flat_indicators[k] = row[k]

    combined_structured = {}
    if isinstance(raw_structured, dict):
        combined_structured.update(raw_structured)
    combined_structured.update(flat_indicators)

    valid_ind, unparsed_ind, ind_warnings = validate_structured_indicators(combined_structured)
    warnings.extend(ind_warnings)

    # Compute Dedupe Hash if basic fields exist
    dedupe_hash: Optional[str] = None
    if mkt_str and user_str and content_str:
        dedupe_hash = compute_dedupe_hash(
            marketplace=mkt_str,
            username=user_str,
            timestamp_iso_utc=ts_iso,
            content=content_str,
        )

    # Check Duplicates
    is_duplicate = False
    if dedupe_hash:
        if existing_hashes_in_batch is not None and dedupe_hash in existing_hashes_in_batch:
            is_duplicate = True
            warnings.append("Duplicate post detected within current upload batch.")
        elif existing_hashes_in_db is not None and dedupe_hash in existing_hashes_in_db:
            is_duplicate = True
            warnings.append("Duplicate post already present in an attached dataset.")

    # Determine status
    if errors:
        status = "invalid"
    elif is_duplicate:
        status = "duplicate"
    elif warnings:
        status = "valid_with_warnings"
    else:
        status = "valid"

    content_excerpt = content_str[:120].strip() if content_str else ""
    if len(content_str) > 120:
        content_excerpt += "..."

    return {
        "row_number": row_number,
        "status": status,
        "marketplace": mkt_str,
        "username": user_str,
        "timestamp": ts_iso,
        "datetime_utc": dt_utc,
        "content": content_str,
        "content_excerpt": content_excerpt,
        "dedupe_hash": dedupe_hash,
        "source_reference": (
            str(row.get("source_reference") or row.get("thread_id") or row.get("title")).strip()
            if (row.get("source_reference") or row.get("thread_id") or row.get("title"))
            else None
        ),
        "structured_indicators": valid_ind,
        "structured_indicators_unparsed": unparsed_ind,
        "errors": errors,
        "warnings": warnings,
    }
