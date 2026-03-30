"""Entity Resolver — the main orchestrator for Tier 3 entity resolution.

Combines multi-index candidate retrieval, Bayesian scoring, adaptive thresholds,
and session state management into a single resolve() call.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from .fingerprint import EntityFingerprint
from .scorer import BayesianScorer, Decision, ResolutionDecision
from .session import SessionGraph


# Per-type threshold configuration
@dataclass(frozen=True)
class TypeConfig:
    base_merge: float
    entropy_penalty: float


DEFAULT_TYPE_CONFIGS: dict[str, TypeConfig] = {
    "PERSON": TypeConfig(base_merge=0.65, entropy_penalty=0.03),
    "EMAIL_ADDRESS": TypeConfig(base_merge=0.90, entropy_penalty=0.01),
    "PHONE_NUMBER": TypeConfig(base_merge=0.85, entropy_penalty=0.01),
    "IP_ADDRESS": TypeConfig(base_merge=0.90, entropy_penalty=0.01),
}

DEFAULT_TYPE_CONFIG = TypeConfig(base_merge=0.75, entropy_penalty=0.02)
THRESHOLD_CEILING = 0.95
DEFER_GAP = 0.35
DEFER_FLOOR = 0.30


class EntityResolver:
    """Orchestrates entity resolution across a session.

    For each new entity detection:
    1. Create a temporary fingerprint
    2. Retrieve candidates from composite index (phonetic + LSH + token)
    3. Score each candidate with 5-signal Bayesian scorer
    4. Apply adaptive entropy threshold
    5. Decide: MERGE / DEFERRED / NEW_ENTITY
    6. Update session graph
    """

    def __init__(
        self,
        session: SessionGraph | None = None,
        scorer: BayesianScorer | None = None,
        type_configs: dict[str, TypeConfig] | None = None,
    ) -> None:
        self.session = session or SessionGraph()
        self.scorer = scorer or BayesianScorer()
        self.type_configs = type_configs or DEFAULT_TYPE_CONFIGS

    def _get_thresholds(self, entity_type: str) -> tuple[float, float]:
        """Compute adaptive merge and defer thresholds for an entity type."""
        config = self.type_configs.get(entity_type, DEFAULT_TYPE_CONFIG)
        num_same_type = self.session.count_by_type(entity_type)
        merge_threshold = config.base_merge + config.entropy_penalty * math.log2(
            1 + num_same_type
        )
        merge_threshold = min(merge_threshold, THRESHOLD_CEILING)
        defer_threshold = max(merge_threshold - DEFER_GAP, DEFER_FLOOR)
        return merge_threshold, defer_threshold

    def resolve(
        self,
        entity_type: str,
        text: str,
        turn: int | None = None,
    ) -> ResolutionDecision:
        """Resolve a detected entity against the session's known entities.

        Returns a ResolutionDecision with the outcome and full signal breakdown.
        """
        # Ensure session is at the right turn (only advances if behind)
        if turn is not None and self.session._current_turn < turn:
            while self.session._current_turn < turn:
                self.session.next_turn()

        # Create temporary fingerprint for query
        temp_fp = EntityFingerprint.create(
            entity_id=-1,  # temporary
            entity_type=entity_type,
            text=text,
        )

        # Retrieve candidates with type filtering
        candidate_ids = self.session.get_candidates(temp_fp, type_filter=entity_type)

        if not candidate_ids:
            # No candidates — create new entity
            fp = self.session.add_entity(entity_type, text)
            return ResolutionDecision(
                decision=Decision.NEW_ENTITY,
                candidate_id=None,
                posterior=0.0,
                total_weight=0.0,
                signals=[],
                query_text=text,
                candidate_text=None,
            )

        # Score each candidate
        merge_threshold, defer_threshold = self._get_thresholds(entity_type)
        best_decision: ResolutionDecision | None = None

        for cid in candidate_ids:
            candidate_fp = self.session.get_fingerprint(cid)
            if candidate_fp is None:
                continue

            # Compute co-occurrence score
            cooccurrence = self.session.compute_cooccurrence(-1, cid)

            decision = self.scorer.decide(
                query_fp=temp_fp,
                candidate_fp=candidate_fp,
                merge_threshold=merge_threshold,
                defer_threshold=defer_threshold,
                cooccurrence_score=cooccurrence,
            )

            if best_decision is None or decision.posterior > best_decision.posterior:
                best_decision = decision

        if best_decision is None:
            # Shouldn't happen, but safety fallback
            fp = self.session.add_entity(entity_type, text)
            return ResolutionDecision(
                decision=Decision.NEW_ENTITY,
                candidate_id=None,
                posterior=0.0,
                total_weight=0.0,
                signals=[],
                query_text=text,
                candidate_text=None,
            )

        # Apply decision
        if best_decision.decision == Decision.MERGE:
            self.session.record_mention(best_decision.candidate_id, text)
        elif best_decision.decision == Decision.DEFERRED:
            # Soft-link: record mention but flag for review
            self.session.record_mention(best_decision.candidate_id, text)
        else:
            # NEW_ENTITY
            self.session.add_entity(entity_type, text)

        return best_decision

    def get_entity_label(self, entity_id: int) -> str:
        """Get the pseudonymization label for an entity (e.g., [USER_1])."""
        record = self.session.get_record(entity_id)
        if record is None:
            return f"[UNKNOWN_{entity_id}]"
        type_prefix = {
            "PERSON": "USER",
            "EMAIL_ADDRESS": "EMAIL",
            "PHONE_NUMBER": "PHONE",
            "IP_ADDRESS": "IP",
        }.get(record.fingerprint.entity_type, "ENTITY")
        return f"[{type_prefix}_{entity_id}]"
