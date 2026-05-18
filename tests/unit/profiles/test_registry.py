"""Tests for bundled source-profile registry behavior."""

from __future__ import annotations

from lerim.profiles import (
    CARD_KIND_DEFAULTS,
    format_signal_pack_context,
    get_signal_pack,
    normalize_signal_pack_id,
)


def test_normalize_signal_pack_id_uses_canonical_bundled_ids() -> None:
    """Profile lookup returns exact bundled ids and falls back without guessing."""
    assert normalize_signal_pack_id("support") == "support"
    assert normalize_signal_pack_id("SUPPORT") == "support"
    assert normalize_signal_pack_id("support handoff trace") == "coding"
    assert normalize_signal_pack_id(None) == "coding"


def test_format_signal_pack_context_excludes_eval_schema() -> None:
    """Runtime prompt context should not include eval-only labels."""
    rendered = format_signal_pack_context("ops")

    assert "Evaluation gold schema" not in rendered
    assert "Domain signal priorities:" in rendered
    assert "Output cards:" in rendered


def test_signal_pack_cards_use_canonical_card_types() -> None:
    """Bundled profile cards should map through the shared card semantics."""
    support_cards = set(get_signal_pack("support").output_cards)
    ops_cards = set(get_signal_pack("ops").output_cards)

    assert "handoff" not in support_cards
    assert "source_of_truth" not in support_cards
    assert "source_of_truth" in ops_cards
    assert support_cards <= set(CARD_KIND_DEFAULTS)
    assert ops_cards <= set(CARD_KIND_DEFAULTS)


def test_signal_pack_priorities_use_canonical_card_terms() -> None:
    """Profile priorities should not introduce a second card taxonomy."""
    for profile in ("coding", "support", "ops"):
        assert set(get_signal_pack(profile).signal_types) <= set(CARD_KIND_DEFAULTS)
