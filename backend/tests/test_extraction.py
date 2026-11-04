"""Unit tests for technical threat indicator extraction, normalisation, and span resolution."""

import time
import pytest
from app.analysis.extraction import (
    EXTRACTOR_VERSION,
    extract_all,
)
from app.analysis.extraction.network import normalise_domain
from app.analysis.extraction.pgp import normalise_pgp


def test_extractor_version_string():
    assert EXTRACTOR_VERSION == "1.0.0"


# ============================================================================
# 1. PGP Fingerprints
# ============================================================================

def test_pgp_fingerprint_formats_normalise_equal():
    """Spaced groups, colon pairs, lowercase, 0x, and double-space midpoint normalise to same."""
    base_fingerprint = "E4A18B9C2D3E4F5A6B7C8D9E0F1A2B3C4D5E6F7A"
    variants = [
        # Spaced groups of 4
        "E4A1 8B9C 2D3E 4F5A 6B7C 8D9E 0F1A 2B3C 4D5E 6F7A",
        # Non-breaking space
        "E4A1\u00a08B9C\u00a02D3E\u00a04F5A\u00a06B7C\u00a08D9E\u00a00F1A\u00a02B3C\u00a04D5E\u00a06F7A",
        # Midpoint double-space
        "E4A1 8B9C 2D3E 4F5A 6B7C  8D9E 0F1A 2B3C 4D5E 6F7A",
        # Colon-separated pairs
        "E4:A1:8B:9C:2D:3E:4F:5A:6B:7C:8D:9E:0F:1A:2B:3C:4D:5E:6F:7A",
        # 0x prefixed uppercase
        "0xE4A18B9C2D3E4F5A6B7C8D9E0F1A2B3C4D5E6F7A",
        # 0x prefixed lowercase
        "0xe4a18b9c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a",
        # Continuous lowercase with preceding label
        "gpg key e4a18b9c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a",
    ]

    for v in variants:
        res = extract_all(v)
        pgp_inds = [i for i in res.indicators if i.indicator_type == "pgp_fingerprint"]
        assert len(pgp_inds) == 1, f"Failed variant: {v}"
        assert pgp_inds[0].normalised_value == base_fingerprint
        assert pgp_inds[0].confidence == "high"


def test_unlabeled_sha1_hash_not_pgp():
    """A 40-hex SHA-1 hash with no label must NOT be extracted as a PGP fingerprint."""
    raw = "Commit sha 2fd4e1c67a2d28fced849ee1bb76e7391b93eb12 pushed to master."
    res = extract_all(raw)
    pgp_inds = [i for i in res.indicators if i.indicator_type == "pgp_fingerprint"]
    assert len(pgp_inds) == 0


def test_unlabeled_64hex_skipped_as_ambiguous():
    """An unlabeled 64-hex run is ambiguous (could be SHA256 or cert or random) and is skipped."""
    raw = "Data integrity hash: e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 verified."
    res = extract_all(raw)
    certs = [i for i in res.indicators if i.indicator_type == "ssl_cert_fingerprint"]
    pgps = [i for i in res.indicators if i.indicator_type == "pgp_fingerprint"]
    assert len(certs) == 0
    assert len(pgps) == 0


# ============================================================================
# 2. Wallets & Case Sensitivity
# ============================================================================

def test_wallet_case_preservation_and_normalization():
    """ETH normalises to lowercase; XMR and BTC Legacy retain case-sensitive characters."""
    eth_mixed = "0x71C7656EC7ab88b098defB751B7401B5f6d8976F"
    btc_legacy = "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"
    xmr_address = "44AFFq5Axm6GryM2P356AJfLZVypt1UnKEjnC2vgMb5SFWaWCKPGLVu945Wch2XJnMiFYwgMMMrCkeuoLtxAs3AGQRqquPE"
    btc_bech32 = "bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq"

    text = f"ETH: {eth_mixed} | BTC: {btc_legacy} | XMR: {xmr_address} | BECH32: {btc_bech32}"
    res = extract_all(text)

    eth = next(i for i in res.indicators if i.indicator_type == "wallet_eth")
    assert eth.normalised_value == eth_mixed.lower()
    assert eth.raw_value == eth_mixed

    btc_leg = next(i for i in res.indicators if i.indicator_type == "wallet_btc" and i.details.get("subtype") == "legacy")
    assert btc_leg.normalised_value == btc_legacy  # Exact case preserved!
    assert btc_leg.raw_value == btc_legacy

    xmr = next(i for i in res.indicators if i.indicator_type == "wallet_xmr")
    assert xmr.normalised_value == xmr_address  # Exact case preserved!
    assert xmr.raw_value == xmr_address

    bech = next(i for i in res.indicators if i.indicator_type == "wallet_btc" and i.details.get("subtype") == "bech32")
    assert bech.normalised_value == btc_bech32.lower()


