#!/usr/bin/env python3
"""Deterministic Synthetic Data & Ground Truth Generator for DARKTRACE.

Generates:
  - backend/datasets/sample/alpha.json
  - backend/datasets/sample/beta.json
  - backend/datasets/ground_truth/alpha_truth.json
  - backend/datasets/ground_truth/beta_truth.json

STRICT SAFETY RULES:
  - Completely fictional dark web marketplace chatter.
  - No real illicit goods, instructions, malware, credentials, or real identities.
  - IP addresses strictly from RFC 5737 ranges (192.0.2.0/24, 198.51.100.0/24, 203.0.113.0/24).
  - Domains strictly end in .example or .invalid.
  - Onion domains start with 'fictional' + base32 + '.onion'.
  - Deterministic: uses random.Random(seed), sorted outputs, no datetime.now().
"""

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import random
from typing import Any, Dict, List, Optional, Tuple

# Base reference timestamp window (UTC)
BASE_START = datetime(2026, 1, 5, 0, 0, 0, tzinfo=timezone.utc)
BASE_END = datetime(2026, 4, 5, 23, 59, 59, tzinfo=timezone.utc)
TOTAL_WINDOW_SECONDS = int((BASE_END - BASE_START).total_seconds())

RFC5737_SUBNETS = [
    (192, 0, 2),     # 192.0.2.0/24 (TEST-NET-1)
    (198, 51, 100),  # 198.51.100.0/24 (TEST-NET-2)
    (203, 0, 113),   # 203.0.113.0/24 (TEST-NET-3)
]

SERVER_BANNERS = [
    "nginx/1.18.0 (Ubuntu)",
    "Apache/2.4.41 (Debian)",
    "OpenResty/1.19.9.1",
    "lighttpd/1.4.55",
]

ALLOWED_PORTS = [80, 443, 8080, 8443, 22]

# Shared topic bank (benign, fictional marketplace chatter)
SHARED_TOPICS = [
    {
        "topic": "clockwork_restock",
        "templates": [
            "Batch {batch_id} of precision clockwork mechanical gear assemblies has landed in storage.",
            "All handcrafted brass escapement modules have completed torque calibration and quality testing.",
            "We have restocked our artisan clockwork movement units for watchmakers and hobbyist engineers.",
            "Inventory levels for precision miniature drive trains are now updated on our primary catalog.",
        ],
    },
    {
        "topic": "hardware_ledger",
        "templates": [
            "New shipment of encrypted ledger micro-controller development boards is ready for dispatch.",
            "Each custom hardware board includes pre-flashed open-source cryptographic bootloaders.",
            "Secure enclave dual-core prototype units have passed burn-in testing without diagnostic faults.",
            "Bulk orders for cryptographic hardware modules now include complementary anti-static shielding.",
        ],
    },
    {
        "topic": "shipping_delay",
        "templates": [
            "Severe coastal winter storms are causing a 48-hour routing delay at central logistics hubs.",
            "Logistics dispatch confirms that international parcels will clear customs routing by midweek.",
            "Regional freight transport maintenance has temporarily shifted our express delivery schedule.",
            "All in-transit orders remain tracked under full escrow protection despite postal transit backlogs.",
        ],
    },
    {
        "topic": "escrow_release",
        "templates": [
            "Multisig milestone release confirmed for order #{order_id}; thanking both parties for clarity.",
            "Buyer verification acknowledged on the 2-of-3 escrow portal; funds successfully released.",
            "Friendly reminder to finalize escrow confirmation once physical inspection of the batch is complete.",
            "Escrow dispute resolved amicably through platform mediation with mutual satisfaction.",
        ],
    },
    {
        "topic": "feedback_reply",
        "templates": [
            "Thank you for the comprehensive five-star review regarding our component packaging standards.",
            "We appreciate your continued patronage and constructive feedback on our delivery speeds.",
            "Pleased to hear the delicate ceramic capacitor assortment arrived in pristine condition.",
            "Feedback from long-time patrons helps us refine our supply channels and trade procedures.",
        ],
    },
    {
        "topic": "key_rotation",
        "templates": [
            "Scheduled annual PGP communication key rotation announcement with signed transition statements.",
            "Please verify our newly generated public subkeys against our primary administrative fingerprint.",
            "Do not transmit encrypted requisitions using our deprecated 2025 subkey; see updated fingerprint below.",
            "Key transition protocol signed with master key; archived proof is hosted on our verified onion mirror.",
        ],
    },
]


def generate_rfc5737_ip(rng: random.Random) -> str:
    subnet = rng.choice(RFC5737_SUBNETS)
    host = rng.randint(1, 254)
    return f"{subnet[0]}.{subnet[1]}.{subnet[2]}.{host}"


