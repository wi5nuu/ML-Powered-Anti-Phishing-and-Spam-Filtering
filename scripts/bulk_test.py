"""
Bulk Email Testing Script — Feed .eml files through the pipeline.
Can run in two modes:
  1. API mode: sends emails to classifier HTTP endpoint (fast, no Redis/worker needed)
  2. Pipeline mode: pushes to Redis queue for full pipeline processing

Usage:
  # Test dataset_1 (default) via classifier API
  python scripts/bulk_test.py --mode api --all

  # Test dataset_2 via classifier API
  python scripts/bulk_test.py --dataset dataset_2 --mode api --all

  # Test specific subfolder
  python scripts/bulk_test.py --dataset dataset_1 --mode api --all --max 50

  # Dry run — just show what would be processed
  python scripts/bulk_test.py --dataset dataset_1 --mode dry-run
"""

import argparse
import asyncio
import json
import logging
import sys
import time
from pathlib import Path
from collections import Counter, defaultdict
from scripts.dataset_config import get_dataset_dir, FOLDER_NAMES

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


async def send_to_classifier_api(raw_email: str, email_id: str,
                                  api_url: str, session, timeout: float = 30.0):
    """Send one email to the classifier /predict-dual endpoint."""
    import aiohttp
    try:
        async with session.post(
            f"{api_url}/predict-dual",
            json={"raw_email": raw_email, "email_id": email_id},
            timeout=aiohttp.ClientTimeout(total=timeout),
        ) as resp:
            if resp.status == 200:
                return await resp.json()
            else:
                text = await resp.text()
                logger.warning("API returned %d for %s: %s", resp.status, email_id, text[:200])
                return {"error": f"HTTP {resp.status}", "email_id": email_id}
    except asyncio.TimeoutError:
        logger.warning("Timeout for %s", email_id)
        return {"error": "timeout", "email_id": email_id}
    except Exception as e:
        logger.warning("Error for %s: %s", email_id, e)
        return {"error": str(e), "email_id": email_id}


async def send_to_redis_pipeline(raw_email: str, email_id: str, redis_url: str, queue_name: str):
    """Push one email to Redis queue for pipeline processing."""
    import redis.asyncio as aio_redis
    try:
        r = await aio_redis.from_url(redis_url)
        payload = json.dumps({
            "email_id": email_id,
            "raw_email": raw_email,
            "received_at": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()),
        })
        await r.rpush(queue_name, payload)
        await r.aclose()
        return {"status": "queued", "email_id": email_id}
    except Exception as e:
        logger.warning("Redis push failed for %s: %s", email_id, e)
        return {"error": str(e), "email_id": email_id}


def classify_result(result: dict) -> str:
    """Categorize prediction result for stats."""
    if "error" in result:
        return "error"
    label = result.get("label", result.get("status", "unknown"))
    if label in ("CLEAN", "ham"):
        return "CLEAN"
    if label in ("WARN",):
        return "WARN"
    if label in ("QUARANTINE", "spam"):
        return "QUARANTINE"
    if label == "queued":
        return "QUEUED"
    return label


async def process_directory_api(dir_path: Path, api_url: str,
                                 concurrency: int = 20, max_emails: int = None,
                                 label_override: str = None):
    """Process all .eml files in directory via classifier API."""
    files = sorted(dir_path.rglob("*.eml"))
    if max_emails:
        files = files[:max_emails]

    total = len(files)
    logger.info("Processing %d emails from %s via API (%s)", total, dir_path, api_url)

    stats = Counter()
    results_by_label = defaultdict(list)
    start_time = time.time()

    import aiohttp
    connector = aiohttp.TCPConnector(limit=concurrency)
    async with aiohttp.ClientSession(connector=connector) as session:
        sem = asyncio.Semaphore(concurrency)

        async def process_one(filepath: Path):
            async with sem:
                email_id = filepath.stem
                raw = filepath.read_text(encoding="utf-8", errors="replace")
                result = await send_to_classifier_api(raw, email_id, api_url, session)
                cat = classify_result(result)
                stats[cat] += 1

                # Store sample results per category
                if len(results_by_label[cat]) < 3:
                    r = {
                        "file": str(filepath.relative_to(dir_path.parent.parent)),
                        "category": cat,
                    }
                    if "spam_probability" in result:
                        r["spam_probability"] = result["spam_probability"]
                    if "anomaly_score" in result:
                        r["anomaly_score"] = result["anomaly_score"]
                    if "label" in result:
                        r["label"] = result["label"]
                    if "xai_summary" in result:
                        r["xai_summary"] = result["xai_summary"][:120]
                    results_by_label[cat].append(r)

        tasks = [process_one(f) for f in files]
        # Process in batches to show progress
        batch_size = 100
        for i in range(0, len(tasks), batch_size):
            batch = tasks[i:i + batch_size]
            await asyncio.gather(*batch)
            done = min(i + batch_size, total)
            elapsed = time.time() - start_time
            rate = done / elapsed if elapsed > 0 else 0
            logger.info("  Progress: %d/%d (%.1f%%) — %.0f emails/sec",
                        done, total, done / total * 100, rate)

    elapsed = time.time() - start_time
    return stats, results_by_label, elapsed


