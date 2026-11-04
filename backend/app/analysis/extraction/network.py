"""Network artifact extraction: IP addresses, ports, domains, and onion addresses."""

import ipaddress
import re
from typing import Any, Dict, List, Optional, Tuple
from app.analysis.extraction.models import ExtractedIndicator

# RFC 5737 Documentation subnets
DOC_NETWORKS = [
    ipaddress.ip_network("192.0.2.0/24"),
    ipaddress.ip_network("198.51.100.0/24"),
    ipaddress.ip_network("203.0.113.0/24"),
    ipaddress.ip_network("2001:db8::/32"),
]

# File extensions to exclude from bare domain matching
EXCLUDED_EXTENSIONS = {
    "txt", "png", "jpg", "jpeg", "gif", "pdf", "py", "js", "exe", "zip",
    "doc", "docx", "md", "json", "csv", "tar", "gz", "rar", "7z", "iso",
    "bin", "sh", "bat", "yml", "yaml", "xml", "html", "htm", "css", "log",
    "svg", "webp", "bak", "conf", "cfg", "ini", "sql", "db", "sqlite"
}

# 1. IPv4 Pattern (including defanged forms [.] and (.))
# Disallow preceding 'v' or 'version'
IPV4_CANDIDATE = re.compile(
    r'(?<![a-zA-Z0-9_\-\.])(?<![vV])(?<![vV]ersion\s)'
    r'(\b\d{1,3}(?:(?:\[\.\]|\(\.\)|\.)\d{1,3}){3}\b)'
    r'(?!\.\d)'
)

# 2. IPv6 Candidate Pattern
IPV6_CANDIDATE = re.compile(
    r'(?<![a-zA-Z0-9_\:])'
    r'('
    r'(?:[0-9a-fA-F]{1,4}:){1,7}:'
    r'|:(?::[0-9a-fA-F]{1,4}){1,7}'
    r'|(?:[0-9a-fA-F]{1,4}:){1,7}[0-9a-fA-F]{1,4}'
    r'|(?:[0-9a-fA-F]{1,4}:)+:(?:[0-9a-fA-F]{1,4}:)*[0-9a-fA-F]{1,4}'
    r'|::'
    r')'
    r'(?![a-zA-Z0-9_\:])'
)

# 3. Ports Patterns
# a. "port N", "ports N, N and N"
PORT_LABEL_PATTERN = re.compile(
    r'(?i)\bports?\s+(\d{1,5}(?:\s*(?:,\s*|and\s+)\d{1,5})*)\b'
)
# b. "N/tcp" or "N/udp"
PORT_PROTO_PATTERN = re.compile(
    r'(?i)\b(?P<port>\d{1,5})/(?P<proto>tcp|udp)\b'
)
# c. ":N" endpoint directly following domain or IP
PORT_COLON_PATTERN = re.compile(
    r'(?:[a-zA-Z0-9\.\-]|\[\.\]|\(\.\)):(?P<port>\d{1,5})\b'
)

# 4. URLs (http, https, hxxp, hxxps, ftp)
URL_PATTERN = re.compile(
    r'(?i)\b(?P<scheme>https?|hxxps?|ftp)://'
    r'(?P<auth>[^\s/@]+@)?'
    r'(?P<host>[a-zA-Z0-9\.\-\[\]\(\)]+)'
    r'(?::\d{1,5})?'
    r'(?P<path>/[^\s<>"\'\)]*)?'
)

# 5. Onion addresses (.onion v3 = 56 b32 chars, v2 = 16 b32 chars)
ONION_PATTERN = re.compile(
    r'(?i)\b(?P<onion>[a-z2-7]{56}|[a-z2-7]{16})\.onion\b'
)

# 6. Email addresses (extract domain part)
EMAIL_PATTERN = re.compile(
    r'\b[a-zA-Z0-9_.+-]+@(?P<domain>[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)\b'
)

# 7. Bare domains (labels + TLD, defanged forms)
BARE_DOMAIN_PATTERN = re.compile(
    r'(?i)\b([a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?'
    r'(?:(?:\[\.\]|\(\.\)|\[dot\]|\.)[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*'
    r'(?:\[\.\]|\(\.\)|\[dot\]|\.)'
    r'(?:[a-zA-Z]{2,24}|example|invalid))\b'
)


