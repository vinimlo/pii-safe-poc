"""Tier 2 Lite: Lightweight name detection using capitalization heuristics.

This is a minimal Tier 2 implementation for the PoC demo. It uses capitalization
patterns to detect potential person names — the same heuristic described in the
proposal's cascade gate. A full Tier 2 would add gazetteer lookups and ONNX NER.
"""

import re
from dataclasses import dataclass

# Common words that are capitalized but aren't names
_STOP_WORDS = frozenset({
    "I", "The", "A", "An", "This", "That", "These", "Those", "My", "Your",
    "His", "Her", "Its", "Our", "Their", "We", "They", "He", "She", "It",
    "Is", "Are", "Was", "Were", "Be", "Been", "Being", "Have", "Has", "Had",
    "Do", "Does", "Did", "Will", "Would", "Could", "Should", "May", "Might",
    "Can", "Must", "Shall", "To", "Of", "In", "For", "On", "With", "At",
    "By", "From", "As", "But", "Or", "And", "Not", "No", "So", "If",
    "Also", "CC", "Send", "Please", "Forward", "Call", "Server", "Key",
    "Contact", "Email", "Phone", "IP", "SSN", "CPF", "Already",
    "Confirmed", "Meeting", "Tomorrow", "Invoice", "Report", "Thread",
    "Said",
})

# Pattern: capitalized word (2+ chars) that isn't all-caps
_CAP_WORD = re.compile(r"\b([A-Z][a-z]+)\b")


@dataclass(frozen=True, slots=True)
class NameMatch:
    """A potential person name detected by capitalization heuristic."""
    text: str
    start: int
    end: int


def detect_names(text: str) -> list[NameMatch]:
    """Detect potential person names using capitalization patterns.

    Finds sequences of capitalized words that aren't common stop words.
    Groups consecutive capitalized words into multi-word names.
    Also catches single capitalized words with initials (e.g., "K. Fernando").
    """
    results: list[NameMatch] = []

    # Find all capitalized words with their positions
    cap_words: list[tuple[str, int, int]] = []
    for m in _CAP_WORD.finditer(text):
        word = m.group(1)
        if word not in _STOP_WORDS:
            cap_words.append((word, m.start(), m.end()))

    # Also find initial patterns like "K."
    for m in re.finditer(r"\b([A-Z])\.\s*", text):
        cap_words.append((m.group(0).strip(), m.start(), m.end()))

    if not cap_words:
        return results

    # Sort by position
    cap_words.sort(key=lambda x: x[1])

    # Group consecutive capitalized words (within 2 chars of each other)
    groups: list[list[tuple[str, int, int]]] = []
    current_group: list[tuple[str, int, int]] = [cap_words[0]]

    for i in range(1, len(cap_words)):
        prev_end = current_group[-1][2]
        curr_start = cap_words[i][1]
        # Allow small gap (space, period+space)
        if curr_start - prev_end <= 2:
            current_group.append(cap_words[i])
        else:
            groups.append(current_group)
            current_group = [cap_words[i]]
    groups.append(current_group)

    # Convert groups to NameMatch
    for group in groups:
        full_text = text[group[0][1] : group[-1][2]]
        results.append(NameMatch(
            text=full_text,
            start=group[0][1],
            end=group[-1][2],
        ))

    return results
