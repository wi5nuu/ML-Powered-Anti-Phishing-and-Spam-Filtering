"""
Seed script for CogniMail — mengisi database dengan data realistis:
- 3 organisasi
- 9 user (3 per org)
- 3 admin mailbox per org
- 500+ quarantine emails (CLEAN, WARN, QUARANTINE) dengan berbagai kategori
- audit_logs (login, view, release, delete)
- audit_trail (admin actions)
- pipeline_metrics
"""

import os
import sys
import uuid
import json
import random
import hashlib
from datetime import datetime, timedelta

# Allow import from project root (works both in Docker /app and local checkout)
_project_root = os.path.dirname(os.path.abspath(__file__))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from database.models import (
    Organization, User, AdminMailbox, QuarantineEmail,
    AuditLog, PipelineMetrics, UserRole,
)
from dashboard.database import SessionLocal
from dashboard.auth import hash_password

# ── helpers ──────────────────────────────────────────────────────────────────

def rand_dt(days_ago_max=90, days_ago_min=0):
    from datetime import timezone
    delta = timedelta(
        days=random.randint(days_ago_min, days_ago_max),
        hours=random.randint(0, 23),
        minutes=random.randint(0, 59),
        seconds=random.randint(0, 59),
    )
    return datetime.now(timezone.utc) - delta

def rand_ip():
    pools = [
        # known malicious-looking IPs
        ["185.220.101.{}", "45.142.212.{}", "91.108.4.{}", "103.75.190.{}"],
        # normal office IPs
        ["192.168.1.{}", "10.0.0.{}", "172.16.0.{}"],
    ]
    pool = random.choice(pools)
    return random.choice(pool).format(random.randint(1, 254))

def fake_hash(text):
    return hashlib.sha256(text.encode()).hexdigest()[:64]

# ── email templates ───────────────────────────────────────────────────────────

PHISHING_SUBJECTS = [
    "Verify your account immediately - action required",
    "Your PayPal account has been limited",
    "Unusual sign-in activity on your Microsoft account",
    "URGENT: Your bank account will be suspended",
    "Action required: Confirm your Apple ID",
    "Your password expires today - click to renew",
    "BRI: Transaksi mencurigakan terdeteksi",
    "Mandiri: Verifikasi akun Anda sekarang",
    "Netflix: Payment failed - update billing info",
    "DHL: Your package is on hold - pay customs fee",
    "Security Alert: New login from unknown device",
    "Your cloud storage is almost full - upgrade now",
    "RE: Invoice #INV-2024-8821 payment overdue",
    "Tokopedia: Akun Anda terdeteksi aktivitas tidak wajar",
    "GOTO: Konfirmasi nomor HP Anda",
]

MALWARE_SUBJECTS = [
    "Invoice_Q4_2024.pdf.exe",
    "Resume_Application.docm",
    "PO-2024-00891.zip",
    "Payment_receipt_scan.iso",
    "Salary_increase_letter.xlsm",
    "NDA_document_final.doc",
    "Meeting_recording_2024.mp4.bat",
    "Software_update_patch.msi",
    "Contract_signed_copy.pdf",
    "HR_announcement_November.pptm",
]

SPAM_SUBJECTS = [
    "You've been selected! Claim your prize",
    "Cheap Rx medications - no prescription needed",
    "Make $5000/week working from home",
    "Hot singles in your area - click here",
    "Lose 20kg in 2 weeks - guaranteed",
    "FREE iPhone 16 Pro Max - limited offer",
    "Invest now: 300% returns in 30 days",
    "Enlargement pills - HUGE discounts",
    "Nigerian Prince needs your help - $10M transfer",
    "Congratulations! You are our lucky winner",
    "PROMO: Beli 1 gratis 10, hari ini saja!",
    "Pinjaman online cair 5 menit tanpa jaminan",
    "Obat kuat pria - diskon 70%",
]

