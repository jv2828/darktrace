"""Pipeline stage registry and stage definitions."""

from typing import Any, Dict, List

STAGE_REGISTRY: Dict[str, Dict[str, Any]] = {
    "crypto_matching": {
        "name": "crypto_matching",
        "label": "Cryptographic Matching",
        "description": "Correlate threat personas using shared PGP keys and cryptocurrency addresses.",
        "available": True,
    },
    "infrastructure_matching": {
        "name": "infrastructure_matching",
        "label": "Infrastructure Matching",
        "description": "Correlate threat personas using shared domains, IPs, SSL certificates, banners, and non-standard ports.",
        "available": True,
    },
    "stylometric_analysis": {
        "name": "stylometric_analysis",
        "label": "Stylometric Analysis",
        "description": "Evaluate linguistic habits, vocabulary richness, writeprints, and character/word n-grams.",
        "available": True,
    },
    "behavioural_analysis": {
        "name": "behavioural_analysis",
        "label": "Behavioural Analysis",
        "description": "Analyze temporal activity patterns, diurnal rhythms, and active posting windows.",
        "available": True,
    },
    "scoring": {
        "name": "scoring",
        "label": "Multi-dimensional Scoring",
        "description": "Synthesize cross-dimensional evidence into composite similarity scores and linkage graph.",
        "available": True,
    },
}


def get_available_stage_names() -> List[str]:
    """Return ordered list of currently available stage names."""
    return [name for name, info in STAGE_REGISTRY.items() if info["available"]]


def get_registered_stages_summary() -> List[Dict[str, Any]]:
    """Return metadata list of all pipeline stages for API inspection."""
    return [
        {
            "name": info["name"],
            "label": info["label"],
            "description": info["description"],
            "available": info["available"],
        }
        for info in STAGE_REGISTRY.values()
    ]
