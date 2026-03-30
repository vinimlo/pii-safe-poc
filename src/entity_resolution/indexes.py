"""Multi-index candidate retrieval for entity resolution.

Three parallel indexes (phonetic, trigram LSH, token) provide O(1) candidate
retrieval. Union of all indexes maximizes recall — no single index failure
can prevent a candidate from being found.
"""

from __future__ import annotations

from .fingerprint import EntityFingerprint


class PhoneticIndex:
    """Hash table keyed on Double Metaphone codes -> entity IDs."""

    def __init__(self) -> None:
        self._primary: dict[str, set[int]] = {}
        self._secondary: dict[str, set[int]] = {}

    def add(self, fp: EntityFingerprint) -> None:
        if fp.phonetic_primary:
            self._primary.setdefault(fp.phonetic_primary, set()).add(fp.entity_id)
        if fp.phonetic_secondary:
            self._secondary.setdefault(fp.phonetic_secondary, set()).add(fp.entity_id)

    def query(self, fp: EntityFingerprint) -> set[int]:
        candidates: set[int] = set()
        if fp.phonetic_primary:
            candidates |= self._primary.get(fp.phonetic_primary, set())
            candidates |= self._secondary.get(fp.phonetic_primary, set())
        if fp.phonetic_secondary:
            candidates |= self._primary.get(fp.phonetic_secondary, set())
            candidates |= self._secondary.get(fp.phonetic_secondary, set())
        candidates.discard(fp.entity_id)
        return candidates

    def remove(self, fp: EntityFingerprint) -> None:
        if fp.phonetic_primary and fp.phonetic_primary in self._primary:
            self._primary[fp.phonetic_primary].discard(fp.entity_id)
        if fp.phonetic_secondary and fp.phonetic_secondary in self._secondary:
            self._secondary[fp.phonetic_secondary].discard(fp.entity_id)


class TrigramLSHIndex:
    """MinHash + LSH banding index for structural similarity."""

    def __init__(self, num_bands: int = 32) -> None:
        self._num_bands = num_bands
        self._bands: list[dict[int, set[int]]] = [{} for _ in range(num_bands)]

    def add(self, fp: EntityFingerprint) -> None:
        for b, band_hash in enumerate(fp.lsh_band_hashes[: self._num_bands]):
            self._bands[b].setdefault(band_hash, set()).add(fp.entity_id)

    def query(self, fp: EntityFingerprint) -> set[int]:
        candidates: set[int] = set()
        for b, band_hash in enumerate(fp.lsh_band_hashes[: self._num_bands]):
            candidates |= self._bands[b].get(band_hash, set())
        candidates.discard(fp.entity_id)
        return candidates

    def remove(self, fp: EntityFingerprint) -> None:
        for b, band_hash in enumerate(fp.lsh_band_hashes[: self._num_bands]):
            if band_hash in self._bands[b]:
                self._bands[b][band_hash].discard(fp.entity_id)


class TokenIndex:
    """Inverted word index for token-level matching."""

    def __init__(self) -> None:
        self._index: dict[str, set[int]] = {}

    def add(self, fp: EntityFingerprint) -> None:
        for token in fp.normalized_tokens:
            self._index.setdefault(token, set()).add(fp.entity_id)

    def query(self, fp: EntityFingerprint) -> set[int]:
        candidates: set[int] = set()
        for token in fp.normalized_tokens:
            candidates |= self._index.get(token, set())
        candidates.discard(fp.entity_id)
        return candidates

    def remove(self, fp: EntityFingerprint) -> None:
        for token in fp.normalized_tokens:
            if token in self._index:
                self._index[token].discard(fp.entity_id)


class CompositeIndex:
    """Union of all three indexes with type filtering."""

    def __init__(self) -> None:
        self.phonetic = PhoneticIndex()
        self.trigram_lsh = TrigramLSHIndex()
        self.token = TokenIndex()

    def add(self, fp: EntityFingerprint) -> None:
        self.phonetic.add(fp)
        self.trigram_lsh.add(fp)
        self.token.add(fp)

    def query(
        self,
        fp: EntityFingerprint,
        fingerprints: dict[int, EntityFingerprint] | None = None,
        type_filter: str | None = None,
    ) -> set[int]:
        """Union of all indexes, optionally filtered by entity type."""
        candidates = (
            self.phonetic.query(fp)
            | self.trigram_lsh.query(fp)
            | self.token.query(fp)
        )
        if type_filter and fingerprints:
            candidates = {
                eid
                for eid in candidates
                if fingerprints.get(eid, None) is not None
                and fingerprints[eid].entity_type == type_filter
            }
        return candidates

    def remove(self, fp: EntityFingerprint) -> None:
        self.phonetic.remove(fp)
        self.trigram_lsh.remove(fp)
        self.token.remove(fp)
