#!/bin/bash
# PII-Safe PoC Demo — for asciinema recording
# Record with: asciinema rec demo.cast -c "bash demo.sh"
#
# Tips:
# - Use `sleep` to give viewers time to read
# - Keep it under 45s total

set -e
cd "$(dirname "$0")"

TYPE_SPEED=0.03

type_cmd() {
  echo ""
  echo -n "$ "
  echo "$1" | while IFS= read -r -n1 char; do
    echo -n "$char"
    sleep $TYPE_SPEED
  done
  echo ""
  sleep 0.3
}

echo ""
echo "  ┌──────────────────────────────────────────────┐"
echo "  │  PII-Safe PoC Demo                           │"
echo "  │  Privacy middleware for AI agent workflows    │"
echo "  │  github.com/vinimlo/pii-safe-poc             │"
echo "  └──────────────────────────────────────────────┘"
echo ""
sleep 2

# 1. Basic scan
type_cmd '.venv/bin/python -m src.cli scan "John Smith'\''s email is john@example.com and his IP is 192.168.1.1"'
.venv/bin/python -m src.cli scan "John Smith's email is john@example.com and his IP is 192.168.1.1" 2>/dev/null
sleep 3

# 2. Strict policy
type_cmd '.venv/bin/python -m src.cli scan --policy strict "Jane Doe, jane@acme.com, 555-867-5309"'
.venv/bin/python -m src.cli scan --policy strict "Jane Doe, jane@acme.com, 555-867-5309" 2>/dev/null
sleep 3

# 3. JSON output
type_cmd '.venv/bin/python -m src.cli scan --format json "Contact Bob Wilson at bob@corp.io"'
.venv/bin/python -m src.cli scan --format json "Contact Bob Wilson at bob@corp.io" 2>/dev/null
sleep 3

# 4. Run tests
type_cmd '.venv/bin/python -m pytest tests/ -v --tb=no -q'
.venv/bin/python -m pytest tests/ -v --tb=no -q 2>/dev/null
sleep 3

# 5. MCP server tools/list
echo ""
type_cmd '# MCP Server — tools/list discovery'
sleep 0.5
printf '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"demo","version":"0.1"}}}\n{"jsonrpc":"2.0","method":"notifications/initialized"}\n{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}\n' | .venv/bin/python -m src.mcp_server 2>/dev/null | tail -1 | python3 -c "
import sys, json
data = json.loads(sys.stdin.read())
tools = data['result']['tools']
print()
print('  MCP Server: pii-safe')
print(f'  Tools discovered: {len(tools)}')
print()
for t in tools:
    print(f'    \033[35m{t[\"name\"]:<20}\033[0m {t[\"description\"][:60]}')
print()
"
sleep 3

echo ""
echo "  ✓ Detection: presidio + spaCy NER (20+ entity types)"
echo "  ✓ Sanitization: policy-driven (redact / pseudonymize / allowlist)"
echo "  ✓ MCP Server: 3 tools via stdio transport"
echo "  ✓ Tests: 24/24 passing"
echo ""
sleep 2
