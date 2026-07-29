#!/usr/bin/env python3
"""
Manual ML Retraining Trigger Script

This script allows you to manually trigger ML model retraining for testing
or maintenance purposes. It can be run from command line or scheduled via cron.

Usage:
    # Run retraining once
    python scripts/trigger_retraining.py
    
    # Dry run (check status without retraining)
    python scripts/trigger_retraining.py --dry-run
    
    # Force retraining even with fewer samples
    python scripts/trigger_retraining.py --force
    
    # Set custom thresholds
    python scripts/trigger_retraining.py --min-samples 50 --min-accuracy 0.80
"""

import argparse
import json
import os
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from worker.ml_retraining_worker import run_retraining, get_db_session
from sqlalchemy import text


def check_status():
    """Check current retraining status and available samples."""
    db = get_db_session()
    
    try:
        # Count approved samples
        approved_query = text("""
            SELECT COUNT(*) as count
            FROM training_samples
            WHERE status = 'approved'
        """)
        approved_count = db.execute(approved_query).scalar() or 0
        
        # Count pending samples
        pending_query = text("""
            SELECT COUNT(*) as count
            FROM training_samples
            WHERE status = 'pending'
        """)
        pending_count = db.execute(pending_query).scalar() or 0
        
        # Count used samples
        used_query = text("""
            SELECT COUNT(*) as count
            FROM training_samples
            WHERE status = 'used_in_training'
        """)
        used_count = db.execute(used_query).scalar() or 0
        
        # Get latest retraining audit
        audit_query = text("""
            SELECT timestamp, status, description, changes
            FROM audit_trail
            WHERE action = 'model_retrain'
            ORDER BY timestamp DESC
            LIMIT 1
        """)
        latest_retrain = db.execute(audit_query).fetchone()
        
        print("\n" + "=" * 60)
        print("ML RETRAINING STATUS")
        print("=" * 60)
        print(f"\nTraining Samples:")
        print(f"  • Approved (ready for training): {approved_count}")
        print(f"  • Pending (awaiting review):     {pending_count}")
        print(f"  • Used in training:              {used_count}")
        
        min_samples = int(os.getenv("RETRAINING_MIN_SAMPLES", "100"))
        print(f"\nRetraining Configuration:")
        print(f"  • Minimum samples required: {min_samples}")
        print(f"  • Minimum accuracy threshold: {os.getenv('RETRAINING_MIN_ACCURACY', '0.85')}")
        print(f"  • Schedule interval: {os.getenv('RETRAINING_SCHEDULE_HOURS', '24')} hours")
        print(f"  • Retraining enabled: {os.getenv('RETRAINING_ENABLED', 'true')}")
        
        print(f"\nReadiness Status:")
        if approved_count >= min_samples:
            print(f"  ✅ READY - {approved_count} samples available (>= {min_samples} required)")
        else:
            print(f"  ⚠️  NOT READY - {approved_count} samples available (< {min_samples} required)")
            print(f"     Need {min_samples - approved_count} more approved samples")
        
        if latest_retrain:
            print(f"\nLast Retraining Attempt:")
            print(f"  • Timestamp: {latest_retrain[0]}")
            print(f"  • Status: {latest_retrain[1]}")
            print(f"  • Description: {latest_retrain[2]}")
            if latest_retrain[3]:
                try:
                    changes = json.loads(latest_retrain[3])
                    if 'model_version' in changes:
                        print(f"  • Model version: {changes['model_version']}")
                except:
                    pass
        else:
            print(f"\nNo previous retraining attempts found")
        
        print("=" * 60 + "\n")
        
        return {
            "approved_count": approved_count,
            "pending_count": pending_count,
            "used_count": used_count,
            "ready": approved_count >= min_samples
        }
        
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(
        description="Manually trigger ML model retraining",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Check status only
  python scripts/trigger_retraining.py --dry-run
  
  # Run retraining with default settings
  python scripts/trigger_retraining.py
  
  # Force retraining with custom thresholds
  python scripts/trigger_retraining.py --force --min-samples 50
        """
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Check status without running retraining"
    )
    
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force retraining even if minimum samples not met"
    )
    
    parser.add_argument(
        "--min-samples",
        type=int,
        help="Override minimum samples threshold"
    )
    
    parser.add_argument(
        "--min-accuracy",
        type=float,
        help="Override minimum accuracy threshold"
    )
    
    args = parser.parse_args()
    
    # Override environment variables if specified
    if args.min_samples:
        os.environ["RETRAINING_MIN_SAMPLES"] = str(args.min_samples)
    
    if args.min_accuracy:
        os.environ["RETRAINING_MIN_ACCURACY"] = str(args.min_accuracy)
    
    if args.force:
        os.environ["RETRAINING_MIN_SAMPLES"] = "1"
    
    # Check status
    status = check_status()
    
    if args.dry_run:
        print("Dry run mode - no retraining will be performed")
        return 0
    
    if not status["ready"] and not args.force:
        print("❌ Not enough approved samples for retraining")
        print("   Use --force to override this check")
        return 1
    
    # Run retraining
    print("\n" + "=" * 60)
    print("STARTING RETRAINING PIPELINE")
    print("=" * 60 + "\n")
    
    try:
        result = run_retraining()
        
        print("\n" + "=" * 60)
        print("RETRAINING RESULT")
        print("=" * 60)
        print(json.dumps(result, indent=2))
        print("=" * 60 + "\n")
        
        if result["status"] == "success":
            print("✅ Retraining completed successfully!")
            print(f"   Model version: {result.get('model_version', 'N/A')}")
            print(f"   Samples used: {result.get('n_samples_used', 'N/A')}")
            if 'validation_metrics' in result:
                metrics = result['validation_metrics'].get('new_model', {})
                print(f"   Accuracy: {metrics.get('accuracy', 'N/A'):.4f}")
                print(f"   F1 Score: {metrics.get('f1', 'N/A'):.4f}")
            return 0
        
        elif result["status"] == "skipped":
            print("⚠️  Retraining skipped")
            print(f"   Reason: {result.get('message', 'N/A')}")
            return 0
        
        elif result["status"] == "rejected":
            print("❌ New model rejected - did not meet quality thresholds")
            print(f"   Reason: {result.get('message', 'N/A')}")
            return 1
        
        else:
            print("❌ Retraining failed")
            print(f"   Error: {result.get('message', 'Unknown error')}")
            return 1
    
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
