"""
Generate 74k extended emails with business context scoring + BEC.

Distribution (73,942 new):
  transaksi (12k) - Financial transaction confirmations (ham)
  cs (8k)       - Customer service replies (ham)
  internal (10k) - Internal B2B docs (ham)
  spam (12k)    - Spam/promotional
  phishing (12k)- Phishing attempts
  malware (10k) - Malware-delivery emails
  bec (9,942)   - Business Email Compromise (CEO fraud)

Each email includes characteristics detectable by our 20+8 business
context feature extraction.

Output: data/dataset_merged/_extended/<category>/*.eml
"""

import argparse
import email.utils
import hashlib
import os
import random
import string
from datetime import datetime, timedelta
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from pathlib import Path

RNG = random.Random(2026)

# ─── Data pools ────────────────────────────────────────────────────────

COMPANIES = [
    "PT Lodaya Teknologi Indonesia", "PT Bank Central Asia Tbk",
    "PT Bank Mandiri Tbk", "PT Bank Negara Indonesia Tbk",
    "PT Bank Rakyat Indonesia Tbk", "PT Gojek Indonesia",
    "PT Tokopedia", "PT Shopee Indonesia", "PT Traveloka",
    "PT Telkom Indonesia", "PT Indosat Ooredoo", "PT XL Axiata",
    "PT Astra International", "PT Unilever Indonesia",
    "PT Kalbe Farma", "PT Gudang Garam Tbk", "PT Sinar Mas",
    "PT Lippo Group", "PT Djarum", "PT Wings Group",
]

DOMAINS = [
    "lodaya.id", "bca.co.id", "mandiri.co.id", "bni.co.id",
    "bri.co.id", "gmail.com", "yahoo.com", "outlook.com",
    "gojek.com", "tokopedia.com", "shopee.co.id", "traveloka.com",
    "telkom.co.id", "g.co", "office365.com", "cimbniaga.co.id",
    "permata.co.id", "danamon.co.id", "pandu.com", "nusantara.co.id",
]

FIRST_NAMES_MALE = [
    "Ahmad", "Bambang", "Citra", "Dedi", "Eko", "Fajar", "Gunawan",
    "Hendra", "Indra", "Joko", "Kurniawan", "Lukman", "Mulyadi",
    "Nugroho", "Pramono", "Rahmat", "Sutrisno", "Tri", "Umar", "Wahyu",
    "Agus", "Bayu", "Cahyo", "Dimas", "Edi", "Farhan", "Gilang",
    "Heru", "Iwan", "Jatmiko", "Krisna", "Lutfi", "Maulana",
    "Nanda", "Prasetyo", "Rudi", "Slamet", "Teguh", "Untung", "Yuda",
]

FIRST_NAMES_FEMALE = [
    "Ani", "Bunga", "Citra", "Dewi", "Erna", "Fitri", "Gita",
    "Heni", "Indah", "Julia", "Kartika", "Lestari", "Maya",
    "Nadia", "Putri", "Ratna", "Sari", "Tina", "Utami", "Wulan",
    "Ayu", "Bella", "Cindy", "Dian", "Elok", "Fara", "Galuh",
    "Hana", "Ika", "Jenny", "Karina", "Lina", "Mega",
    "Nita", "Puspita", "Rina", "Silvi", "Tari", "Vina", "Yanti",
]

LAST_NAMES = [
    "Wijaya", "Kusuma", "Pratama", "Santoso", "Setiawan", "Nugraha",
    "Hidayat", "Saputra", "Purnama", "Susanto", "Wibowo", "Hartono",
    "Gunawan", "Wahyudi", "Handayani", "Lestari", "Utami", "Maryati",
    "Hasanah", "Anggraini", "Pertiwi", "Ramadhani", "Fadhilah",
    "Rahmawati", "Ningsih", "Siregar", "Nasution", "Harahap",
    "Simanjuntak", "Sitorus", "Sibarani", "Sinaga", "Manurung",
]

