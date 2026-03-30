# pii-safe

**Real-time privacy guard for agentic AI workflows — 3-tier cascading PII detection with Bayesian entity resolution.**

![Tests](https://img.shields.io/badge/tests-88%2F88_passing-10b981?style=flat-square)
![Python](https://img.shields.io/badge/Python-3.11+-3776ab?style=flat-square)
![MCP](https://img.shields.io/badge/MCP-tool_server-8b5cf6?style=flat-square)
![License](https://img.shields.io/badge/license-MIT-444?style=flat-square)
![Latency](https://img.shields.io/badge/Tier_1-44μs_(272x_faster_than_Presidio)-f59e0b?style=flat-square)

> **Status:** Proof of concept for [GSoC 2026 — C2SI PII-Safe](https://c2si.org/gsoc/)

AI agents in frameworks like LangGraph and CrewAI process sensitive data across dozens of tool calls per second — but no existing middleware can detect and sanitize PII at that speed while maintaining consistent entity identity across conversation turns. PII-Safe fills this gap with a **3-tier cascading privacy guard** designed specifically for real-time agentic workflows.

---

## Entity Resolution Demo

[![asciicast](https://asciinema.org/a/wEo2Ds5068kogRrA.svg)](https://asciinema.org/a/wEo2Ds5068kogRrA)

Run the multi-turn demo to see Bayesian entity resolution in action:

```bash
.venv/bin/python -m src.demo --script demo_script.json --verbose
```

This simulates a 6-turn agent conversation and shows:
- **Turn 1:** "Kavishka Fernando" and "kavishka@wso2.com" detected as new entities
- **Turn 3:** "Kavihska Fernando" (typo) → **MERGE** with [USER_2] (posterior: 83.1%)
- **Turn 4:** "Fernando" (partial name) → **DEFERRED** to [USER_2] (posterior: 62.7%)
- **Turn 6:** "Catherine" → **DEFERRED** to "Katherine" (phonetic match, 64.5%)

Each resolution shows the full 5-signal Bayesian breakdown (phonetic, edit distance, trigram, token, co-occurrence).

---

## Benchmarks

```bash
.venv/bin/python benchmarks/entity_resolution_bench.py   # precision/recall
.venv/bin/python benchmarks/tier1_latency_bench.py        # latency comparison
```

| Metric | Value |
|--------|-------|
| Tier 1 latency (p50) | 44μs |
| Tier 1 throughput | 22,600 scans/s |
| Presidio latency (p50) | 11,829μs |
| **Speedup** | **272x** |
| Entity resolution F1 (threshold 0.90) | 0.923 |
| Typo recall | 100% |
| Reordering recall | 100% |
| Phonetic recall | 100% |

---

## What This Proves

- **Tier 1: Pure regex detection** — 44μs mean latency, 272x faster than Presidio, zero external dependencies
- **Tier 3: Bayesian entity resolution** — Probabilistic Entity Fingerprint (PEF) system resolves typos, reordering, and phonetic variants. F1=0.923 on synthetic benchmark. "Kavihska" correctly merges with "Kavishka Fernando" (83.1% posterior).
- **Three-outcome model** — MERGE / DEFERRED / NEW_ENTITY. Ambiguous cases are flagged, not silently merged.
- **Secure session teardown** — Entity fingerprints are zero-filled via `ctypes.memset` before GC. Privacy of the privacy guard.
- **Policy-driven sanitization** — redact, pseudonymize, or allowlist per entity type
- **MCP tool interface** — AI agents discover and call PII-Safe via the Model Context Protocol
- **88 passing tests** across detection, sanitization, engine, Tier 1, and entity resolution modules

---

## Quick Start

```bash
# Clone and install
git clone https://github.com/vinimlo/pii-safe-poc.git
cd pii-safe-poc
uv venv && uv pip install -e ".[dev]"
uv pip install en_core_web_sm@https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl

# Scan text for PII
python -m src.cli scan "John Smith's email is john@example.com and IP is 192.168.1.1"

# Detect only (no sanitization)
python -m src.cli detect "Contact jane@company.com"

# Strict policy (redact everything)
python -m src.cli scan --policy strict "John Smith called from 555-867-5309"

# JSON output for programmatic use
python -m src.cli scan --format json "Jane Doe, jane@acme.com, 555-867-5309"
```

### Example Output

```
PII-Safe v0.1.0

Input:  Jane Doe works at ACME, email: jane@acme.com, phone: 555-867-5309

Detected 3 PII entities:
  PERSON           "Jane Doe"        [0:8]      confidence: 0.85
  EMAIL_ADDRESS    "jane@acme.com"   [31:44]    confidence: 1.00
  PHONE_NUMBER     "555-867-5309"    [53:65]    confidence: 0.75

Output: Michael Lee works at ACME, email: [REDACTED_EMAIL_ADDRESS], phone: [REDACTED_PHONE_NUMBER]

Privacy Risk Score: 0.53 (HIGH)
  3 entities detected, 3 sanitized, 0 leaked
```

---

## MCP Tool Server

PII-Safe exposes three MCP tools that AI agents can discover and call:

| Tool | Description |
|------|-------------|
| `pii_safe_scan` | Detect and sanitize PII in text |
| `pii_safe_detect` | Detect PII entities only (no sanitization) |
| `pii_safe_score` | Compute privacy risk score (0.0–1.0) |

```bash
# Run as MCP server (stdio transport)
python -m src.mcp_server

# Test with MCP Inspector
npx @modelcontextprotocol/inspector python -m src.mcp_server
```

An AI agent calling `pii_safe_scan` receives:
```json
{
  "sanitized_text": "Daniel Taylor email: [REDACTED_EMAIL_ADDRESS] ...",
  "entities_found": 4,
  "privacy_score": { "score": 0.6, "level": "HIGH" },
  "details": [
    { "entity_type": "PERSON", "original": "John Smith", "replacement": "Daniel Taylor", "action": "pseudonymize" },
    { "entity_type": "EMAIL_ADDRESS", "original": "john@example.com", "replacement": "[REDACTED_EMAIL_ADDRESS]", "action": "redact" }
  ]
}
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     PII-Safe: 3-Tier Cascading Guard                    │
│                                                                         │
│  Input ──▶ ┌─────────────────┐                                          │
│            │ TIER 1: SPEED   │  Compiled regex DFA (44μs, 272x Presidio)│
│            │ Pattern Guard   │  + Luhn, CPF, IP, email validators       │
│            └────────┬────────┘                                          │
│                     │                                                   │
│                     ▼                                                   │
│            ┌─────────────────┐                                          │
│            │ TIER 3: STATE   │  Probabilistic Entity Fingerprint (PEF)  │
│            │ Entity Resolver │  + Multi-index retrieval (phonetic+LSH)  │
│            │                 │  + 5-signal Bayesian scorer              │
│            │                 │  + MERGE / DEFERRED / NEW_ENTITY         │
│            └────────┬────────┘                                          │
│                     │                                                   │
│                     ▼                                                   │
│            ┌─────────────────┐  ┌──────────────────────────────────┐    │
│            │ Policy Engine   │─▶│ Sanitize: redact / pseudonymize  │    │
│            │ (YAML-config)   │  │ Score: 0.0–1.0 privacy risk     │    │
│            └─────────────────┘  │ Audit: structured log record     │    │
│                                 └──────────────────────────────────┘    │
│                                                                         │
│  Interfaces: Python API │ CLI │ MCP Server │ Interactive Demo           │
└─────────────────────────────────────────────────────────────────────────┘
```

## Sanitization Policies

Three built-in policies, plus YAML-defined custom policies:

| Policy | Behavior |
|--------|----------|
| `default` | Redact all PII, pseudonymize person names |
| `strict` | Redact everything, no exceptions |
| `permissive` | Only redact high-risk entities (emails, credit cards, SSN, phones, IPs) |

```yaml
# policies/custom.yaml
name: custom
description: "My custom policy"
default_action: redact
entities:
  PERSON:
    action: pseudonymize
  PHONE_NUMBER:
    action: allowlist
```

---

## Running Tests

```bash
.venv/bin/python -m pytest tests/ -v
```

```
tests/test_detector.py           8 passed   — Presidio-based detection (original)
tests/test_sanitizer.py          7 passed   — redaction, pseudonymization, allowlisting
tests/test_engine.py             9 passed   — full pipeline, policy switching, serialization
tests/test_tier1.py             30 passed   — pure regex detection, validators, performance
tests/test_entity_resolution.py 34 passed   — PEF fingerprints, indexes, Bayesian scorer,
                                              resolver, session graph, secure teardown

88 passed (5.0s)
```

---

## PoC → GSoC Project Mapping

| PoC Module | GSoC Deliverable |
|------------|-----------------|
| `detector.py` | Schema-aware PII detection (structured JSON + free text) |
| `sanitizer.py` + `policies.py` | Policy-driven sanitization with configurable rules |
| `mcp_server.py` | MCP tool interface for agent workflow integration |
| `engine.py` | Core orchestration engine with privacy scoring |
| `cli.py` | Batch sanitization CLI |

---

## Tech Stack

**Core (no external dependencies for Tier 1 + Tier 3):**
- Pure Python `re` module — compiled regex DFA for Tier 1
- Custom implementations — Double Metaphone, MinHash/LSH, Damerau-Levenshtein, Bayesian scorer

**Original pipeline (Tier 2 / sanitization):**
- **presidio-analyzer** + **presidio-anonymizer** — Batch-oriented detection (being replaced by 3-tier cascade)
- **spaCy** `en_core_web_sm` — NER model backend

**Infrastructure:**
- **MCP Python SDK** — Model Context Protocol server implementation
- **pydantic** — Policy schema validation
- **pytest** — 88 tests across all modules
