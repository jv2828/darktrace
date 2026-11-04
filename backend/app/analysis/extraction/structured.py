"""Structured indicator normalisation and ingestion."""

import ipaddress
from typing import Any, Dict, List, Tuple
from app.analysis.extraction.banners import parse_banner_details
from app.analysis.extraction.certs import normalise_cert_fingerprint
from app.analysis.extraction.models import ExtractedIndicator
from app.analysis.extraction.network import get_ip_scope, normalise_domain
from app.analysis.extraction.pgp import normalise_pgp
from app.analysis.extraction.wallets import classify_wallet_format


def extract_structured_indicators(
    structured: Dict[str, Any],
) -> Tuple[List[ExtractedIndicator], List[str]]:
    """Convert structured indicator dictionary into validated ExtractedIndicator instances.

    Returns:
        (indicators, warnings)
    """
    indicators: List[ExtractedIndicator] = []
    warnings: List[str] = []

    if not structured or not isinstance(structured, dict):
        return indicators, warnings

    for key, raw_val in structured.items():
        if raw_val is None:
            continue

        # Handle list or single value
        values = raw_val if isinstance(raw_val, list) else [raw_val]

        for val_item in values:
            if val_item is None:
                continue
            str_val = str(val_item).strip()
            if not str_val:
                continue

            if key == "pgp_fingerprint":
                norm = normalise_pgp(str_val)
                if len(norm) in (40, 64):
                    indicators.append(
                        ExtractedIndicator(
                            indicator_type="pgp_fingerprint",
                            raw_value=str_val,
                            normalised_value=norm,
                            span_start=None,
                            span_end=None,
                            extraction_method="structured_field",
                            is_valid_format=True,
                            confidence="high",
                            details={"length": len(norm)},
                        )
                    )
                else:
                    warnings.append(f"Invalid structured PGP fingerprint: '{str_val}'")

            elif key in ("wallet", "wallet_btc", "wallet_eth", "wallet_xmr", "wallet_other"):
                w_type, w_norm, is_valid, subtype = classify_wallet_format(str_val)
                indicators.append(
                    ExtractedIndicator(
                        indicator_type=w_type,
                        raw_value=str_val,
                        normalised_value=w_norm,
                        span_start=None,
                        span_end=None,
                        extraction_method="structured_field",
                        is_valid_format=is_valid,
                        confidence="high",
                        details={"subtype": subtype, "checksum_verified": False},
                    )
                )

            elif key == "domain":
                norm = normalise_domain(str_val)
                if "." in norm or norm.endswith(".onion"):
                    indicators.append(
                        ExtractedIndicator(
                            indicator_type="domain",
                            raw_value=str_val,
                            normalised_value=norm,
                            span_start=None,
                            span_end=None,
                            extraction_method="structured_field",
                            is_valid_format=True,
                            confidence="high",
                            details={"onion": norm.endswith(".onion")},
                        )
                    )
                else:
                    warnings.append(f"Invalid structured domain: '{str_val}'")

            elif key == "ip_address":
                clean_ip = str_val.replace("[.]", ".").replace("(.)", ".")
                try:
                    ip_obj = ipaddress.ip_address(clean_ip)
                    indicators.append(
                        ExtractedIndicator(
                            indicator_type="ip_address",
                            raw_value=str_val,
                            normalised_value=str(ip_obj),
                            span_start=None,
                            span_end=None,
                            extraction_method="structured_field",
                            is_valid_format=True,
                            confidence="high",
                            details={"version": ip_obj.version, "scope": get_ip_scope(ip_obj)},
                        )
                    )
                except ValueError:
                    warnings.append(f"Invalid structured IP address: '{str_val}'")

            elif key == "ssl_cert_fingerprint":
                norm = normalise_cert_fingerprint(str_val)
                if len(norm) in (40, 64):
                    indicators.append(
                        ExtractedIndicator(
                            indicator_type="ssl_cert_fingerprint",
                            raw_value=str_val,
                            normalised_value=norm,
                            span_start=None,
                            span_end=None,
                            extraction_method="structured_field",
                            is_valid_format=True,
                            confidence="high",
                            details={"algorithm": "sha256" if len(norm) == 64 else "sha1"},
                        )
                    )
                else:
                    warnings.append(f"Invalid structured SSL cert fingerprint: '{str_val}'")

            elif key == "server_banner":
                norm = " ".join(str_val.lower().split())
                details = parse_banner_details(str_val)
                indicators.append(
                    ExtractedIndicator(
                        indicator_type="server_banner",
                        raw_value=str_val,
                        normalised_value=norm,
                        span_start=None,
                        span_end=None,
                        extraction_method="structured_field",
                        is_valid_format=True,
                        confidence="high",
                        details=details,
                    )
                )

            elif key == "port":
                try:
                    port_int = int(str_val)
                    if 1 <= port_int <= 65535:
                        indicators.append(
                            ExtractedIndicator(
                                indicator_type="port",
                                raw_value=str_val,
                                normalised_value=str(port_int),
                                span_start=None,
                                span_end=None,
                                extraction_method="structured_field",
                                is_valid_format=True,
                                confidence="high",
                                details={"port": port_int},
                            )
                        )
                    else:
                        warnings.append(f"Structured port out of range 1-65535: '{str_val}'")
                except ValueError:
                    warnings.append(f"Invalid non-integer structured port: '{str_val}'")

    return indicators, warnings