C_LEVEL = [
    "CEO", "CFO", "COO", "CTO", "CIO", "VP Finance", "VP Operations",
    "Director of Finance", "Managing Director", "President Director",
]

# ─── BEC-specific pools ────────────────────────────────────────────────

BEC_SUBJECTS = [
    "Urgent: Wire Transfer #{ref}",
    "RE: Payment to {vendor} - Action Needed",
    "Confidential: Acquisition #{ref}",
    "Urgent Invoice #{ref} - Payment Required Today",
    "FW: Request from {ceo_name}",
    "Important: Vendor Payment Change",
    "Re: Strategy Meeting Tomorrow",
    "Urgent: Can you process a payment?",
    "Quick favor needed",
    "{ceo_last}: Preparing for audit - need payment approval",
    "Confidential request from {ceo_name}",
    "RE: Legal settlement #{ref}",
    "Payment #{ref} - CEO approved",
    "FW: Urgent request from {ceo_name}",
    "Time-sensitive: Wire #{ref}",
]

BEC_TEMPLATES = [
    "Hi {name},\n\nI'm in a meeting and can't talk freely. I need you to process an urgent wire transfer of ${amount:,} to the following account:\n\nBeneficiary: {vendor}\nBank: {bank}\nAccount: {account}\nRouting: {routing}\n\nThis is for the {deal_type} deal. I'll sign the paperwork when I'm back. Keep this confidential.\n\nRegards,\n{ceo_name}",
    "{name},\n\nCan you do me a quick favor? I need you to send ${amount:,} to our new legal counsel for the {deal_type} matter. Details below:\n\n{account_info}\n\nPlease process this today. I'll explain more when I'm out of this meeting.\n\nThanks,\n{ceo_name}",
    "Hi {name},\n\nPer our urgent discussion, please process payment #{ref} for ${amount:,} to {vendor}. This is time-sensitive and needs to go out today.\n\nWire instructions:\nBank: {bank}\nAccount: {account}\nSwift: {swift}\n\nI need confirmation once done.\n\nBest,\n{ceo_name}",
    "Dear {name},\n\nI need your help with a confidential matter. We're finalizing the {deal_type} acquisition and need to transfer ${amount:,} for the escrow deposit.\n\nPlease wire to:\n{account_info}\n\nDo not discuss this with anyone - this is extremely sensitive.\n\nRegards,\n{ceo_name}",
    "Hi {name},\n\nOur vendor {vendor} has changed their banking details. Please update our records and process the outstanding invoice #{ref} of ${amount:,} to their new account:\n\n{account_info}\n\nThis needs to be done before EOD to avoid service disruption.\n\nThanks,\n{ceo_name}",
    "Hi {name},\n\nI need you to purchase {gift_cards_amount} in Google Play gift cards for client gifts. Please buy them from {store} and email me the codes.\n\nThis is urgent - client is waiting.\n\nRegards,\n{ceo_name}",
    "Good morning {name},\n\nPer legal's request, please wire ${amount:,} for settlement #{ref}. The details are below.\n\n{account_info}\n\nI need the confirmation receipt by end of day.\n\nBest,\n{ceo_name}",
    "Hi {name},\n\nCan you process the monthly payroll bonus of ${amount:,} today? Here are the distribution details.\n\n{account_info}\n\nThe staff are expecting this by Friday.\n\nThanks,\n{ceo_name}",
]

BEC_ACCOUNT_INFO = "Beneficiary: {vendor}\nBank: {bank}\nAccount: {account}\nRouting: {routing}\nSwift: {swift}"

BEC_VENDORS = [
    "PT Mitra Solusi Global", "PT Karya Mandiri Sejahtera",
    "PT Anugerah Cipta Digital", "PT Sarana Multi Infrastruktur",
    "PT Prima Kencana Abadi", "PT Bumi Resource Tbk",
    "PT Indah Kiat Pulp & Paper", "PT Samudra Perkasa",
    "PT Multi Nitrotama Kimia", "PT Adhi Karya Tbk",
]

