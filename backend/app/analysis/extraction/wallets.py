"""Cryptocurrency wallet address extraction and validation."""

import re
from typing import List, Tuple
from app.analysis.extraction.models import ExtractedIndicator

# BTC Bech32 (mainnet bc1, testnet tb1)
BTC_BECH32_PATTERN = re.compile(
    r'(?<![a-zA-Z0-9])((?:bc1|tb1)[0-9a-z]{11,71})(?![a-zA-Z0-9])'
)

# BTC Legacy Base58 (P2PKH starting with 1, P2SH starting with 3; 26-35 chars)
BTC_LEGACY_PATTERN = re.compile(
    r'(?<![a-zA-Z0-9])([13][1-9A-HJ-NP-Za-km-z]{25,34})(?![a-zA-Z0-9])'
)

# ETH (0x prefix + 40 hex)
ETH_PATTERN = re.compile(
    r'(?i)(?<![0-9a-zA-Z])(0x[0-9a-fA-F]{40})(?![0-9a-zA-Z])'
)

# XMR (Monero, 95 Base58 chars starting with 4 or 8)
XMR_PATTERN = re.compile(
    r'(?<![a-zA-Z0-9])([48][1-9A-HJ-NP-Za-km-z]{94})(?![a-zA-Z0-9])'
)

# Labelled generic / other crypto wallet
OTHER_WALLET_PATTERN = re.compile(
    r'(?i)\b(?:wallet|address|crypto|pay|escrow|settlement)\s*[:=]\s*([1-9A-HJ-NP-Za-km-z]{20,95})\b'
)


def classify_wallet_format(raw_address: str) -> Tuple[str, str, bool, str]:
    """Classify a wallet address by its string format.

    Returns:
        (indicator_type, normalised_value, is_valid_format, subtype)
    """
    val = raw_address.strip()

    # 1. BTC Bech32
    if (val.startswith("bc1") or val.startswith("tb1")) and 14 <= len(val) <= 74:
        base32_chars = set("0123456789abcdefghijklmnopqrstuvwxyz")
        if all(c in base32_chars for c in val[3:].lower()):
            return "wallet_btc", val.lower(), True, "bech32"

    # 2. ETH
    if val.lower().startswith("0x") and len(val) == 42:
        hex_chars = set("0123456789abcdefABCDEF")
        if all(c in hex_chars for c in val[2:]):
            return "wallet_eth", val.lower(), True, "eth"

    # 3. XMR
    if val.startswith(("4", "8")) and len(val) == 95:
        b58_chars = set("123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz")
        if all(c in b58_chars for c in val):
            return "wallet_xmr", val, True, "xmr"  # Case-sensitive!

    # 4. BTC Legacy Base58
    if val.startswith(("1", "3")) and 26 <= len(val) <= 35:
        b58_chars = set("123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz")
        if all(c in b58_chars for c in val):
            has_digit = any(c.isdigit() for c in val)
            has_letter = any(c.isalpha() for c in val)
            if has_digit and has_letter:
                return "wallet_btc", val, True, "legacy"  # Case-sensitive!

    # Fallback to wallet_other
    return "wallet_other", val, True, "other"


def extract_wallets(content: str) -> List[ExtractedIndicator]:
    """Extract cryptocurrency wallet addresses from text."""
    indicators: List[ExtractedIndicator] = []
    seen_spans = set()

    # 1. BTC Bech32
    for m in BTC_BECH32_PATTERN.finditer(content):
        raw = m.group(1)
        norm = raw.lower()
        seen_spans.add((m.start(1), m.end(1)))
        indicators.append(
            ExtractedIndicator(
                indicator_type="wallet_btc",
                raw_value=raw,
                normalised_value=norm,
                span_start=m.start(1),
                span_end=m.end(1),
                extraction_method="regex",
                is_valid_format=True,
                confidence="high",
                details={"subtype": "bech32", "checksum_verified": False},
            )
        )

    # 2. ETH
    for m in ETH_PATTERN.finditer(content):
        raw = m.group(1)
        norm = raw.lower()
        seen_spans.add((m.start(1), m.end(1)))
        indicators.append(
            ExtractedIndicator(
                indicator_type="wallet_eth",
                raw_value=raw,
                normalised_value=norm,
                span_start=m.start(1),
                span_end=m.end(1),
                extraction_method="regex",
                is_valid_format=True,
                confidence="high",
                details={"subtype": "eth", "checksum_verified": False},
            )
        )

    # 3. XMR
    for m in XMR_PATTERN.finditer(content):
        raw = m.group(1)
        # Monero is case-sensitive!
        seen_spans.add((m.start(1), m.end(1)))
        indicators.append(
            ExtractedIndicator(
                indicator_type="wallet_xmr",
                raw_value=raw,
                normalised_value=raw,
                span_start=m.start(1),
                span_end=m.end(1),
                extraction_method="regex",
                is_valid_format=True,
                confidence="high",
                details={"subtype": "xmr", "checksum_verified": False},
            )
        )

    # 4. BTC Legacy Base58
    for m in BTC_LEGACY_PATTERN.finditer(content):
        span = (m.start(1), m.end(1))
        if span in seen_spans:
            continue
        raw = m.group(1)
        has_digit = any(c.isdigit() for c in raw)
        has_letter = any(c.isalpha() for c in raw)
        if not (has_digit and has_letter):
            continue
        # Base58 legacy is case-sensitive!
        seen_spans.add(span)
        indicators.append(
            ExtractedIndicator(
                indicator_type="wallet_btc",
                raw_value=raw,
                normalised_value=raw,
                span_start=m.start(1),
                span_end=m.end(1),
                extraction_method="regex",
                is_valid_format=True,
                confidence="high",
                details={"subtype": "legacy", "checksum_verified": False},
            )
        )

    # 5. Labelled other wallets
    for m in OTHER_WALLET_PATTERN.finditer(content):
        span = (m.start(1), m.end(1))
        if any(max(span[0], s) < min(span[1], e) for s, e in seen_spans):
            continue
        raw = m.group(1)
        w_type, w_norm, is_valid, subtype = classify_wallet_format(raw)
        seen_spans.add(span)
        indicators.append(
            ExtractedIndicator(
                indicator_type=w_type,
                raw_value=raw,
                normalised_value=w_norm,
                span_start=m.start(1),
                span_end=m.end(1),
                extraction_method="regex",
                is_valid_format=is_valid,
                confidence="high" if w_type != "wallet_other" else "medium",
                details={"subtype": subtype, "checksum_verified": False},
            )
        )

    return indicators
