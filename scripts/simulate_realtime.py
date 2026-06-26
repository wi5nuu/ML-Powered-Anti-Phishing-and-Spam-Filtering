"""
Simulasi Real-time Email Flow untuk LTI Anti-Phishing.

Meniru skenario perusahaan FinTech (lodaya.id):
- 30.000+ email aman (transaksi, cs, internal) → langsung ke inbox
- 1.000+ email ancaman (spam, phishing, malware) → karantina/diblokir

Alur:
  1. Pipeline mode: push representative sample ke Redis → worker proses → WebSocket real-time
  2. API mode: proses batch besar cepat untuk populate statistik
  3. Tampilkan ringkasan hasil

Usage:
  python scripts/simulate_realtime.py          # jalankan simulasi lengkap
  python scripts/simulate_realtime.py --quick   # hanya sample kecil (60 email)
"""

import argparse
import asyncio
import json
import logging
import random
import sys
import time
from pathlib import Path
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger("simulator")

# ─── Konfigurasi ────────────────────────────────────────────────────────────────
DATASET_DIR = Path(__file__).parent.parent / "data" / "dataset_merged" / "_extended"
CLASSIFIER_URL = "http://localhost:8006"
REDIS_URL = "redis://localhost:6379/0"
QUEUE_NAME = "email_pipeline"

# Target: masing-masing kategori ambil N email untuk pipeline, sisanya via API
PIPELINE_SAMPLE = {
    "transaksi":    15,   # ham  → CLEAN
    "cs":           10,   # ham  → CLEAN
    "internal":     10,   # ham  → CLEAN
    "casual_ham":    5,   # ham  → CLEAN
    "spam":          8,   # spam → QUARANTINE
    "phishing":      8,   # phishing → QUARANTINE
    "malware":       6,   # malware → QUARANTINE
    "bec":           6,   # phishing → QUARANTINE
}

API_BATCH = {
    "transaksi":    500,
    "cs":           300,
    "internal":     300,
    "casual_ham":   100,
    "spam":         200,
    "phishing":     200,
    "malware":      150,
    "bec":          150,
}


def get_eml_files(subdir: Path, count: int) -> list[Path]:
    """Ambil N file .eml dari subdirektori (acak)."""
    files = sorted(subdir.rglob("*.eml"))
    if not files:
        return []
    return random.sample(files, min(count, len(files)))


async def push_to_redis(raw: str, email_id: str) -> dict:
    """Push satu email ke Redis queue."""
    import redis.asyncio as aio_redis
    try:
        r = await aio_redis.from_url(REDIS_URL)
        payload = json.dumps({
            "email_id": email_id,
            "raw_email": raw,
            "received_at": datetime.now(timezone.utc).isoformat(),
        })
        await r.rpush(QUEUE_NAME, payload)
        await r.aclose()
        return {"status": "queued"}
    except Exception as e:
        return {"error": str(e)}


async def classify_via_api(raw: str, email_id: str, session) -> dict:
    """Kirim satu email ke classifier API."""
    import aiohttp
    try:
        async with session.post(
            f"{CLASSIFIER_URL}/predict-dual",
            json={"raw_email": raw, "email_id": email_id},
            timeout=aiohttp.ClientTimeout(total=30),
        ) as resp:
            if resp.status == 200:
                return await resp.json()
            return {"error": f"HTTP {resp.status}"}
    except asyncio.TimeoutError:
        return {"error": "timeout"}
    except Exception as e:
        return {"error": str(e)}


async def simulate_pipeline(label: str, files: list[Path]):
    """Push sample emails ke Redis pipeline (real-time WebSocket)."""
    total = len(files)
    logger.info(f"  ⏳ Pipeline ({label}): mengirim {total} email ke Redis...")
    success = 0
    for i, f in enumerate(files):
        raw = f.read_text(encoding="utf-8", errors="replace")
        email_id = f.stem[:16]
        result = await push_to_redis(raw, email_id)
        if "error" not in result:
            success += 1
        if (i + 1) % 5 == 0:
            logger.info(f"    Progress {label}: {i+1}/{total}")
        await asyncio.sleep(0.1)  # sedikit jeda biar real-time terasa
    logger.info(f"  ✅ Pipeline ({label}): {success}/{total} terkirim ke Redis")
    return success


async def simulate_api(label: str, files: list[Path]):
    """Kirim batch besar email ke classifier API untuk statistik."""
    total = len(files)
    logger.info(f"  ⏳ API ({label}): memproses {total} email...")
    stats = {"CLEAN": 0, "WARN": 0, "QUARANTINE": 0, "error": 0}
    start = time.time()

    import aiohttp
    connector = aiohttp.TCPConnector(limit=20)
    sem = asyncio.Semaphore(20)

    async with aiohttp.ClientSession(connector=connector) as session:
        async def process_one(f: Path):
            async with sem:
                raw = f.read_text(encoding="utf-8", errors="replace")
                email_id = f.stem[:16]
                result = await classify_via_api(raw, email_id, session)
                if "error" in result:
                    stats["error"] += 1
                    return
                label_resp = result.get("label", "").upper()
                if label_resp == "CLEAN":
                    stats["CLEAN"] += 1
                elif label_resp == "WARN":
                    stats["WARN"] += 1
                else:
                    stats["QUARANTINE"] += 1

        # Batch 50 emails
        batch_size = 50
        for i in range(0, total, batch_size):
            batch = files[i:i + batch_size]
            await asyncio.gather(*[process_one(f) for f in batch])
            done = min(i + batch_size, total)
            elapsed = time.time() - start
            rate = done / elapsed if elapsed > 0 else 0
            pct = done / total * 100
            total_done = sum(stats.values())
            logger.info(f"    API {label}: {done}/{total} ({pct:.0f}%) — {rate:.0f} eml/s — hasil: {stats}")

    elapsed = time.time() - start
    logger.info(f"  ✅ API ({label}): {total} email dalam {elapsed:.1f}s ({total/elapsed:.0f} eml/s)")
    return stats


