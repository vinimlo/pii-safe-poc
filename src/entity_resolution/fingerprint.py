"""Probabilistic Entity Fingerprint (PEF) — compact multi-signal representation.

Each canonical entity is represented as a ~500-byte fingerprint combining
phonetic codes, structural similarity signatures, and normalized tokens.
"""

from dataclasses import dataclass

from .phonetic import double_metaphone
from .similarity import character_trigrams, lsh_bands, minhash_signature


@dataclass(frozen=True, slots=True)
class EntityFingerprint:
    """Compact multi-signal fingerprint for entity resolution."""

    entity_id: int
    entity_type: str
    canonical_text: str
    phonetic_primary: str
    phonetic_secondary: str
    trigram_minhash: tuple[int, ...]
    lsh_band_hashes: tuple[int, ...]
    normalized_tokens: frozenset[str]

    @classmethod
    def create(cls, entity_id: int, entity_type: str, text: str) -> "EntityFingerprint":
        """Factory method to create a fingerprint from raw text."""
        primary, secondary = double_metaphone(text)
        trigrams = character_trigrams(text.lower())
        minhash = minhash_signature(trigrams)
        bands = lsh_bands(minhash)
        tokens = frozenset(text.lower().split())
        return cls(
            entity_id=entity_id,
            entity_type=entity_type,
            canonical_text=text,
            phonetic_primary=primary,
            phonetic_secondary=secondary,
            trigram_minhash=minhash,
            lsh_band_hashes=tuple(bands),
            normalized_tokens=tokens,
        )