CLEAN_SUBJECTS = [
    "Q3 Financial Report - Attached",
    "Team sync meeting - tomorrow 10am",
    "Welcome to the team, {}!",
    "Monthly newsletter - October 2024",
    "Your order has been shipped",
    "Meeting notes from last week",
    "Project Gemini - kickoff agenda",
    "Reminder: Submit timesheet by Friday",
    "New employee onboarding schedule",
    "IT Maintenance window - Saturday night",
    "Security awareness training reminder",
    "Budget approval for Q4 initiatives",
    "Happy Birthday from the team!",
    "Annual performance review schedule",
    "Updated company policy handbook",
]

PHISHING_BODIES = [
    """Dear Customer,

We have detected unusual activity on your account. Your account has been temporarily limited.
To restore access, please verify your information immediately:

Click here: http://secure-paypa1-verify.tk/login

Failure to verify within 24 hours will result in permanent suspension.

PayPal Security Team""",

    """Dear User,

Your Microsoft account shows a sign-in from:
Location: Russia (Moscow)
IP: 185.220.101.47
Time: {time}

If this wasn't you, click below to secure your account:
http://microsoft-account-security.xyz/verify?token={token}

Microsoft Account Team""",

    """Yth. Nasabah BRI,

Kami mendeteksi transaksi mencurigakan senilai Rp 15.000.000 dari akun Anda.
Segera konfirmasi melalui tautan berikut dalam 1x24 jam:

http://bri-online-secure.co/konfirmasi?id={token}

Jika tidak dikonfirmasi, akun Anda akan diblokir sementara.

Tim Keamanan BRI""",
]

MALWARE_BODIES = [
    """Please find attached the invoice for services rendered in Q4 2024.
Total amount: $12,450.00
Due date: 30 days from receipt

Please review and process payment at your earliest convenience.

[ATTACHMENT: Invoice_Q4_2024.pdf.exe - 2.4MB]""",

    """Hi,

I'm applying for the Senior Developer position. Please find my resume attached.
I have 8 years of experience in enterprise software development.

Best regards,
[ATTACHMENT: Resume_Application.docm - 1.1MB]""",

    """Dear HR Team,

Please find the updated salary structure document attached.
This contains the new compensation bands for 2025.

[ATTACHMENT: Salary_increase_letter.xlsm - 856KB]""",
]

SPAM_BODIES = [
    """CONGRATULATIONS!!!

You have been SELECTED as our LUCKY WINNER!
Prize: $50,000 cash + iPhone 16 Pro Max

To claim: Reply with your full name, address, and bank account number.
Offer expires in 24 HOURS!

Lucky Draw International Ltd.""",

    """Make money from home - GUARANTEED!

Our proven system earns $5,000-$10,000 per WEEK.
No experience needed. Start TODAY!

Click: http://easy-money-now.biz/start

P.S. Over 10,000 members already earning!""",

    """PROMO SPESIAL HARI INI SAJA!!!

Pinjaman online CAIR 5 MENIT
- Tanpa jaminan
- Tanpa BI checking
- Bunga 0% bulan pertama

Daftar sekarang: WA 0812-XXXX-XXXX""",
]

CLEAN_BODIES = [
    """Hi team,

Please find attached the Q3 financial report for your review.
Key highlights:
- Revenue: $2.4M (up 18% YoY)
- EBITDA margin: 24%
- Headcount: 87 FTE

Let me know if you have questions.

Best,
Finance Team""",

    """Hi {},

Just a reminder that we have our weekly team sync tomorrow at 10am.
Agenda:
1. Sprint review
2. Blockers
3. Planning for next week

Zoom link: https://zoom.us/j/internal-meeting

See you there!""",

    """Dear All,

IT will be performing scheduled maintenance this Saturday from 10pm to 2am.
The following services will be unavailable:
- Email (brief interruption ~5 min)
- VPN
- Internal wiki

Please save your work before the maintenance window.

IT Operations""",
]

PHISHING_SENDERS = [
    "security@paypa1-verify.tk", "noreply@microsoft-account-security.xyz",
    "alert@bri-online-secure.co", "support@app1e-id-verify.com",
    "billing@netfl1x-payment.ru", "admin@dhl-customs-fee.biz",
    "no-reply@tokopedia-security.xyz", "support@goto-konfirmasi.tk",
    "security@mandiri-online-verify.co", "alert@gmai1-security.net",
]

