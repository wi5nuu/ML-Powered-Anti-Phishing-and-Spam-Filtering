"""Check pipeline results."""
import redis
from database.models import QuarantineEmail
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

r = redis.Redis(host="localhost", port=6379)
print(f"Queue: {r.llen('email_pipeline')}")

engine = create_engine("sqlite:///./lti_antiphishing.db")
s = sessionmaker(bind=engine)()
count = s.query(QuarantineEmail).count()
print(f"DB records: {count}")
for e in s.query(QuarantineEmail).order_by(QuarantineEmail.fused_score.desc()).all():
    print(f"  {e.email_id[:16]} | {e.label:10s} | {e.fused_score:.3f} | sa={e.sa_score:.1f} | ml={e.ml_probability:.3f} | {e.subject[:50]}")
