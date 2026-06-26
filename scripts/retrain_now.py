"""Retrain model using latest 105k feature extraction."""
import sys, logging
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
from classifier.train import train
train("data/processed/train_100k.csv", "_latest")
print("=== TRAINING COMPLETE ===")
