"""
Automated PDF Security Report Generator — Enterprise weekly report.
Usage: python scripts/generate_report.py [--days 7] [--output reports/weekly.pdf]
"""

import argparse
import json
import os
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import create_engine, func, case
from sqlalchemy.orm import sessionmaker
from jinja2 import Environment, FileSystemLoader

from database.models import QuarantineEmail, Feedback

DB_URL = os.getenv("DB_URL", "sqlite:///./lti_antiphishing.db")
REPORTS_DIR = Path("reports")
REPORTS_DIR.mkdir(exist_ok=True)

engine = create_engine(DB_URL)
SessionLocal = sessionmaker(bind=engine)


def generate_report(days: int = 7, output: str = None):
    db = SessionLocal()
    since = datetime.utcnow() - timedelta(days=days)

    total = db.query(func.count(QuarantineEmail.id)).filter(
        QuarantineEmail.created_at >= since
    ).scalar() or 0

    quarantine_count = db.query(func.count(QuarantineEmail.id)).filter(
        QuarantineEmail.created_at >= since,
        QuarantineEmail.label == "QUARANTINE"
    ).scalar() or 0

    warn_count = db.query(func.count(QuarantineEmail.id)).filter(
        QuarantineEmail.created_at >= since,
        QuarantineEmail.label == "WARN"
    ).scalar() or 0

    clean_count = total - quarantine_count - warn_count

    top_phishing = db.query(QuarantineEmail).filter(
        QuarantineEmail.created_at >= since,
        QuarantineEmail.label == "QUARANTINE"
    ).order_by(QuarantineEmail.fused_score.desc()).limit(5).all()

    top_senders = db.query(
        QuarantineEmail.sender,
        func.count(QuarantineEmail.id).label("count")
    ).filter(
        QuarantineEmail.created_at >= since
    ).group_by(QuarantineEmail.sender).order_by(
        func.count(QuarantineEmail.id).desc()
    ).limit(10).all()

    daily_stats = db.query(
        func.date(QuarantineEmail.created_at).label("day"),
        func.count(QuarantineEmail.id).label("total"),
        func.sum(case((QuarantineEmail.label == "QUARANTINE", 1), else_=0)).label("quarantines"),
    ).filter(
        QuarantineEmail.created_at >= since
    ).group_by(func.date(QuarantineEmail.created_at)).order_by(
        func.date(QuarantineEmail.created_at)
    ).all()

    avg_anomaly = db.query(func.avg(QuarantineEmail.anomaly_score)).filter(
        QuarantineEmail.created_at >= since
    ).scalar() or 0

    avg_fused = db.query(func.avg(QuarantineEmail.fused_score)).filter(
        QuarantineEmail.created_at >= since
    ).scalar() or 0

    total_feedback = db.query(func.count(Feedback.id)).filter(
        Feedback.created_at >= since
    ).scalar() or 0

    context = {
        "generated_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        "period_days": days,
        "period_start": since.strftime("%Y-%m-%d"),
        "period_end": datetime.utcnow().strftime("%Y-%m-%d"),
        "total": total,
        "quarantine_count": quarantine_count,
        "warn_count": warn_count,
        "clean_count": clean_count,
        "top_phishing": top_phishing,
        "top_senders": top_senders,
        "daily_stats": daily_stats,
        "avg_anomaly": round(float(avg_anomaly), 4),
        "avg_fused": round(float(avg_fused), 4),
        "total_feedback": total_feedback,
    }

    # Generate HTML
    env = Environment(loader=FileSystemLoader("dashboard/templates"))
    html_str = env.get_template("report_pdf.html").render(**context)

    output_path = output or str(REPORTS_DIR / f"weekly_{datetime.utcnow().date()}.pdf")

    # Try WeasyPrint, fallback to HTML
    try:
        from weasyprint import HTML
        HTML(string=html_str).write_pdf(output_path)
        print(f"PDF report generated: {output_path}")
    except ImportError:
        html_path = output_path.replace(".pdf", ".html")
        with open(html_path, "w") as f:
            f.write(html_str)
        print(f"WeasyPrint not installed. HTML report saved: {html_path}")
        print("Install with: pip install weasyprint")

    # Save JSON data for reference
    json_path = output_path.replace(".pdf", ".json")
    with open(json_path, "w") as f:
        json.dump(context, f, indent=2, default=str)

    db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate weekly security report")
    parser.add_argument("--days", type=int, default=7, help="Number of days to cover")
    parser.add_argument("--output", type=str, default=None, help="Output PDF path")
    args = parser.parse_args()
    generate_report(days=args.days, output=args.output)
