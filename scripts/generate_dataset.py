"""
Enterprise Email Dataset Generator — LTI Anti-Phishing Project
=============================================================
Generates 15,000 realistic .eml files across 5 people:
  - chris  (3,000): Transaction + Customer Service emails
  - ilham  (3,000): Internal Document + B2B emails
  - brian  (3,000): Spam emails
  - wisnu  (3,000): Phishing emails
  - risly  (3,000): Malware emails

Each email has:
  - Proper RFC 2822 headers
  - Multipart MIME (text/plain + text/html)
  - Embedded links, images, and attachments
  - Realistic sender/recipient names
  - Indonesian & English content mix
  - Varied length, structure, and formatting

Usage:
  python scripts/generate_dataset.py [--count 3000] [--output data/dataset]

(c) 2026 LTI Anti-Phishing — Final Project
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
from typing import Optional

# ─── Seed for reproducibility ──────────────────────────────────────────────
RNG = random.Random(42)

# ─── Indonesian names ──────────────────────────────────────────────────────
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

SUBJECTS_TRANSACTION = [
    "Konfirmasi Pembayaran #{ref}",
    "Invoice #{ref} — Pembayaran Diterima",
    "Notifikasi Transfer Masuk Rp{amount:,}",
    "Tagihan Bulanan #{ref} — Lunas",
    "Struk Pembayaran #{ref}",
    "Pembayaran Berhasil — {service}",
    "Ringkasan Transaksi #{ref}",
    "Bukti Transfer — {amount_formatted}",
    "Pembayaran Tagihan {month} — Sukses",
    "Konfirmasi Order #{ref}",
    "Invoice Bulanan — {company}",
    "Notifikasi Pembayaran Otomatis",
    "Pembayaran Anda Telah Diverifikasi",
    "Riwayat Transaksi #{ref}",
    "Receipt #{ref} — Payment Confirmed",
    "Monthly Statement — {month} {year}",
    "Transaction Alert — {amount_formatted}",
    "Payment Received — Thank You",
    "Your Invoice #{ref} Is Ready",
    "Order #{ref} — Payment Successful",
]

SUBJECTS_CUSTOMER_SERVICE = [
    "Respon Tiket #{ticket} — {status}",
    "Pertanyaan Anda #{ticket} — Telah Dijawab",
    "Update Laporan #{ticket}",
    "Konfirmasi Penerimaan Keluhan #{ticket}",
    "Solusi untuk Masalah #{ticket}",
    "Tiket #{ticket} — Butuh Informasi Tambahan",
    "Permintaan Anda #{ticket} — Selesai",
    "Informasi Akun — {service}",
    "Verifikasi Data Nasabah #{ref}",
    "Pemberitahuan Perubahan Kebijakan",
    "Kami Membantu Anda — Tiket #{ticket}",
    "Tanggapan CS — #{ticket}",
    "FAQ: {topic}",
    "Panduan Penggunaan {service}",
    "Notifikasi Akun — Update Profil",
    "Survey Kepuasan — Tiket #{ticket}",
    "Your Support Ticket #{ticket} Has Been Updated",
    "Case #{ticket} — Resolution Provided",
    "Account Update — Action Required",
    "Service Feedback Request — Ticket #{ticket}",
]

SUBJECTS_INTERNAL = [
    "Rapat {topic} — {date}",
    "Notulensi Rapat #{meeting}",
    "Memo Internal: {topic}",
    "Proyek {project} — Update Mingguan",
    "Laporan {month} — Divisi {division}",
    "Dokumen Kontrak — {partner}",
    "Proposal B2B — {client}",
    "Approval Request — #{ref}",
    "Pengumuman: {topic}",
    "Budget {year} — {division}",
    "HR Announcement: {topic}",
    "Data Karyawan — Update {month}",
    "Vendor {vendor} — Evaluation Report",
    "Collaboration Proposal — {partner}",
    "Internal Memo: {topic}",
    "Quarterly Review — Q{q} {year}",
    "Minutes of Meeting — #{meeting}",
    "Contract Renewal — {partner}",
    "B2B Partnership — {client} Update",
    "Security Bulletin — {month} {year}",
]

SUBJECTS_SPAM = [
    "SELAMAT! Anda Memenangkan {prize}!",
    "DAPATKAN Rp{amount:,} SEKARANG!",
    "Penawaran Spesial — Diskon 90%!",
    "Anda Terpilih! Klik di Sini",
    "RESMI: Anda Pemenang Undian #{ref}",
    "Kartu Kredit Anda Disetujui!",
    "Rp{amount:,} — Cairkan Sekarang!",
    "INVESTASI: Return 500% dalam 30 Hari",
    "Berat Badan Turun 10kg dalam 1 Minggu!",
    "Lowongan Kerja — Gaji Rp{amount:,}/bulan",
    "PINJAMAN TANPA JAMINAN — CAIRKAN!",
    "Obat Kuat Alami — Pesan Sekarang",
    "Pasangan Idaman Menanti Anda!",
    "Bisnis Online — Rp{amount:,}/hari",
    "VPN Gratis — Buka Semua Situs",
    "Nonton Film Dewasa Gratis!",
    "YOU WON! Claim Your {prize} Now!",
    "ACT NOW! Limited Time Offer",
    "Congratulations! You Are Our Lucky Winner",
    "Earn {amount_formatted} Per Day — Work From Home!",
]

SUBJECTS_PHISHING = [
    "SEGERA! Akun Anda Akan Diblokir",
    "Verifikasi Akun — 24 Jam Terakhir",
    "Pembayaran Gagal — Perbarui Data",
    "Kartu ATM Anda Diblokir Sementara",
    "INFORMASI PENTING — Akun Ditangguhkan",
    "Pendeteksian Aktivitas Mencurigakan",
    "Password Akan Kedaluwarsa — Perbarui",
    "Konfirmasi Data Nasabah — BCA",
    "Notifikasi Keamanan — Login Baru",
    "Rekening Anda Dibatukan Sementara",
    "Update Sistem — Verifikasi Wajib",
    "Pemberitahuan Penting dari Lodaya",
    "Reset Password — Segera Konfirmasi",
    "Invoice Menunggak — Segera Bayar",
    "Konfirmasi Pengiriman Paket — Data Dibutuhkan",
    "Urgent: Account Verification Required",
    "Your Account Has Been Compromised",
    "Suspicious Login Attempt — Verify Now",
    "Payment Declined — Update Billing Info",
    "DocuSign: Document Requires Your Signature",
]

SUBJECTS_MALWARE = [
    "Fwd: Invoice #{ref} — Segera Dibayar",
    "Dokumen Kontrak #{ref} — Tanda Tangan",
    "File Penting — #{ref}",
    "RE: Laporan Keuangan {month}",
    "Update Sistem — Eksekusi File",
    "Package Tracking — #{tracking}",
    "Your Resume — Job Application #{ref}",
    "Foto Acara — {event}",
    "Dokumen Proyek #{ref} — Revisi Final",
    "Notula Rapat #{meeting} — Terlampir",
    "Software Update — Critical Patch",
    "Shared Document: {project} Proposal",
    "Fw: Data Karyawan {month} {year}",
    "Security Patch — Immediate Action Required",
    "Tax Document #{ref} — Review Needed",
    "UPS Tracking — Delivery #{tracking}",
    "Archived Records — {year}",
    "Presentation — Q{q} Review",
    "Scanned Document — #{ref}",
    "Payment Confirmation — #{ref} (attachment)",
]

TRANSACTION_TEMPLATES = [
    "Kepada Yth. {name},\n\nKami informasikan bahwa pembayaran Anda sebesar Rp{amount:,} untuk {service} telah kami terima.\n\nDetail Transaksi:\n- Nomor Referensi: {ref}\n- Tanggal: {date}\n- Jumlah: Rp{amount:,}\n- Metode: {method}\n- Status: BERHASIL\n\nTerima kasih telah menggunakan layanan kami.\n\nHormat kami,\n{company}",
    "Dear {name},\n\nYour payment of Rp{amount:,} for {service} has been successfully processed.\n\nTransaction Details:\n- Reference: {ref}\n- Date: {date}\n- Amount: Rp{amount:,}\n- Payment Method: {method}\n- Status: COMPLETED\n\nThank you for your business.\n\nBest regards,\n{company}",
    "Yth. {name},\n\nBerikut adalah ringkasan transaksi Anda:\n\n{detail_lines}\n\nSaldo terkini: Rp{balance:,}\n\nUntuk informasi lebih lanjut, silakan hubungi customer service.\n\nTerima kasih,\n{company}",
    "Hi {name},\n\nThis is a confirmation of your recent transaction with {company}.\n\nTransaction ID: {ref}\nService: {service}\nAmount: Rp{amount:,}\nDate: {date}\n\nIf you did not authorize this transaction, please contact us immediately.\n\nRegards,\nSupport Team",
]

CS_TEMPLATES = [
    "Yth. {name},\n\nTerima kasih telah menghubungi kami. Tiket Anda #{ticket} telah kami terima dan akan segera diproses.\n\nRingkasan:\n- Topik: {topic}\n- Prioritas: {priority}\n- Status: {status}\n\nKami akan merespon dalam 1x24 jam.\n\nHormat kami,\nCustomer Service {company}",
    "Dear {name},\n\nYour support ticket #{ticket} has been updated.\n\nStatus: {status}\nResponse:\n{solution}\n\nPlease let us know if this resolves your issue.\n\nBest regards,\n{agent}\nCustomer Support",
    "Yth. {name},\n\nMenindaklanjuti laporan Anda #{ticket}, kami informasikan bahwa:\n\n{solution}\n\nJika ada pertanyaan lebih lanjut, silakan balas email ini.\n\nTerima kasih,\n{company}",
    "Hi {name},\n\nThank you for your patience. We have resolved your issue regarding {topic}.\n\nSummary:\n{solution}\n\nPlease rate your experience: {survey_link}\n\nRegards,\n{agent}",
]

INTERNAL_TEMPLATES = [
    "Selamat pagi/{time_of_day} rekan-rekan,\n\nBerikut adalah notulensi rapat {topic} pada {date}.\n\nAgenda:\n{agenda_items}\n\nKeputusan:\n{decisions}\n\nAction Items:\n{action_items}\n\nMohon review dan konfirmasi.\n\nTerima kasih,\n{name}",
    "Dear Team,\n\nPlease find attached the {month} report for {division}.\n\nKey Highlights:\n{highlights}\n\nPlease review and provide feedback by {deadline}.\n\nBest regards,\n{name}\n{division} Division",
    "Yth. {name},\n\nDengan ini kami lampirkan dokumen kontrak kerja sama dengan {partner} untuk periode {year}.\n\nMohon ditinjau dan ditandatangani sebelum {deadline}.\n\nTerima kasih,\nLegal Department",
    "Hi All,\n\nProject {project} weekly update:\n\nCompleted:\n{completed}\n\nIn Progress:\n{in_progress}\n\nBlockers:\n{blockers}\n\nNext week plan:\n{next_week}\n\nBest,\n{name}",
    "Dear {name},\n\nWe are pleased to propose a partnership between {company_a} and {company_b}.\n\nProposal Overview:\n{proposal_details}\n\nWe look forward to your response.\n\nBest regards,\n{name}\n{company_a}",
]

SPAM_TEMPLATES = [
    "SELAMAT! {name},\n\nAnda terpilih sebagai pemenang undian {prize} senilai Rp{amount:,}!\n\nKlik link berikut untuk klaim hadiah:\n{link}\n\nJangan lewatkan kesempatan ini! HARI INI JUGA!\n\nTim Promosi",
    "Halo {name},\n\nDapatkan penghasilan Rp{amount:,}/hari hanya dari rumah!\n\n{link}\n\nGabung sekarang juga! Terbatas!\n\nINFO LENGKAP DI SINI: {link}",
    "Dear {name},\n\nCongratulations! You have won our lucky draw!\n\nPrize: {prize}\nValue: Rp{amount:,}\n\nClaim here: {link}\n\nLimited time only!",
    "{name}, kami punya penawaran spesial untuk Anda!\n\nDiskon 90% untuk semua produk!\nHURRY! Stok terbatas!\n\nKLIK: {link}\n\nBELANJA SEKARANG!",
    "ANDA KAMI BUTUHKAN!\n\nKami mencari agen penjualan di daerah Anda.\nGaji Rp{amount:,}/bulan + bonus!\n\n{link}\n\nLowongan terbatas! Daftar sekarang!",
    "Halo! Ingin terlihat lebih muda?\n\nProduk anti-aging kami terbukti secara klinis!\n\nPesan sekarang: {link}\n\nDiskon 70% untuk pemesanan pertama!",
    "FREE VOUCHER Rp{amount:,}!\n\n{link}\n\nKlaim voucher belanja Anda sekarang!\nTANPA SYARAT! GRATIS!",
    "{name}, Anda berhak mendapatkan PINJAMAN hingga Rp{amount:,}!\n\nProses cepat, tanpa jaminan, tanpa BI checking!\n\nAjukan sekarang: {link}\n\nDANA CAIR HARI INI!",
    "You are pre-approved for a loan of Rp{amount:,}!\n\nZero collateral, low interest, instant approval!\n\nApply now: {link}\n\nDon't miss this opportunity!",
    "SEGERA! Promo Spesial Akhir Tahun!\n\nSemua produk diskon 80%!\n{link}\n\nBELANJA SEKARANG SEBELUM KEHABISAN!",
]

PHISHING_TEMPLATES = [
    "KEPADA NASABAH BCA YTH.,\n\nKami mendeteksi aktivitas mencurigakan pada akun Anda. Demi keamanan, akun Anda akan diblokir sementara.\n\nSEGERA verifikasi data Anda melalui link berikut:\n{link}\n\nJika tidak diverifikasi dalam 24 jam, akun Anda akan ditangguhkan permanen.\n\nPT Bank Central Asia Tbk",
    "Yth. Pengguna Lodaya,\n\nSistem kami mendeteksi percobaan login dari perangkat baru.\n\nTanggal: {date}\nLokasi: {location}\nPerangkat: {device}\n\nJika bukan Anda, segera amankan akun:\n{link}\n\nTim Keamanan Lodaya",
    "Dear Customer,\n\nYour account has been limited due to unusual activity. To restore full access, please verify your identity:\n\n{link}\n\nFailure to verify within 24 hours will result in permanent account suspension.\n\nSecurity Department",
    "PEMBERITAHUAN PENTING!\n\nKami sedang melakukan update sistem keamanan. Semua nasabah WAJIB melakukan verifikasi ulang data.\n\nSilakan klik link berikut untuk verifikasi:\n{link}\n\nEmail ini dikirim otomatis. Harap tidak dibalas.\n\nManagement",
    "Yth. {name},\n\nInvoice #{ref} sebesar Rp{amount:,} sudah jatuh tempo.\n\nSegera lakukan pembayaran untuk menghindari denda.\n\nLihat invoice: {link}\n\nTerima kasih,\nCollection Department",
    "Your Netflix account has been suspended!\n\nWe were unable to process your latest payment. Please update your billing information:\n\n{link}\n\nReactivate your account now!\n\nNetflix Billing Team",
    "KONFIRMASI DATA NASABAH\n\nYth. Nasabah Mandiri,\n\nUntuk meningkatkan keamanan, kami memerlukan konfirmasi data diri Anda.\n\nSilakan isi form berikut:\n{link}\n\nProses memakan waktu 2-3 menit.\n\nBank Mandiri",
    "DocuSign: Document Ready for Review\n\n{name}, you have a document waiting for your signature.\n\nReview document: {link}\n\nThis request will expire in 7 days.\n\nDocuSign Electronic Signature Service",
    "Your PayPal account has been permanently limited.\n\nWe detected unusual activity on your account. To appeal this decision:\n\n{link}\n\nPayPal Resolution Center",
    "SEGERA! Paket Anda tertahan di bea cukai!\n\nNomor resi: {tracking}\nUntuk membebaskan paket, harap bayar biaya bea cukai sebesar Rp{amount:,}:\n\n{link}\n\nPembayaran sebelum 24 jam untuk menghindari denda.\n\nJNE Customer Service",
]

MALWARE_TEMPLATES = [
    "Yth. {name},\n\nBersama ini kami lampirkan invoice #{ref} yang perlu segera dibayarkan.\n\nMohon dibuka file lampiran untuk detail tagihan.\n\nTerima kasih,\nFinance Department {company}",
    "Dear {name},\n\nPlease find attached the contract document for {partner}.\n\nReview and sign the document. Your signature is required by {deadline}.\n\nRegards,\nLegal Team",
    "Hi {name},\n\nHere is the weekly report for {project}.\n\nI've attached the updated file with all revisions.\n\nPlease review when you get a chance.\n\nBest,\n{agent}",
    "Fwd: Laporan Keuangan {month} {year}\n\n---------- Forwarded message ---------\nFrom: Finance\n\nMohon review laporan terlampir.\n\nTerima kasih.",
    "Update Sistem Keamanan — Critical Patch\n\nYth. Karyawan,\n\nSilakan jalankan file update berikut untuk menjaga keamanan sistem.\n\nLampiran: security_patch_{ref}.exe\n\nTim IT",
    "Your package is ready for delivery!\n\nTracking: {tracking}\n\nPlease print the attached shipping label to receive your package.\n\nCourier Service",
    "Hi {name},\n\nHere are the photos from the {event} event last week.\n\nPlease find the attached zip file with all images.\n\nCheers,\n{agent}",
    "Resume — Job Application\n\nDear Hiring Manager,\n\nPlease find my attached resume and portfolio for the {position} position.\n\nThank you for your consideration.\n\n{name}",
    "Scanned Document — {company}\n\nPlease review the attached scanned document.\n\nThis is an automated notification.\n\nDocument Management System",
    "Tax Documents {year} — Action Required\n\nDear {name},\n\nYour tax documents for fiscal year {year} are ready for review.\n\nPlease download and complete the attached forms.\n\nTax Department",
]

TICKET_STATUSES = ["Open", "In Progress", "Resolved", "Closed", "Waiting Customer", "Escalated"]
PRIORITIES = ["Low", "Normal", "High", "Critical"]
TOPICS_CS = [
    "Gagal login", "Transaksi tidak dikenal", "Lupa password",
    "Akun diblokir", "Laporan bug aplikasi", "Pengaduan spam",
    "Permintaan refund", "Ubah data profil", "Aktivasi fitur",
    "Informasi produk", "Keluhan layanan", "Permintaan dokumen",
    "Gangguan sistem", "Update data", "Kartu hilang",
]
SOLUTIONS = [
    "Masalah telah kami selesaikan. Silakan coba kembali.",
    "Kami telah melakukan reset pada akun Anda. Silakan login dengan password baru.",
    "Tim teknis kami telah memperbaiki gangguan tersebut. Mohon maaf atas ketidaknyamanannya.",
    "Permintaan Anda telah diproses. Perubahan akan berlaku dalam 1x24 jam.",
    "Kami telah menindaklanjuti laporan Anda dan mengirimkan solusi melalui email terpisah.",
    "Setelah kami investigasi, masalah disebabkan oleh kesalahan sistem yang sudah kami perbaiki.",
    "Untuk masalah ini, kami sarankan Anda menghubungi tim teknis di nomor 0800-123-4567.",
    "Your issue has been resolved. Please verify and confirm.",
    "We have processed your request. Changes will reflect within 24 hours.",
    "Our team has investigated and fixed the underlying issue.",
]

DIVISIONS = ["Finance", "HR", "Engineering", "Marketing", "Operations", "Legal", "Sales", "IT Support"]
PROJECTS = [
    "Mercury", "Venus", "Gemini", "Apollo", "Athena", "Odyssey",
    "Horizon", "Nexus", "Quantum", "Apex", "Vertex", "Orion",
    "Sistem Pembayaran", "Migrasi Cloud", "Aplikasi Mobile",
    "Security Audit", "Data Warehouse", "Integrasi API",
]
TOPICS_INTERNAL = [
    "Sprint Review", "Q{q} Planning", "Budget Meeting", "Project Sync",
    "Security Briefing", "Product Launch", "Vendor Evaluation",
    "Performance Review", "Team Building", "Training Session",
    "Compliance Update", "Infrastructure Upgrade", "Client Meeting",
]

AGENDA_ITEMS = [
    "Review pencapaian minggu lalu",
    "Pembahasan target minggu ini",
    "Kendala dan solusi",
    "Diskusi timeline proyek",
    "Alokasi resource",
    "Update dari masing-masing tim",
    "Risk assessment dan mitigasi",
    "Q&A session",
]
DECISIONS = [
    "Timeline dipercepat 1 minggu",
    "Budget tambahan disetujui untuk pengembangan",
    "Menggunakan pendekatan agile untuk sprint berikutnya",
    "Perlu dilakukan testing tambahan sebelum rilis",
    "Vendor X dipilih sebagai mitra infrastruktur",
    "Menerapkan kebijakan keamanan baru",
    "Perubahan scope disetujui dengan catatan",
]
ACTION_ITEMS = [
    "- {name}: Finalisasi dokumen (EOD {deadline})",
    "- {name}: Koordinasi dengan tim IT ( {deadline})",
    "- {name}: Review hasil testing ( {deadline})",
    "- {name}: Kirim proposal ke client ( {deadline})",
    "- {name}: Update status proyek di dashboard",
    "- {name}: Follow up dengan vendor",
]

HIGHLIGHTS_TEMPLATES = [
    "- Revenue meningkat 15% dibanding bulan lalu\n- 3 klien baru ditambahkan\n- Customer satisfaction score: 4.5/5",
    "- Project timeline sesuai target\n- 0 critical bugs ditemukan\n- Team velocity meningkat 20%",
    "- 500 transaksi baru diproses\n- 98% SLA tercapai\n- 5 enhancement requests completed",
    "- Cost reduction 10% dari optimasi infrastruktur\n- 2 patent applications filed\n- 3 new features launched",
]

PRIZES = [
    "iPhone 15 Pro Max", "Rp 100.000.000", "Mobil Toyota Avanza",
    "Paket Liburan ke Bali", "Laptop Gaming", "Voucher Belanja Rp 50.000.000",
    "Smart TV 65 inch", "Motor Honda Vario", "Emas 100 gram",
    "Logam Mulia 1 kg",
]

SERVICES = [
    "Internet Banking", "Mobile Banking", "Transfer Antar Bank",
    "Pembayaran Tagihan", "Pembelian Pulsa", "Top Up E-Wallet",
    "Investasi Reksadana", "Asuransi", "Transaksi Kartu Kredit",
    "QRIS Payment", "SMS Banking", "Autopay",
]

METHODS = ["Transfer Bank", "Virtual Account", "Kartu Kredit", "QRIS", "GoPay", "OVO", "DANA", "ShopeePay"]

MALWARE_FILENAMES = [
    "Invoice_{ref}.exe", "Kontrak_{ref}.vbs", "Laporan_{month}.js",
    "Dokumen_{ref}.docm", "Update_Keamanan_{ref}.exe",
    "Foto_{event}.scr", "Data_{ref}.pif", "Paket_{tracking}.bat",
    "Resume_{name}.ps1", "Tax_{year}.jar", "Document_{ref}.com",
    "Scan_{ref}.hta", "Report_{ref}.msi", "Protected_{ref}.vba",
    "Images_{event}.scr",
]

PHISHING_LINKS = [
    "http://bca-secure-login.xyz/verify",
    "http://mandiri-verifikasi.tk/auth",
    "http://lodaya-account.ml/secure",
    "http://bni-konfirmasi.cf/login",
    "http://paypal-resolve.tk/confirm",
    "http://netflix-billing.ga/payment",
    "http://gojek-promo.tk/free",
    "http://bri-update.ml/verify",
    "http://apple-id-verify.cf/login",
    "http://google-security.tk/recover",
    "http://shopee-menang.xyz/klaim",
    "http://docusign-doc.tk/sign",
    "http://permata-login.ga/auth",
    "http://cimb-verifikasi.ml/confirm",
    "http://lodaya-secure.tk/verifikasi",
]

SPAM_LINKS = [
    "http://bit.ly/prize-winner-2026",
    "http://tinyurl.com/klaim-hadiah",
    "http://bit.ly/pinjaman-online",
    "http://tinyurl.com/diskon-90",
    "http://bit.ly/kerja-online",
    "http://adf.ly/weight-loss",
    "http://bit.ly/voucher-gratis",
    "http://shorturl.at/promosi",
    "http://tinyurl.com/bisnis-online",
    "http://bit.ly/obat-kuat",
    "http://tinyurl.com/dewasa",
    "http://bit.ly/turunkan-berat",
    "http://tinyurl.com/investasi-500",
    "http://bit.ly/lowongan-kerja",
    "http://adf.ly/diet-cepat",
]

VALID_LINKS = [
    "https://www.lodaya.id/help",
    "https://www.bca.co.id/informasi",
    "https://www.mandiri.co.id/support",
    "https://www.tokopedia.com/help",
    "https://www.gojek.com/faq",
    "https://www.traveloka.com/support",
    "https://www.telkom.co.id/kontak",
    "https://www.permata.co.id/cs",
    "https://www.danamon.co.id/hubungi",
]

TRACKING_NUMBERS = [
    "JNE{ref}", "JNT{ref}", "SI{ref}", "TIKI{ref}", "POS{ref}",
    "DHL{ref}", "FEDEX{ref}", "UPS{ref}",
]


def random_name() -> str:
    gender = RNG.choice(["male", "female"])
    first = RNG.choice(FIRST_NAMES_MALE if gender == "male" else FIRST_NAMES_FEMALE)
    last = RNG.choice(LAST_NAMES)
    return f"{first} {last}"


def random_email(name: Optional[str] = None) -> str:
    if name is None:
        name = random_name()
    name_part = name.lower().replace(" ", ".")
    domain = RNG.choice(DOMAINS)
    return f"{name_part}@{domain}"


def generate_ref() -> str:
    return f"INV-{RNG.randint(100000, 999999)}"


def generate_ticket() -> str:
    return f"TKT-{RNG.randint(10000, 99999)}"


def generate_date(start_days_ago: int = 365) -> str:
    d = datetime.now() - timedelta(days=RNG.randint(0, start_days_ago))
    return email.utils.formatdate(timeval=d.timestamp(), localtime=True)


def generate_past_date_str(days_ago: Optional[int] = None) -> str:
    if days_ago is None:
        days_ago = RNG.randint(0, 365)
    d = datetime.now() - timedelta(days=days_ago)
    return d.strftime("%d/%m/%Y")


def generate_amount(min_v: int = 10000, max_v: int = 50000000) -> int:
    return RNG.randint(min_v, max_v)


def format_amount(v: int) -> str:
    return f"Rp{v:,}"


def generate_message_id() -> str:
    rand = hashlib.md5(str(RNG.random()).encode()).hexdigest()[:16]
    return f"<{rand}.{RNG.randint(1000,9999)}@lti-antiphishing.local>"


def generate_html_body(plain_text: str, links: list[str] = None,
                       category: str = "") -> str:
    """Generate an HTML version of the plain text with optional links and images."""
    lines = plain_text.replace("\n", "<br>\n")
    
    # Add embedded image references for realism
    img_html = ""
    if category in ("transaction", "customer_service") and RNG.random() < 0.3:
        img_html = '<img src="https://www.lodaya.id/logo.png" alt="Logo" width="150" style="margin-bottom:16px;">\n'
    elif category == "spam" and RNG.random() < 0.5:
        img_html = '<img src="http://bit.ly/spam_banner_2026" alt="Promo" width="100%" style="max-width:600px;">\n'
    elif category == "phishing" and RNG.random() < 0.4:
        img_html = '<img src="http://bit.ly/fake_logo" alt="Bank" width="120" style="margin:0 auto;display:block;">\n'
    
    link_html = ""
    if links:
        for l in links:
            link_html += f'<br><a href="{l}" style="color:#0066cc;">{l}</a>'
    
    style = ""
    if category == "spam":
        style = 'style="background:#ffe0e0;padding:20px;font-family:Arial;color:#cc0000;font-weight:bold;font-size:18px;"'
    elif category == "phishing":
        style = 'style="background:#fff;padding:24px;font-family:Arial;border:2px solid #cc0000;max-width:600px;margin:0 auto;"'
    elif category == "malware":
        style = 'style="background:#f5f5f5;padding:20px;font-family:Consolas;font-size:12px;"'
    else:
        style = 'style="font-family:Arial,sans-serif;padding:16px;line-height:1.6;"'
    
    return f"""<html><body><div {style}>
{img_html}
{lines}{link_html}
</div></body></html>"""


def generate_image_attachment(email_id: str) -> Optional[MIMEBase]:
    """Generate a placeholder image attachment for realism."""
    if RNG.random() > 0.15:
        return None
    # Create a tiny valid PNG placeholder
    width = RNG.randint(100, 800)
    height = RNG.randint(100, 600)
    # Minimal valid PNG (1x1 transparent pixel for size)
    png_data = bytes([
        0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A,  # PNG signature
        0x00, 0x00, 0x00, 0x0D, 0x49, 0x48, 0x44, 0x52,  # IHDR chunk
        0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,
        0x08, 0x02, 0x00, 0x00, 0x00, 0x90, 0x77, 0x53,
        0xDE, 0x00, 0x00, 0x00, 0x0C, 0x49, 0x44, 0x41,
        0x54, 0x08, 0xD7, 0x63, 0x60, 0x60, 0x00, 0x00,
        0x00, 0x04, 0x00, 0x01, 0x27, 0x34, 0x27, 0xBA,
        0x00, 0x00, 0x00, 0x00, 0x49, 0x45, 0x4E, 0x44,
        0xAE, 0x42, 0x60, 0x82,
    ])
    img = MIMEImage(png_data, _subtype="png")
    img.add_header("Content-Disposition", "attachment",
                   filename=f"image_{email_id[:8]}_{RNG.randint(1,100)}.png")
    return img


def generate_malware_attachment(ref: str, name: str, event: str,
                                 tracking: str) -> list[MIMEBase]:
    """Generate fake malicious attachment for malware category."""
    attachments = []
    filename = RNG.choice(MALWARE_FILENAMES).format(
        ref=ref, name=name.replace(" ", "_")[:8], event=event[:8].replace(" ", "_"),
        tracking=tracking, month=datetime.now().strftime("%B"),
        year=datetime.now().year,
    )
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "txt"
    
    # Create a fake binary payload (simulated malware)
    payload = RNG.randbytes(RNG.randint(512, 4096))
    
    part = MIMEBase("application", f"x-msdos-program" if ext == "exe" else "octet-stream")
    part.set_payload(payload)
    part.add_header("Content-Disposition", "attachment", filename=filename)
    part.add_header("Content-Type", "application/octet-stream", name=filename)
    attachments.append(part)
    
    # Sometimes add a second attachment (innocent-looking doc)
    if RNG.random() < 0.25:
        doc = MIMEText("See the attached file for details.\n\nRegards,\n" + name)
        doc.add_header("Content-Disposition", "attachment",
                       filename=f"ReadMe_{ref}.txt")
        attachments.append(doc)
    
    return attachments


def build_eml(subject: str, body_plain: str, from_name: str, from_email: str,
              to_name: str, to_email: str, cc: list = None,
              attachments: list = None, links: list = None,
              category: str = "") -> str:
    """Build a complete .eml file as a string."""
    msg = MIMEMultipart("mixed")
    msg["From"] = f"{from_name} <{from_email}>"
    msg["To"] = f"{to_name} <{to_email}>"
    msg["Subject"] = subject
    msg["Date"] = generate_date()
    msg["Message-ID"] = generate_message_id()
    msg["MIME-Version"] = "1.0"
    
    if cc:
        msg["Cc"] = ", ".join(f"{n} <{e}>" for n, e in cc)
    
    # Add some headers for authenticity
    msg["X-Mailer"] = RNG.choice([
        "Microsoft Outlook 16.0", "Mozilla Thunderbird 115.0",
        "Apple Mail 16.0", "Google Mail", "Roundcube Webmail 1.6",
        "LTI Mail System v3.2", "Zimbra 9.0",
    ])
    msg["X-Priority"] = RNG.choice(["3 (Normal)", "2 (High)", "1 (Low)"])
    
    if category == "phishing":
        # Fake authentication headers to look legitimate
        msg["Authentication-Results"] = "spf=pass smtp.mailfrom=" + from_email.split("@")[1]
        msg["DKIM-Signature"] = f"v=1; a=rsa-sha256; d={from_email.split('@')[1]}; s=selector1; bh=fake;"
    elif category == "spam":
        msg["X-Spam-Flag"] = "YES"
        msg["X-Spam-Level"] = "*****" * RNG.randint(1, 5)
    
    # Body
    body_alt = MIMEMultipart("alternative")
    body_text = MIMEText(body_plain, "plain", "utf-8")
    body_html_content = generate_html_body(body_plain, links, category)
    body_html_part = MIMEText(body_html_content, "html", "utf-8")
    body_alt.attach(body_text)
    body_alt.attach(body_html_part)
    msg.attach(body_alt)
    
    # Attachments
    if attachments:
        for a in attachments:
            msg.attach(a)
    
    return msg.as_string()


def generate_transaction_email(idx: int) -> str:
    name = random_name()
    email_addr = random_email(name)
    to_name = random_name()
    to_email = random_email(to_name)
    ref = generate_ref()
    amount = generate_amount()
    service = RNG.choice(SERVICES)
    method = RNG.choice(METHODS)
    company = RNG.choice(COMPANIES)
    date = generate_past_date_str()
    balance = generate_amount(50000, 200000000)
    
    template = RNG.choice(TRANSACTION_TEMPLATES)
    detail_lines = (
        f"- Tanggal: {date}\n"
        f"- Merchant: {company}\n"
        f"- Jumlah: Rp{amount:,}\n"
        f"- Status: Sukses\n"
        f"- Referensi: {ref}"
    )
    body = template.format(
        name=to_name, amount=amount, service=service, ref=ref,
        date=date, method=method, company=company,
        balance=balance, detail_lines=detail_lines,
        amount_formatted=format_amount(amount),
        month=datetime.now().strftime("%B"),
        year=datetime.now().year,
    )
    
    subject = RNG.choice(SUBJECTS_TRANSACTION).format(
        ref=ref, amount=amount, service=service,
        amount_formatted=format_amount(amount),
        company=company, month=datetime.now().strftime("%B"),
        year=datetime.now().year,
    )
    
    links = RNG.sample(VALID_LINKS, RNG.randint(0, 2)) if RNG.random() < 0.3 else None
    attachment = generate_image_attachment(ref)
    att_list = [attachment] if attachment else None
    
    return build_eml(subject, body, company, email_addr, to_name, to_email,
                     links=links, attachments=att_list, category="transaction")


def generate_cs_email(idx: int) -> str:
    name = random_name()
    email_addr = random_email(name)
    to_name = random_name()
    to_email = random_email(to_name)
    ticket = generate_ticket()
    topic = RNG.choice(TOPICS_CS)
    priority = RNG.choice(PRIORITIES)
    status = RNG.choice(TICKET_STATUSES)
    solution = RNG.choice(SOLUTIONS)
    company = RNG.choice(COMPANIES)
    agent = random_name()
    
    survey_link = f"https://survey.lodaya.id/ticket/{ticket}"
    template = RNG.choice(CS_TEMPLATES)
    body = template.format(
        name=to_name, ticket=ticket, topic=topic,
        priority=priority, status=status, solution=solution,
        company=company, agent=agent, survey_link=survey_link,
    )
    
    subject = RNG.choice(SUBJECTS_CUSTOMER_SERVICE).format(
        ticket=ticket, status=status, service=RNG.choice(SERVICES),
        topic=topic, ref=generate_ref(),
    )
    
    links = [survey_link] if RNG.random() < 0.5 else None
    return build_eml(subject, body, agent, email_addr, to_name, to_email,
                     links=links, category="customer_service")


def generate_internal_email(idx: int) -> str:
    name = random_name()
    email_addr = random_email(name)
    to_name = random_name()
    to_email = random_email(to_name)
    company_a = RNG.choice(COMPANIES)
    company_b = RNG.choice([c for c in COMPANIES if c != company_a])
    partner = company_b
    client = company_b
    vendor = company_b.split()[-1] if " " in company_b else company_b
    division = RNG.choice(DIVISIONS)
    project = RNG.choice(PROJECTS)
    month = datetime.now().strftime("%B")
    year = datetime.now().year
    q = (datetime.now().month - 1) // 3 + 1
    ref = generate_ref()
    
    topic = RNG.choice(TOPICS_INTERNAL).format(q=q, year=year)
    meeting = RNG.randint(1, 200)
    deadline = generate_past_date_str(RNG.randint(1, 14))
    date = generate_past_date_str(RNG.randint(1, 30))
    
    n_agenda = RNG.randint(2, 5)
    agenda_items = "\n".join(f"{i+1}. {RNG.choice(AGENDA_ITEMS)}" for i in range(n_agenda))
    decisions = "\n".join(f"- {RNG.choice(DECISIONS)}" for _ in range(RNG.randint(1, 4)))
    
    n_actions = RNG.randint(2, 4)
    action_items = "\n".join(
        RNG.choice(ACTION_ITEMS).format(name=random_name(), deadline=deadline)
        for _ in range(n_actions)
    )
    
    highlights = RNG.choice(HIGHLIGHTS_TEMPLATES)
    completed = "- " + "\n- ".join(
        RNG.choice(["Database migration done", "API integration tested",
                     "UI mockups approved", "Load testing completed",
                     "Security audit passed", "Documentation updated"])
        for _ in range(RNG.randint(2, 4))
    )
    in_progress = "- " + "\n- ".join(
        RNG.choice(["Feature development", "Unit testing", "Code review",
                     "Client onboarding", "Performance optimization"])
        for _ in range(RNG.randint(2, 3))
    )
    blockers = RNG.choice([
        "Waiting for third-party API access\n- Missing design assets from client",
        "None",
        "Pending legal approval for contract\n- Server delivery delayed by 2 days",
    ])
    next_week = "- " + "\n- ".join(
        RNG.choice(["Complete feature X", "Start testing phase",
                     "Client demo preparation", "Deploy to staging",
                     "Performance benchmarking", "Documentation review"])
        for _ in range(RNG.randint(2, 3))
    )
    
    proposal_details = (
        f"1. Partnership Type: Strategic Alliance\n"
        f"2. Duration: 12 months\n"
        f"3. Estimated Value: Rp{RNG.randint(500000000, 5000000000):,}\n"
        f"4. Scope: {RNG.choice(['Technology integration', 'Joint marketing', 'Co-development', 'Distribution agreement'])}\n"
        f"5. Revenue Share: {RNG.randint(30, 70)}% / {100 - RNG.randint(30, 70)}%\n"
    )
    
    time_of_day = RNG.choice(["pagi", "siang", "sore"])
    
    template = RNG.choice(INTERNAL_TEMPLATES)
    body = template.format(
        name=name, to_name=to_name, topic=topic, date=date,
        agenda_items=agenda_items, decisions=decisions,
        action_items=action_items, month=month, division=division,
        highlights=highlights, year=year, deadline=deadline,
        partner=partner, project=project, completed=completed,
        in_progress=in_progress, blockers=blockers,
        next_week=next_week, time_of_day=time_of_day,
        company_a=company_a, company_b=company_b, client=client,
        proposal_details=proposal_details, vendor=vendor,
        ref=ref, meeting=meeting, q=q,
    )
    
    subject = RNG.choice(SUBJECTS_INTERNAL).format(
        topic=topic, date=date, month=month, division=division,
        year=year, partner=partner, client=client, vendor=vendor,
        project=project, ref=ref, meeting=meeting, q=q,
    )
    
    # B2B emails often have attachments
    attachments = None
    if RNG.random() < 0.4:
        doc = MIMEText("PROPOSAL DOCUMENT\n\n" + proposal_details + "\n\nThis is a sample attachment for demonstration.")
        doc.add_header("Content-Disposition", "attachment",
                       filename=f"Proposal_{partner}_{ref}.pdf")
        doc.add_header("Content-Type", "application/pdf", name=f"Proposal_{partner}_{ref}.pdf")
        attachments = [doc]
    
    return build_eml(subject, body, name, email_addr, to_name, to_email,
                     attachments=attachments, category="internal_b2b")


def generate_spam_email(idx: int) -> str:
    name = random_name()
    to_name = random_name()
    to_email = random_email(to_name)
    amount = generate_amount(5000000, 500000000)
    prize = RNG.choice(PRIZES)
    ref = generate_ref()
    link = RNG.choice(SPAM_LINKS)
    
    template = RNG.choice(SPAM_TEMPLATES)
    body = template.format(
        name=to_name, amount=amount, prize=prize, ref=ref, link=link,
        amount_formatted=format_amount(amount),
    )
    
    subject = RNG.choice(SUBJECTS_SPAM).format(
        prize=prize, amount=amount, ref=ref,
        amount_formatted=format_amount(amount),
    )
    
    # Spam emails often come from weird senders
    spam_domains = ["marketing-promo.tk", "winner-lucky.ga", "bonus-anda.ml",
                    "promo-spesial.cf", "info-terbaru.xyz", "penawaran.gq",
                    "bit.ly", "tinyurl.com", "promosi.tk"]
    spam_name = RNG.choice([
        "Tim Promosi", "Marketing Team", "Customer Service",
        "PT Pemenang Undian", "Info Penting", "Admin",
    ])
    spam_email = f"promo{RNG.randint(1000,9999)}@{RNG.choice(spam_domains)}"
    
    # No image attachment for most spam (just HTML imagery)
    return build_eml(subject, body, spam_name, spam_email, to_name, to_email,
                     links=[link], category="spam")


def generate_phishing_email(idx: int) -> str:
    to_name = random_name()
    to_email = random_email(to_name)
    amount = generate_amount(50000, 5000000)
    ref = generate_ref()
    tracking = RNG.choice(TRACKING_NUMBERS).format(ref=RNG.randint(100000, 999999))
    link = RNG.choice(PHISHING_LINKS)
    
    # The sender pretends to be a legitimate company
    legit_company = RNG.choice([
        "PT Bank Central Asia Tbk", "PT Bank Mandiri Tbk",
        "PT Bank Negara Indonesia Tbk", "PT Bank Rakyat Indonesia Tbk",
        "Lodaya Teknologi Indonesia", "Netflix Indonesia",
        "PayPal Indonesia", "Google Indonesia",
        "PT Gojek Indonesia", "PT Tokopedia",
    ])
    legit_domain = RNG.choice(["bca.co.id", "mandiri.co.id", "bni.co.id",
                                "bri.co.id", "lodaya.id", "netflix.com",
                                "paypal.com", "google.com", "gojek.com",
                                "tokopedia.com"])
    # BUT the actual sender address will be spoofed (using a lookalike domain)
    spoofed_domain = legit_domain.replace(".", "-") + RNG.choice([".tk", ".ml", ".ga", ".cf", ".xyz", ".life"])
    sender_email = f"noreply@{spoofed_domain}"
    
    template = RNG.choice(PHISHING_TEMPLATES)
    body = template.format(
        name=to_name, ref=ref, amount=amount, link=link,
        tracking=tracking, date=generate_past_date_str(),
        location=RNG.choice(["Jakarta", "Bandung", "Surabaya", "Medan",
                              "Makassar", "Denpasar", "Singapore", "Kuala Lumpur"]),
        device=RNG.choice(["Chrome/Windows", "Safari/Mac", "Chrome/Android",
                            "Safari/iPhone", "Firefox/Linux"]),
        amount_formatted=format_amount(amount),
    )
    
    subject = RNG.choice(SUBJECTS_PHISHING).format(ref=ref, tracking=tracking)
    
    # Sometimes add a fake legitimate link to appear real
    extra_links = [link]
    if RNG.random() < 0.3:
        extra_links.append(RNG.choice(VALID_LINKS))
    
    # Phishing emails look professional with HTML formatting
    return build_eml(subject, body, legit_company, sender_email, to_name, to_email,
                     links=extra_links, category="phishing")


def generate_malware_email(idx: int) -> str:
    name = random_name()
    to_name = random_name()
    to_email = random_email(to_name)
    ref = generate_ref()
    tracking = RNG.choice(TRACKING_NUMBERS).format(ref=generate_ref())
    event = RNG.choice(["Team Building", "Company Gathering", "Annual Party",
                         "Workshop Q{q}".format(q=RNG.randint(1, 4)),
                         "Launch Event", "Press Conference", "Site Visit"])
    agent = random_name()
    project = RNG.choice(PROJECTS)
    position = RNG.choice(["Software Engineer", "Data Analyst", "Security Specialist",
                            "Project Manager", "System Administrator", "Network Engineer"])
    month = datetime.now().strftime("%B")
    year = datetime.now().year
    company = RNG.choice(COMPANIES)
    
    template = RNG.choice(MALWARE_TEMPLATES)
    body = template.format(
        name=to_name, ref=ref, company=company, partner=RNG.choice(COMPANIES),
        deadline=generate_past_date_str(RNG.randint(1, 7)),
        project=project, agent=agent, event=event, tracking=tracking,
        position=position, month=month, year=year,
    )
    
    subject = RNG.choice(SUBJECTS_MALWARE).format(
        ref=ref, tracking=tracking, month=month, year=year,
        meeting=RNG.randint(1, 200), project=project, event=event,
        q=RNG.randint(1, 4),
    )
    
    # Generate the malware attachment
    malware_attachments = generate_malware_attachment(ref, name, event, tracking)
    
    # Sometimes also add a benign image to appear legitimate
    img_att = generate_image_attachment(ref)
    if img_att:
        malware_attachments.append(img_att)
    
    # Sender looks like a colleague or business partner
    sender_name = random_name()
    sender_email = random_email(sender_name)
    
    return build_eml(subject, body, sender_name, sender_email, to_name, to_email,
                     attachments=malware_attachments, category="malware")


def generate_dataset(output_dir: str, count_per_person: int = 3000):
    """Generate the full dataset — 5 people x N emails."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Each person gets a mixed set of email types
    people = {
        "chris":  {  # Transaction + Customer Service
            "gen": lambda i: generate_transaction_email(i) if i % 2 == 0 else generate_cs_email(i),
            "pct": 0.5,  # 50% transaction, 50% CS
        },
        "ilham":  {  # Internal Doc + B2B
            "gen": lambda i: generate_internal_email(i),
            "pct": 1.0,
        },
        "brian":  {  # Spam
            "gen": lambda i: generate_spam_email(i),
            "pct": 1.0,
        },
        "wisnu":  {  # Phishing
            "gen": lambda i: generate_phishing_email(i),
            "pct": 1.0,
        },
        "risly":  {  # Malware
            "gen": lambda i: generate_malware_email(i),
            "pct": 1.0,
        },
    }
    
    total = 0
    for person_name, config in people.items():
        person_dir = output_path / person_name
        person_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"\n{'='*60}")
        print(f"Generating {count_per_person} emails for {person_name.upper()}...")
        print(f"{'='*60}")
        
        for i in range(count_per_person):
            try:
                eml_content = config["gen"](i)
                content_hash = hashlib.sha256(eml_content.encode()).hexdigest()[:16]
                filename = f"{person_name}_{i+1:04d}_{content_hash}.eml"
                filepath = person_dir / filename
                
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(eml_content)
                
                total += 1
                if (i + 1) % 500 == 0:
                    print(f"  Progress: {i+1}/{count_per_person} generated...")
                    
            except Exception as e:
                print(f"  ERROR at index {i}: {e}")
        
        print(f"  [OK] {count_per_person} emails saved for {person_name} -> {person_dir}")
    
    print(f"\n{'='*60}")
    print(f"DATASET GENERATION COMPLETE")
    print(f"Total: {total} emails across {len(people)} people")
    print(f"Location: {output_path.absolute()}")
    print(f"{'='*60}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate LTI email dataset")
    parser.add_argument("--output", default="data/dataset",
                        help="Output directory (default: data/dataset)")
    parser.add_argument("--count", type=int, default=3000,
                        help="Emails per person (default: 3000)")
    args = parser.parse_args()
    
    print(f"LTI Anti-Phishing Email Dataset Generator")
    print(f"Output: {args.output}")
    print(f"Count per person: {args.count}")
    print(f"Total emails to generate: {args.count * 5}")
    print(f"People: chris (transaction+CS), ilham (internal+B2B), brian (spam), wisnu (phishing), risly (malware)")
    print()
    
    generate_dataset(args.output, args.count)
