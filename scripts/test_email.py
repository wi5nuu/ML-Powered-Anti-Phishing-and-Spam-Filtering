"""
LTI Anti-Phishing System - Interactive Tester
=============================================
Cara pakai:
  1. Start API:   python scripts/run_api.py
  2. Test email:  python scripts/test_email.py
"""

import sys, time, json, requests
from pathlib import Path

API = "http://localhost:8006"

def test_email(filepath: str):
    """Send one .eml file and print result."""
    raw = Path(filepath).read_text(encoding="utf-8", errors="replace")
    t0 = time.perf_counter()
    r = requests.post(f"{API}/predict-dual", json={"raw_email": raw, "email_id": Path(filepath).stem}, timeout=30)
    lat = (time.perf_counter() - t0) * 1000
    data = r.json()
    return data, lat

def print_result(data, lat, filepath):
    """Pretty print prediction result."""
    print(f"\n{'='*60}")
    print(f"  FILE : {Path(filepath).relative_to('data/dataset')}")
    print(f"  TIME : {lat:.0f}ms")
    print(f"{'='*60}")
    print(f"  LABEL          : {data['label']}")
    print(f"  SpamProb       : {data['spam_probability']:.4f}")
    print(f"  AnomalyScore   : {data['anomaly_score']:.2f}")
    print(f"  Is Anomaly     : {data['is_anomaly']}")
    print(f"\n  XAI Summary:")
    print(f"  {data['xai_summary']}")
    print(f"\n  Top Reasons:")
    for r in data['top_reasons'][:5]:
        emoji = "SPAM" if r['direction'] == "spam" else "OK"
        print(f"    [{emoji}] {r['feature']} (SHAP: {r['shap_value']:.4f})")
    print(f"{'='*60}\n")

def show_menu():
    """Show interactive menu."""
    samples = [
        ("1", "Ham - Transaksi Bank", "data/dataset/chris/chris_0001_8ca553d955a0bf88.eml"),
        ("2", "Ham - Internal Meeting", "data/dataset/ilham/ilham_0001_9fefa4942adca243.eml"),
        ("3", "Spam - Promo Menang", "data/dataset/brian/brian_0001_316e50a87d13354c.eml"),
        ("4", "Phishing - Akun Diblokir", "data/dataset/wisnu/wisnu_0001_b0d875c197e282ac.eml"),
        ("5", "Malware - Invoice.exe", "data/dataset/risly/risly_0001_004807eea4750c9d.eml"),
        ("6", "Phishing - Lookalike Domain", "data/dataset/wisnu/wisnu_0040_0b9dacdfeced5f45.eml"),
        ("7", "Malware - DocM Macro", "data/dataset/risly/risly_0010_f9d983bd298fb40f.eml"),
        ("8", "Custom - Enter your own path", ""),
        ("0", "Exit", ""),
    ]

    while True:
        print("\n  PILIH EMAIL UNTUK DIUJI:")
        print(f"  {'-'*50}")
        for key, desc, _ in samples:
            print(f"    [{key}] {desc}")
        print(f"  {'-'*50}")

        choice = input("  Pilihan: ").strip()

        if choice == "0":
            print("  Bye!")
            break

        filepath = None
        for key, desc, fp in samples:
            if choice == key:
                filepath = fp
                break

        if choice == "8":
            filepath = input("  Path ke file .eml: ").strip()

        if not filepath or not Path(filepath).exists():
            print("  [ERROR] File tidak ditemukan!")
            continue

        try:
            data, lat = test_email(filepath)
            print_result(data, lat, filepath)

            # Summary line
            expected = "HAM" if "chris" in filepath or "ilham" in filepath else "THREAT"
            actual = data['label']
            status = "OK" if (expected == "HAM" and actual == "CLEAN") or (expected == "THREAT" and actual != "CLEAN") else "MISMATCH"
            print(f"  >>> Expected: {expected:8s} | Actual: {actual:12s} | Status: {status}")
        except Exception as e:
            print(f"  [ERROR] {e}")


if __name__ == "__main__":
    # Check API health
    try:
        h = requests.get(f"{API}/health", timeout=5).json()
        print(f"[OK] API server: {API} (supervised={h['supervised_loaded']}, unsupervised={h['unsupervised_loaded']})")
    except Exception:
        print(f"[ERROR] API server not running at {API}!")
        print(f"  Jalankan dulu: python scripts/run_api.py")
        sys.exit(1)

    show_menu()
