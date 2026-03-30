"""Session graph for per-session entity state management.

Maintains entity fingerprints, co-occurrence tracking, LRU eviction,
and secure memory teardown.
"""

from __future__ import annotations

import ctypes
import math
import time
from collections import OrderedDict
from dataclasses import dataclass, field

from .fingerprint import EntityFingerprint
from .indexes import CompositeIndex


@dataclass
class EntityRecord:
    """Runtime entity record with metadata."""
    fingerprint: EntityFingerprint
    variants: list[str] = field(default_factory=list)
    mention_count: int = 0
    first_seen_turn: int = 0
    last_seen_turn: int = 0
    cooccurring_entities: dict[int, float] = field(default_factory=dict)


class SessionGraph:
    """Per-session entity state with LRU eviction and secure teardown.

    Maintains:
    - Entity fingerprints indexed for O(1) retrieval
    - Co-occurrence edges between entities in the same turn
    - LRU eviction at configurable capacity
    - Secure memory zeroing on destroy()
    """

    def __init__(self, max_entities: int = 1024, decay_lambda: float = 0.1) -> None:
        self.max_entities = max_entities
        self.decay_lambda = decay_lambda
        self._next_id = 1
        self._records: OrderedDict[int, EntityRecord] = OrderedDict()
        self._index = CompositeIndex()
        self._current_turn = 0
        self._turn_entities: list[set[int]] = []  # entities per turn
        self._destroyed = False

    @property
    def entity_count(self) -> int:
        return len(self._records)

    def count_by_type(self, entity_type: str) -> int:
        return sum(
            1 for r in self._records.values()
            if r.fingerprint.entity_type == entity_type
        )

    def next_turn(self) -> int:
        """Advance to the next turn and return its number."""
        self._current_turn += 1
        self._turn_entities.append(set())
        return self._current_turn

    def add_entity(self, entity_type: str, text: str) -> EntityFingerprint:
        """Create a new canonical entity and index it."""
        self._check_alive()
        entity_id = self._next_id
        self._next_id += 1

        fp = EntityFingerprint.create(entity_id, entity_type, text)
        record = EntityRecord(
            fingerprint=fp,
            variants=[text],
            mention_count=1,
            first_seen_turn=self._current_turn,
            last_seen_turn=self._current_turn,
        )

        self._records[entity_id] = record
        self._records.move_to_end(entity_id)
        self._index.add(fp)

        # Track in current turn
        if self._turn_entities:
            self._turn_entities[-1].add(entity_id)

        self._evict_if_needed()
        return fp

    def record_mention(self, entity_id: int, variant_text: str) -> None:
        """Record a new mention of an existing entity."""
        self._check_alive()
        if entity_id not in self._records:
            return
        record = self._records[entity_id]
        record.mention_count += 1
        record.last_seen_turn = self._current_turn
        if variant_text not in record.variants:
            record.variants.append(variant_text)
        self._records.move_to_end(entity_id)

        # Track co-occurrence
        if self._turn_entities:
            self._turn_entities[-1].add(entity_id)

    def get_fingerprint(self, entity_id: int) -> EntityFingerprint | None:
        record = self._records.get(entity_id)
        return record.fingerprint if record else None

    def get_record(self, entity_id: int) -> EntityRecord | None:
        return self._records.get(entity_id)

    def get_all_fingerprints(self) -> dict[int, EntityFingerprint]:
        return {eid: r.fingerprint for eid, r in self._records.items()}

    def get_candidates(self, fp: EntityFingerprint, type_filter: str | None = None) -> set[int]:
        """Retrieve candidate entity IDs from all indexes."""
        return self._index.query(fp, self.get_all_fingerprints(), type_filter)

    def compute_cooccurrence(self, entity_id_a: int, entity_id_b: int) -> float:
        """Compute co-occurrence score between two entities.

        Uses Jaccard overlap of turns where both entities appear,
        weighted by exponential decay for recency.
        """
        turns_a: set[int] = set()
        turns_b: set[int] = set()

        for turn_idx, entities in enumerate(self._turn_entities):
            if entity_id_a in entities:
                turns_a.add(turn_idx)
            if entity_id_b in entities:
                turns_b.add(turn_idx)

        if not turns_a or not turns_b:
            return 0.0

        shared_turns = turns_a & turns_b
        if not shared_turns:
            return 0.0

        # Weight shared turns by recency
        weighted_sum = sum(
            math.exp(-self.decay_lambda * (self._current_turn - t))
            for t in shared_turns
        )
        max_possible = min(len(turns_a), len(turns_b))
        return min(1.0, weighted_sum / max_possible) if max_possible > 0 else 0.0

    def get_session_summary(self) -> list[dict]:
        """Get a summary of all entities in the session."""
        summary = []
        for eid, record in self._records.items():
            summary.append({
                "entity_id": eid,
                "type": record.fingerprint.entity_type,
                "canonical": record.fingerprint.canonical_text,
                "variants": record.variants,
                "mentions": record.mention_count,
            })
        return summary

    def _evict_if_needed(self) -> None:
        """Evict oldest entities if over capacity using LRU."""
        while len(self._records) > self.max_entities:
            oldest_id, oldest_record = next(iter(self._records.items()))
            self._index.remove(oldest_record.fingerprint)
            del self._records[oldest_id]

    def destroy(self) -> None:
        """Secure session teardown — best-effort zero-fill of PII in memory.

        Attempts to overwrite the underlying bytes of Python string objects
        using CPython-specific memory address manipulation. This is inherently
        fragile: CPython may intern strings, and the GC can relocate objects.

        A production implementation should store PII in mmap-backed buffers
        or a C extension that guarantees zeroing. This PoC demonstrates the
        *pattern* — detect PII residue and attempt erasure — not a hardened
        implementation. See the proposal's Threat Model section for the full
        attack surface analysis.
        """
        import sys

        for record in self._records.values():
            for text in [record.fingerprint.canonical_text] + record.variants:
                if not text:
                    continue
                try:
                    # CPython-specific: str objects store UTF-8 data at a
                    # known offset from the object's id(). We attempt to
                    # overwrite those bytes in-place. This is best-effort:
                    # interned or cached strings may have other references.
                    str_size = sys.getsizeof(text)
                    text_len = len(text.encode("utf-8"))
                    addr = id(text) + str_size - text_len - 1
                    ctypes.memset(addr, 0, text_len)
                except Exception:
                    pass  # Non-CPython or address calculation failed

        self._records.clear()
        self._index = CompositeIndex()
        self._turn_entities.clear()
        self._destroyed = True

    def _check_alive(self) -> None:
        if self._destroyed:
            raise RuntimeError("Session has been destroyed — cannot add entities")