BEC_BANKS = ["Bank of America", "JPMorgan Chase", "Citibank", "HSBC",
             "Standard Chartered", "Deutsche Bank", "UBS", "Credit Suisse",
             "DBS Bank", "OCBC Bank"]

BEC_DEAL_TYPES = [
    "acquisition", "merger", "joint venture", "legal settlement",
    "strategic investment", "land acquisition", "patent licensing",
    "offshore investment", "bond issuance", "ESOP buyback",
]

# ─── Helpers ───────────────────────────────────────────────────────────

def random_name():
    gender = RNG.choice(["male", "female"])
    first = RNG.choice(FIRST_NAMES_MALE if gender == "male" else FIRST_NAMES_FEMALE)
    last = RNG.choice(LAST_NAMES)
    return f"{first} {last}"

def random_email(name=None):
    if name is None:
        name = random_name()
    name_part = name.lower().replace(" ", ".")
    domain = RNG.choice(DOMAINS)
    return f"{name_part}@{domain}"

def generate_ref():
    return f"INV-{RNG.randint(100000, 999999)}"

def generate_ticket():
    return f"TKT-{RNG.randint(10000, 99999)}"

def generate_date():
    d = datetime.now() - timedelta(days=RNG.randint(0, 365))
    return email.utils.formatdate(timeval=d.timestamp(), localtime=True)

def generate_message_id():
    rand = hashlib.md5(str(RNG.random()).encode()).hexdigest()[:16]
    return f"<{rand}.{RNG.randint(1000,9999)}@extended.lti.local>"

def generate_amount(min_v=10000, max_v=50000000):
    return RNG.randint(min_v, max_v)

def generate_html_body(plain_text, links=None, category=""):
    lines = plain_text.replace("\n", "<br>\n")
    img_html = ""
    if category == "bec" and RNG.random() < 0.2:
        img_html = '<img src="https://www.lodaya.id/logo.png" alt="Lodaya" width="150"><br>\n'
    elif category == "phishing" and RNG.random() < 0.4:
        img_html = '<img src="http://bit.ly/fake_bank_logo" alt="Bank" width="120"><br>\n'
    link_html = ""
    if links:
        for l in links:
            link_html += f'<br><a href="{l}">{l}</a>'
    styles = {
        "bec": 'style="font-family:Calibri,sans-serif;padding:20px;color:#333;"',
        "transaction": 'style="font-family:Arial,sans-serif;padding:16px;line-height:1.6;"',
        "cs": 'style="font-family:Arial,sans-serif;padding:16px;line-height:1.6;"',
        "internal": 'style="font-family:Calibri,sans-serif;padding:16px;"',
        "spam": 'style="background:#fff3cd;padding:20px;font-family:Arial;color:#856404;"',
        "phishing": 'style="background:#fff;padding:24px;font-family:Arial;border:2px solid #cc0000;"',
        "malware": 'style="background:#f5f5f5;padding:20px;font-family:Consolas;font-size:12px;"',
    }
    style = styles.get(category, 'style="font-family:Arial,sans-serif;padding:16px;"')
    return f'<html><body><div {style}>{img_html}{lines}{link_html}</div></body></html>'