def get_ip_scope(ip_obj: ipaddress.IPv4Address | ipaddress.IPv6Address) -> str:
    """Classify IP scope into documentation, loopback, private, link_local, multicast, or public."""
    for doc_net in DOC_NETWORKS:
        if ip_obj in doc_net:
            return "documentation"
    if ip_obj.is_loopback:
        return "loopback"
    if ip_obj.is_private:
        return "private"
    if ip_obj.is_link_local:
        return "link_local"
    if ip_obj.is_multicast:
        return "multicast"
    return "public"


def normalise_domain(raw_host: str) -> str:
    """Normalise domain or onion address: clean defanging, lowercase, strip trailing dot, punycode."""
    cleaned = raw_host.strip()
    cleaned = cleaned.replace("[.]", ".").replace("(.)", ".").replace("[dot]", ".").replace("(dot)", ".")
    if cleaned.endswith("."):
        cleaned = cleaned[:-1]
    # Lowercase
    cleaned = cleaned.lower()
    # IDNA encoding for non-ascii characters
    try:
        cleaned = cleaned.encode("idna").decode("ascii")
    except Exception:
        pass
    return cleaned


def extract_ips(content: str) -> List[ExtractedIndicator]:
    """Extract and validate IPv4 and IPv6 addresses."""
    indicators: List[ExtractedIndicator] = []
    seen_spans = set()

    # 1. IPv4 Candidates
    for m in IPV4_CANDIDATE.finditer(content):
        raw = m.group(1)
        start = m.start(1)
        end = m.end(1)

        # Check if preceding character is 'v' or 'V' or version word
        pre_char = content[max(0, start - 1) : start]
        if pre_char.lower() == 'v':
            continue
        pre_word = content[max(0, start - 10) : start].lower()
        if pre_word.endswith("version ") or pre_word.endswith("version"):
            continue

        clean_ip = raw.replace("[.]", ".").replace("(.)", ".")
        # Reject if octets out of range or not 4 octets
        try:
            ip_obj = ipaddress.IPv4Address(clean_ip)
            norm = str(ip_obj)
            scope = get_ip_scope(ip_obj)

            seen_spans.add((start, end))
            indicators.append(
                ExtractedIndicator(
                    indicator_type="ip_address",
                    raw_value=raw,
                    normalised_value=norm,
                    span_start=start,
                    span_end=end,
                    extraction_method="regex",
                    is_valid_format=True,
                    confidence="high",
                    details={
                        "version": 4,
                        "scope": scope,
                        "defanged": clean_ip != raw,
                    },
                )
            )
        except ValueError:
            continue

    # 2. IPv6 Candidates
    for m in IPV6_CANDIDATE.finditer(content):
        start = m.start(1)
        end = m.end(1)
        if any(max(start, s) < min(end, e) for s, e in seen_spans):
            continue

        raw = m.group(1)
        # Must contain at least two colons to be candidate IPv6
        if raw.count(":") < 2:
            continue

        try:
            ip_obj = ipaddress.IPv6Address(raw)
            norm = str(ip_obj)
            scope = get_ip_scope(ip_obj)

            seen_spans.add((start, end))
            indicators.append(
                ExtractedIndicator(
                    indicator_type="ip_address",
                    raw_value=raw,
                    normalised_value=norm,
                    span_start=start,
                    span_end=end,
                    extraction_method="regex",
                    is_valid_format=True,
                    confidence="high",
                    details={
                        "version": 6,
                        "scope": scope,
                        "defanged": False,
                    },
                )
            )
        except ValueError:
            continue

    return indicators


def extract_ports(content: str) -> List[ExtractedIndicator]:
    """Extract port numbers with mandatory explicit context."""
    indicators: List[ExtractedIndicator] = []
    seen_spans = set()

    def add_port(raw_port: str, start: int, end: int, proto: Optional[str] = None):
        try:
            port_int = int(raw_port)
            if 1 <= port_int <= 65535:
                norm = str(port_int)
                span = (start, end)
                if span not in seen_spans:
                    seen_spans.add(span)
                    details: Dict[str, Any] = {"port": port_int}
                    if proto:
                        details["protocol"] = proto.lower()
                    indicators.append(
                        ExtractedIndicator(
                            indicator_type="port",
                            raw_value=content[start:end],
                            normalised_value=norm,
                            span_start=start,
                            span_end=end,
                            extraction_method="regex",
                            is_valid_format=True,
                            confidence="high",
                            details=details,
                        )
                    )
        except ValueError:
            pass

    # 1. "N/tcp" or "N/udp" (Run first to capture protocol detail)
    for m in PORT_PROTO_PATTERN.finditer(content):
        p_str = m.group("port")
        proto = m.group("proto")
        add_port(p_str, m.start("port"), m.end("port"), proto=proto)

    # 2. "port N", "ports N, N and N"
    for m in PORT_LABEL_PATTERN.finditer(content):
        full_group = m.group(1)
        base_offset = m.start(1)
        # Find all digit sequences inside the group
        for num_m in re.finditer(r'\b\d{1,5}\b', full_group):
            num_str = num_m.group(0)
            p_start = base_offset + num_m.start()
            p_end = base_offset + num_m.end()
            if (p_start, p_end) not in seen_spans:
                add_port(num_str, p_start, p_end)

    # 3. ":N" directly following an IP or domain
    for m in PORT_COLON_PATTERN.finditer(content):
        p_str = m.group("port")
        add_port(p_str, m.start("port"), m.end("port"))

    return indicators


