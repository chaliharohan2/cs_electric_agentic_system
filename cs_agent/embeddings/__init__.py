"""Configurable query embeddings for pgvector search."""

from .factory import EmbeddingConfig, clear_embedding_cache, embed, resolve_embedding

__all__ = ["EmbeddingConfig", "clear_embedding_cache", "embed", "resolve_embedding"]
