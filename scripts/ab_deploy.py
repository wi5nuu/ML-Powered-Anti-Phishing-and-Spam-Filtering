"""
A/B Model Deployment — Deploy and compare two model versions in production.
Routes traffic between model A (current) and model B (candidate).

Usage:
  python scripts/ab_deploy.py --model-a xgb_model_v1.joblib --model-b xgb_model_v2.joblib --traffic-a 50
"""

import argparse
import json
import os
import random
import shutil
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score

MODEL_DIR = Path("classifier/models")


class ABRouter:
    def __init__(self, model_a_name: str, model_b_name: str, traffic_a_pct: int = 50):
        self.model_a = joblib.load(MODEL_DIR / model_a_name)
        self.model_b = joblib.load(MODEL_DIR / model_b_name)
        self.traffic_a_pct = traffic_a_pct
        self.stats = {"a": {"requests": 0, "spam_preds": 0},
                      "b": {"requests": 0, "spam_preds": 0}}

    def predict(self, features: np.ndarray) -> tuple:
        choice = "A" if random.randint(1, 100) <= self.traffic_a_pct else "B"
        model = self.model_a if choice == "A" else self.model_b
        prob = float(model.predict_proba(features)[0, 1])
        self.stats[choice.lower()]["requests"] += 1
        if prob > 0.5:
            self.stats[choice.lower()]["spam_preds"] += 1
        return prob, choice

    def get_stats(self) -> dict:
        a = self.stats["a"]
        b = self.stats["b"]
        return {
            "model_a": {"requests": a["requests"], "spam_rate": round(a["spam_preds"] / max(a["requests"], 1), 4)},
            "model_b": {"requests": b["requests"], "spam_rate": round(b["spam_preds"] / max(b["requests"], 1), 4)},
        }


def promote_model(source: str, target: str = "xgb_model_latest.joblib"):
    """Promote a candidate model to production (copy as latest)."""
    src = MODEL_DIR / source
    dst = MODEL_DIR / target
    shutil.copy2(src, dst)
    print(f"Promoted {source} -> {target}")


def evaluate_models(test_csv: str, model_names: list):
    """Compare multiple models on held-out test set."""
    df = pd.read_csv(test_csv)
    y_true = df["label"].values

    results = []
    for model_name in model_names:
        model = joblib.load(MODEL_DIR / model_name)
        from classifier.train import build_feature_matrix
        import joblib as jl
        tfidf = jl.load(MODEL_DIR / "tfidf_latest.joblib")
        scaler = jl.load(MODEL_DIR / "scaler_latest.joblib")
        X = build_feature_matrix(df, tfidf, scaler, fit=False)
        y_prob = model.predict_proba(X)[:, 1]
        y_pred = (y_prob > 0.5).astype(int)

        results.append({
            "model": model_name,
            "accuracy": round(accuracy_score(y_true, y_pred), 4),
            "precision": round(precision_score(y_true, y_pred), 4),
            "recall": round(recall_score(y_true, y_pred), 4),
            "f1": round(f1_score(y_true, y_pred), 4),
            "roc_auc": round(roc_auc_score(y_true, y_prob), 4),
        })

    print("\nA/B Model Comparison:")
    print("-" * 80)
    print(f"{'Model':<30} {'Accuracy':>10} {'Precision':>10} {'Recall':>10} {'F1':>10} {'ROC-AUC':>10}")
    print("-" * 80)
    for r in results:
        print(f"{r['model']:<30} {r['accuracy']:>10.4f} {r['precision']:>10.4f} {r['recall']:>10.4f} {r['f1']:>10.4f} {r['roc_auc']:>10.4f}")
    print("-" * 80)

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command")

    p_route = sub.add_parser("route", help="Test A/B routing")
    p_route.add_argument("--model-a", default="xgb_model_latest.joblib")
    p_route.add_argument("--model-b", default="xgb_model_20260622_201332.joblib")
    p_route.add_argument("--traffic-a", type=int, default=50)

    p_eval = sub.add_parser("evaluate", help="Compare models on test set")
    p_eval.add_argument("--test-csv", default="data/processed/test.csv")
    p_eval.add_argument("--models", nargs="+", default=["xgb_model_latest.joblib", "xgb_model_20260622_201332.joblib"])

    p_promote = sub.add_parser("promote", help="Promote model to latest")
    p_promote.add_argument("--source", required=True)

    args = parser.parse_args()

    if args.command == "route":
        router = ABRouter(args.model_a, args.model_b, args.traffic_a)
        print(f"A/B router ready. Model A: {args.model_a}, Model B: {args.model_b}, Traffic A: {args.traffic_a}%")
    elif args.command == "evaluate":
        evaluate_models(args.test_csv, args.models)
    elif args.command == "promote":
        promote_model(args.source)
    else:
        parser.print_help()
