"""
Add 5,000 casual conversational ham emails to dataset_merged.
These cover everyday conversation that was missing from the original training set.
"""

import hashlib
import random
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
import email.utils
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

RNG = random.Random(2026)

NAMES = ["Budi", "Sari", "Doni", "Rina", "Agus", "Maya", "Tono", "Dewi",
         "Alex", "Jane", "Mike", "Sarah", "Tom", "Lisa", "John", "Emma",
         "David", "Anna", "James", "Kate"]
DOMAINS = ["gmail.com", "yahoo.com", "outlook.com", "proton.me", "icloud.com"]

CASUAL_SUBJECTS = [
    "Lunch tomorrow?",
    "Meeting reminder",
    "Thanks for your help",
    "Re: project update",
    "Quick question",
    "Weekend plans?",
    "Happy birthday!",
    "Can you review this?",
    "Fwd: interesting article",
    "Thanks!",
    "Re: team outing",
    "See you at the meeting",
    "About the deadline",
    "Please check your email",
    "Happy holidays!",
    "Re: your application",
    "Welcome to the team!",
    "Monthly newsletter",
    "Your order has shipped",
    "Package delivered",
]

CASUAL_BODIES_EN = [
    "Hi {to},\n\nJust wanted to check in about the project. Let me know if you need anything.\n\nBest,\n{from}",
    "Dear {to},\n\nThanks for your email. I'll get back to you by Friday.\n\nRegards,\n{from}",
    "Hi {to},\n\nMeeting reminder for tomorrow at 10am in the main conference room.\n\nSee you there,\n{from}",
    "Hey {to},\n\nCan you send me the latest version of the report? Thanks!\n\nCheers,\n{from}",
    "Hi team,\n\nJust a quick update: everything is on track for the launch next week.\n\nBest,\n{from}",
    "Dear {to},\n\nThank you for your application. We would like to invite you for an interview.\n\nSincerely,\n{from}",
    "Hi {to},\n\nHappy birthday! Hope you have a great day!\n\nBest wishes,\n{from}",
    "Hi {to},\n\nThanks for your help with the presentation. It went really well!\n\nCheers,\n{from}",
    "Hello {to},\n\nCould you please review the attached document and let me know your thoughts?\n\nThanks,\n{from}",
    "Hi everyone,\n\nPlease find attached the agenda for tomorrow's meeting.\n\nRegards,\n{from}",
    "Dear {to},\n\nJust a reminder that the deadline for submissions is next Monday.\n\nBest regards,\n{from}",
    "Hi {to},\n\nI've uploaded the files to the shared drive. Please let me know if you can access them.\n\nThanks,\n{from}",
    "Hey {to},\n\nAre you free for a quick chat this afternoon?\n\nCheers,\n{from}",
    "Hi {to},\n\nYour package has been delivered. Enjoy!\n\nCustomer Service",
    "Dear {to},\n\nPlease find the invoice attached for your records.\n\nRegards,\nBilling",
]

CASUAL_BODIES_ID = [
    "Yth. {to},\n\nMohon konfirmasi kehadiran untuk acara hari Jumat.\n\nTerima kasih,\n{from}",
    "Halo {to},\n\nTerima kasih atas bantuannya. Sangat membantu!\n\nSalam,\n{from}",
    "Dear {to},\n\nIni adalah reminder untuk meeting besok jam 9 pagi.\n\nTerima kasih,\n{from}",
    "Halo teman-teman,\n\nMohon maaf saya tidak bisa ikut meeting hari ini karena sakit.\n\nTerima kasih,\n{from}",
    "Yth. {to},\n\nBerkas yang Bapak/Ibu minta sudah saya siapkan.\n\nHormat saya,\n{from}",
    "Halo {to},\n\nSelamat ulang tahun! Semoga sehat selalu.\n\nSalam,\n{from}",
    "Kepada {to},\n\nMohon infonya untuk jadwal meeting selanjutnya.\n\nTerima kasih,\n{from}",
]


def generate_casual_ham(idx):
    from_name = RNG.choice(NAMES)
    to_name = RNG.choice(NAMES)
    from_email = f"{from_name.lower()}{RNG.randint(1,999)}@{RNG.choice(DOMAINS)}"
    to_email = f"{to_name.lower()}{RNG.randint(1,999)}@lodaya.id"

    is_indonesian = RNG.random() < 0.3
    pool = CASUAL_BODIES_ID if is_indonesian else CASUAL_BODIES_EN
    body = RNG.choice(pool).replace("{to}", to_name).replace("{from}", from_name)

    subject = RNG.choice(CASUAL_SUBJECTS)

    msg = MIMEText(body, "plain", "utf-8")
    msg["From"] = f"{from_name} <{from_email}>"
    msg["To"] = f"{to_name} <{to_email}>"
    msg["Subject"] = subject
    d = datetime.now() - timedelta(days=RNG.randint(0, 30))
    msg["Date"] = email.utils.formatdate(timeval=d.timestamp(), localtime=True)
    msg["Message-ID"] = f"<casual.{idx}.{RNG.randint(1000,9999)}@local>"
    msg["MIME-Version"] = "1.0"
    msg["X-Mailer"] = RNG.choice(["Outlook", "Gmail", "Apple Mail", "Thunderbird"])

    return msg.as_string()


def main(count=5000):
    out_dir = Path("data/dataset_merged/_extended/casual_ham")
    out_dir.mkdir(parents=True, exist_ok=True)

    for i in range(count):
        eml = generate_casual_ham(i)
        h = hashlib.sha256(eml.encode()).hexdigest()[:16]
        fname = f"casual_ham_{i+1:04d}_{h}.eml"
        (out_dir / fname).write_text(eml, encoding="utf-8")
        if (i+1) % 1000 == 0:
            print(f"  {i+1}/{count}...")

    print(f"Generated {count} casual ham emails -> {out_dir}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=5000)
    main(parser.parse_args().count)
