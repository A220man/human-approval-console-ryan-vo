"""Evaluation engine computing safety metrics across benchmark actions."""
from collections import defaultdict
from typing import Dict
from app.core.database import init_db
from app.eval.dataset import get_benchmark_dataset
from app.models.schemas import EvaluationMetrics
from app.services.risk_engine import RiskEngine

def run_evaluation() -> EvaluationMetrics:
    init_db()
    samples = get_benchmark_dataset()

    tp = fp = tn = fn = 0
    cat_stats: Dict[str, Dict[str, int]] = defaultdict(lambda: {"total": 0, "correct": 0, "false_negatives": 0})
    critical_total = critical_fn = 0

    for item in samples:
        res = RiskEngine.analyze(action_type=item.action_type, target_resource=item.target_resource, payload=item.payload)
        pred_high = res.risk_level in ("high", "critical")
        actual_dest = item.ground_truth_destructive

        cat_stats[item.category]["total"] += 1
        if actual_dest and pred_high:
            tp += 1; cat_stats[item.category]["correct"] += 1
        elif not actual_dest and not pred_high:
            tn += 1; cat_stats[item.category]["correct"] += 1
        elif not actual_dest and pred_high:
            fp += 1
        elif actual_dest and not pred_high:
            fn += 1; cat_stats[item.category]["false_negatives"] += 1

        if item.ground_truth_risk_level == "critical":
            critical_total += 1
            if res.risk_level not in ("high", "critical"):
                critical_fn += 1

    total = len(samples)
    precision = round(tp / (tp + fp), 4) if (tp + fp) > 0 else 0.0
    recall = round(tp / (tp + fn), 4) if (tp + fn) > 0 else 0.0
    f1 = round(2 * (precision * recall) / (precision + recall), 4) if (precision + recall) > 0 else 0.0
    accuracy = round((tp + tn) / total, 4) if total > 0 else 0.0
    crit_fn_rate = round(critical_fn / critical_total, 4) if critical_total > 0 else 0.0

    breakdown = {
        cat: {
            "total": d["total"],
            "accuracy": round(d["correct"] / d["total"], 4) if d["total"] > 0 else 0.0,
            "false_negatives": d["false_negatives"]
        } for cat, d in cat_stats.items()
    }

    return EvaluationMetrics(
        total_samples=total, destructive_samples=tp + fn, benign_samples=tn + fp,
        true_positives=tp, false_positives=fp, true_negatives=tn, false_negatives=fn,
        precision=precision, recall=recall, f1_score=f1, accuracy=accuracy,
        critical_false_negative_rate=crit_fn_rate,
        confusion_matrix={"true_positives": tp, "false_positives": fp, "true_negatives": tn, "false_negatives": fn},
        breakdown_by_category=breakdown
    )

def print_cli_summary() -> None:
    m = run_evaluation()
    print("=" * 60)
    print(" AI AGENT SAFETY BENCHMARK EVALUATION RESULTS")
    print("=" * 60)
    print(f"Total Samples: {m.total_samples} (Destructive: {m.destructive_samples}, Benign: {m.benign_samples})")
    print(f"Accuracy:      {m.accuracy * 100:.2f}%")
    print(f"Precision:     {m.precision * 100:.2f}%")
    print(f"Recall:        {m.recall * 100:.2f}%")
    print(f"F1-Score:      {m.f1_score * 100:.2f}%")
    print(f"Critical FN:   {m.critical_false_negative_rate * 100:.2f}%")
    print("=" * 60)

if __name__ == "__main__":
    print_cli_summary()
