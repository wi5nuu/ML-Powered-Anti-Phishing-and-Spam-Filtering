"""Single clean push and verify."""
import hashlib, json, time, redis
from database.models import QuarantineEmail
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

r = redis.Redis(host="localhost", port=6379)
q = "email_pipeline"
r.delete(q)
time.sleep(0.5)

# Push just 1 phishing email
raw = (
    'From: "Bank BCA" <noreply@bca-secure-login.xyz>\r\n'
    "To: admin@lodaya.id\r\n"
    "Subject: SEGERA! Akun Anda Akan Diblokir\r\n"
    "Content-Type: text/html\r\n\r\n"
    "<html><body>"
    '<form action="http://1odaya-id.xyz/login">'
    "<h2>SEGERA! Akun Anda Akan Diblokir</h2>"
    '<p>Klik <a href="http://bit.ly/verifikasi-akun">di sini</a> untuk verifikasi.</p>'
    "<p>Verifikasi sekarang atau akun ditangguhkan!</p>"
    "</form></body></html>"
)
email_id = hashlib.sha256(raw.encode()).hexdigest()[:16]
payload = {"email_id": email_id, "raw_email": raw, "received_at": "2026-06-22T17:00:00", "raw_hash": email_id}
r.rpush(q, json.dumps(payload))
print(f"Pushed 1 phishing email: {email_id[:16]}")
print(f"Queue: {r.llen(q)}")

time.sleep(30)

print(f"Queue after 30s: {r.llen(q)}")
engine = create_engine("sqlite:///./lti_antiphishing.db")
s = sessionmaker(bind=engine)()
count = s.query(QuarantineEmail).count()
print(f"DB records: {count}")
for e in s.query(QuarantineEmail).order_by(QuarantineEmail.id.desc()).limit(5).all():
    print(f"  id={e.email_id[:16]} | {e.label:10s} | {e.fused_score:.3f} | sa={e.sa_score:.1f} | ml={e.ml_probability:.3f} | subject=[{e.subject[:60]}] | sender=[{e.sender[:60]}]")
