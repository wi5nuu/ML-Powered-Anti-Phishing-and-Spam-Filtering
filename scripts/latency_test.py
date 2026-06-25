"""Latency test for LTI classifier API."""
import time
import requests
from pathlib import Path

BASE = "http://localhost:8001"

cases = [
    ("chris (ham)", "data/dataset/chris/chris_0001_8ca553d955a0bf88.eml"),
    ("ilham (ham)", "data/dataset/ilham/ilham_0001_9fefa4942adca243.eml"),
    ("brian (spam)", "data/dataset/brian/brian_0001_316e50a87d13354c.eml"),
    ("wisnu (phish)", "data/dataset/wisnu/wisnu_0001_b0d875c197e282ac.eml"),
    ("risly (malw)", "data/dataset/risly/risly_0001_004807eea4750c9d.eml"),
]

hdr = f"{'Category':20s} {'Latency':>8s}  {'SpamProb':>8s}  {'Label':>12s}  {'XAI'}"
print(hdr)
print("-" * 75)

for cat, path in cases:
    raw = Path(path).read_text(encoding="utf-8", errors="replace")
    t0 = time.perf_counter()
    r = requests.post(f"{BASE}/predict", json={"raw_email": raw, "email_id": cat[:8]}, timeout=30)
    lat = (time.perf_counter() - t0) * 1000
    data = r.json()
    xai = data["xai_summary"][:60]
    print(f"{cat:20s} {lat:>7.0f}ms  {data['spam_probability']:>8.4f}  {data['label']:>12s}  {xai}")

# Sequential bulk
files = sorted(Path("data/dataset/chris").rglob("*.eml"))[:50]
t0 = time.perf_counter()
for f in files:
    raw = f.read_text(encoding="utf-8", errors="replace")
    requests.post(f"{BASE}/predict", json={"raw_email": raw}, timeout=30)
elapsed = time.perf_counter() - t0
avg = elapsed / 50 * 1000
print(f"\nSequential 50 emails: {elapsed*1000:.0f}ms total, {avg:.0f}ms avg")
print(f"Throughput: {1/(avg/1000):.0f} emails/sec (single-thread)")
print(f"Max (32 workers): {32/(avg/1000):.0f} emails/sec")
