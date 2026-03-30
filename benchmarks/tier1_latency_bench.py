"""Tier 1 Latency Benchmark: regex vs Presidio detection speed.

Compares our pure-regex Tier 1 engine against Presidio's AnalyzerEngine
on the same input text across 10,000 iterations.
"""

import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.tier1 import scan


SAMPLE_TEXT = (
    "Contact john@example.com at 555-123-4567. "
    "Server 192.168.1.100 in datacenter. "
    "CC: 4532015112830366. SSN: 123-45-6789. "
    "CPF: 529.982.247-25. Key: sk-abcdefghijklmnopqrstuvwxyz. "
    "Additional context text to pad the string to approximately "
    "five hundred characters for a realistic benchmark scenario "
    "that simulates typical agent tool-call payload sizes with "
    "mixed PII and non-PII content in a single text block."
)

ITERATIONS = 10_000


def bench_tier1():
    """Benchmark our regex Tier 1."""
    # Warmup
    for _ in range(100):
        scan(SAMPLE_TEXT)

    latencies = []
    for _ in range(ITERATIONS):
        start = time.perf_counter_ns()
        scan(SAMPLE_TEXT)
        elapsed = time.perf_counter_ns() - start
        latencies.append(elapsed / 1_000)  # convert to microseconds

    return latencies


def bench_presidio():
    """Benchmark Presidio AnalyzerEngine (if available)."""
    try:
        from presidio_analyzer import AnalyzerEngine
        analyzer = AnalyzerEngine()

        # Warmup
        for _ in range(10):
            analyzer.analyze(text=SAMPLE_TEXT, language="en")

        latencies = []
        iterations = min(ITERATIONS, 1000)  # Presidio is slow, use fewer iterations
        for _ in range(iterations):
            start = time.perf_counter_ns()
            analyzer.analyze(text=SAMPLE_TEXT, language="en")
            elapsed = time.perf_counter_ns() - start
            latencies.append(elapsed / 1_000)

        return latencies
    except ImportError:
        return None


def print_stats(name: str, latencies: list[float]):
    latencies.sort()
    p50 = latencies[len(latencies) // 2]
    p95 = latencies[int(len(latencies) * 0.95)]
    p99 = latencies[int(len(latencies) * 0.99)]
    mean = statistics.mean(latencies)
    throughput = 1_000_000 / mean  # scans per second

    print(f"  {name:20s}  p50={p50:>10.1f}μs  p95={p95:>10.1f}μs  "
          f"p99={p99:>10.1f}μs  mean={mean:>10.1f}μs  "
          f"throughput={throughput:>10,.0f} scans/s")


def main():
    print(f"\n{'=' * 80}")
    print(f"  Tier 1 Latency Benchmark")
    print(f"  Input: {len(SAMPLE_TEXT)} chars, {ITERATIONS:,} iterations")
    print(f"{'=' * 80}\n")

    # Verify detection works
    results = scan(SAMPLE_TEXT)
    types = [r.entity_type for r in results]
    print(f"  Detected entities: {', '.join(types)}\n")

    # Tier 1 benchmark
    tier1_latencies = bench_tier1()
    print_stats("Tier 1 (regex)", tier1_latencies)

    # Presidio benchmark (optional)
    presidio_latencies = bench_presidio()
    if presidio_latencies:
        print_stats("Presidio", presidio_latencies)
        speedup = statistics.mean(presidio_latencies) / statistics.mean(tier1_latencies)
        print(f"\n  Speedup: {speedup:.0f}x faster with Tier 1 regex")
    else:
        print(f"\n  (Presidio not installed — install for comparison benchmark)")

    print()


if __name__ == "__main__":
    main()