MALWARE_SENDERS = [
    "invoice@supplier-corp.ru", "hr@company-hr-dept.com",
    "accounts@billing-system.xyz", "noreply@docusign-secure.biz",
    "payroll@finance-dept.co", "recruitment@job-portal.tk",
    "it-support@helpdesk-ticket.xyz", "contracts@legal-dept.biz",
]

SPAM_SENDERS = [
    "promo@lucky-winner-intl.com", "offer@easy-money-system.biz",
    "deals@cheap-meds-online.ru", "winner@lottery-international.tk",
    "info@work-from-home-guru.com", "promo@pinjaman-cepat.biz",
    "offers@diet-pills-cheap.com", "contact@adult-dating-site.xyz",
]

CLEAN_SENDERS_TEMPLATES = [
    "finance@{domain}", "hr@{domain}", "it@{domain}",
    "noreply@{domain}", "notifications@{domain}", "team@{domain}",
    "support@{domain}", "admin@{domain}",
]

CATEGORIES = {
    "QUARANTINE": ["phishing", "malware", "ransomware", "credential_harvesting", "business_email_compromise"],
    "WARN":       ["spam", "suspicious_link", "lookalike_domain", "bulk_marketing"],
    "CLEAN":      ["legitimate", "internal", "newsletter", "transactional"],
}

SHAP_TEMPLATE = {
    "base_value": 0.0,
    "output_value": 0.0,
    "feature_names": ["url_count", "suspicious_keywords", "sender_reputation", "html_ratio", "attachment_count"],
    "shap_values": [],
    "features": {},
}

def make_shap(label):
    if label == "QUARANTINE":
        shap_values = [round(random.uniform(0.1, 0.4), 3) for _ in range(5)]
        output_value = round(random.uniform(0.75, 0.98), 3)
    elif label == "WARN":
        shap_values = [round(random.uniform(-0.1, 0.25), 3) for _ in range(5)]
        output_value = round(random.uniform(0.45, 0.74), 3)
    else:
        shap_values = [round(random.uniform(-0.3, 0.05), 3) for _ in range(5)]
        output_value = round(random.uniform(0.02, 0.35), 3)

    feature_names = SHAP_TEMPLATE["feature_names"]
    return json.dumps({
        "base_value": round(random.uniform(-0.2, 0.2), 3),
        "output_value": output_value,
        "feature_names": feature_names,
        "shap_values": shap_values,
        "features": {name: round(random.uniform(0, 1), 2) for name in feature_names},
    })

def make_xai(label, category):
    reasons = {
        "phishing": "Email contains credential harvesting links mimicking legitimate financial institutions. Sender domain registered < 7 days ago.",
        "malware": "Attachment contains macro-enabled Office document with obfuscated VBA code. High probability of dropper payload.",
        "ransomware": "Attachment hash matches known ransomware signature. JavaScript redirect to C2 server detected.",
        "credential_harvesting": "HTML form action points to external domain. Login fields present with suspicious POST endpoint.",
        "business_email_compromise": "Display name spoofs CEO. Sender domain differs from legitimate corporate domain by one character.",
        "spam": "Message contains bulk marketing indicators. Unsubscribe link leads to data harvesting page.",
        "suspicious_link": "URL uses URL shortener redirecting to flagged domain. TLS certificate issued today.",
        "lookalike_domain": "Sender domain uses homoglyph attack (e.g., rn→m). Visual similarity score: 94%.",
        "bulk_marketing": "Message sent to >500 recipients. Contains tracking pixel. Opt-out mechanism non-compliant.",
        "legitimate": "No threat indicators detected. Sender domain verified, SPF/DKIM/DMARC passed.",
        "internal": "Internal email. Sender and recipient share same organization domain.",
        "newsletter": "Legitimate newsletter with valid unsubscribe mechanism and verified sender reputation.",
        "transactional": "Transactional email from verified service provider. No malicious content detected.",
    }
    return reasons.get(category, "Analysis completed. Confidence score within normal parameters.")

