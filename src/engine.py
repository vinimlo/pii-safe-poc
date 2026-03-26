"""PII-Safe Engine — orchestrates detection, sanitization, and scoring.

This is the main entry point for programmatic usage:
    from src.engine import PIISafeEngine
    engine = PIISafeEngine()
    result = engine.scan("John's email is john@example.com")
"""

from __future__ import annotations

from dataclasses import dataclass

from .detector import DetectionResult, PIIDetector
from .policies import SanitizationPolicy, BUILTIN_POLICIES, DEFAULT_POLICY
from .sanitizer import PIISanitizer, SanitizationResult


@dataclass
class PrivacyScore:
    """Privacy risk assessment for a piece of text."""

    score: float  # 0.0 (no risk) to 1.0 (critical risk)
    level: str  # LOW, MEDIUM, HIGH, CRITICAL
    total_entities: int
    sanitized_entities: int
    leaked_entities: int

    def to_dict(self) -> dict:
        return {
            "score": round(self.score, 2),
            "level": self.level,
            "total_entities": self.total_entities,
            "sanitized": self.sanitized_entities,
            "leaked": self.leaked_entities,
        }


def _compute_score(detection: DetectionResult, sanitization: SanitizationResult) -> PrivacyScore:
    """Compute a privacy risk score based on detection and sanitization results.

    Score is based on:
    - Number of PII entities found
    - Average confidence of detections
    - How many entities were leaked (allowlisted)
    """
    total = detection.entity_count
    if total == 0:
        return PrivacyScore(
            score=0.0, level="NONE", total_entities=0,
            sanitized_entities=0, leaked_entities=0,
        )

    leaked = sanitization.allowed_count
    sanitized = total - leaked

    # Base score: proportion of text that contains PII, weighted by confidence
    avg_confidence = (
        sum(e.confidence for e in detection.entities) / total
        if total > 0
        else 0
    )

    # Risk increases with entity count and confidence
    density_factor = min(total / 5.0, 1.0)  # caps at 5 entities
    leak_penalty = leaked / total if total > 0 else 0

    # Score: high confidence + high density + leaks = high risk
    raw_score = avg_confidence * 0.4 + density_factor * 0.3 + leak_penalty * 0.3
    score = min(raw_score, 1.0)

    if score >= 0.75:
        level = "CRITICAL"
    elif score >= 0.5:
        level = "HIGH"
    elif score >= 0.25:
        level = "MEDIUM"
    else:
        level = "LOW"

    return PrivacyScore(
        score=score,
        level=level,
        total_entities=total,
        sanitized_entities=sanitized,
        leaked_entities=leaked,
    )


@dataclass
class ScanResult:
    """Complete result of a PII scan: detection + sanitization + score."""

    detection: DetectionResult
    sanitization: SanitizationResult
    privacy_score: PrivacyScore

    def to_dict(self) -> dict:
        return {
            "detection": self.detection.to_dict(),
            "sanitization": self.sanitization.to_dict(),
            "privacy_score": self.privacy_score.to_dict(),
        }


class PIISafeEngine:
    """Main engine orchestrating PII detection, sanitization, and scoring.

    Usage:
        engine = PIISafeEngine()
        result = engine.scan("John's email is john@example.com")
        print(result.sanitization.sanitized_text)
        print(result.privacy_score.level)
    """

    def __init__(self, policy: SanitizationPolicy | None = None):
        self._detector = PIIDetector()
        self._policy = policy or DEFAULT_POLICY
        self._sanitizer = PIISanitizer(self._policy)

    @property
    def policy(self) -> SanitizationPolicy:
        return self._policy

    def set_policy(self, policy: SanitizationPolicy | str) -> None:
        """Change the active sanitization policy."""
        if isinstance(policy, str):
            if policy not in BUILTIN_POLICIES:
                raise ValueError(
                    f"Unknown policy '{policy}'. Available: {list(BUILTIN_POLICIES.keys())}"
                )
            policy = BUILTIN_POLICIES[policy]
        self._policy = policy
        self._sanitizer = PIISanitizer(policy)

    def detect(self, text: str, language: str = "en") -> DetectionResult:
        """Detect PII entities without sanitizing."""
        return self._detector.detect(text, language)

    def scan(self, text: str, language: str = "en") -> ScanResult:
        """Full pipeline: detect PII, sanitize, and score."""
        detection = self._detector.detect(text, language)
        sanitization = self._sanitizer.sanitize(detection)
        score = _compute_score(detection, sanitization)
        return ScanResult(
            detection=detection,
            sanitization=sanitization,
            privacy_score=score,
        )

    def scan_dict(self, data: dict, language: str = "en") -> dict[str, ScanResult]:
        """Scan all string values in a dictionary."""
        results: dict[str, ScanResult] = {}
        for key, value in data.items():
            if isinstance(value, str):
                result = self.scan(value, language)
                if result.detection.has_pii:
                    results[key] = result
        return results
