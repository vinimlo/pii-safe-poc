"""Interactive multi-turn demo for PII-Safe entity resolution.

Demonstrates Tier 1 (regex detection) + Tier 3 (Bayesian entity resolution)
working together across a multi-turn conversation.

Usage:
    python -m src.demo                              # interactive mode
    python -m src.demo --script demo_script.json    # scripted mode
    python -m src.demo --script demo_script.json --verbose  # with signal breakdown
"""

import argparse
import json
import sys
from pathlib import Path

from src.entity_resolution.resolver import EntityResolver
from src.entity_resolution.scorer import Decision
from src.tier1 import scan
from src.tier2_lite import detect_names


# ANSI colors
class C:
    BOLD = "\033[1m"
    DIM = "\033[2m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    CYAN = "\033[36m"
    RED = "\033[31m"
    MAGENTA = "\033[35m"
    RESET = "\033[0m"


# Entity type -> display prefix
TYPE_LABELS = {
    "PERSON": "USER",
    "EMAIL_ADDRESS": "EMAIL",
    "PHONE_NUMBER": "PHONE",
    "IP_ADDRESS": "IP",
    "CREDIT_CARD": "CC",
    "US_SSN": "SSN",
    "BRAZILIAN_CPF": "CPF",
    "API_KEY": "APIKEY",
}

# PII types that go through entity resolution (names need cross-turn tracking)
RESOLVABLE_TYPES = {"PERSON"}


def _label(entity_type: str, entity_id: int) -> str:
    prefix = TYPE_LABELS.get(entity_type, "ENTITY")
    return f"[{prefix}_{entity_id}]"


def _decision_color(decision: Decision) -> str:
    if decision == Decision.MERGE:
        return C.GREEN
    elif decision == Decision.DEFERRED:
        return C.YELLOW
    return C.CYAN


def process_turn(
    turn_num: int,
    text: str,
    resolver: EntityResolver,
    verbose: bool = False,
) -> str:
    """Process a single turn: detect PII, resolve entities, sanitize."""
    resolver.session.next_turn()

    # Tier 1: regex detection (deterministic PII)
    tier1_detections = scan(text)

    # Tier 2 lite: name detection (capitalization heuristic)
    name_detections = detect_names(text)

    # Merge detections, avoiding overlaps (Tier 1 takes priority)
    tier1_spans = {(d.start, d.end) for d in tier1_detections}
    all_detections = []
    for d in tier1_detections:
        all_detections.append(("tier1", d.entity_type, d.text, d.start, d.end))
    for n in name_detections:
        # Skip if overlapping with any Tier 1 detection
        overlaps = any(
            not (n.end <= s or n.start >= e)
            for s, e in tier1_spans
        )
        if not overlaps:
            all_detections.append(("tier2", "PERSON", n.text, n.start, n.end))

    if not all_detections:
        return text

    print(f"  {C.DIM}│{C.RESET}")
    print(f"  {C.DIM}│  Detected:{C.RESET}")

    sanitized = text
    replacements = []

    for tier, entity_type, det_text, start, end in all_detections:
        # Tier 3: entity resolution for all detected entities
        result = resolver.resolve(entity_type, det_text, turn=turn_num)
        dc = _decision_color(result.decision)

        if result.decision == Decision.NEW_ENTITY:
            summary = resolver.session.get_session_summary()
            new_id = summary[-1]["entity_id"] if summary else 0
            label = _label(entity_type, new_id)
            print(f"  {C.DIM}│{C.RESET}    {C.BOLD}{entity_type:15s}{C.RESET} "
                  f'"{det_text}" → {dc}{label} (new entity){C.RESET}')
        else:
            label = _label(entity_type, result.candidate_id)
            print(f"  {C.DIM}│{C.RESET}    {C.BOLD}{entity_type:15s}{C.RESET} "
                  f'"{det_text}"')

            if verbose and result.signals:
                print(f"  {C.DIM}│{C.RESET}      ├─ Candidates: [{TYPE_LABELS.get(entity_type, 'E')}_{result.candidate_id}] "
                      f'"{result.candidate_text}"')
                for sig in result.signals:
                    bar = "█" * int(sig.value * 10) + "░" * (10 - int(sig.value * 10))
                    sign = "+" if sig.log_lr >= 0 else ""
                    print(f"  {C.DIM}│{C.RESET}      ├─ {sig.name:22s} "
                          f"{bar} {sig.value:.3f}  log-LR: {sign}{sig.log_lr:.2f}")
                print(f"  {C.DIM}│{C.RESET}      ├─ Posterior: {C.BOLD}{result.posterior:.1%}{C.RESET}")
                print(f"  {C.DIM}│{C.RESET}      └─ Decision: {dc}{result.decision.value} → {label} ✓{C.RESET}")
            else:
                print(f"  {C.DIM}│{C.RESET}      └─ {dc}{result.decision.value} → {label} "
                      f"(posterior: {result.posterior:.1%}){C.RESET}")

        replacements.append((start, end, label))

    # Apply replacements in reverse order
    for start, end, label in sorted(replacements, reverse=True):
        sanitized = sanitized[:start] + label + sanitized[end:]

    return sanitized


def print_session_state(resolver: EntityResolver) -> None:
    """Print current session entity state."""
    summary = resolver.session.get_session_summary()
    if not summary:
        return
    print(f"\n  {C.BOLD}Session State:{C.RESET}")
    for entity in summary:
        eid = entity["entity_id"]
        etype = entity["type"]
        canonical = entity["canonical"]
        variants = entity["variants"]
        mentions = entity["mentions"]
        label = _label(etype, eid)
        variant_str = ""
        if len(variants) > 1:
            extra = [v for v in variants if v != canonical]
            if extra:
                variant_str = f"  variants: {', '.join(extra)}"
        print(f"    {C.CYAN}{label:12s}{C.RESET} "
              f'"{canonical}"{variant_str}  ({mentions} mention{"s" if mentions != 1 else ""})')


def main() -> None:
    parser = argparse.ArgumentParser(description="PII-Safe Entity Resolution Demo")
    parser.add_argument("--script", type=str, help="JSON file with pre-written turns")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show signal breakdown")
    args = parser.parse_args()

    print(f"\n{C.BOLD}╔══════════════════════════════════════════════════════════╗{C.RESET}")
    print(f"{C.BOLD}║  PII-Safe Entity Resolution — Multi-Turn Demo           ║{C.RESET}")
    print(f"{C.BOLD}║  Tier 1 (Regex) + Tier 3 (Bayesian PEF)                 ║{C.RESET}")
    print(f"{C.BOLD}╚══════════════════════════════════════════════════════════╝{C.RESET}\n")

    resolver = EntityResolver()

    if args.script:
        # Scripted mode
        script_path = Path(args.script)
        if not script_path.exists():
            print(f"Error: script file not found: {args.script}", file=sys.stderr)
            sys.exit(1)
        turns = json.loads(script_path.read_text())

        for i, text in enumerate(turns, 1):
            print(f"  {C.BOLD}Turn {i}{C.RESET} │ {text}")
            sanitized = process_turn(i, text, resolver, verbose=args.verbose)
            print(f"  {C.DIM}│{C.RESET}")
            print(f"  {C.DIM}│{C.RESET}  {C.MAGENTA}Sanitized:{C.RESET} {sanitized}")
            print()

        print_session_state(resolver)
    else:
        # Interactive mode
        print(f"  Type a message and press Enter. Type 'quit' to exit.\n")
        turn = 0
        while True:
            try:
                text = input(f"  {C.BOLD}Turn {turn + 1}{C.RESET} │ ")
            except (EOFError, KeyboardInterrupt):
                break
            if text.strip().lower() in ("quit", "exit", "q"):
                break
            turn += 1
            sanitized = process_turn(turn, text, resolver, verbose=args.verbose)
            print(f"  {C.DIM}│{C.RESET}")
            print(f"  {C.DIM}│{C.RESET}  {C.MAGENTA}Sanitized:{C.RESET} {sanitized}")
            print()

        print_session_state(resolver)

    print()


if __name__ == "__main__":
    main()
