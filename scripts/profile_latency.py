"""Profile prediction pipeline to find bottlenecks."""
import time
import requests
from pathlib import Path

BASE = "http://localhost:8001"

# Warmup - first call often loads caches
raw = Path("data/dataset/chris/chris_0001_8ca553d955a0bf88.eml").read_text(encoding="utf-8", errors="replace")
print("Warmup...")
requests.post(f"{BASE}/predict", json={"raw_email": raw, "email_id": "warmup"}, timeout=30)

# Cold/Hot comparison
for label, path in [
    ("chris (ham)", "data/dataset/chris/chris_0001_8ca553d955a0bf88.eml"),
    ("brian (spam)", "data/dataset/brian/brian_0001_316e50a87d13354c.eml"),
]:
    for run in range(3):
        raw = Path(path).read_text(encoding="utf-8", errors="replace")
        t0 = time.perf_counter()
        r = requests.post(f"{BASE}/predict", json={"raw_email": raw, "email_id": f"{label[:4]}-{run}"}, timeout=30)
        lat = (time.perf_counter() - t0) * 1000
        sp = r.json()["spam_probability"]
        print(f"  {label:15s} run {run}: {lat:7.0f}ms  spam_prob={sp:.4f}")

# Test with /predict-dual vs /predict
raw = Path("data/dataset/chris/chris_0001_8ca553d955a0bf88.eml").read_text(encoding="utf-8", errors="replace")
for endpoint in ["/predict", "/predict-dual"]:
    t0 = time.perf_counter()
    r = requests.post(f"{BASE}{endpoint}", json={"raw_email": raw}, timeout=30)
    lat = (time.perf_counter() - t0) * 1000
    data = r.json()
    print(f"  {endpoint:20s}: {lat:7.0f}ms  label={data.get('label','?')} anomaly={data.get('anomaly_score','N/A')}")