def extract_domains_and_onions(content: str) -> List[ExtractedIndicator]:
    """Extract URLs, onion services, email domains, and hostnames."""
    indicators: List[ExtractedIndicator] = []
    seen_spans = set()

    # 1. URLs
    for m in URL_PATTERN.finditer(content):
        raw_host = m.group("host")
        scheme = m.group("scheme").lower()
        path = m.group("path")
        h_start = m.start("host")
        h_end = m.end("host")

        # Skip if host is a pure IPv4 address (will be captured as IP)
        clean_host = raw_host.replace("[.]", ".").replace("(.)", ".")
        try:
            ipaddress.IPv4Address(clean_host)
            continue
        except ValueError:
            pass

        norm = normalise_domain(raw_host)
        seen_spans.add((h_start, h_end))
        indicators.append(
            ExtractedIndicator(
                indicator_type="domain",
                raw_value=content[h_start:h_end],
                normalised_value=norm,
                span_start=h_start,
                span_end=h_end,
                extraction_method="regex",
                is_valid_format=True,
                confidence="high",
                details={
                    "scheme": scheme,
                    "path_present": bool(path),
                    "onion": norm.endswith(".onion"),
                },
            )
        )

    # 2. Onion addresses (standalone)
    for m in ONION_PATTERN.finditer(content):
        span = (m.start(), m.end())
        if any(max(span[0], s) < min(span[1], e) for s, e in seen_spans):
            continue

        raw = m.group(0)
        norm = raw.lower()
        onion_hash = m.group("onion")
        seen_spans.add(span)
        indicators.append(
            ExtractedIndicator(
                indicator_type="domain",
                raw_value=raw,
                normalised_value=norm,
                span_start=m.start(),
                span_end=m.end(),
                extraction_method="regex",
                is_valid_format=True,
                confidence="high",
                details={
                    "onion": True,
                    "onion_version": 3 if len(onion_hash) == 56 else 2,
                },
            )
        )

    # 3. Email addresses (domain portion)
    for m in EMAIL_PATTERN.finditer(content):
        d_start = m.start("domain")
        d_end = m.end("domain")
        span = (d_start, d_end)
        if any(max(span[0], s) < min(span[1], e) for s, e in seen_spans):
            continue

        raw_domain = m.group("domain")
        norm = normalise_domain(raw_domain)
        seen_spans.add(span)
        indicators.append(
            ExtractedIndicator(
                indicator_type="domain",
                raw_value=raw_domain,
                normalised_value=norm,
                span_start=d_start,
                span_end=d_end,
                extraction_method="regex",
                is_valid_format=True,
                confidence="high",
                details={"source": "email"},
            )
        )

    # 4. Bare hostnames and defanged domains
    for m in BARE_DOMAIN_PATTERN.finditer(content):
        span = (m.start(), m.end())
        if any(max(span[0], s) < min(span[1], e) for s, e in seen_spans):
            continue

        raw = m.group(0)
        norm = normalise_domain(raw)

        # Skip bare onion domains; onions must be matched via ONION_PATTERN or URL_PATTERN
        if norm.endswith(".onion"):
            continue

        # Check if last token is an excluded file extension (e.g. notes.txt, image.png)
        parts = norm.split(".")
        if len(parts) >= 2 and parts[-1].lower() in EXCLUDED_EXTENSIONS:
            continue

        # Skip if all digits (e.g. invalid IP)
        if all(p.isdigit() for p in parts):
            continue

        seen_spans.add(span)
        indicators.append(
            ExtractedIndicator(
                indicator_type="domain",
                raw_value=raw,
                normalised_value=norm,
                span_start=m.start(),
                span_end=m.end(),
                extraction_method="regex",
                is_valid_format=True,
                confidence="high",
                details={
                    "defanged": norm != raw.lower(),
                    "onion": norm.endswith(".onion"),
                },
            )
        )

    return indicators