def build_eml(subject, body_plain, from_name, from_email, to_name, to_email,
              links=None, attachments=None, category=""):
    msg = MIMEMultipart("mixed")
    msg["From"] = f"{from_name} <{from_email}>"
    msg["To"] = f"{to_name} <{to_email}>"
    msg["Subject"] = subject
    msg["Date"] = generate_date()
    msg["Message-ID"] = generate_message_id()
    msg["MIME-Version"] = "1.0"
    msg["X-Mailer"] = RNG.choice([
        "Microsoft Outlook 16.0", "Mozilla Thunderbird 115.0",
        "Apple Mail 16.0", "Google Mail", "Roundcube Webmail 1.6",
        "Zimbra 9.0",
    ])
    msg["X-Priority"] = RNG.choice(["3 (Normal)", "2 (High)", "1 (Low)"])

    if category == "phishing":
        msg["Authentication-Results"] = "spf=pass smtp.mailfrom=" + from_email.split("@")[1]
        msg["DKIM-Signature"] = f"v=1; a=rsa-sha256; d={from_email.split('@')[1]}; s=selector1; bh=fake;"
    elif category == "bec":
        msg["X-Priority"] = "1 (High)"
        msg["Importance"] = "high"
        msg["X-MSMail-Priority"] = "High"
    elif category == "spam":
        msg["X-Spam-Flag"] = "YES"

    body_alt = MIMEMultipart("alternative")
    body_text = MIMEText(body_plain, "plain", "utf-8")
    body_html_content = generate_html_body(body_plain, links, category)
    body_html_part = MIMEText(body_html_content, "html", "utf-8")
    body_alt.attach(body_text)
    body_alt.attach(body_html_part)
    msg.attach(body_alt)

    if attachments:
        for a in attachments:
            msg.attach(a)

    return msg.as_string()

# ─── Email generators ──────────────────────────────────────────────────

def generate_transaction_email(idx):
    name = random_name()
    email_addr = random_email(name)
    to_name = random_name()
    to_email = random_email(to_name)
    ref = generate_ref()
    amount = generate_amount()
    service = RNG.choice(["Internet Banking", "Mobile Banking", "Transfer Antar Bank",
                          "Pembayaran Tagihan", "Pembelian Pulsa", "Top Up E-Wallet",
                          "Investasi Reksadana", "Asuransi", "Transaksi Kartu Kredit",
                          "QRIS Payment", "SMS Banking", "Autopay"])
    method = RNG.choice(["Transfer Bank", "Virtual Account", "Kartu Kredit", "QRIS", "GoPay", "OVO", "DANA", "ShopeePay"])
    company = RNG.choice(COMPANIES)
    date_str = (datetime.now() - timedelta(days=RNG.randint(0, 30))).strftime("%d/%m/%Y")
    balance = generate_amount(50000, 200000000)

    templates = [
        "Kepada Yth. {name},\n\nPembayaran Anda sebesar Rp{amount:,} untuk {service} telah kami terima.\n\nDetail:\n- Ref: {ref}\n- Tanggal: {date}\n- Jumlah: Rp{amount:,}\n- Metode: {method}\n- Status: BERHASIL\n\nTerima kasih.\n{company}",
        "Dear {name},\n\nYour payment of Rp{amount:,} for {service} has been processed.\n\nReference: {ref}\nDate: {date}\nAmount: Rp{amount:,}\nStatus: COMPLETED\n\nRegards,\n{company}",
        "Hi {name},\n\nTransaction alert: Rp{amount:,} transferred from your account.\n\nReference: {ref}\nMerchant: {company}\nBalance: Rp{balance:,}\n\nThank you for using {service}.",
    ]
    body = RNG.choice(templates).format(name=to_name, amount=amount, service=service,
        ref=ref, date=date_str, method=method, company=company, balance=balance)
    subject = f"Konfirmasi Transaksi #{ref}" if RNG.random() < 0.5 else f"Payment Confirmed #{ref}"
    return build_eml(subject, body, company, email_addr, to_name, to_email, category="transaction")

