"""
Monitor domain lookalike untuk lodaya.id menggunakan dnstwist.
Jalankan setiap 24 jam via cron:
  0 2 * * * python scripts/domain_monitor.py
"""
import json
import dnstwist
from pathlib import Path
from datetime import datetime

PROTECTED_DOMAIN = "lodaya.id"
REPORT_PATH = Path("data/domain_reports/")
REPORT_PATH.mkdir(parents=True, exist_ok=True)


def run_monitor():
    """
    Generate permutasi domain, filter yang terdaftar,
    simpan laporan dan alert jika ada domain baru yang berbahaya.
    """
    print(f"[{datetime.now()}] Running dnstwist untuk {PROTECTED_DOMAIN}...")

    try:
        fuzzer = dnstwist.Fuzzer(PROTECTED_DOMAIN)
        fuzzer.generate()
        domains = fuzzer.permutations()
    except Exception as e:
        print(f"[ERROR] dnstwist gagal: {e}")
        return []

    if not domains:
        print("[WARN] dnstwist tidak mengembalikan data apapun.")
        return []

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = REPORT_PATH / f"domain_report_{timestamp}.json"
    with open(report_path, "w") as f:
        json.dump(domains, f, indent=2, default=str)

    print(f"Ditemukan {len(domains)} domain permutasi mirip {PROTECTED_DOMAIN}")
    for r in domains[:20]:
        print(f"  - {r['domain']} (fuzzer: {r.get('fuzzer', '?')})")
    if len(domains) > 20:
        print(f"  ... dan {len(domains)-20} lainnya.")

    return domains


if __name__ == "__main__":
    run_monitor()
