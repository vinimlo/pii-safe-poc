#!/bin/bash
# Demo recording script for pii-safe-poc
# Records a ~45-60s asciinema demo showing the full PoC capabilities
#
# Record: asciinema rec demo.cast -c "bash record-demo.sh" --overwrite
# Upload: asciinema upload demo.cast

set -e
cd "$(dirname "$0")"

# Colors
G='\033[32m'   # green
C='\033[36m'   # cyan
B='\033[1m'    # bold
D='\033[2m'    # dim
R='\033[0m'    # reset
Y='\033[33m'   # yellow
M='\033[35m'   # magenta

# ── Scene 1: Title ──
clear
echo ""
echo -e "  ${C}${B}pii-safe${R} ${D}v0.1.0${R}"
echo -e "  ${D}Privacy middleware for AI agent workflows${R}"
echo -e "  ${D}GSoC 2026 — C2SI PII-Safe Proof of Concept${R}"
echo ""
sleep 3

# ── Scene 2: What it does ──
echo -e "  ${D}Detects PII using presidio + spaCy NER (20+ entity types),${R}"
echo -e "  ${D}applies policy-driven sanitization (redact / pseudonymize / allowlist),${R}"
echo -e "  ${D}and exposes everything as MCP tools for AI agents.${R}"
echo ""
sleep 3

# ── Scene 3: Default scan ──
echo -e "  ${Y}${B}Demo 1:${R} ${D}Scan text with default policy (redact all, pseudonymize names)${R}"
echo ""
sleep 1

.venv/bin/python -m src.cli scan "John Smith's email is john@example.com and his IP is 192.168.1.1" 2>/dev/null

sleep 4

# ── Scene 4: Strict policy ──
echo -e "  ${Y}${B}Demo 2:${R} ${D}Strict policy — redact everything including names${R}"
echo ""
sleep 1

.venv/bin/python -m src.cli scan --policy strict "Jane Doe, jane@acme.com, 555-867-5309" 2>/dev/null

sleep 4

# ── Scene 5: JSON output ──
echo -e "  ${Y}${B}Demo 3:${R} ${D}JSON output for programmatic use${R}"
echo ""
sleep 1

.venv/bin/python -m src.cli scan --format json "Contact Bob Wilson at bob@corp.io" 2>/dev/null

sleep 4

# ── Scene 6: Tests ──
echo ""
echo -e "  ${Y}${B}Demo 4:${R} ${D}Running test suite${R}"
echo ""
sleep 1

.venv/bin/python -m pytest tests/ -v --tb=no -q 2>/dev/null

sleep 3

# ── Scene 7: MCP Server ──
echo ""
echo -e "  ${Y}${B}Demo 5:${R} ${D}MCP Server — tool discovery via JSON-RPC${R}"
echo ""
sleep 1

printf '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"demo","version":"0.1"}}}\n{"jsonrpc":"2.0","method":"notifications/initialized"}\n{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}\n' | .venv/bin/python -m src.mcp_server 2>/dev/null | tail -1 | python3 -c "
import sys, json
data = json.loads(sys.stdin.read())
tools = data['result']['tools']
print(f'  MCP Server: pii-safe | Protocol: {data[\"result\"].get(\"protocolVersion\", \"N/A\")}')
print(f'  Tools discovered: {len(tools)}')
print()
for t in tools:
    print(f'    \033[35m{t[\"name\"]:<20}\033[0m {t[\"description\"][:65]}')
print()
"

sleep 4

# ── Scene 8: Closing ──
echo -e "  ${G}${B}24/24 tests passing${R} ${D}|${R} ${C}3 MCP tools${R} ${D}|${R} ${M}3 policies${R} ${D}|${R} ${G}20+ entity types${R}"
echo -e "  ${D}github.com/vinimlo/pii-safe-poc${R}"
echo ""
sleep 4