def generate_onion(rng: random.Random) -> str:
    b32_chars = "abcdefghijklmnopqrstuvwxyz234567"
    slug = "".join(rng.choice(b32_chars) for _ in range(47))
    return f"fictional{slug}.onion"


def generate_pgp_fingerprint(rng: random.Random) -> str:
    hex_chars = "0123456789ABCDEF"
    return "".join(rng.choice(hex_chars) for _ in range(40))


def generate_wallet(rng: random.Random, coin_type: str = "btc") -> str:
    if coin_type == "btc":
        b32 = "023456789acdefghjkmnpqrstuvwxyz"
        return "bc1q" + "".join(rng.choice(b32) for _ in range(38))
    elif coin_type == "eth":
        hex_c = "0123456789abcdef"
        return "0x" + "".join(rng.choice(hex_c) for _ in range(40))
    elif coin_type == "xmr":
        base58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
        return "4" + "".join(rng.choice(base58) for _ in range(94))
    return "bc1q" + "".join(rng.choice("0123456789abcdef") for _ in range(38))


def generate_sha256_cert(rng: random.Random) -> str:
    hex_c = "0123456789ABCDEF"
    return "".join(rng.choice(hex_c) for _ in range(64))


def format_pgp_in_text(pgp: str, style_idx: int) -> str:
    """Format PGP fingerprint in post body using varied real-world conventions."""
    if style_idx % 4 == 0:
        # Space grouped 4s
        return " ".join(pgp[i : i + 4] for i in range(0, len(pgp), 4))
    elif style_idx % 4 == 1:
        # Colon separated 2s
        return ":".join(pgp[i : i + 2] for i in range(0, len(pgp), 2))
    elif style_idx % 4 == 2:
        # 0x prefixed uppercase
        return f"0x{pgp}"
    else:
        # Lowercase continuous
        return pgp.lower()


class OperatorModel:
    def __init__(
        self,
        operator_id: str,
        name: str,
        description: str,
        personas: List[Tuple[str, str]],
        style_case: str,  # "sentence_case", "all_lowercase", "Title Case"
        mean_sentence_len: int,
        signature_phrases: List[str],
        greeting: str,
        signoff: str,
        punctuation_habit: str,  # "ellipses", "exclamation", "double_space", "standard"
        misspellings: Dict[str, str],
        active_hours: Tuple[int, int],  # (start_hour, end_hour) in UTC
        crypto_pgp: Optional[str] = None,
        crypto_btc: Optional[str] = None,
        crypto_eth: Optional[str] = None,
        crypto_xmr: Optional[str] = None,
        infra_ip: Optional[str] = None,
        infra_domain: Optional[str] = None,
        infra_cert: Optional[str] = None,
        infra_banner: Optional[str] = None,
        infra_port: Optional[int] = None,
        is_short_text: bool = False,
        missing_timestamps: bool = False,
    ):
        self.operator_id = operator_id
        self.name = name
        self.description = description
        self.personas = sorted(personas)
        self.style_case = style_case
        self.mean_sentence_len = mean_sentence_len
        self.signature_phrases = signature_phrases
        self.greeting = greeting
        self.signoff = signoff
        self.punctuation_habit = punctuation_habit
        self.misspellings = misspellings
        self.active_hours = active_hours
        self.crypto_pgp = crypto_pgp
        self.crypto_btc = crypto_btc
        self.crypto_eth = crypto_eth
        self.crypto_xmr = crypto_xmr
        self.infra_ip = infra_ip
        self.infra_domain = infra_domain
        self.infra_cert = infra_cert
        self.infra_banner = infra_banner
        self.infra_port = infra_port
        self.is_short_text = is_short_text
        self.missing_timestamps = missing_timestamps