async def main():
    parser = argparse.ArgumentParser(description="Simulasi Real-time Email LTI Anti-Phishing")
    parser.add_argument("--quick", action="store_true", help="Mode cepat: hanya pipeline sample, tanpa API batch")
    args = parser.parse_args()

    logger.info("=" * 65)
    logger.info("  SIMULASI REAL-TIME EMAIL — LTI Anti-Phishing")
    logger.info("  Skenario: FinTech lodaya.id — 30k aman + 1k ancaman")
    logger.info("=" * 65)
    logger.info(f"  Dataset: {DATASET_DIR}")
    logger.info(f"  Classifier: {CLASSIFIER_URL}")
    logger.info(f"  Redis queue: {QUEUE_NAME}")
    logger.info("=" * 65)

    if not DATASET_DIR.exists():
        logger.error(f"Dataset tidak ditemukan: {DATASET_DIR}")
        sys.exit(1)

    # ─── Fase 1: Pipeline (Real-time WebSocket) ────────────────────────────
    logger.info("\n" + "=" * 65)
    logger.info("  FASE 1: PIPELINE REDIS → WORKER → WEBSOCKET (Real-time)")
    logger.info("  Email akan muncul LIVE di dashboard via WebSocket!")
    logger.info("=" * 65)

    total_pipeline = sum(PIPELINE_SAMPLE.values())
    logger.info(f"  Total: {total_pipeline} email dikirim ke Redis pipeline\n")

    grand_queued = 0
    for label, count in PIPELINE_SAMPLE.items():
        subdir = DATASET_DIR / label
        if not subdir.exists():
            logger.warning(f"    ⚠️  Subdirektori tidak ditemukan: {subdir}")
            continue
        files = get_eml_files(subdir, count)
        if not files:
            logger.warning(f"    ⚠️  Tidak ada file .eml di {subdir}")
            continue
        queued = await simulate_pipeline(label, files)
        grand_queued += queued

    logger.info(f"\n  ✅ FASE 1 SELESAI: {grand_queued} email masuk ke Redis pipeline")
    logger.info(f"  ⏳ Worker sedang memproses... Buka dashboard untuk melihat real-time!")

    # Tunggu worker proses
    logger.info(f"\n  ⏳ Menunggu worker memproses email (10 detik)...")
    await asyncio.sleep(10)

    # ─── Fase 2: API Batch (Populate Statistik) ────────────────────────────
    if not args.quick:
        logger.info("\n" + "=" * 65)
        logger.info("  FASE 2: API BATCH — Populasi Statistik Dashboard")
        logger.info("  (Memproses ribuan email via classifier API)") 
        logger.info("=" * 65)

        total_api = sum(API_BATCH.values())
        logger.info(f"  Total: ~{total_api} email via classifier API\n")

        grand_stats = {"CLEAN": 0, "WARN": 0, "QUARANTINE": 0, "error": 0}
        grand_api_time = 0

        for label, count in API_BATCH.items():
            subdir = DATASET_DIR / label
            if not subdir.exists():
                continue
            files = get_eml_files(subdir, count)
            if not files:
                continue
            stats = await simulate_api(label, files)
            for k, v in stats.items():
                grand_stats[k] += v

        logger.info("\n" + "-" * 65)
        logger.info("  HASIL AKHIR SIMULASI")
        logger.info("-" * 65)
        total_processed = sum(grand_stats.values())
        logger.info(f"  Total email diproses: {total_processed}")
        logger.info(f"  ✅ CLEAN (aman):       {grand_stats['CLEAN']}")
        logger.info(f"  ⚠️  WARN (warning):     {grand_stats['WARN']}")
        logger.info(f"  🛑 QUARANTINE (blokir): {grand_stats['QUARANTINE']}")
        logger.info(f"  ❌ Error:               {grand_stats['error']}")
        if total_processed > 0:
            threat = grand_stats['WARN'] + grand_stats['QUARANTINE']
            logger.info(f"\n  📊 Threat rate: {threat/total_processed*100:.1f}%")
            logger.info(f"  📊 Keamanan: {grand_stats['CLEAN']/total_processed*100:.1f}%")

    logger.info(f"\n  {'='*65}")
    logger.info(f"  ✅ SIMULASI SELESAI!")
    logger.info(f"  Buka http://localhost:8082 dan login sebagai analyst")
    logger.info(f"  untuk melihat hasil real-time di dashboard.")
    logger.info(f"  {'='*65}")


if __name__ == "__main__":
    asyncio.run(main())
