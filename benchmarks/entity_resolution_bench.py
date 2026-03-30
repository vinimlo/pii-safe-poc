"""Entity Resolution Benchmark: precision/recall/F1 on synthetic dataset.

Evaluates the PEF entity resolution engine across typos, reordering,
phonetic variants, and false-positive pairs at multiple thresholds.
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.entity_resolution.fingerprint import EntityFingerprint
from src.entity_resolution.scorer import BayesianScorer, Decision


def load_dataset() -> list[dict]:
    path = Path(__file__).parent / "datasets" / "synthetic_entities.json"
    data = json.loads(path.read_text())
    return data["pairs"]


def evaluate(pairs: list[dict], merge_threshold: float, defer_threshold: float) -> dict:
    """Evaluate entity resolution at given thresholds.

    MERGE decisions on MERGE-expected pairs = True Positive
    NEW_ENTITY decisions on NEW_ENTITY-expected pairs = True Negative
    MERGE on NEW_ENTITY-expected = False Positive
    NEW_ENTITY on MERGE-expected = False Negative
    DEFERRED counts as MERGE for evaluation (it still links the entity)
    """
    scorer = BayesianScorer()
    tp = fp = tn = fn = 0
    category_results = defaultdict(lambda: {"tp": 0, "fp": 0, "tn": 0, "fn": 0})

    for pair in pairs:
        fp1 = EntityFingerprint.create(1, "PERSON", pair["canonical"])
        fp2 = EntityFingerprint.create(2, "PERSON", pair["variant"])
        result = scorer.decide(fp1, fp2, merge_threshold, defer_threshold)

        is_match_decision = result.decision in (Decision.MERGE, Decision.DEFERRED)
        expected_match = pair["expected"] == "MERGE"
        cat = pair["category"]

        if expected_match and is_match_decision:
            tp += 1
            category_results[cat]["tp"] += 1
        elif expected_match and not is_match_decision:
            fn += 1
            category_results[cat]["fn"] += 1
        elif not expected_match and is_match_decision:
            fp += 1
            category_results[cat]["fp"] += 1
        else:
            tn += 1
            category_results[cat]["tn"] += 1

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    return {
        "threshold": merge_threshold,
        "tp": tp, "fp": fp, "tn": tn, "fn": fn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "categories": dict(category_results),
    }


def main():
    pairs = load_dataset()
    total_merge = sum(1 for p in pairs if p["expected"] == "MERGE")
    total_new = sum(1 for p in pairs if p["expected"] == "NEW_ENTITY")

    print(f"\n{'=' * 72}")
    print(f"  PII-Safe Entity Resolution Benchmark")
    print(f"  Dataset: {len(pairs)} pairs ({total_merge} MERGE, {total_new} NEW_ENTITY)")
    print(f"{'=' * 72}\n")

    thresholds = [0.40, 0.50, 0.60, 0.65, 0.70, 0.80, 0.85, 0.90]
    print(f"  {'Threshold':>10s}  {'Precision':>10s}  {'Recall':>10s}  {'F1':>10s}  {'TP':>4s}  {'FP':>4s}  {'TN':>4s}  {'FN':>4s}")
    print(f"  {'-' * 10}  {'-' * 10}  {'-' * 10}  {'-' * 10}  {'-' * 4}  {'-' * 4}  {'-' * 4}  {'-' * 4}")

    best_f1 = 0
    best_result = None

    for t in thresholds:
        defer_t = max(t - 0.35, 0.30)
        result = evaluate(pairs, t, defer_t)
        f1_str = f"{result['f1']:.3f}"
        marker = ""
        if result["f1"] > best_f1:
            best_f1 = result["f1"]
            best_result = result
            marker = " ◀ best"
        print(f"  {t:>10.2f}  {result['precision']:>10.3f}  {result['recall']:>10.3f}  "
              f"{result['f1']:>10.3f}  {result['tp']:>4d}  {result['fp']:>4d}  "
              f"{result['tn']:>4d}  {result['fn']:>4d}{marker}")

    if best_result:
        print(f"\n  Best F1 = {best_f1:.3f} at threshold {best_result['threshold']:.2f}")
        print(f"\n  Per-category breakdown (at best threshold):")
        for cat, counts in sorted(best_result["categories"].items()):
            total = counts["tp"] + counts["fp"] + counts["tn"] + counts["fn"]
            correct = counts["tp"] + counts["tn"]
            print(f"    {cat:20s}  {correct}/{total} correct")

    print()


if __name__ == "__main__":
    main()
