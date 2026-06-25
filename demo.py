"""
LTI ANTI-PHISHING SYSTEM - LIVE DEMO
=====================================
Jalankan dengan: python demo.py
Tunggu startup + warmup ~20 detik.
"""

import sys, os, time, subprocess, requests
from pathlib import Path

root = Path(__file__).resolve().parent
os.chdir(str(root))
os.environ["PYTHONPATH"] = str(root)
sys.path.insert(0, str(root))

from scripts import dataset_config as cfg

ACTIVE_DATASET = os.environ.get("ACTIVE_DATASET", "dataset_1")
DS_DIR = cfg.get_dataset_dir(ACTIVE_DATASET)
TEST_EMAILS = [
    ("Ham - Notifikasi Transfer",       str(DS_DIR / "chris/chris_0001_8ca553d955a0bf88.eml")),
    ("Ham - Internal Meeting",           str(DS_DIR / "ilham/ilham_0001_9fefa4942adca243.eml")),
    ("Spam - Promo Menang Hadiah",       str(DS_DIR / "brian/brian_0001_316e50a87d13354c.eml")),
    ("Phishing - Akun Diblokir",         str(DS_DIR / "wisnu/wisnu_0001_b0d875c197e282ac.eml")),
    ("Malware - Invoice .exe",           str(DS_DIR / "risly/risly_0001_004807eea4750c9d.eml")),
]

# Tampilkan dataset aktif
print(f"  Dataset aktif: {ACTIVE_DATASET}")


def main():
    print("=" * 60)
    print("  LTI ANTI-PHISHING SYSTEM - LIVE DEMO")
    print("  Dual-Layer ML (XGBoost + Anomaly) + SHAP XAI")
    print("=" * 60)

    # ── Start server via subprocess ──────────────────────────────
    print("\n  [....] Memuat model + warmup... (20-30 detik)\n")
    server = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "classifier.predict:app",
         "--host", "0.0.0.0", "--port", "8006", "--log-level", "warning"],
        cwd=str(root),
        env={**os.environ, "PYTHONPATH": str(root)},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    # Wait for server
    t0 = time.time()
    ready = False
    while time.time() - t0 < 60:
        try:
            r = requests.get("http://localhost:8006/health", timeout=3)
            if r.status_code == 200:
                h = r.json()
                print(f"  [OK] Server siap! supervised={h['supervised_loaded']} "
                      f"unsupervised={h['unsupervised_loaded']}")
                ready = True
                break
        except:
            time.sleep(2)
    if not ready:
        print("  [FAIL] Server gagal start dalam 60 detik!")
        server.kill()
        return

    # ── Test emails ─────────────────────────────────────────────
    header = f"  {'TEST':20s} | {'Latency':>8s} | {'Prob':>8s} | {'Label':>12s} | Status"
    print(f"\n  {header}")
    print(f"  {'-'*70}")

    correct = 0
    total = 0

    for desc, filepath in TEST_EMAILS:
        raw = Path(filepath).read_text(encoding="utf-8", errors="replace")
        expected = "HAM" if "chris" in filepath or "ilham" in filepath else "THREAT"

        t_start = time.perf_counter()
        try:
            r = requests.post(
                "http://localhost:8006/predict-dual",
                json={"raw_email": raw, "email_id": Path(filepath).stem},
                timeout=30,
            )
            lat = (time.perf_counter() - t_start) * 1000
            data = r.json()
            prob = data["spam_probability"]
            label = data["label"]
            anomaly = data["anomaly_score"]
            xai = data["xai_summary"][:80]

            is_ok = (expected == "HAM" and label == "CLEAN") or \
                     (expected == "THREAT" and label != "CLEAN")
            if is_ok:
                correct += 1
            total += 1
            status = "OK" if is_ok else "FAIL"

            print(f"  {desc[:20]:20s} | {lat:>7.0f}ms | {prob:>7.4f} | {label:>12s} | {status}")
            print(f"  {'':20s} | {'':>8s} | {'':>8s} | {'':>12s} | XAI: {xai}")
            print(f"  {'':20s} | {'':>8s} | {'':>8s} | {'':>12s} | Anomaly: {anomaly:.2f}")

        except Exception as e:
            print(f"  {desc[:20]:20s} | {'ERROR':>8s} | {str(e)[:50]}")
            total += 1

        print(f"  {'-'*70}")

    # ── Summary ─────────────────────────────────────────────────
    pct = correct / max(total, 1) * 100
    print(f"\n  HASIL: {correct}/{total} benar ({pct:.0f}%)")

    # ── Custom test ─────────────────────────────────────────────
    print("\n  Test email custom?")
    while True:
        path = input("  Path .eml (kosong=selesai): ").strip()
        if not path:
            break
        if not Path(path).exists():
            print(f"  [FAIL] File tidak ditemukan: {path}")
            continue
        try:
            raw = Path(path).read_text(encoding="utf-8", errors="replace")
            r = requests.post(
                "http://localhost:8006/predict-dual",
                json={"raw_email": raw, "email_id": Path(path).stem},
                timeout=30,
            )
            data = r.json()
            print(f"\n  LABEL : {data['label']}")
            print(f"  Prob  : {data['spam_probability']:.4f}")
            print(f"  XAI   : {data['xai_summary']}\n")
        except Exception as e:
            print(f"  [FAIL] {e}")

    # ── Cleanup ─────────────────────────────────────────────────
    print("\n  Server dimatikan.")
    server.kill()


if __name__ == "__main__":
    main()
