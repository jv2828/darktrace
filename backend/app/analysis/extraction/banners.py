"""Server banner extraction and parsing."""

import re
from typing import Any, Dict, List, Optional, Tuple
from app.analysis.extraction.models import ExtractedIndicator

# Known server products
PRODUCTS = [
    "nginx", "Apache", "lighttpd", "Microsoft-IIS", "OpenSSH",
    "Caddy", "Tomcat", "Jetty", "Gunicorn", "Express", "OpenResty",
]

# 1. "Server: <value>" header line
SERVER_HEADER_PATTERN = re.compile(
    r'(?i)^Server:\s*([^\r\n]+)',
    re.MULTILINE,
)

# 2. "SSH-2.0-<value>" banner
SSH_BANNER_PATTERN = re.compile(
    r'\b(SSH-2\.0-[^\s\r\n]+)\b'
)

# 3. Known product tokens followed by a version string
PRODUCT_VERSION_PATTERN = re.compile(
    r'(?i)\b('
    + '|'.join(re.escape(p) for p in PRODUCTS)
    + r')[/_ ]v?(\d+(?:\.\d+)*(?:[a-zA-Z0-9_\-\.]+)?(?:\s*\([^\)\r\n]+\))?)'
)


def parse_banner_details(banner_str: str) -> Dict[str, Any]:
    """Parse product name, version, and optional OS hint from a banner string."""
    details: Dict[str, Any] = {}
    cleaned = banner_str.strip()

    # Check for OS hint in parentheses, e.g. "(Ubuntu)", "(Debian)"
    os_match = re.search(r'\(([^)]+)\)', cleaned)
    if os_match:
        details["os_hint"] = os_match.group(1).strip().lower()

    # Try matching product and version
    for prod in PRODUCTS:
        pattern = re.compile(
            rf'(?i)\b{re.escape(prod)}[/_ ]v?([0-9a-zA-Z_\-\.]+)'
        )
        m = pattern.search(cleaned)
        if m:
            details["product"] = prod.lower()
            details["version"] = m.group(1).strip()
            break

    if "product" not in details:
        # Fallback to first word
        first_token = cleaned.split()[0].split("/")[0]
        details["product"] = first_token.lower()

    return details


def extract_server_banners(content: str) -> List[ExtractedIndicator]:
    """Extract web server and service banners from post text."""
    indicators: List[ExtractedIndicator] = []
    seen_spans = set()

    # 1. Server: header lines
    for m in SERVER_HEADER_PATTERN.finditer(content):
        raw = m.group(1).strip()
        start = m.start(1)
        end = m.end(1)
        norm = " ".join(raw.lower().split())
        seen_spans.add((start, end))
        details = parse_banner_details(raw)
        indicators.append(
            ExtractedIndicator(
                indicator_type="server_banner",
                raw_value=raw,
                normalised_value=norm,
                span_start=start,
                span_end=end,
                extraction_method="regex",
                is_valid_format=True,
                confidence="high",
                details=details,
            )
        )

    # 2. SSH-2.0- banners
    for m in SSH_BANNER_PATTERN.finditer(content):
        span = (m.start(1), m.end(1))
        if span in seen_spans:
            continue
        raw = m.group(1)
        norm = raw.lower()
        seen_spans.add(span)
        indicators.append(
            ExtractedIndicator(
                indicator_type="server_banner",
                raw_value=raw,
                normalised_value=norm,
                span_start=span[0],
                span_end=span[1],
                extraction_method="regex",
                is_valid_format=True,
                confidence="high",
                details={"product": "openssh", "banner": norm},
            )
        )

    # 3. Known product tokens with version
    for m in PRODUCT_VERSION_PATTERN.finditer(content):
        span = (m.start(0), m.end(0))
        if any(max(span[0], s) < min(span[1], e) for s, e in seen_spans):
            continue
        raw = m.group(0)
        norm = " ".join(raw.lower().split())
        seen_spans.add(span)
        details = parse_banner_details(raw)
        indicators.append(
            ExtractedIndicator(
                indicator_type="server_banner",
                raw_value=raw,
                normalised_value=norm,
                span_start=span[0],
                span_end=span[1],
                extraction_method="regex",
                is_valid_format=True,
                confidence="high",
                details=details,
            )
        )

    return indicators

