"""Tier 1: Compiled regex DFA with named groups for deterministic PII detection.

Single-pass scan — each character tested once against the combined automaton.
No external dependencies. Pure Python stdlib.
"""

import re
from dataclasses import dataclass

from .validators import validate_credit_card, validate_cpf, validate_email, validate_ip

# Entity type name mapping from regex group -> canonical type
_GROUP_TO_TYPE = {
    "EMAIL": "EMAIL_ADDRESS",
    "PHONE": "PHONE_NUMBER",
    "IPV4": "IP_ADDRESS",
    "CREDIT_CARD": "CREDIT_CARD",
    "SSN": "US_SSN",
    "CPF": "BRAZILIAN_CPF",
    "API_KEY": "API_KEY",
}

# Validators per entity type (group name -> validator function)
_VALIDATORS = {
    "CREDIT_CARD": validate_credit_card,
    "CPF": validate_cpf,
    "IPV4": validate_ip,
    "EMAIL": validate_email,
}

# Single compiled regex alternation with named groups
COMBINED_PATTERN = re.compile(
    r"""
    (?P<EMAIL>[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z]{2,})
    |(?P<CPF>\b\d{3}\.\d{3}\.\d{3}-\d{2}\b)
    |(?P<SSN>\b\d{3}-\d{2}-\d{4}\b)
    |(?P<CREDIT_CARD>\b(?:\d[ -]*?){13,19}\b)
    |(?P<PHONE>(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b)
    |(?P<IPV4>\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\b)
    |(?P<API_KEY>\b(?:sk|pk|api)[_-][a-zA-Z0-9]{20,}\b)
    """,
    re.VERBOSE,
)


@dataclass(frozen=True, slots=True)
class PIIMatch:
    """A single PII detection from Tier 1 regex scan."""

    entity_type: str
    text: str
    start: int
    end: int
    confidence: float


def scan(text: str) -> list[PIIMatch]:
    """Single-pass regex scan with post-match validation.

    Returns only validated matches. Confidence is 1.0 for validator-confirmed
    matches, 0.95 for types without validators.
    """
    results: list[PIIMatch] = []
    for match in COMBINED_PATTERN.finditer(text):
        group_name = match.lastgroup
        if group_name is None:
            continue
        matched_text = match.group()
        validator = _VALIDATORS.get(group_name)
        if validator is not None and not validator(matched_text):
            continue
        entity_type = _GROUP_TO_TYPE[group_name]
        confidence = 1.0 if validator is not None else 0.95
        results.append(
            PIIMatch(
                entity_type=entity_type,
                text=matched_text,
                start=match.start(),
                end=match.end(),
                confidence=confidence,
            )
        )
    return results