def generate_cs_email(idx):
    name = random_name()
    email_addr = random_email(name)
    to_name = random_name()
    to_email = random_email(to_name)
    ticket = generate_ticket()
    topics = ["Gagal login", "Transaksi tidak dikenal", "Lupa password",
              "Akun diblokir", "Laporan bug", "Pengaduan spam", "Permintaan refund"]
    topic = RNG.choice(topics)
    solutions = [
        "Masalah telah kami selesaikan. Silakan coba kembali.",
        "Kami telah melakukan reset akun Anda.",
        "Tim teknis telah memperbaiki gangguan tersebut.",
        "Permintaan Anda telah diproses.",
        "Your issue has been resolved. Please verify.",
    ]
    body = f"Yth. {to_name},\n\nTiket #{ticket} ({topic}) telah selesai diproses.\n\n{RNG.choice(solutions)}\n\nTerima kasih,\nCustomer Service"
    subject = f"Respon Tiket #{ticket}" if RNG.random() < 0.5 else f"Support Ticket #{ticket} Updated"
    return build_eml(subject, body, name, email_addr, to_name, to_email, category="cs")

def generate_internal_email(idx):
    name = random_name()
    email_addr = random_email(name)
    to_name = random_name()
    to_email = random_email(to_name)
    company = RNG.choice(COMPANIES)
    partner = RNG.choice(COMPANIES)
    topics = ["Sprint Review", "Q{0} Planning".format(RNG.randint(1,4)),
              "Budget Meeting", "Project Sync", "Security Briefing",
              "Vendor Evaluation", "Performance Review"]
    topic = RNG.choice(topics)
    body = f"Dear {to_name},\n\nPlease find the {topic} documents attached. Kindly review and provide feedback by EOD.\n\nBest regards,\n{name}\n{company}"
    subject = f"{topic} - {datetime.now().strftime('%B %Y')}"
    return build_eml(subject, body, name, email_addr, to_name, to_email, category="internal")

def generate_spam_email(idx):
    name = random_name()
    to_name = random_name()
    to_email = random_email(to_name)
    amount = generate_amount(5000000, 500000000)
    prize = RNG.choice(["iPhone 16", "Rp 100.000.000", "Mobil", "Paket Liburan",
                        "Voucher Rp 50.000.000", "Smart TV", "Emas 100 gram"])
    link = RNG.choice(["http://bit.ly/prize-winner", "http://tinyurl.com/klaim-hadiah",
                       "http://bit.ly/pinjaman-online", "http://tinyurl.com/diskon-90",
                       "http://adf.ly/promosi"])
    templates = [
        f"SELAMAT! Anda pemenang {prize}!\n\nKlik: {link}\n\nJangan lewatkan!",
        f"ANDA TERPILIH! Dapatkan Rp{amount:,} sekarang!\n\n{link}",
        f"Halo {to_name}, penawaran spesial untuk Anda!\nDiskon 90%!\n{link}",
        f"Dear {to_name}, you won {prize}!\nClaim: {link}\nLimited time!",
    ]
    body = RNG.choice(templates)
    subject = f"SELAMAT! Anda Memenangkan {prize}!" if RNG.random() < 0.5 else f"YOU WON {prize.upper()}! Claim Now!"
    spam_name = RNG.choice(["Tim Promosi", "Marketing", "Customer Service", "Admin"])
    spam_email = f"promo{RNG.randint(1000,9999)}@{RNG.choice(['marketing.tk', 'winner.ga', 'bonus.ml', 'promo.cf'])}"
    return build_eml(subject, body, spam_name, spam_email, to_name, to_email,
                     links=[link], category="spam")

