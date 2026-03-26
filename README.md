# pii-safe

**Privacy middleware for AI agent workflows — detects, sanitizes, and scores PII before it reaches an LLM.**

![Tests](https://img.shields.io/badge/tests-24%2F24_passing-10b981?style=flat-square)
![Python](https://img.shields.io/badge/Python-3.11+-3776ab?style=flat-square)
![MCP](https://img.shields.io/badge/MCP-tool_server-8b5cf6?style=flat-square)
![License](https://img.shields.io/badge/license-MIT-444?style=flat-square)

> **Status:** Proof of concept for [GSoC 2026 — C2SI PII-Safe](https://c2si.org/gsoc/)

As AI agents increasingly process security logs, chat transcripts, and incident reports, they are exposed to sensitive personal information. PII-Safe is a middleware that automatically detects and sanitizes PII using configurable policies — available as a Python library, CLI tool, and MCP server for direct integration into agent workflows.

---

## What This Proves

- **Real PII detection** using presidio + spaCy NER — not regex, not mocks
- **Policy-driven sanitization** — redact, pseudonymize, or allowlist per entity type
- **MCP tool interface** — AI agents discover and call PII-Safe via the Model Context Protocol
- **Three interfaces from one engine** — CLI, MCP server, and Python API
- **24 passing tests** across detection, sanitization, and engine modules

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
┌──────────────────────────────────────────────────┐
│                    pii-safe                       │
│                                                   │
│  ┌──────────────┐  ┌──────────────────────────┐  │
│  │  Detector     │  │  Sanitizer               │  │
│  │  (presidio +  │  │  (redact / pseudonymize  │  │
│  │   spaCy NER)  │  │   / allowlist)           │  │
│  └──────┬───────┘  └──────────┬───────────────┘  │
│         │                     │                   │
│  ┌──────▼─────────────────────▼───────────────┐  │
│  │           PII-Safe Engine                   │  │
│  │  detect() → sanitize() → score()           │  │
│  └──────────────┬─────────────────────────────┘  │
│                 │                                  │
│  ┌──────────────▼─────────────────────────────┐  │
│  │  Interfaces                                 │  │
│  │  ├── CLI      (scan, detect, policies)      │  │
│  │  ├── MCP      (3 tools, stdio transport)    │  │
│  │  └── Python   (from src.engine import ...)  │  │
│  └────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────┘
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
python -m pytest tests/ -v
```

```
tests/test_detector.py    8 passed   — email, name, IP, phone detection + edge cases
tests/test_sanitizer.py   7 passed   — redaction, pseudonymization, allowlisting
tests/test_engine.py      9 passed   — full pipeline, policy switching, serialization

24 passed (4.3s)
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

- **presidio-analyzer** + **presidio-anonymizer** — Microsoft's PII detection library (20+ entity types)
- **spaCy** `en_core_web_sm` — NER model backend
- **MCP Python SDK** — Model Context Protocol server implementation
- **pydantic** — Policy schema validation
- **pytest** — Test framework
