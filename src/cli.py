"""CLI interface for PII-Safe.

Usage:
    pii-safe scan "text with PII"
    pii-safe scan --policy strict "text with PII"
    pii-safe scan --format json "text with PII"
    pii-safe detect "text with PII"
"""

from __future__ import annotations

import argparse
import json
import sys

from .engine import PIISafeEngine, ScanResult
from .policies import BUILTIN_POLICIES, SanitizationPolicy


# ANSI colors for terminal output
class _C:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"


def _print_scan_result(result: ScanResult) -> None:
    """Print a formatted scan result to the terminal."""
    det = result.detection
    san = result.sanitization
    score = result.privacy_score

    print(f"\n{_C.BOLD}PII-Safe v0.1.0{_C.RESET}\n")
    print(f"{_C.DIM}Input:{_C.RESET}  {det.original_text}\n")

    if not det.has_pii:
        print(f"{_C.GREEN}No PII detected.{_C.RESET}\n")
        return

    print(f"Detected {_C.BOLD}{det.entity_count}{_C.RESET} PII entities:")
    for entity in det.entities:
        color = _C.RED if entity.confidence >= 0.8 else _C.YELLOW
        print(
            f"  {color}{entity.entity_type:<16}{_C.RESET} "
            f'"{_C.BOLD}{entity.text}{_C.RESET}"'
            f"  {_C.DIM}[{entity.start}:{entity.end}]{_C.RESET}"
            f"  confidence: {entity.confidence:.2f}"
        )

    print(f"\n{_C.DIM}Output:{_C.RESET} {_C.GREEN}{san.sanitized_text}{_C.RESET}\n")

    # Privacy score
    level_colors = {
        "NONE": _C.GREEN,
        "LOW": _C.GREEN,
        "MEDIUM": _C.YELLOW,
        "HIGH": _C.RED,
        "CRITICAL": _C.RED + _C.BOLD,
    }
    color = level_colors.get(score.level, _C.RESET)
    print(
        f"Privacy Risk Score: {color}{score.score:.2f} ({score.level}){_C.RESET}"
    )
    print(
        f"  {score.total_entities} entities detected, "
        f"{score.sanitized_entities} sanitized, "
        f"{score.leaked_entities} leaked"
    )
    print()


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="pii-safe",
        description="PII-Safe: Privacy middleware for AI agent workflows",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # scan command
    scan_parser = subparsers.add_parser("scan", help="Detect and sanitize PII")
    scan_parser.add_argument("text", help="Text to scan for PII")
    scan_parser.add_argument(
        "--policy",
        choices=list(BUILTIN_POLICIES.keys()),
        default="default",
        help="Sanitization policy (default: default)",
    )
    scan_parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)",
    )

    # detect command (detection only, no sanitization)
    detect_parser = subparsers.add_parser("detect", help="Detect PII only")
    detect_parser.add_argument("text", help="Text to scan for PII")
    detect_parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)",
    )

    # policies command
    subparsers.add_parser("policies", help="List available policies")

    args = parser.parse_args()

    if args.command == "policies":
        print(f"\n{_C.BOLD}Available policies:{_C.RESET}\n")
        for name, policy in BUILTIN_POLICIES.items():
            print(f"  {_C.CYAN}{name}{_C.RESET} — {policy.description}")
        print()
        return

    if args.command == "detect":
        engine = PIISafeEngine()
        detection = engine.detect(args.text)
        if args.format == "json":
            print(json.dumps(detection.to_dict(), indent=2))
        else:
            print(f"\n{_C.BOLD}PII-Safe v0.1.0{_C.RESET} (detect only)\n")
            if not detection.has_pii:
                print(f"{_C.GREEN}No PII detected.{_C.RESET}\n")
            else:
                print(f"Detected {detection.entity_count} PII entities:")
                for e in detection.entities:
                    print(f"  {e.entity_type:<16} \"{e.text}\"  confidence: {e.confidence:.2f}")
                print()
        return

    if args.command == "scan":
        policy = BUILTIN_POLICIES[args.policy]
        engine = PIISafeEngine(policy=policy)
        result = engine.scan(args.text)

        if args.format == "json":
            print(json.dumps(result.to_dict(), indent=2))
        else:
            _print_scan_result(result)
        return


if __name__ == "__main__":
    main()
