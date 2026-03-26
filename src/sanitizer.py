"""Policy-driven PII sanitization.

Applies sanitization actions (redact, pseudonymize, allowlist) to
detected PII entities based on configurable policies.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from .detector import DetectionResult, PIIEntity
from .policies import Action, SanitizationPolicy, DEFAULT_POLICY

# Deterministic fake names for pseudonymization (seeded by original value)
_FAKE_NAMES = [
    "James Wilson", "Maria Garcia", "Robert Chen", "Sarah Johnson",
    "David Kim", "Emily Brown", "Michael Lee", "Anna Martinez",
    "Thomas Wright", "Lisa Anderson", "Daniel Taylor", "Rachel Moore",
]


def _pseudonymize_value(entity: PIIEntity) -> str:
    """Generate a deterministic fake replacement for a PII entity.

    Uses a hash of the original value to pick a consistent replacement,
    so the same input always maps to the same pseudonym within a session.
    """
    h = int(hashlib.sha256(entity.text.encode()).hexdigest(), 16)

    if entity.entity_type == "PERSON":
        return _FAKE_NAMES[h % len(_FAKE_NAMES)]
    if entity.entity_type == "EMAIL_ADDRESS":
        name = _FAKE_NAMES[h % len(_FAKE_NAMES)].lower().replace(" ", ".")
        return f"{name}@example.com"
    if entity.entity_type == "PHONE_NUMBER":
        digits = str(h)[:10]
        return f"+1-{digits[:3]}-{digits[3:6]}-{digits[6:10]}"
    if entity.entity_type == "IP_ADDRESS":
        parts = [(h >> (i * 8)) & 0xFF for i in range(4)]
        return ".".join(str(p) for p in parts)

    # Generic pseudonymization: hash-based placeholder
    short_hash = hashlib.sha256(entity.text.encode()).hexdigest()[:8]
    return f"[PSEUDO_{entity.entity_type}_{short_hash}]"


def _redact_value(entity: PIIEntity) -> str:
    """Generate a redaction placeholder for a PII entity."""
    return f"[REDACTED_{entity.entity_type}]"


@dataclass
class SanitizedEntity:
    """A PII entity after sanitization."""

    original: PIIEntity
    replacement: str
    action: Action


@dataclass
class SanitizationResult:
    """Result of sanitizing a text input."""

    original_text: str
    sanitized_text: str
    sanitized_entities: list[SanitizedEntity] = field(default_factory=list)

    @property
    def entity_count(self) -> int:
        return len(self.sanitized_entities)

    @property
    def redacted_count(self) -> int:
        return sum(1 for e in self.sanitized_entities if e.action == Action.REDACT)

    @property
    def pseudonymized_count(self) -> int:
        return sum(
            1 for e in self.sanitized_entities if e.action == Action.PSEUDONYMIZE
        )

    @property
    def allowed_count(self) -> int:
        return sum(1 for e in self.sanitized_entities if e.action == Action.ALLOWLIST)

    def to_dict(self) -> dict:
        return {
            "original_text": self.original_text,
            "sanitized_text": self.sanitized_text,
            "entity_count": self.entity_count,
            "redacted": self.redacted_count,
            "pseudonymized": self.pseudonymized_count,
            "allowed": self.allowed_count,
            "entities": [
                {
                    "entity_type": e.original.entity_type,
                    "original": e.original.text,
                    "replacement": e.replacement,
                    "action": e.action.value,
                }
                for e in self.sanitized_entities
            ],
        }


class PIISanitizer:
    """Applies policy-driven sanitization to detected PII entities."""

    def __init__(self, policy: SanitizationPolicy | None = None):
        self.policy = policy or DEFAULT_POLICY

    def sanitize(self, detection: DetectionResult) -> SanitizationResult:
        """Apply the sanitization policy to a detection result.

        Processes entities in reverse order to preserve string positions.
        """
        text = detection.original_text
        sanitized_entities: list[SanitizedEntity] = []

        # Process in reverse order so positions stay valid
        for entity in sorted(detection.entities, key=lambda e: e.start, reverse=True):
            action = self.policy.action_for(entity.entity_type)

            if action == Action.REDACT:
                replacement = _redact_value(entity)
            elif action == Action.PSEUDONYMIZE:
                replacement = _pseudonymize_value(entity)
            else:
                replacement = entity.text  # allowlist: keep original

            sanitized_entities.append(
                SanitizedEntity(
                    original=entity,
                    replacement=replacement,
                    action=action,
                )
            )

            text = text[: entity.start] + replacement + text[entity.end :]

        # Reverse to restore original order
        sanitized_entities.reverse()

        return SanitizationResult(
            original_text=detection.original_text,
            sanitized_text=text,
            sanitized_entities=sanitized_entities,
        )
