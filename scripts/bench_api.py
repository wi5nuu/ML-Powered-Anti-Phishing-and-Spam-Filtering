"""Quick benchmark for optimized API."""
import time, requests, json, sys
from pathlib import Path

API = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8002"

# Single email benchmark
raw = Path("data/dataset/chris/chris_0001_8ca553d955a0bf88.eml").read_text(encoding="utf-8", errors="replace")

for label, path in [
    ("chris (ham)", "data/dataset/chris/chris_0001_8ca553d955a0bf88.eml"),
    ("brian (spam)", "data/dataset/brian/brian_0001_316e50a87d13354c.eml"),
]:
    raw = Path(path).read_text(encoding="utf-8", errors="replace")
    times = []
    for _ in range(3):
        t0 = time.perf_counter()
        r = requests.post(f"{API}/predict", json={"raw_email": raw, "email_id": label[:4]}, timeout=30)
        t = (time.perf_counter() - t0) * 1000
        times.append(t)
    avg = sum(times) / len(times)
    data = r.json()
    print(f"{label:15s} avg={avg:6.0f}ms  prob={data['spam_probability']:.4f}  label={data['label']}")

# Sequential throughput
print()
raw = Path("data/dataset/chris/chris_0001_8ca553d955a0bf88.eml").read_text(encoding="utf-8", errors="replace")
t0 = time.perf_counter()
for i in range(20):
    requests.post(f"{API}/predict", json={"raw_email": raw, "email_id": f"s{i}"}, timeout=30)
elapsed = time.perf_counter() - t0
print(f"20 sequential: {elapsed*1000:.0f}ms total, {elapsed/20*1000:.0f}ms avg")
print(f"Throughput: {20/elapsed:.0f} emails/sec")

# /predict-dual benchmark
print()
t0 = time.perf_counter()
r = requests.post(f"{API}/predict-dual", json={"raw_email": raw, "email_id": "dual"}, timeout=30)
t = (time.perf_counter() - t0) * 1000
data = r.json()
print(f"predict-dual: {t:.0f}ms  prob={data['spam_probability']:.4f}  anomaly={data['anomaly_score']:.2f}  label={data['label']}")