# ============================================================================
# 3. IP Addresses & Span Slicing
# ============================================================================

def test_defanged_ips_and_original_spans():
    """Defanged IPv4 text[span_start:span_end] == raw_value exactly."""
    text = "Relay node 192[.]0[.]2[.]10 and secondary 198(.)51(.)100(.)42 are running."
    res = extract_all(text)

    ips = [i for i in res.indicators if i.indicator_type == "ip_address"]
    assert len(ips) == 2

    for ip_ind in ips:
        assert text[ip_ind.span_start : ip_ind.span_end] == ip_ind.raw_value
        assert ip_ind.details["defanged"] is True
        assert ip_ind.details["scope"] == "documentation"

    assert ips[0].normalised_value == "192.0.2.10"
    assert ips[1].normalised_value == "198.51.100.42"


def test_ip_boundary_rules():
    """IPv4 inside 'v1.2.3.4' is skipped; octet 256 is rejected; 5-octet numbers rejected."""
    text = "Upgraded to v1.2.3.4. Invalid octet: 192.0.2.256. Long dotted: 10.0.0.1.2. Valid: 203.0.113.5."
    res = extract_all(text)
    ips = [i for i in res.indicators if i.indicator_type == "ip_address"]
    assert len(ips) == 1
    assert ips[0].normalised_value == "203.0.113.5"


def test_ipv6_normalization():
    """IPv6 compressed and expanded forms normalise to the same compressed format."""
    expanded = "2001:0db8:0000:0000:0000:0000:0000:0001"
    compressed = "2001:db8::1"
    res1 = extract_all(f"Address {expanded}")
    res2 = extract_all(f"Address {compressed}")

    assert res1.indicators[0].normalised_value == "2001:db8::1"
    assert res2.indicators[0].normalised_value == "2001:db8::1"
    assert res1.indicators[0].details["scope"] == "documentation"


# ============================================================================
# 4. Ports
# ============================================================================

def test_ports_require_explicit_context():
    """Port numbers are only extracted with explicit context; bare numbers ignored."""
    text = "We have 80 apples, 443 oranges, but port 8080 and 8443/tcp or endpoint 198.51.100.42:9000 are open."
    res = extract_all(text)
    ports = [i for i in res.indicators if i.indicator_type == "port"]
    port_vals = {p.normalised_value for p in ports}
    assert port_vals == {"8080", "8443", "9000"}
    assert "80" not in port_vals
    assert "443" not in port_vals

    tcp_port = next(p for p in ports if p.normalised_value == "8443")
    assert tcp_port.details.get("protocol") == "tcp"


# ============================================================================
# 5. Domains, Onion, Filename Exclusions, and Email
# ============================================================================

def test_domain_filename_exclusions_and_emails():
    """Filenames like notes.txt are excluded; email domains have details.source='email'."""
    text = "Download notes.txt and diagram.png from https://secure.mesh.example/files or email admin@darknet-hub.invalid"
    res = extract_all(text)
    domains = [i for i in res.indicators if i.indicator_type == "domain"]
    domain_vals = {d.normalised_value: d for d in domains}

    assert "notes.txt" not in domain_vals
    assert "diagram.png" not in domain_vals
    assert "secure.mesh.example" in domain_vals
    assert "darknet-hub.invalid" in domain_vals

    email_domain = domain_vals["darknet-hub.invalid"]
    assert email_domain.details.get("source") == "email"
    assert text[email_domain.span_start : email_domain.span_end] == "darknet-hub.invalid"


def test_onion_v3_length_check():
    """Onion addresses require 56 base32 characters for v3."""
    v3 = "fictionalabcdefghijklmnopqrstuvwxyz234567abcdefghijklmno.onion"
    too_short = "short.onion"
    text = f"Visit {v3} or fake {too_short}"
    res = extract_all(text)
    domains = [i for i in res.indicators if i.indicator_type == "domain"]
    assert len(domains) == 1
    assert domains[0].normalised_value == v3
    assert domains[0].details["onion_version"] == 3


