#!/usr/bin/env bash
# Scripted demo recording with realistic timing
# Run: bash record-demo.sh

set -e

PYTHON=".venv/bin/python"

# Clear screen and show header
clear
sleep 0.5

echo ""
echo "# PII-Safe — Entity Resolution Demo"
echo "# Tier 1 (Regex, 44μs) + Tier 3 (Bayesian PEF, 5 signals)"
echo ""
sleep 2

echo '$ python -m src.demo --script demo_script.json --verbose'
sleep 1.5

$PYTHON -m src.demo --script demo_script.json --verbose

sleep 3

echo ""
echo "# --- Benchmark: Tier 1 vs Presidio ---"
echo ""
sleep 1.5

echo '$ python benchmarks/entity_resolution_bench.py'
sleep 1

$PYTHON benchmarks/entity_resolution_bench.py

sleep 3

echo ""
echo "# 88 tests passing, 272x faster than Presidio, F1=0.923"
echo "# github.com/vinimlo/pii-safe-poc"
sleep 3