def generate_phishing_email(idx):
    to_name = random_name()
    to_email = random_email(to_name)
    amount = generate_amount(50000, 5000000)
    ref = generate_ref()
    link = RNG.choice([
        "http://bca-secure.xyz/verify", "http://mandiri-verifikasi.tk/auth",
        "http://lodaya-account.ml/secure", "http://bni-konfirmasi.cf/login",
        "http://paypal-resolve.tk/confirm", "http://netflix-billing.ga/payment",
        "http://gojek-promo.tk/free",
    ])
    legit_companies = [
        "PT Bank Central Asia Tbk", "PT Bank Mandiri Tbk",
        "PT Bank Negara Indonesia Tbk", "Lodaya Teknologi Indonesia",
        "Netflix Indonesia", "PayPal Indonesia",
    ]
    legit_company = RNG.choice(legit_companies)
    spoofed_domain = RNG.choice(["bca.co.id", "mandiri.co.id", "lodaya.id"]).replace(".", "-") + RNG.choice([".tk", ".ml", ".ga", ".cf", ".xyz"])
    sender_email = f"noreply@{spoofed_domain}"

    templates = [
        f"Kami mendeteksi aktivitas mencurigakan. Verifikasi: {link}\n\n{legit_company}",
        f"Akun Anda akan diblokir. Segera perbarui data:\n{link}\n\nTim Keamanan {legit_company}",
        f"Dear Customer,\nYour account has been limited. Restore access:\n{link}\n\nSecurity Team",
        f"PEMBERITAHUAN: Update sistem. Verifikasi wajib:\n{link}\n\nManagement {legit_company}",
    ]
    body = RNG.choice(templates).format(legit_company=legit_company)
    subject = RNG.choice(["SEGERA! Akun Anda Akan Diblokir", "Verifikasi Akun - 24 Jam",
                          "Your Account Has Been Compromised", "Urgent: Verify Now"])
    extra_links = [link]
    if RNG.random() < 0.3:
        extra_links.append(RNG.choice(["https://www.bca.co.id", "https://www.lodaya.id/help"]))
    return build_eml(subject, body, legit_company, sender_email, to_name, to_email,
                     links=extra_links, category="phishing")

def generate_malware_email(idx):
    name = random_name()
    to_name = random_name()
    to_email = random_email(to_name)
    ref = generate_ref()
    filenames = [
        f"Invoice_{ref}.exe", f"Kontrak_{ref}.vbs", f"Laporan_{datetime.now().strftime('%B')}.js",
        f"Dokumen_{ref}.docm", f"Update_Keamanan_{ref}.exe",
    ]
    filename = RNG.choice(filenames)
    payload = RNG.randbytes(RNG.randint(256, 2048))
    part = MIMEBase("application", "octet-stream")
    part.set_payload(payload)
    part.add_header("Content-Disposition", "attachment", filename=filename)
    part.add_header("Content-Type", "application/octet-stream", name=filename)

    templates = [
        f"Yth. {to_name},\n\nBersama ini invoice #{ref} terlampir. Mohon segera dibayarkan.\n\nFinance Department",
        f"Dear {to_name},\n\nPlease find the contract document attached. Your signature is required.\n\nLegal Team",
        f"Hi {to_name},\n\nHere is the weekly report. I've attached the updated file.\n\nBest,\n{name}",
        f"Update Sistem - Critical Patch\n\nSilakan jalankan file update berikut.\n\nTim IT",
    ]
    body = RNG.choice(templates)
    subject = RNG.choice([f"Fwd: Invoice #{ref}", f"Dokumen Kontrak #{ref}",
                          f"Update Sistem - Critical Patch", "Package Tracking #{ref}"])
    return build_eml(subject, body, name, random_email(name), to_name, to_email,
                     attachments=[part], category="malware")

def generate_bec_email(idx):
    """Generate Business Email Compromise (CEO fraud) email."""
    to_name = random_name()
    to_email = random_email(to_name)
    ceo_name = random_name()
    ceo_last = ceo_name.split()[-1]
    ceo_email = random_email(ceo_name)
    vendor = RNG.choice(BEC_VENDORS)
    bank = RNG.choice(BEC_BANKS)
    amount = generate_amount(10000000, 5000000000)
    account = "".join(RNG.choices(string.digits, k=10))
    routing = "".join(RNG.choices(string.digits, k=9))
    swift = "".join(RNG.choices(string.ascii_uppercase, k=8))
    ref = generate_ref()
    deal_type = RNG.choice(BEC_DEAL_TYPES)
    gift_cards_amount = RNG.choice(["$500", "$1,000", "$2,000", "$5,000"])
    store = RNG.choice(["Best Buy", "Walmart", "Target", "Amazon"])
    account_info = BEC_ACCOUNT_INFO.format(vendor=vendor, bank=bank, account=account, routing=routing, swift=swift)

    template = RNG.choice(BEC_TEMPLATES)
    body = template.format(
        name=to_name, ceo_name=ceo_name, ceo_last=ceo_last,
        amount=amount, vendor=vendor, bank=bank, account=account,
        routing=routing, swift=swift, ref=ref, deal_type=deal_type,
        account_info=account_info, gift_cards_amount=gift_cards_amount,
        store=store,
    )
    subject = RNG.choice(BEC_SUBJECTS).format(
        ref=ref, vendor=vendor, ceo_name=ceo_name, ceo_last=ceo_last,
    )

    return build_eml(subject, body, ceo_name, ceo_email, to_name, to_email,
                     category="bec")

