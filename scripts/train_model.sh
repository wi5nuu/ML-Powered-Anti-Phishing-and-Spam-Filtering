#!/bin/bash
set -euo pipefail

echo "==> Training LTI Anti-Phishing Classifier..."
python -m classifier.train "$@"

echo "==> Evaluating..."
python -m classifier.evaluate "$@"

echo "Training selesai. Model di classifier/models/"
