"""Test classifier with the exact phishing email."""
import httpx

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

r = httpx.post("http://localhost:8001/predict", json={"raw_email": raw, "email_id": "phish001"}, timeout=10)
print(f"Status: {r.status_code}")
print(f"Response: {r.json()}")