def generate_post_content(
    op: OperatorModel,
    persona_mkt: str,
    persona_user: str,
    rng: random.Random,
    post_idx: int,
    custom_pgp: Optional[str] = None,
    custom_btc: Optional[str] = None,
    include_decoy: bool = False,
    decoy_pgp: Optional[str] = None,
    decoy_wallet: Optional[str] = None,
) -> Tuple[str, Dict[str, Any]]:
    """Synthesize post text adhering to operator's stylistic and linguistic fingerprint."""
    topic_data = SHARED_TOPICS[post_idx % len(SHARED_TOPICS)]
    templates = topic_data["templates"]
    base_sentence = rng.choice(templates).format(
        batch_id=100 + (post_idx * 7) % 899,
        order_id=5000 + (post_idx * 13) % 4999,
    )

    pgp_val = custom_pgp if custom_pgp is not None else op.crypto_pgp
    btc_val = custom_btc if custom_btc is not None else op.crypto_btc

    structured_indicators: Dict[str, Any] = {}
    if pgp_val:
        structured_indicators["pgp_fingerprint"] = pgp_val
    if btc_val:
        structured_indicators["wallet"] = btc_val
    if op.infra_domain:
        structured_indicators["domain"] = op.infra_domain
    if op.infra_ip:
        structured_indicators["ip_address"] = op.infra_ip
    if op.infra_cert:
        structured_indicators["ssl_cert_fingerprint"] = op.infra_cert
    if op.infra_banner:
        structured_indicators["server_banner"] = op.infra_banner
    if op.infra_port:
        structured_indicators["port"] = op.infra_port

    if op.is_short_text:
        short_sentences = [
            f"Restock arrived on {persona_mkt}. Safe escrow.",
            f"Escrow released. Thanks for clear trading.",
            f"Inquiries replied. Check our key fingerprint.",
            f"Postal delays clearing. All orders insured.",
            f"Batch {100 + post_idx} tested ok. Moving fast.",
        ]
        raw_text = rng.choice(short_sentences)
        if op.style_case == "all_lowercase":
            raw_text = raw_text.lower()
        elif op.style_case == "Title Case":
            raw_text = raw_text.title()
        return raw_text, structured_indicators

    phrase = op.signature_phrases[post_idx % len(op.signature_phrases)]
    body_parts = [op.greeting, base_sentence]

    if op.mean_sentence_len > 15:
        body_parts.append(
            f"As stated in our trading manifesto, {phrase}, we prioritize consistent technical precision."
        )
    else:
        body_parts.append(f"Remember: {phrase}.")

    if pgp_val and post_idx % 2 == 0:
        formatted_pgp = format_pgp_in_text(pgp_val, post_idx)
        body_parts.append(f"Primary PGP fingerprint: {formatted_pgp}")
    elif btc_val and post_idx % 2 == 1:
        body_parts.append(f"Escrow settlement wallet: {btc_val}")

    if include_decoy and decoy_pgp and decoy_wallet and post_idx % 3 == 0:
        body_parts.append(
            f"Official marketplace support key: {decoy_pgp} | Platform escrow: {decoy_wallet}"
        )

    body_parts.append(op.signoff)

    separator = " "
    if op.punctuation_habit == "double_space":
        separator = "  "
    elif op.punctuation_habit == "ellipses":
        body_parts[1] = body_parts[1].replace(".", "...")

    text = separator.join(body_parts)

    for correct, misspelled in sorted(op.misspellings.items()):
        text = text.replace(correct, misspelled)
        text = text.replace(correct.capitalize(), misspelled.capitalize())

    if op.style_case == "all_lowercase":
        text = text.lower()
    elif op.style_case == "Title Case":
        text = text.title()

    return text, structured_indicators