def make_routing(label, category):
    if label == "QUARANTINE":
        return f"Blocked: {category.replace('_',' ').title()} detected. ML confidence > 85%. Moved to quarantine."
    elif label == "WARN":
        return f"Warning: {category.replace('_',' ').title()} indicators present. Delivered with warning banner."
    else:
        return "Delivered: No threat indicators detected. All authentication checks passed."

def make_attachments(label, category):
    if label == "QUARANTINE" and category == "malware":
        files = [
            {"filename": random.choice(["invoice.pdf.exe","resume.docm","report.xlsm","patch.msi","update.bat"]),
             "size": random.randint(50000, 5000000),
             "mime": "application/octet-stream",
             "sha256": fake_hash(str(random.random())),
             "malicious": True}
        ]
        return json.dumps(files)
    elif label == "QUARANTINE" and category == "ransomware":
        files = [
            {"filename": "decrypt_instructions.zip",
             "size": random.randint(100000, 2000000),
             "mime": "application/zip",
             "sha256": fake_hash(str(random.random())),
             "malicious": True}
        ]
        return json.dumps(files)
    return json.dumps([])

# ── main seed ─────────────────────────────────────────────────────────────────

def seed():
    db = SessionLocal()
    try:
        print("Starting seed...")

        # ── 1. Organizations ──────────────────────────────────────────────────
        orgs_data = [
            {"name": "PT Teknologi Nusantara", "domain": "teknologi-nusantara.id"},
            {"name": "Bank Maju Bersama",       "domain": "bankmajubersama.co.id"},
            {"name": "Universitas Digital Indonesia", "domain": "udi.ac.id"},
        ]
        orgs = []
        for o in orgs_data:
            org = db.query(Organization).filter(Organization.name == o["name"]).first()
            if not org:
                org = Organization(name=o["name"])
                db.add(org)
                db.flush()
            orgs.append((org, o["domain"]))
        db.commit()
        print(f"  Organizations: {len(orgs)}")

        # ── 2. Users (3 per org) ──────────────────────────────────────────────
        users_seed = [
            # org 0 - PT Teknologi Nusantara
            {"username": "budi.santoso",  "email": "budi.santoso@teknologi-nusantara.id",  "org_idx": 0},
            {"username": "siti.rahayu",   "email": "siti.rahayu@teknologi-nusantara.id",   "org_idx": 0},
            {"username": "andi.firmansyah","email":"andi.firmansyah@teknologi-nusantara.id","org_idx": 0},
            # org 1 - Bank Maju Bersama
            {"username": "dewi.kusuma",   "email": "dewi.kusuma@bankmajubersama.co.id",    "org_idx": 1},
            {"username": "rizky.pratama", "email": "rizky.pratama@bankmajubersama.co.id",  "org_idx": 1},
            {"username": "nisa.wulandari","email": "nisa.wulandari@bankmajubersama.co.id", "org_idx": 1},
            # org 2 - Universitas Digital Indonesia
            {"username": "fajar.hidayat", "email": "fajar.hidayat@udi.ac.id",              "org_idx": 2},
            {"username": "mega.lestari",  "email": "mega.lestari@udi.ac.id",               "org_idx": 2},
            {"username": "hendra.wijaya", "email": "hendra.wijaya@udi.ac.id",              "org_idx": 2},
        ]
        created_users = []
        for u in users_seed:
            user = db.query(User).filter(User.username == u["username"]).first()
            if not user:
                org, domain = orgs[u["org_idx"]]
                user = User(
                    username=u["username"],
                    email=u["email"],
                    hashed_password=hash_password("Pass@1234"),
                    role=UserRole.USER.value,
                    organization_id=org.id,
                    is_active=True,
                    created_at=rand_dt(180, 30),
                )
                db.add(user)
            created_users.append((u, orgs[u["org_idx"]]))
        db.commit()
        print(f"  Users: {len(users_seed)}")

        # ── 3. Admin Mailboxes ────────────────────────────────────────────────
        mailbox_count = 0
        for org, domain in orgs:
            for box_name in ["inbox", "security-alerts", "it-support"]:
                address = f"{box_name}@{domain}"
                exists = db.query(AdminMailbox).filter(AdminMailbox.email == address).first()
                if not exists:
                    mb = AdminMailbox(
                        email=address,
                        domain=domain,
                        sender_name=f"{box_name.replace('-',' ').title()} - {org.name}",
                        created_by="super",
                        is_active=True,
                        created_at=rand_dt(90, 60),
                    )
                    db.add(mb)
                    mailbox_count += 1
        db.commit()
        print(f"  Mailboxes: {mailbox_count}")

        # ── 4. Quarantine Emails ──────────────────────────────────────────────
        # Distribution: CLEAN 50%, WARN 25%, QUARANTINE 25%
        EMAIL_COUNT = 600
        DIST = [
            ("CLEAN",      0.50),
            ("WARN",       0.25),
            ("QUARANTINE", 0.25),
        ]

        email_records = []
        for _ in range(EMAIL_COUNT):
            roll = random.random()
            if roll < 0.50:
                label = "CLEAN"
            elif roll < 0.75:
                label = "WARN"
            else:
                label = "QUARANTINE"

            category = random.choice(CATEGORIES[label])
            org, domain = random.choice(orgs)

            # Scores by label
            if label == "QUARANTINE":
                fused    = round(random.uniform(0.75, 0.99), 4)
                ml_prob  = round(random.uniform(0.72, 0.98), 4)
                sa_score = round(random.uniform(8.0,  25.0), 2)
                anomaly  = round(random.uniform(0.6,  0.95), 4)
                spf      = random.choice(["fail", "softfail", "none"])
                dkim     = random.choice(["fail", "none"])
                dmarc    = random.choice(["fail", "none"])
                status   = random.choice(["quarantined", "quarantined", "released"])
            elif label == "WARN":
                fused    = round(random.uniform(0.40, 0.74), 4)
                ml_prob  = round(random.uniform(0.35, 0.70), 4)
                sa_score = round(random.uniform(3.5,  7.9),  2)
                anomaly  = round(random.uniform(0.2,  0.59), 4)
                spf      = random.choice(["pass", "softfail", "none"])
                dkim     = random.choice(["pass", "fail"])
                dmarc    = random.choice(["pass", "none"])
                status   = "delivered"
            else:
                fused    = round(random.uniform(0.01, 0.35), 4)
                ml_prob  = round(random.uniform(0.01, 0.30), 4)
                sa_score = round(random.uniform(0.0,  3.4),  2)
                anomaly  = round(random.uniform(0.0,  0.19), 4)
                spf      = "pass"
                dkim     = "pass"
                dmarc    = "pass"
                status   = "delivered"

            # Sender
            if label == "QUARANTINE":
                if category in ("phishing", "credential_harvesting", "business_email_compromise"):
                    sender = random.choice(PHISHING_SENDERS)
                    subject = random.choice(PHISHING_SUBJECTS)
                    body = random.choice(PHISHING_BODIES).format(
                        time=datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
                        token=uuid.uuid4().hex[:16]
                    )
                else:
                    sender = random.choice(MALWARE_SENDERS)
                    subject = random.choice(MALWARE_SUBJECTS)
                    body = random.choice(MALWARE_BODIES)
            elif label == "WARN":
                if category in ("spam", "bulk_marketing"):
                    sender = random.choice(SPAM_SENDERS)
                    subject = random.choice(SPAM_SUBJECTS)
                    body = random.choice(SPAM_BODIES)
                else:
                    sender = random.choice(PHISHING_SENDERS)
                    subject = random.choice(PHISHING_SUBJECTS)
                    body = random.choice(PHISHING_BODIES).format(
                        time=datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
                        token=uuid.uuid4().hex[:16]
                    )
            else:
                sender_tpl = random.choice(CLEAN_SENDERS_TEMPLATES)
                sender = sender_tpl.format(domain=domain)
                subject = random.choice(CLEAN_SUBJECTS).format("New Employee")
                body = random.choice(CLEAN_BODIES).format("Team")

            # Recipient: pick random user from same org
            org_users = [u for u, (ud, od) in zip(users_seed, created_users) if od[0].id == org.id]
            if org_users:
                recipient = org_users[0]["email"]
            else:
                recipient = f"user@{domain}"

            created_dt = rand_dt(90, 0)
            email_id   = uuid.uuid4().hex

            raw = f"From: {sender}\nTo: {recipient}\nSubject: {subject}\n\n{body}"

            rec = QuarantineEmail(
                email_id         = email_id,
                received_at      = created_dt.strftime("%Y-%m-%d %H:%M:%S"),
                label            = label,
                fused_score      = fused,
                sa_score         = sa_score,
                ml_probability   = ml_prob,
                anomaly_score    = anomaly,
                shap_json        = make_shap(label),
                xai_summary      = make_xai(label, category),
                routing_reason   = make_routing(label, category),
                raw_content_hash = fake_hash(raw),
                raw_content      = raw,
                attachments_json = make_attachments(label, category),
                spf_result       = spf,
                dkim_result      = dkim,
                dmarc_result     = dmarc,
                status           = status,
                is_read          = random.choice([True, True, False]),
                deleted_at       = None,
                category         = category,
                subject          = subject,
                sender           = sender,
                recipient_list   = recipient,
                organization_id  = org.id,
                model_version    = random.choice(["v2.1.0", "v2.2.0", "v2.3.0"]),
                created_at       = created_dt,
            )
            email_records.append(rec)

        db.bulk_save_objects(email_records)
        db.commit()
        print(f"  Quarantine emails: {len(email_records)}")

        # ── 5. Audit Logs ─────────────────────────────────────────────────────
        all_users = ["super", "admin", "budi.santoso", "siti.rahayu", "dewi.kusuma", "rizky.pratama", "fajar.hidayat"]
        actions_pool = ["login", "view_email", "release_email", "delete_email", "export_report",
                        "login_failed", "change_password", "create_user", "deactivate_user"]

        audit_records = []
        for _ in range(300):
            user = random.choice(all_users)
            action = random.choice(actions_pool)
            audit_records.append(AuditLog(
                user       = user,
                action     = action,
                email_id   = uuid.uuid4().hex if "email" in action else None,
                ip_address = rand_ip(),
                details    = f"Action '{action}' performed by {user}",
                created_at = rand_dt(60, 0),
            ))

        db.bulk_save_objects(audit_records)
        db.commit()
        print(f"  Audit logs: {len(audit_records)}")

        # ── 6. Pipeline Metrics ───────────────────────────────────────────────
        metrics_records = []
        for i in range(90):
            dt    = datetime.utcnow() - timedelta(days=i)
            total = random.randint(50, 250)
            warn  = random.randint(10, 60)
            quar  = random.randint(5, 40)
            clean = max(total - warn - quar, 0)
            fp    = random.randint(0, 5)

            metrics_records.append(PipelineMetrics(
                date                 = dt.strftime("%Y-%m-%d"),
                total_processed      = total,
                total_clean          = clean,
                total_warn           = warn,
                total_quarantine     = quar,
                false_positive_count = fp,
                avg_latency_ms       = round(random.uniform(120, 890), 1),
                model_version        = random.choice(["v2.1.0", "v2.2.0", "v2.3.0"]),
                created_at           = dt,
            ))

        db.bulk_save_objects(metrics_records)
        db.commit()
        print(f"  Pipeline metrics: {len(metrics_records)} days")

        print("\nSeed completed successfully!")

        # ── Summary ───────────────────────────────────────────────────────────
        from sqlalchemy import func as sqlfunc
        counts = {}
        for tbl_name, model in [
            ("organizations",    Organization),
            ("users",            User),
            ("admin_mailboxes",  AdminMailbox),
            ("quarantine_emails",QuarantineEmail),
            ("audit_logs",       AuditLog),
            ("pipeline_metrics", PipelineMetrics),
        ]:
            counts[tbl_name] = db.query(sqlfunc.count(model.id)).scalar()

        print("\nFinal row counts:")
        for tbl, cnt in counts.items():
            print(f"  {tbl:<25} {cnt}")

    except Exception as e:
        db.rollback()
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    seed()