# ─── Main ──────────────────────────────────────────────────────────────

GENERATORS = {
    "transaksi": generate_transaction_email,
    "cs": generate_cs_email,
    "internal": generate_internal_email,
    "spam": generate_spam_email,
    "phishing": generate_phishing_email,
    "malware": generate_malware_email,
    "bec": generate_bec_email,
}

LABEL_MAP = {
    "transaksi": "ham",
    "cs": "ham",
    "internal": "ham",
    "spam": "spam",
    "phishing": "phishing",
    "malware": "malware",
    "bec": "phishing",  # BEC is a type of phishing
}


def generate_extended(output_dir, counts):
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    total = 0
    total_target = sum(counts.values())

    for category, count in counts.items():
        gen_func = GENERATORS.get(category)
        if not gen_func:
            print(f"  Unknown category: {category}, skipping")
            continue
        cat_dir = output / category
        cat_dir.mkdir(parents=True, exist_ok=True)
        print(f"\n{'='*50}")
        print(f"{category} -> generating {count} emails...")
        for i in range(count):
            try:
                eml_content = gen_func(i)
                content_hash = hashlib.sha256(eml_content.encode()).hexdigest()[:16]
                filename = f"{category}_{i+1:04d}_{content_hash}.eml"
                (cat_dir / filename).write_text(eml_content, encoding="utf-8")
                total += 1
                if (i + 1) % 2000 == 0:
                    print(f"  {i+1}/{count}...")
            except Exception as e:
                print(f"  ERROR at {category}[{i}]: {e}")
        print(f"  [OK] {count} {category} emails done")

    print(f"\n{'='*50}")
    print(f"GENERATION COMPLETE: {total} emails ({total_target} target)")
    print(f"Output: {output}")
    return total


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate extended dataset")
    parser.add_argument("--output", default="data/dataset_merged/_extended")
    parser.add_argument("--transaksi", type=int, default=12000)
    parser.add_argument("--cs", type=int, default=8000)
    parser.add_argument("--internal", type=int, default=10000)
    parser.add_argument("--spam", type=int, default=12000)
    parser.add_argument("--phishing", type=int, default=12000)
    parser.add_argument("--malware", type=int, default=10000)
    parser.add_argument("--bec", type=int, default=9942)
    args = parser.parse_args()

    counts = {
        "transaksi": args.transaksi,
        "cs": args.cs,
        "internal": args.internal,
        "spam": args.spam,
        "phishing": args.phishing,
        "malware": args.malware,
        "bec": args.bec,
    }
    target = sum(counts.values())
    print(f"Extended Dataset Generator (target: {target} emails)")
    print(f"Distribution:")
    for k, v in counts.items():
        print(f"  {k}: {v}")
    print()
    total = generate_extended(args.output, counts)

    # Write summary
    summary_path = Path(args.output) / "_generation_summary.txt"
    summary_path.write_text(
        f"Extended Dataset Generation Summary\n"
        f"Generated: {total} emails\n"
        f"Target:    {target}\n"
        f"Date:      {datetime.now().isoformat()}\n"
    )
    print(f"Summary written to {summary_path}")
