"""Policy definitions for PII sanitization.

Each policy defines how detected PII entities should be handled:
- REDACT: Replace with a placeholder like [REDACTED_EMAIL]
- PSEUDONYMIZE: Replace with a realistic fake value
- ALLOWLIST: Keep the original value (no sanitization)
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel


class Action(str, Enum):
    REDACT = "redact"
    PSEUDONYMIZE = "pseudonymize"
    ALLOWLIST = "allowlist"


class EntityPolicy(BaseModel):
    action: Action = Action.REDACT


class SanitizationPolicy(BaseModel):
    """Maps entity types to sanitization actions."""

    name: str = "default"
    description: str = ""
    default_action: Action = Action.REDACT
    entities: dict[str, EntityPolicy] = {}

    def action_for(self, entity_type: str) -> Action:
        if entity_type in self.entities:
            return self.entities[entity_type].action
        return self.default_action

    @classmethod
    def from_yaml(cls, path: str | Path) -> SanitizationPolicy:
        with open(path) as f:
            data = yaml.safe_load(f)
        return cls(**data)


# Built-in policies

DEFAULT_POLICY = SanitizationPolicy(
    name="default",
    description="Redact all PII by default, pseudonymize person names",
    default_action=Action.REDACT,
    entities={
        "PERSON": EntityPolicy(action=Action.PSEUDONYMIZE),
    },
)

STRICT_POLICY = SanitizationPolicy(
    name="strict",
    description="Redact everything, no exceptions",
    default_action=Action.REDACT,
    entities={},
)

PERMISSIVE_POLICY = SanitizationPolicy(
    name="permissive",
    description="Only redact high-risk entities (emails, credit cards, SSN)",
    default_action=Action.ALLOWLIST,
    entities={
        "EMAIL_ADDRESS": EntityPolicy(action=Action.REDACT),
        "CREDIT_CARD": EntityPolicy(action=Action.REDACT),
        "US_SSN": EntityPolicy(action=Action.REDACT),
        "PHONE_NUMBER": EntityPolicy(action=Action.REDACT),
        "IP_ADDRESS": EntityPolicy(action=Action.REDACT),
    },
)

BUILTIN_POLICIES: dict[str, SanitizationPolicy] = {
    "default": DEFAULT_POLICY,
    "strict": STRICT_POLICY,
    "permissive": PERMISSIVE_POLICY,
}
