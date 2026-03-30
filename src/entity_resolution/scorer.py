"""Bayesian log-likelihood scorer adapted from Fellegi-Sunter record linkage theory.

Combines 5 independent signals via log-likelihood ratios to produce a posterior
probability of entity match. Three-outcome decision: MERGE / DEFERRED / NEW_ENTITY.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum

from .fingerprint import EntityFingerprint
from .similarity import (
    normalized_damerau_levenshtein,
    phonetic_similarity,
    token_jaccard,
    trigram_jaccard,
)


class Decision(Enum):
    MERGE = "MERGE"
    DEFERRED = "DEFERRED"
    NEW_ENTITY = "NEW_ENTITY"


@dataclass(frozen=True)
class SignalScore:
    """Score for a single comparison signal."""
    name: str
    value: float
    log_lr: float


@dataclass(frozen=True)
class ResolutionDecision:
    """Full scoring result for an entity resolution decision."""
    decision: Decision
    candidate_id: int | None
    posterior: float
    total_weight: float
    signals: list[SignalScore]
    query_text: str
    candidate_text: str | None


# Default m (match) and u (non-match) probability parameters per signal.
# Tuned on synthetic typo/abbreviation/reordering examples.
# GSoC implementation will calibrate empirically on larger datasets.
_DEFAULT_M_U = {
    "phonetic": (0.80, 0.15),
    "damerau_levenshtein": (0.85, 0.10),
    "trigram_jaccard": (0.75, 0.20),
    "token_jaccard": (0.90, 0.08),     # high weight — critical for reordering
    "cooccurrence": (0.60, 0.40),       # weak signal — absence is not informative
}


def _log_likelihood_ratio(value: float, m: float, u: float) -> float:
    """Compute log-likelihood ratio for a signal value.

    Uses a linear interpolation model:
      P(value | match) = m * value + (1-m) * (1-value)
      P(value | non-match) = u * value + (1-u) * (1-value)

    This gives positive LR for high similarity and negative for low.
    """
    p_match = m * value + (1 - m) * (1 - value)
    p_non_match = u * value + (1 - u) * (1 - value)

    # Clamp to avoid log(0)
    p_match = max(p_match, 1e-10)
    p_non_match = max(p_non_match, 1e-10)

    return math.log2(p_match / p_non_match)


class BayesianScorer:
    """5-signal Bayesian scorer for entity resolution."""

    def __init__(
        self,
        prior: float = 0.3,
        m_u_params: dict[str, tuple[float, float]] | None = None,
    ) -> None:
        self.prior = prior
        self.m_u = m_u_params or _DEFAULT_M_U

    def score(
        self,
        query_fp: EntityFingerprint,
        candidate_fp: EntityFingerprint,
        cooccurrence_score: float = 0.0,
    ) -> tuple[float, float, list[SignalScore]]:
        """Score a candidate match using 5 signals.

        Returns (posterior, total_weight, signal_scores).
        """
        signals: list[SignalScore] = []

        # Signal 1: Phonetic similarity
        # Compare full-string codes AND per-token codes (handles reordering)
        phon_sim = max(
            phonetic_similarity(query_fp.phonetic_primary, candidate_fp.phonetic_primary),
            phonetic_similarity(query_fp.phonetic_primary, candidate_fp.phonetic_secondary),
            phonetic_similarity(query_fp.phonetic_secondary, candidate_fp.phonetic_primary),
        )
        # Per-token phonetic: compare individual word codes for best match
        from .phonetic import double_metaphone as _dm
        q_tokens = query_fp.canonical_text.lower().split()
        c_tokens = candidate_fp.canonical_text.lower().split()
        if q_tokens and c_tokens:
            token_phon_scores = []
            for qt in q_tokens:
                qp, qs = _dm(qt)
                best = 0.0
                for ct in c_tokens:
                    cp, cs = _dm(ct)
                    best = max(best, phonetic_similarity(qp, cp), phonetic_similarity(qp, cs),
                               phonetic_similarity(qs, cp) if qs else 0.0)
                token_phon_scores.append(best)
            if token_phon_scores:
                phon_sim = max(phon_sim, sum(token_phon_scores) / len(token_phon_scores))
        m, u = self.m_u["phonetic"]
        signals.append(SignalScore("phonetic", phon_sim, _log_likelihood_ratio(phon_sim, m, u)))

        # Signal 2: Damerau-Levenshtein
        # Compare raw AND sorted-token versions (handles word reordering)
        q_text = query_fp.canonical_text.lower()
        c_text = candidate_fp.canonical_text.lower()
        dl_sim_raw = normalized_damerau_levenshtein(q_text, c_text)
        dl_sim_sorted = normalized_damerau_levenshtein(
            " ".join(sorted(q_text.split())),
            " ".join(sorted(c_text.split())),
        )
        dl_sim = max(dl_sim_raw, dl_sim_sorted)
        m, u = self.m_u["damerau_levenshtein"]
        signals.append(SignalScore("damerau_levenshtein", dl_sim, _log_likelihood_ratio(dl_sim, m, u)))

        # Signal 3: Trigram Jaccard
        tri_sim = trigram_jaccard(query_fp.canonical_text, candidate_fp.canonical_text)
        m, u = self.m_u["trigram_jaccard"]
        signals.append(SignalScore("trigram_jaccard", tri_sim, _log_likelihood_ratio(tri_sim, m, u)))

        # Signal 4: Token Jaccard
        tok_sim = token_jaccard(query_fp.canonical_text, candidate_fp.canonical_text)
        m, u = self.m_u["token_jaccard"]
        signals.append(SignalScore("token_jaccard", tok_sim, _log_likelihood_ratio(tok_sim, m, u)))

        # Signal 5: Co-occurrence (neutral when no data — absence is not evidence)
        m, u = self.m_u["cooccurrence"]
        cooc_lr = 0.0 if cooccurrence_score == 0.0 else _log_likelihood_ratio(cooccurrence_score, m, u)
        signals.append(SignalScore("cooccurrence", cooccurrence_score, cooc_lr))

        # Compute total weight and posterior
        total_weight = sum(s.log_lr for s in signals)
        odds_ratio = (self.prior / (1 - self.prior)) * (2 ** total_weight)
        posterior = odds_ratio / (1 + odds_ratio)

        return posterior, total_weight, signals

    def decide(
        self,
        query_fp: EntityFingerprint,
        candidate_fp: EntityFingerprint,
        merge_threshold: float,
        defer_threshold: float,
        cooccurrence_score: float = 0.0,
    ) -> ResolutionDecision:
        """Score and produce a three-outcome decision."""
        posterior, total_weight, signals = self.score(
            query_fp, candidate_fp, cooccurrence_score
        )

        if posterior >= merge_threshold:
            decision = Decision.MERGE
        elif posterior >= defer_threshold:
            decision = Decision.DEFERRED
        else:
            decision = Decision.NEW_ENTITY

        return ResolutionDecision(
            decision=decision,
            candidate_id=candidate_fp.entity_id,
            posterior=posterior,
            total_weight=total_weight,
            signals=signals,
            query_text=query_fp.canonical_text,
            candidate_text=candidate_fp.canonical_text,
        )
