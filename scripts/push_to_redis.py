"""Push test emails directly to Redis queue for pipeline testing."""

import hashlib
import json
from datetime import datetime, timezone
import redis

r = redis.Redis(host="localhost", port=6379)
queue = "email_pipeline"

emails = [
    (
        'SEGERA! Akun Anda Akan Diblokir',
        '<html><body><form action="http://1odaya-id.xyz/login">'
        "<h2>SEGERA! Akun Anda Akan Diblokir</h2>"
        '<p>Klik <a href="http://bit.ly/verifikasi-akun">di sini</a> untuk verifikasi.</p>'
        "<p>Verifikasi sekarang atau akun ditangguhkan!</p>"
        '<input type="text" name="password" placeholder="Password">'
        "</form></body></html>",
        '"Bank BCA" <noreply@bca-secure-login.xyz>',
    ),
    (
        "Update sistem maintenance jadwal Minggu ini",
        "Halo tim LTI,\n\nBerikut jadwal maintenance server untuk minggu ini:\n"
        "- Rabu, 22:00 - 23:00 WIB: Database maintenance\n"
        "- Kamis, 23:00 - 01:00 WIB: API gateway update\n\n"
        "Terima kasih,\nTim DevOps",
        '"Tim LTI" <devops@lodaya.id>',
    ),
    (
        "Anda Mendapatkan Hadiah Rp 50.000.000!",
        "Klik http://tinyurl.com/menang-hadiah untuk klaim hadiah Anda!",
        '"Undian Berhadiah" <noreply@undian-menang.xyz>',
    ),
    (
        "Invoice bulanan - Layanan Cloud",
        "Halo, berikut invoice layanan cloud bulan Maret 2026 sebesar Rp 2.500.000.",
        '"LTI Billing" <billing@lodaya.id>',
    ),
]

for subj, body, sender in emails:
    raw = f"From: {sender}\r\nTo: admin@lodaya.id\r\nSubject: {subj}\r\nContent-Type: text/html\r\n\r\n{body}"
    email_id = hashlib.sha256(raw.encode()).hexdigest()[:16]
    payload = {
        "email_id": email_id,
        "raw_email": raw,
        "received_at": datetime.now(timezone.utc).isoformat(),
        "raw_hash": email_id,
    }
    r.rpush(queue, json.dumps(payload))
    print(f"Pushed: {subj[:50]}")

print(f"\nQueue size: {r.llen(queue)}")
