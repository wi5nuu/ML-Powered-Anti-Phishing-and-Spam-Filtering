"""
Seed test emails ke Mailpit untuk pengujian pipeline.

Mengirim contoh email phishing dan legit ke SMTP Mailpit.
"""

import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

SMTP_HOST = "localhost"
SMTP_PORT = 1025


def send_email(to: str, subject: str, body: str, from_addr: str = "test@lti.local"):
    msg = MIMEMultipart()
    msg["From"] = from_addr
    msg["To"] = to
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "html" if "<html" in body else "plain"))

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.send_message(msg)
    print(f"Sent: {subject}")


def main():
    phishing_email = """\
<html><body>
<form action="http://1odaya-id.xyz/login">
  <h2>SEGERA! Akun Anda Akan Diblokir</h2>
  <p>Klik <a href="http://bit.ly/verifikasi-akun">di sini</a> untuk verifikasi.</p>
  <p>Verifikasi sekarang atau akun ditangguhkan!</p>
  <input type="text" name="password" placeholder="Password">
</form>
</body></html>
"""

    legitimate_email = """\
Halo tim LTI,

Berikut jadwal maintenance server untuk minggu ini:
- Rabu, 22:00 - 23:00 WIB: Database maintenance
- Kamis, 23:00 - 01:00 WIB: API gateway update

Terima kasih,
Tim DevOps
"""

    send_email("admin@lodaya.id", "SEGERA! Akun Anda Akan Diblokir", phishing_email,
               from_addr='"Bank BCA" <noreply@bca-secure-login.xyz>')
    send_email("all@lodaya.id", "Update sistem maintenance jadwal Minggu ini",
               legitimate_email, from_addr='"Tim LTI" <devops@lodaya.id>')
    send_email("admin@lodaya.id", "Anda Mendapatkan Hadiah Rp 50.000.000!",
               "Klik http://tinyurl.com/menang-hadiah untuk klaim hadiah Anda!",
               from_addr='"Undian Berhadiah" <noreply@undian-menang.xyz>')
    send_email("cs@lodaya.id", "Invoice bulanan - Layanan Cloud",
               "Halo, berikut invoice layanan cloud bulan Maret 2026 sebesar Rp 2.500.000.",
               from_addr='"LTI Billing" <billing@lodaya.id>')

    print("Test emails sent to Mailpit.")


if __name__ == "__main__":
    main()
