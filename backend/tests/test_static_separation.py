"""Static analysis test verifying strict separation between production app code and ground-truth evaluation datasets."""

from pathlib import Path
import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
APP_DIR = BACKEND_DIR / "app"


def test_no_ground_truth_imports_in_app():
    """Assert that no file under backend/app imports or references datasets/ground_truth."""
    assert APP_DIR.exists()

    forbidden_patterns = [
        "datasets/ground_truth",
        "datasets.ground_truth",
        "ground_truth",
        "alpha_truth.json",
        "beta_truth.json",
    ]

    violations = []
    py_files = sorted(APP_DIR.rglob("*.py"))
    assert len(py_files) > 10, "Sanity check: expected multiple Python files in app/"

    for py_file in py_files:
        content = py_file.read_text(encoding="utf-8")
        for pattern in forbidden_patterns:
            if pattern in content:
                violations.append(f"{py_file.relative_to(BACKEND_DIR)} contains '{pattern}'")

    assert not violations, f"Ground-truth leakage detected in production code:\n" + "\n".join(violations)

