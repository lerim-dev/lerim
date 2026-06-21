"""Tests for bundled source-profile registry behavior."""

from __future__ import annotations

from pathlib import Path

import pytest

from lerim.config.settings import reload_config
from lerim.profiles import (
    format_signal_pack_context,
    get_signal_pack,
    normalize_signal_pack_id,
    reload_signal_packs,
)
from tests.helpers import write_test_config


def test_normalize_signal_pack_id_uses_canonical_bundled_ids() -> None:
    """Profile lookup returns exact bundled ids and falls back without guessing."""
    assert normalize_signal_pack_id("support") == "support"
    assert normalize_signal_pack_id("SUPPORT") == "support"
    assert normalize_signal_pack_id("generic") == "generic"
    assert normalize_signal_pack_id("support handoff trace") == "coding"
    assert normalize_signal_pack_id(None) == "coding"


def test_format_signal_pack_context_excludes_eval_schema() -> None:
    """Runtime prompt context should not include eval-only labels."""
    rendered = format_signal_pack_context("ops")

    assert "Evaluation gold schema" not in rendered
    assert "Focus rules:" in rendered
    assert "Output cards:" not in rendered
    assert "card_type" not in rendered


def test_signal_pack_focus_is_guidance_not_output_taxonomy() -> None:
    """Profiles should guide extraction without defining product card outputs."""
    for profile in ("coding", "generic", "support", "ops"):
        pack = get_signal_pack(profile)

        assert pack.focus_rules
        assert not hasattr(pack, "output_cards")
        assert not hasattr(pack, "signal_types")


def test_registered_custom_signal_pack_feeds_extraction_context(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Custom YAML profiles registered in config are loaded by the registry."""
    profile_path = tmp_path / "analyst.yaml"
    profile_path.write_text(
        "\n".join(
            [
                "id: analyst",
                "display_name: Research Analyst",
                "description: Research and market-analysis agent traces.",
                "focus_rules:",
                "  - Remember durable analyst preferences and source-quality rules.",
                "reject_as_noise:",
                "  - Ignore temporary browsing failures and dead links.",
                "evidence_rules:",
                "  - Keep source URLs, dates, and uncertainty qualifiers.",
                "scope_rules:",
                "  - Use domain scope for reusable research workflow context.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    config_path = write_test_config(
        tmp_path,
        profiles={"analyst": str(profile_path)},
    )
    monkeypatch.setenv("LERIM_CONFIG", str(config_path))

    try:
        reload_config()
        reload_signal_packs()

        pack = get_signal_pack("analyst")
        rendered = format_signal_pack_context("analyst")

        assert pack.id == "analyst"
        assert pack.source == "custom"
        assert pack.path == str(profile_path.resolve())
        assert normalize_signal_pack_id("ANALYST") == "analyst"
        assert "Remember durable analyst preferences" in rendered
        assert "Keep source URLs" in rendered
    finally:
        reload_config()
        reload_signal_packs()
