from __future__ import annotations

from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
CREATIVE_TEMPLATE = REPO / "templates" / "clawseat-creative.toml"


def test_creative_template_has_been_deleted() -> None:
    assert not CREATIVE_TEMPLATE.exists()