def generate_timestamp(
    op: OperatorModel,
    rng: random.Random,
    post_idx: int,
    total_posts: int,
) -> Optional[str]:
    """Generate deterministic UTC timestamp matching operator's diurnal active window."""
    if op.missing_timestamps:
        return None

    fraction = (post_idx + 0.5) / max(total_posts, 1)
    base_second = int(fraction * TOTAL_WINDOW_SECONDS)

    approx_dt = BASE_START + timedelta(seconds=base_second)

    start_h, end_h = op.active_hours
    if start_h <= end_h:
        hour = rng.randint(start_h, end_h)
    else:
        options = list(range(start_h, 24)) + list(range(0, end_h + 1))
        hour = rng.choice(options)

    minute = rng.randint(0, 59)
    second = rng.randint(0, 59)

    adjusted_dt = approx_dt.replace(hour=hour, minute=minute, second=second)
    return adjusted_dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def build_alpha_dataset() -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Build Alpha dataset (6 operators, 10 personas, 4 marketplaces, 180 posts)."""
    rng = random.Random(42)

    shared_pgp = "E4A18B9C2D3E4F5A6B7C8D9E0F1A2B3C4D5E6F7A"
    shared_btc = "bc1q9d4k2t8x7m1w5p3z0s6y8v2c4b6n8m0k2j4h6f"

    shared_ip = "198.51.100.42"
    shared_domain = "relay.fictional-mesh.example"
    shared_cert = "E3B0C44298FC1C149AFBF4C8996FB92427AE41E4649B934CA495991B7852B855"

    op1 = OperatorModel(
        operator_id="op_alpha_1",
        name="The Iron Artisan",
        description="Strong positive actor sharing PGP, BTC wallet, stylistic fingerprint, and active hours across 3 marketplaces.",
        personas=[
            ("Velvet Bazaar", "iron_weaver"),
            ("Greywharf", "iron_artisan"),
            ("Tidepool Exchange", "iron_craft"),
        ],
        style_case="sentence_case",
        mean_sentence_len=16,
        signature_phrases=[
            "integrity above all",
            "prompt dispatch guaranteed",
            "verified stock always",
        ],
        greeting="Greetings patrons,",
        signoff="Best regards, Iron.",
        punctuation_habit="standard",
        misspellings={"definitely": "definately", "separate": "seperate"},
        active_hours=(8, 15),
        crypto_pgp=shared_pgp,
        crypto_btc=shared_btc,
    )

    op2 = OperatorModel(
        operator_id="op_alpha_2",
        name="Night Owl Merchant",
        description="Operator sharing stylometric habits and night active window, but using zero shared crypto indicators.",
        personas=[
            ("Velvet Bazaar", "nightshade_trader"),
            ("Lanternroot", "dusk_merchant"),
        ],
        style_case="all_lowercase",
        mean_sentence_len=9,
        signature_phrases=[
            "clean escrow only",
            "no time wasters",
            "quick quiet drop",
        ],
        greeting="hey all,",
        signoff="stay quiet.",
        punctuation_habit="double_space",
        misspellings={"received": "recieved"},
        active_hours=(22, 4),
        crypto_pgp=None,
        crypto_btc=None,
    )

    op3 = OperatorModel(
        operator_id="op_alpha_3",
        name="Infrastructure Operator",
        description="Operator with 2 personas sharing backend host, IP, and TLS cert, but completely differing in writing style and active hours.",
        personas=[
            ("Greywharf", "harbor_master"),
            ("Lanternroot", "beacon_light"),
        ],
        style_case="sentence_case",
        mean_sentence_len=18,
        signature_phrases=[
            "beacon verified",
            "harbor authority clearance",
        ],
        greeting="Good day members,",
        signoff="At your service.",
        punctuation_habit="ellipses",
        misspellings={},
        active_hours=(6, 12),
        infra_ip=shared_ip,
        infra_domain=shared_domain,
        infra_cert=shared_cert,
        infra_banner="nginx/1.18.0 (Ubuntu)",
        infra_port=443,
    )

    op4 = OperatorModel(
        operator_id="op_alpha_4",
        name="Tidepool Drift Courier",
        description="First hard negative operator operating in afternoon UTC window with no shared indicators.",
        personas=[
            ("Tidepool Exchange", "drift_courier"),
        ],
        style_case="sentence_case",
        mean_sentence_len=14,
        signature_phrases=[
            "steady waves",
            "on-time delivery",
        ],
        greeting="Ahoy traders,",
        signoff="Fair winds.",
        punctuation_habit="standard",
        misspellings={"accommodate": "acommodate"},
        active_hours=(13, 19),
        crypto_btc=generate_wallet(rng, "btc"),
    )

    op5 = OperatorModel(
        operator_id="op_alpha_5",
        name="Greywharf Current Runner",
        description="Second hard negative operator sharing the same afternoon UTC window as drift_courier but distinct person.",
        personas=[
            ("Greywharf", "current_runner"),
        ],
        style_case="sentence_case",
        mean_sentence_len=15,
        signature_phrases=[
            "swift current",
            "trusted route",
        ],
        greeting="Greetings travelers,",
        signoff="Safe travels.",
        punctuation_habit="standard",
        misspellings={"occurrence": "occurence"},
        active_hours=(13, 19),
        crypto_btc=generate_wallet(rng, "btc"),
    )

    op6 = OperatorModel(
        operator_id="op_alpha_6",
        name="The Silver Quill",
        description="Single-persona control vendor on Velvet Bazaar.",
        personas=[
            ("Velvet Bazaar", "silver_quill"),
        ],
        style_case="sentence_case",
        mean_sentence_len=20,
        signature_phrases=[
            "quality documented",
            "proven craft",
        ],
        greeting="Esteemed colleagues,",
        signoff="Yours faithfully, Quill.",
        punctuation_habit="standard",
        misspellings={},
        active_hours=(10, 17),
        crypto_pgp="778899AABBCCDDEEFF0011223344556677889900",
        crypto_btc=generate_wallet(rng, "btc"),
    )

    operators = [op1, op2, op3, op4, op5, op6]
    all_personas: List[Tuple[str, str, OperatorModel]] = []
    for op in operators:
        for mkt, user in op.personas:
            all_personas.append((mkt, user, op))

    all_personas.sort(key=lambda x: (x[0], x[1]))

    posts: List[Dict[str, Any]] = []
    for mkt, user, op in all_personas:
        num_posts = 18
        for p_idx in range(num_posts):
            content, structured = generate_post_content(op, mkt, user, rng, p_idx)
            ts = generate_timestamp(op, rng, p_idx, num_posts)
            posts.append({
                "marketplace": mkt,
                "username": user,
                "timestamp": ts,
                "content": content,
                "source_reference": f"thread_{1000 + p_idx}",
                "structured_indicators": structured,
            })

    posts.sort(key=lambda x: (x["timestamp"] or "", x["marketplace"], x["username"], x["content"]))

    sample_alpha = {
        "key": "alpha",
        "name": "Alpha Benchmark Sample",
        "description": "Fictional dark web marketplace chatter with ground-truth actor correlation benchmarks.",
        "version": 1,
        "is_fictional": True,
        "generator_seed": 42,
        "posts": posts,
    }

    pairs: List[Dict[str, Any]] = []
    persona_list = [(mkt, user, op) for mkt, user, op in all_personas]
    for i in range(len(persona_list)):
        for j in range(i + 1, len(persona_list)):
            mkt_a, user_a, op_a = persona_list[i]
            mkt_b, user_b, op_b = persona_list[j]

            if op_a.operator_id == op_b.operator_id:
                label = "same_operator"
                if op_a.operator_id == "op_alpha_1":
                    shared_dims = ["cryptographic", "stylometric", "behavioural"]
                    case_type = "strong_positive"
                elif op_a.operator_id == "op_alpha_2":
                    shared_dims = ["stylometric", "behavioural"]
                    case_type = "partial_positive_style_behaviour"
                elif op_a.operator_id == "op_alpha_3":
                    shared_dims = ["infrastructure"]
                    case_type = "partial_positive_infra"
                else:
                    shared_dims = ["stylometric"]
                    case_type = "strong_positive"
            else:
                label = "different_operator"
                if (op_a.operator_id, op_b.operator_id) in [("op_alpha_4", "op_alpha_5"), ("op_alpha_5", "op_alpha_4")]:
                    shared_dims = ["behavioural"]
                    case_type = "hard_negative_behaviour"
                else:
                    shared_dims = []
                    case_type = "control"

            pairs.append({
                "a": {"marketplace": mkt_a, "username": user_a},
                "b": {"marketplace": mkt_b, "username": user_b},
                "label": label,
                "shared_dimensions": shared_dims,
                "case_type": case_type,
            })

    pairs.sort(key=lambda p: (p["a"]["marketplace"], p["a"]["username"], p["b"]["marketplace"], p["b"]["username"]))

    truth_alpha = {
        "key": "alpha",
        "name": "Alpha Ground Truth Labels",
        "version": 1,
        "generator_seed": 42,
        "operators": [
            {
                "operator_id": op.operator_id,
                "name": op.name,
                "description": op.description,
                "personas": [{"marketplace": m, "username": u} for m, u in sorted(op.personas)],
            }
            for op in sorted(operators, key=lambda x: x.operator_id)
        ],
        "pairs": pairs,
    }

    return sample_alpha, truth_alpha


def build_beta_dataset() -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Build Beta dataset (14 operators, exactly 30 personas, 6 marketplaces, 714 posts)."""
    rng = random.Random(1337)

    # Common indicator decoy
    decoy_pgp = "DEC07DEC07DEC07DEC07DEC07DEC07DEC07DEC07"
    decoy_wallet = "bc1qdecoymarketescrow00000000000000000000"

    # Contradictory crypto shared PGP
    contradictory_pgp = "F0E1D2C3B4A5968778695A4B3C2D1E0F12345678"

    # Partial overlap shared BTC
    partial_shared_btc = "bc1qpartialvault9999999999999999999999999"

    # 14 Operators with 30 Personas Total:
    # Op 1: 3 personas
    op1 = OperatorModel(
        "op_beta_1", "The Iron Artisan", "Strong positive actor",
        [("Velvet Bazaar", "iron_weaver"), ("Greywharf", "iron_artisan"), ("Tidepool Exchange", "iron_craft")],
        "sentence_case", 16, ["integrity above all", "prompt dispatch guaranteed"],
        "Greetings patrons,", "Best regards, Iron.", "standard", {}, (8, 15),
        crypto_pgp="E4A18B9C2D3E4F5A6B7C8D9E0F1A2B3C4D5E6F7A",
        crypto_btc="bc1q9d4k2t8x7m1w5p3z0s6y8v2c4b6n8m0k2j4h6f",
    )
    # Op 2: 2 personas
    op2 = OperatorModel(
        "op_beta_2", "Night Owl Merchant", "Style + hours positive",
        [("Velvet Bazaar", "nightshade_trader"), ("Lanternroot", "dusk_merchant")],
        "all_lowercase", 9, ["clean escrow only", "quick quiet drop"],
        "hey all,", "stay quiet.", "double_space", {}, (22, 4),
    )
    # Op 3: 2 personas
    op3 = OperatorModel(
        "op_beta_3", "Infrastructure Operator", "Infra only positive",
        [("Greywharf", "harbor_master"), ("Lanternroot", "beacon_light")],
        "sentence_case", 18, ["beacon verified", "harbor clearance"],
        "Good day members,", "At your service.", "ellipses", {}, (6, 12),
        infra_ip="198.51.100.42", infra_domain="relay.fictional-mesh.example",
        infra_cert="E3B0C44298FC1C149AFBF4C8996FB92427AE41E4649B934CA495991B7852B855",
        infra_banner="nginx/1.18.0 (Ubuntu)", infra_port=443,
    )
    # Op 4: 2 personas
    op4 = OperatorModel(
        "op_beta_4", "Tidepool Drift Courier", "Hard negative afternoon with 2 personas",
        [("Tidepool Exchange", "drift_courier"), ("Cobalt Harbor", "drift_courier_sea")],
        "sentence_case", 14, ["steady waves", "coastal dispatch"],
        "Ahoy traders,", "Fair winds.", "standard", {}, (13, 19),
        crypto_btc="bc1qdriftvault0000000000000000000000000000",
    )
    # Op 5: 2 personas
    op5 = OperatorModel(
        "op_beta_5", "Greywharf Current Runner", "Hard negative afternoon with 2 personas",
        [("Greywharf", "current_runner"), ("Whispering Pines", "current_courier")],
        "sentence_case", 15, ["swift current", "river courier"],
        "Greetings travelers,", "Safe travels.", "standard", {}, (13, 19),
        crypto_btc="bc1qcurrentrun111111111111111111111111111",
    )
    # Op 6: 2 personas
    op6 = OperatorModel(
        "op_beta_6", "The Silver Quill", "Control vendor with 2 personas",
        [("Velvet Bazaar", "silver_quill"), ("Lanternroot", "silver_scribe")],
        "sentence_case", 20, ["proven craft", "scholarly record"],
        "Esteemed colleagues,", "Yours faithfully.", "standard", {}, (10, 17),
        crypto_pgp="778899AABBCCDDEEFF0011223344556677889900",
    )
    # Op 7: 1 persona (Contradictory crypto A)
    op7 = OperatorModel(
        "op_beta_7", "Key Sharer A", "Contradictory crypto actor A (lowercase, night hours)",
        [("Cobalt Harbor", "cipher_echo_a")],
        "all_lowercase", 7, ["fast trade", "no chatter"], "hi,", "peace.", "standard", {}, (1, 5),
        crypto_pgp=contradictory_pgp,
    )
    # Op 8: 1 persona (Contradictory crypto B)
    op8 = OperatorModel(
        "op_beta_8", "Key Sharer B", "Contradictory crypto actor B (Title Case, afternoon hours)",
        [("Whispering Pines", "cipher_echo_b")],
        "Title Case", 24, ["Formally Certified Quality", "Distinguished Excellence"],
        "Dearest Patrons,", "With Highest Regard.", "ellipses", {}, (13, 19),
        crypto_pgp=contradictory_pgp,
    )
    # Op 9: 2 personas (Short text)
    op9 = OperatorModel(
        "op_beta_9", "Terse Trader", "Short-text persona with 5-10 short posts",
        [("Cobalt Harbor", "terse_bob"), ("Whispering Pines", "terse_bobby")],
        "sentence_case", 8, ["moving fast"], "Hello,", "Done.", "standard", {}, (9, 14),
        is_short_text=True,
    )
    # Op 10: 2 personas (Missing timestamps)
    op10 = OperatorModel(
        "op_beta_10", "Timeless Vendor", "Personas with null timestamps",
        [("Lanternroot", "timeless_echo_a"), ("Tidepool Exchange", "timeless_echo_b")],
        "sentence_case", 15, ["always available", "timeless service"],
        "Greetings,", "Regards.", "standard", {}, (12, 18),
        missing_timestamps=True,
        crypto_btc="bc1qtimelessecho22222222222222222222222222",
    )
    # Op 11: 3 personas (Partial crypto overlap)
    op11 = OperatorModel(
        "op_beta_11", "Split Vault Operator", "3 personas sharing one BTC wallet",
        [("Greywharf", "split_vault_a"), ("Velvet Bazaar", "split_vault_b"), ("Tidepool Exchange", "split_vault_c")],
        "sentence_case", 16, ["secure split", "dual chain"],
        "Hello all,", "Best, Vault.", "standard", {}, (10, 16),
        crypto_btc=partial_shared_btc,
    )
    # Op 12: 2 personas (Near-duplicate username broker A)
    op12 = OperatorModel(
        "op_beta_12", "Cobalt Shadow Broker", "Legitimate broker on Cobalt Harbor and Greywharf",
        [("Cobalt Harbor", "shadow_broker"), ("Greywharf", "shadow_proxy")],
        "sentence_case", 14, ["shadow escrow", "cobalt seal"],
        "Greetings harbor,", "Shadow out.", "standard", {}, (8, 14),
        crypto_btc="bc1qshadowcobalt3333333333333333333333333",
    )
    # Op 13: 2 personas (Near-duplicate username broker B)
    op13 = OperatorModel(
        "op_beta_13", "Pines Shadow Broker", "Unrelated broker on Whispering Pines with identical username",
        [("Whispering Pines", "shadow_broker"), ("Velvet Bazaar", "shadow_delegate")],
        "all_lowercase", 11, ["pines courier", "forest route"],
        "yo pines,", "laters.", "double_space", {}, (18, 23),
        crypto_btc="bc1qshadowpines44444444444444444444444444",
    )
    # Op 14: 4 personas (Multi-market guild)
    op14 = OperatorModel(
        "op_beta_14", "Northern Merchant Guild", "Strong positive multi-market operator",
        [
            ("Cobalt Harbor", "north_vendor"),
            ("Whispering Pines", "pine_vendor"),
            ("Lanternroot", "root_vendor"),
            ("Velvet Bazaar", "velvet_guildmaster"),
        ],
        "sentence_case", 17, ["northern standard", "guild assurance"],
        "Members of the guild,", "Honor and trade.", "standard", {}, (7, 13),
        crypto_pgp="1234567890ABCDEF1234567890ABCDEF12345678",
        crypto_btc="bc1qnorthernguild55555555555555555555555",
    )

    # Sum of personas: 3 + 2 + 2 + 2 + 2 + 2 + 1 + 1 + 2 + 2 + 3 + 2 + 2 + 4 = 30 personas!
    operators = [op1, op2, op3, op4, op5, op6, op7, op8, op9, op10, op11, op12, op13, op14]

    all_personas: List[Tuple[str, str, OperatorModel]] = []
    for op in operators:
        for mkt, user in op.personas:
            all_personas.append((mkt, user, op))

    all_personas.sort(key=lambda x: (x[0], x[1]))

    posts: List[Dict[str, Any]] = []
    for mkt, user, op in all_personas:
        num_posts = 7 if op.is_short_text else 25
        include_decoy = op.operator_id in ["op_beta_4", "op_beta_6", "op_beta_12"]
        for p_idx in range(num_posts):
            content, structured = generate_post_content(
                op, mkt, user, rng, p_idx,
                include_decoy=include_decoy,
                decoy_pgp=decoy_pgp,
                decoy_wallet=decoy_wallet,
            )
            ts = generate_timestamp(op, rng, p_idx, num_posts)
            posts.append({
                "marketplace": mkt,
                "username": user,
                "timestamp": ts,
                "content": content,
                "source_reference": f"thread_{2000 + p_idx}",
                "structured_indicators": structured,
            })

    posts.sort(key=lambda x: (x["timestamp"] or "", x["marketplace"], x["username"], x["content"]))

    sample_beta = {
        "key": "beta",
        "name": "Beta Benchmark Sample",
        "description": "Expanded benchmark dataset containing contradictory keys, common decoys, short texts, and missing timestamps.",
        "version": 1,
        "is_fictional": True,
        "generator_seed": 1337,
        "posts": posts,
    }

    pairs: List[Dict[str, Any]] = []
    persona_list = [(mkt, user, op) for mkt, user, op in all_personas]
    for i in range(len(persona_list)):
        for j in range(i + 1, len(persona_list)):
            mkt_a, user_a, op_a = persona_list[i]
            mkt_b, user_b, op_b = persona_list[j]

            if op_a.operator_id == op_b.operator_id:
                label = "same_operator"
                if op_a.operator_id in ["op_beta_1", "op_beta_14"]:
                    shared_dims = ["cryptographic", "stylometric", "behavioural"]
                    case_type = "strong_positive"
                elif op_a.operator_id == "op_beta_2":
                    shared_dims = ["stylometric", "behavioural"]
                    case_type = "partial_positive_style_behaviour"
                elif op_a.operator_id == "op_beta_3":
                    shared_dims = ["infrastructure"]
                    case_type = "partial_positive_infra"
                elif op_a.operator_id == "op_beta_9":
                    shared_dims = ["stylometric", "behavioural"]
                    case_type = "short_text"
                elif op_a.operator_id == "op_beta_10":
                    shared_dims = ["stylometric"]
                    case_type = "missing_timestamps"
                elif op_a.operator_id == "op_beta_11":
                    shared_dims = ["cryptographic", "stylometric"]
                    case_type = "strong_positive"
                elif op_a.operator_id in ["op_beta_4", "op_beta_5", "op_beta_6", "op_beta_12", "op_beta_13"]:
                    shared_dims = ["cryptographic", "stylometric", "behavioural"]
                    case_type = "strong_positive"
                else:
                    shared_dims = ["stylometric"]
                    case_type = "strong_positive"
            else:
                label = "different_operator"
                if (op_a.operator_id, op_b.operator_id) in [("op_beta_7", "op_beta_8"), ("op_beta_8", "op_beta_7")]:
                    shared_dims = ["cryptographic"]
                    case_type = "contradictory_crypto"
                elif op_a.operator_id in ["op_beta_4", "op_beta_6", "op_beta_12"] and op_b.operator_id in ["op_beta_4", "op_beta_6", "op_beta_12"]:
                    shared_dims = []
                    case_type = "common_indicator_decoy"
                elif (op_a.operator_id, op_b.operator_id) in [("op_beta_4", "op_beta_5"), ("op_beta_5", "op_beta_4")]:
                    shared_dims = ["behavioural"]
                    case_type = "hard_negative_behaviour"
                else:
                    shared_dims = []
                    case_type = "control"

            pairs.append({
                "a": {"marketplace": mkt_a, "username": user_a},
                "b": {"marketplace": mkt_b, "username": user_b},
                "label": label,
                "shared_dimensions": shared_dims,
                "case_type": case_type,
            })

    pairs.sort(key=lambda p: (p["a"]["marketplace"], p["a"]["username"], p["b"]["marketplace"], p["b"]["username"]))

    truth_beta = {
        "key": "beta",
        "name": "Beta Ground Truth Labels",
        "version": 1,
        "generator_seed": 1337,
        "operators": [
            {
                "operator_id": op.operator_id,
                "name": op.name,
                "description": op.description,
                "personas": [{"marketplace": m, "username": u} for m, u in sorted(op.personas)],
            }
            for op in sorted(operators, key=lambda x: x.operator_id)
        ],
        "pairs": pairs,
    }

    return sample_beta, truth_beta