async def process_directory_pipeline(dir_path: Path, redis_url: str,
                                      queue_name: str, max_emails: int = None):
    """Push all .eml files to Redis queue for full pipeline processing."""
    files = sorted(dir_path.rglob("*.eml"))
    if max_emails:
        files = files[:max_emails]

    total = len(files)
    logger.info("Pushing %d emails from %s to Redis queue %s", total, dir_path, queue_name)

    stats = Counter()
    start_time = time.time()

    for i, filepath in enumerate(files):
        email_id = filepath.stem
        raw = filepath.read_text(encoding="utf-8", errors="replace")
        result = await send_to_redis_pipeline(raw, email_id, redis_url, queue_name)
        stats[classify_result(result)] += 1

        if (i + 1) % 100 == 0:
            elapsed = time.time() - start_time
            rate = (i + 1) / elapsed if elapsed > 0 else 0
            logger.info("  Pushed %d/%d (%.1f%%) — %.0f emails/sec",
                        i + 1, total, (i + 1) / total * 100, rate)

    elapsed = time.time() - start_time
    return stats, elapsed


async def main():
    parser = argparse.ArgumentParser(
        description="Bulk test .eml files through LTI Anti-Phishing pipeline"
    )
    parser.add_argument("--dir", default=None,
                        help="Directory containing .eml files (default: dataset_1 root)")
    parser.add_argument("--dataset", default=None,
                        help="Dataset folder name: dataset_1 or dataset_2 (default: from ACTIVE_DATASET env or dataset_1)")
    parser.add_argument("--mode", choices=["api", "pipeline", "dry-run"],
                        default="api",
                        help="Processing mode (default: api)")
    parser.add_argument("--api-url", default="http://localhost:8001",
                        help="Classifier API URL (default: http://localhost:8001)")
    parser.add_argument("--redis-url", default="redis://localhost:6379/0",
                        help="Redis URL for pipeline mode")
    parser.add_argument("--queue", default="email_pipeline",
                        help="Redis queue name (default: email_pipeline)")
    parser.add_argument("--concurrency", type=int, default=20,
                        help="Concurrent API calls (default: 20)")
    parser.add_argument("--max", type=int, default=None,
                        help="Max emails to process")
    parser.add_argument("--all", action="store_true",
                        help="Process all subdirectories recursively")
    parser.add_argument("--label", default=None,
                        help="Override expected label for reporting")
    args = parser.parse_args()

    # Resolve directory: --dir overrides --dataset
    if args.dir:
        dir_path = Path(args.dir)
    elif args.dataset:
        dir_path = get_dataset_dir(args.dataset)
    else:
        dir_path = get_dataset_dir()
    if not dir_path.exists():
        logger.error("Directory not found: %s", dir_path)
        sys.exit(1)

    # Find all .eml files
    if args.all:
        # Process each subdirectory separately
        subdirs = sorted([d for d in dir_path.iterdir() if d.is_dir()])
        if not subdirs:
            subdirs = [dir_path]
    else:
        subdirs = [dir_path]

    grand_stats = Counter()
    grand_elapsed = 0
    all_samples = defaultdict(list)

    for subdir in subdirs:
        logger.info("=" * 60)
        logger.info("Processing: %s", subdir.name if subdir != dir_path else dir_path.name)
        logger.info("=" * 60)

        if args.mode == "dry-run":
            files = list(subdir.rglob("*.eml"))
            if args.max:
                files = files[:args.max]
            logger.info("Found %d .eml files in %s", len(files), subdir)
            for f in files[:10]:
                size = f.stat().st_size
                first_line = f.read_text(encoding="utf-8", errors="replace")[:100].split("\n")[0]
                logger.info("  %s (%d bytes) — %s", f.name, size, first_line[:80])
            if len(files) > 10:
                logger.info("  ... and %d more files", len(files) - 10)
            continue

        if args.mode == "api":
            stats, samples, elapsed = await process_directory_api(
                subdir, args.api_url, args.concurrency, args.max, args.label
            )
        elif args.mode == "pipeline":
            stats, elapsed = await process_directory_pipeline(
                subdir, args.redis_url, args.queue, args.max
            )
            samples = {}

        grand_stats.update(stats)
        grand_elapsed += elapsed
        for k, v in samples.items():
            all_samples[k].extend(v)

        # Per-directory summary
        logger.info("\n  Results for %s:", subdir.name)
        logger.info("  %-15s: %5d",
                    "Total", sum(stats.values()))
        for cat in ["CLEAN", "WARN", "QUARANTINE", "QUEUED", "error"]:
            if stats.get(cat, 0) > 0:
                pct = stats[cat] / max(sum(stats.values()), 1) * 100
                logger.info("  %-15s: %5d  (%.1f%%)", cat, stats[cat], pct)
        if elapsed > 0:
            logger.info("  %-15s: %5.1f sec (%.0f emails/sec)",
                        "Time", elapsed, sum(stats.values()) / elapsed)

    # Grand summary
    if args.mode != "dry-run" and grand_stats:
        total = sum(grand_stats.values())
        logger.info("\n" + "=" * 60)
        logger.info("GRAND SUMMARY")
        logger.info("=" * 60)
        logger.info("  %-15s: %5d", "Total", total)
        rate = total / grand_elapsed if grand_elapsed > 0 else 0
        logger.info("  %-15s: %5.1f sec (%.0f emails/sec)", "Total Time", grand_elapsed, rate)

        for cat in ["CLEAN", "WARN", "QUARANTINE", "QUEUED", "error"]:
            if grand_stats.get(cat, 0) > 0:
                pct = grand_stats[cat] / max(total, 1) * 100
                logger.info("  %-15s: %5d  (%.1f%%)", cat, grand_stats[cat], pct)

        # Show sample results
        if all_samples:
            logger.info("\n  Sample results:")
            for cat in ["QUARANTINE", "WARN", "CLEAN", "error"]:
                if cat in all_samples:
                    for s in all_samples[cat][:2]:
                        logger.info("    [%s] %s", cat, json.dumps(s, indent=6))

    logger.info("\nDone.")


if __name__ == "__main__":
    asyncio.run(main())
