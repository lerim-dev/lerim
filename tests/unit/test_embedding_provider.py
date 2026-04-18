"""Unit tests for the local ONNX embedding provider contract."""

from __future__ import annotations

import json
from dataclasses import dataclass

import numpy as np
import pytest

from lerim.context.embedding import EmbeddingProvider


@dataclass
class _FakeEncoding:
    ids: list[int]
    attention_mask: list[int]


class _FakeTokenizer:
    """Tiny tokenizer stub for provider unit tests."""

    def encode_batch(self, texts: list[str]) -> list[_FakeEncoding]:
        return [
            _FakeEncoding(ids=[idx + 1, idx + 2], attention_mask=[1, 1])
            for idx, _text in enumerate(texts)
        ]


class _FakeSession:
    """Tiny ONNX session stub that returns fixed embeddings."""

    def run(self, _output_names, _inputs):
        return [np.asarray([[3.0, 4.0, 0.0], [0.0, 0.0, 0.0]], dtype=np.float32)]


def test_embedding_provider_normalizes_vectors(tmp_path, monkeypatch) -> None:
    """Provider normalizes model output before returning vectors."""
    provider = EmbeddingProvider(model_id="demo/model", cache_dir=tmp_path)
    monkeypatch.setattr(provider, "_ensure_tokenizer", lambda: _FakeTokenizer())
    monkeypatch.setattr(provider, "_ensure_session", lambda: _FakeSession())

    vectors = provider._embed_texts(["first", "second"])

    assert len(vectors) == 2
    assert vectors[0] == pytest.approx([0.6, 0.8, 0.0], abs=1e-6)
    assert vectors[1] == [0.0, 0.0, 0.0]


def test_embedding_provider_reads_embedding_dims_from_config(tmp_path, monkeypatch) -> None:
    """Provider reads hidden size from the downloaded model config."""
    provider = EmbeddingProvider(model_id="demo/model", cache_dir=tmp_path)
    config_dir = tmp_path / "demo-model"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "config.json").write_text(json.dumps({"hidden_size": 123}), encoding="utf-8")
    monkeypatch.setattr(provider, "_download_model_files", lambda **_kwargs: config_dir)

    assert provider.embedding_dims == 123