def main():
    root = Path(__file__).resolve().parents[2]
    if not (root / "backend").exists():
        root = Path(__file__).resolve().parents[1]

    datasets_dir = root / "backend" / "datasets"
    sample_dir = datasets_dir / "sample"
    truth_dir = datasets_dir / "ground_truth"

    sample_dir.mkdir(parents=True, exist_ok=True)
    truth_dir.mkdir(parents=True, exist_ok=True)

    sample_alpha, truth_alpha = build_alpha_dataset()
    alpha_sample_path = sample_dir / "alpha.json"
    alpha_truth_path = truth_dir / "alpha_truth.json"

    with open(alpha_sample_path, "w", encoding="utf-8") as f:
        json.dump(sample_alpha, f, indent=2, ensure_ascii=False)
        f.write("\n")

    with open(alpha_truth_path, "w", encoding="utf-8") as f:
        json.dump(truth_alpha, f, indent=2, ensure_ascii=False)
        f.write("\n")

    sample_beta, truth_beta = build_beta_dataset()
    beta_sample_path = sample_dir / "beta.json"
    beta_truth_path = truth_dir / "beta_truth.json"

    with open(beta_sample_path, "w", encoding="utf-8") as f:
        json.dump(sample_beta, f, indent=2, ensure_ascii=False)
        f.write("\n")

    with open(beta_truth_path, "w", encoding="utf-8") as f:
        json.dump(truth_beta, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"Generated Alpha: {len(sample_alpha['posts'])} posts, {len(truth_alpha['operators'])} operators, {len(truth_alpha['pairs'])} pairs")
    print(f"Generated Beta: {len(sample_beta['posts'])} posts, {len(truth_beta['operators'])} operators, {len(truth_beta['pairs'])} pairs")


if __name__ == "__main__":
    main()
