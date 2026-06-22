"""Push phishing email and check results."""
import hashlib, json, redis, time

r = redis.Redis(host="localhost", port=6379)
q = "email_pipeline"

raw = 'From: "Bank BCA" <noreply@bca-secure-login.xyz>\r\nTo: admin@lodaya.id\r\nSubject: SEGERA! Akun Anda Akan Diblokir\r\nContent-Type: text/html\r\n\r\n<html><body><form action="http://1odaya-id.xyz/login"><h2>SEGERA! Akun Anda Akan Diblokir</h2><p>Klik <a href="http://bit.ly/verifikasi-akun">di sini</a></p></form></body></html>'
email_id = hashlib.sha256(raw.encode()).hexdigest()[:16]
payload = {"email_id": email_id, "raw_email": raw, "received_at": "2026-06-22T17:00:00", "raw_hash": email_id}
r.rpush(q, json.dumps(payload))
print(f"Pushed: {email_id}")
time.sleep(20)

from database.models import QuarantineEmail
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
engine = create_engine("sqlite:///./lti_antiphishing.db")
s = sessionmaker(bind=engine)()
count = s.query(QuarantineEmail).count()
print(f"Queue: {r.llen(q)}, DB: {count}")
for e in s.query(QuarantineEmail).order_by(QuarantineEmail.id.desc()).limit(5).all():
    print(f"  {e.email_id[:16]} | {e.label:10s} | {e.fused_score:.3f} | {e.subject[:60]}")