# ============================================================================
# 6. Server Banners and Cert Metadata
# ============================================================================

def test_server_banner_and_cert_metadata():
    """Server headers and cert metadata fields are parsed cleanly."""
    text = (
        "Server: nginx/1.18.0 (Ubuntu)\n"
        "SSH-2.0-OpenSSH_8.2p1 Ubuntu-4ubuntu0.5\n"
        "TLS Subject: CN=vpn.mesh.example, Issuer: Fictional CA, Serial: 0A:1B:2C:3D\n"
    )
    res = extract_all(text)

    banners = [i for i in res.indicators if i.indicator_type == "server_banner"]
    meta = [i for i in res.indicators if i.indicator_type == "cert_metadata"]

    assert len(banners) >= 2
    assert any("nginx" in b.normalised_value for b in banners)
    assert any("ssh" in b.normalised_value for b in banners)

    meta_vals = {m.details.get("field"): m.normalised_value for m in meta}
    assert meta_vals.get("subject_cn") == "subject_cn:vpn.mesh.example"
    assert meta_vals.get("issuer") == "issuer:fictional ca"
    assert meta_vals.get("serial") == "serial:0A1B2C3D"


# ============================================================================
# 7. Deduplication, Span Overlaps, and Structured Merging
# ============================================================================

def test_deduplication_within_post_records_occurrences_and_all_spans():
    """Multiple occurrences of the same indicator within text record occurrences and all_spans."""
    text = "Send to 198.51.100.55 first, and if down retry 198.51.100.55."
    res = extract_all(text)
    ips = [i for i in res.indicators if i.indicator_type == "ip_address"]
    assert len(ips) == 1  # Deduped to 1 indicator
    assert ips[0].details["occurrences"] == 2
    assert len(ips[0].details["all_spans"]) == 2
    for s, e in ips[0].details["all_spans"]:
        assert text[s:e] == "198.51.100.55"


def test_no_partial_overlaps():
    """Overlapping spans must resolve by priority without partial span intersections."""
    # A labelled cert fingerprint containing a potential IP or subtoken
    text = "Certificate SHA256: E3:B0:C4:42:98:FC:1C:14:9A:FB:F4:C8:99:6F:B9:24:27:AE:41:E4:64:9B:93:4C:A4:95:99:1B:78:52:B8:55"
    res = extract_all(text)
    spans = [(i.span_start, i.span_end) for i in res.indicators if i.span_start is not None]
    for idx1, (s1, e1) in enumerate(spans):
        for idx2, (s2, e2) in enumerate(spans):
            if idx1 != idx2:
                # Must not partially overlap
                assert not (max(s1, s2) < min(e1, e2)), f"Overlapping spans: ({s1},{e1}) and ({s2},{e2})"


def test_structured_fields_merged_with_flag():
    """Structured fields matching text indicators set also_in_structured_field=True."""
    text = "Our public key is E4A1 8B9C 2D3E 4F5A 6B7C  8D9E 0F1A 2B3C 4D5E 6F7A."
    struct = {
        "pgp_fingerprint": "E4A18B9C2D3E4F5A6B7C8D9E0F1A2B3C4D5E6F7A",
        "wallet": "bc1q9d4k2t8x7m1w5p3z0s6y8v2c4b6n8m0k2j4h6f",
    }
    res = extract_all(text, structured=struct)
    by_type = {i.indicator_type: i for i in res.indicators}

    pgp = by_type["pgp_fingerprint"]
    assert pgp.extraction_method == "regex"
    assert pgp.span_start is not None
    assert pgp.details.get("also_in_structured_field") is True

    wallet = by_type["wallet_btc"]
    assert wallet.extraction_method == "structured_field"
    assert wallet.span_start is None
    assert wallet.details.get("also_in_structured_field") is True


# ============================================================================
# 8. Performance Test
# ============================================================================

def test_adversarial_performance_under_one_second():
    """20,000 characters of adversarial input completes in under 1 second."""
    adversarial = (
        ("a." * 2000)
        + ("[.]" * 1000)
        + ("0x" * 1000)
        + ("f" * 5000)
        + ("port 80, 80 and " * 500)
    )[:20000]

    t0 = time.perf_counter()
    res = extract_all(adversarial)
    elapsed = time.perf_counter() - t0

    assert elapsed < 1.0, f"Extraction took too long: {elapsed:.3f}s"
    assert res.text_stats.char_count == 20000
