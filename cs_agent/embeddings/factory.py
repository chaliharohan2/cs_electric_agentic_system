"""Embedding factory with model profiles and dimension checks."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, PositiveInt


class EmbeddingConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    model: str
    dimension: PositiveInt
    normalize: bool = True
    trust_remote_code: bool = False


class EmbeddingsFile(BaseModel):
    profiles: dict[str, EmbeddingConfig]
    active: str


_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "embeddings.yaml"


@lru_cache(maxsize=1)
def _load_config() -> EmbeddingsFile:
    with open(_CONFIG_PATH, encoding="utf-8") as file:
        return EmbeddingsFile.model_validate(yaml.safe_load(file))


def resolve_embedding() -> EmbeddingConfig:
    config = _load_config()
    profile = os.getenv("CS_EMBEDDING_MODEL", config.active).strip()
    if profile not in config.profiles:
        choices = ", ".join(sorted(config.profiles))
        raise KeyError(f"Unknown embedding profile '{profile}'. Choose one of: {choices}")
    return config.profiles[profile]


@lru_cache(maxsize=1)
def _get_model():
    from sentence_transformers import SentenceTransformer

    config = resolve_embedding()
    return SentenceTransformer(
        config.model,
        trust_remote_code=config.trust_remote_code,
    )


def embed(text: str, *, expected_dimension: int | None = None) -> list[float]:
    """Embed one query and reject configuration/database dimension mismatches."""
    config = resolve_embedding()
    if expected_dimension is not None and config.dimension != expected_dimension:
        raise ValueError(
            f"Embedding profile '{config.model}' produces {config.dimension} dimensions, "
            f"but product_chunks.embedding expects {expected_dimension}. Re-embed the "
            "catalogue and alter the vector column before switching profiles."
        )
    vector = _get_model().encode(
        text,
        normalize_embeddings=config.normalize,
        convert_to_numpy=True,
    ).tolist()
    if len(vector) != config.dimension:
        raise ValueError(
            f"Embedding model returned {len(vector)} dimensions; "
            f"configuration declares {config.dimension}."
        )
    return [float(value) for value in vector]


def clear_embedding_cache() -> None:
    _get_model.cache_clear()
    _load_config.cache_clear()
