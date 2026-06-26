import { useParams, useNavigate } from 'react-router-dom'
import { 
  ArrowLeft, Reply, MoreVertical, Archive, Trash2, Mail, Clock, 
  FolderSymlink, Tag, Printer, ExternalLink, Star, Smile, ShieldAlert,
  ChevronLeft, ChevronRight, CornerUpRight, X
} from 'lucide-react'
import GmailShell from '../components/layout/GmailShell'
import { 
  useEmail, 
  useEmails,
  useReleaseEmail, 
  useConfirmSpam, 
  useReportFalsePositive,
  useDeleteEmail 
} from '../api/emails'
import { useMe } from '../api/auth'
import { useToast } from '../hooks/useToast'
import { useState } from 'react'
import styles from './EmailDetailPage.module.css'

const BADGE_CFG = {
  quarantine: { text: 'KARANTINA', cls: styles.badgeQ },
  warn: { text: 'PERINGATAN', cls: styles.badgeW },
  clean: { text: 'BERSIH', cls: styles.badgeC },
}

const MOCK_BODIES = {
  'selamat! anda memenangkan smart tv!': `
    <div style="font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; max-width: 600px; margin: 0 auto; color: #333333;">
      <div style="background-color: #ea4335; padding: 24px; text-align: center; color: white; border-radius: 8px 8px 0 0;">
        <h1 style="margin: 0; font-size: 24px; font-weight: bold; letter-spacing: 1px;">PROMO SPECIAL EVENT</h1>
      </div>
      <div style="padding: 24px; line-height: 1.6; border: 1px solid #e0e0e0; border-top: none; border-radius: 0 0 8px 8px; background-color: #ffffff;">
        <p>Halo Pelanggan Setia,</p>
        <p>Kami sangat senang mengumumkan bahwa alamat email Anda telah terpilih sebagai pemenang utama dalam <strong>Lotre Tahunan Smart Device 2026</strong>!</p>
        <div style="background-color: #f9f9f9; border-left: 4px solid #ea4335; padding: 16px; margin: 20px 0; border-radius: 4px;">
          <h3 style="margin-top: 0; color: #ea4335; font-size: 15px;">Hadiah Anda:</h3>
          <p style="margin: 0; font-size: 18px; font-weight: bold; color: #222;">Samsung QLED Smart TV 55 Inch</p>
        </div>
        <p>Untuk mengklaim hadiah Anda, silakan lakukan konfirmasi alamat pengiriman dan verifikasi identitas Anda dengan mengklik tautan resmi di bawah ini:</p>
        <div style="text-align: center; margin: 30px 0;">
          <a href="http://smarttv-claim.lodaya.id.verification-portal.com/claim" target="_blank" rel="noopener noreferrer" style="background-color: #ea4335; color: white; padding: 12px 24px; text-align: center; text-decoration: none; display: inline-block; border-radius: 4px; font-weight: bold; box-shadow: 0 2px 5px rgba(0,0,0,0.15);">Klaim Hadiah Sekarang</a>
        </div>
        <p style="color: #666666; font-size: 12px; border-top: 1px solid #eeeeee; padding-top: 16px; margin-top: 24px;">Pemberitahuan ini berlaku selama 24 jam. Jika tidak diklaim, hadiah akan dialihkan ke pemenang lain.</p>
      </div>
    </div>
  `,
  'you won rp 100.000.000! claim now!': `
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; color: #333;">
      <div style="background: #1a73e8; color: #fff; padding: 20px; text-align: center; border-radius: 8px 8px 0 0;">
        <h2 style="margin:0; font-size: 22px;">MEGA DRAW 2026</h2>
      </div>
      <div style="padding: 24px; border: 1px solid #e0e0e0; border-top: none; border-radius: 0 0 8px 8px; background: #fff; line-height: 1.6;">
        <p>Dear Valued Winner,</p>
        <p>We are pleased to inform you that your email address has won a cash prize of <strong>Rp 100.000.000 (Seratus Juta Rupiah)</strong> in our global promotional draw.</p>
        <p>To process your cash payout directly to your bank account, please click the secure link below to submit your bank credentials and verify your account:</p>
        <div style="text-align: center; margin: 24px 0;">
          <a href="http://payout-portal-banking.co.id.info-security.cf/verify" target="_blank" rel="noopener noreferrer" style="background: #1a73e8; color: #fff; padding: 12px 20px; text-decoration: none; border-radius: 4px; font-weight: bold; display: inline-block;">Verify & Payout Now</a>
        </div>
        <p style="font-size: 11px; color: #888; border-top: 1px solid #eee; padding-top: 12px; margin-top: 20px;">This promotion is sponsored by Bank Association Partner Group.</p>
      </div>
    </div>
  `,
  'segera! akun anda akan diblokir': `
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; color: #333;">
      <div style="background: #b06000; color: #fff; padding: 16px 24px; border-radius: 8px 8px 0 0;">
        <h3 style="margin:0; font-size: 18px;">PEMBERITAHUAN KEAMANAN MANDIRI</h3>
      </div>
      <div style="padding: 24px; border: 1px solid #e0e0e0; border-top: none; border-radius: 0 0 8px 8px; background-color: #ffffff; line-height: 1.6;">
        <p>Nasabah Yth,</p>
        <p>Kami mendeteksi adanya aktivitas login mencurigakan pada akun Mandiri Online Anda dari IP address tidak dikenal pada 25 Juni 2026 pukul 22:15 WIB.</p>
        <p>Demi keamanan, akun Mandiri Online Anda <strong>akan diblokir sementara dalam waktu 2 jam</strong> kecuali Anda melakukan konfirmasi data diri Anda segera.</p>
        <p>Silakan klik tombol di bawah untuk verifikasi kepemilikan rekening Anda:</p>
        <div style="text-align: center; margin: 30px 0;">
          <a href="http://ib-bankmandiri.co.id.portal-security.cf/login" target="_blank" rel="noopener noreferrer" style="background: #b06000; color: #fff; padding: 12px 24px; text-decoration: none; border-radius: 4px; font-weight: bold; display: inline-block;">Verifikasi Rekening Mandiri</a>
        </div>
        <p style="font-size: 12px; color: #777;">Terima kasih atas perhatian Anda.<br/>PT Bank Mandiri (Persero) Tbk.</p>
      </div>
    </div>
  `,
  'urgent: verify now': `
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; color: #333;">
      <div style="background: #d32f2f; color: #fff; padding: 20px; text-align: center; border-radius: 8px 8px 0 0;">
        <h2 style="margin:0; font-size: 20px;">URGENT: SYSTEM ACCOUNT WARNING</h2>
      </div>
      <div style="padding: 24px; border: 1px solid #e0e0e0; border-top: none; border-radius: 0 0 8px 8px; background: #fff; line-height: 1.6;">
        <p>Hello,</p>
        <p>Your institutional email account has been flagged for violating security protocols. If you do not verify your login password immediately, your account access will be terminated indefinitely.</p>
        <div style="text-align: center; margin: 24px 0;">
          <a href="http://login-ldap-verification.lodaya.id.cf/auth" target="_blank" rel="noopener noreferrer" style="background: #d32f2f; color: #fff; padding: 12px 24px; text-decoration: none; font-weight: bold; border-radius: 4px; display: inline-block;">VERIFY MY ACCOUNT NOW</a>
        </div>
        <p>Thank you for your prompt attention to this matter.</p>
      </div>
    </div>
  `,
  'update sistem - critical patch': `
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; color: #333;">
      <div style="padding: 20px; border: 1px solid #ddd; background: #fdfdfd; border-radius: 8px 8px 0 0; border-bottom: none;">
        <h3 style="margin:0; color: #222; font-size: 16px;">IT Helpdesk: Critical System Update</h3>
      </div>
      <div style="padding: 24px; border: 1px solid #ddd; border-radius: 0 0 8px 8px; background: #fff; line-height: 1.6;">
        <p>Dear Staff,</p>
        <p>We are releasing a critical security patch today to prevent data breach vulnerabilities on all workstations. All employees are required to download the patch package (.exe format) and run the installer immediately.</p>
        <div style="background: #fcfcfc; padding: 16px; border: 1px dashed #bbb; border-radius: 4px; margin: 20px 0;">
          <strong>Attachment:</strong> <a href="http://files-patch-server.lodaya.id.net/SecurityPatch_Setup_2026.exe" target="_blank" rel="noopener noreferrer" style="color: #1a73e8; text-decoration: underline; font-weight: 500;">SecurityPatch_Setup_2026.exe</a> (12.4 MB)
        </div>
        <p>Your workstation must be patched before the end of the day.</p>
        <p style="font-size: 13px; color: #555;">Sincerely,<br/><strong>IT Security Infrastructure Team</strong></p>
      </div>
    </div>
  `,
  'urgent: your account will be suspended': `
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; color: #333;">
      <div style="background: #ea4335; color: #fff; padding: 20px; text-align: center; border-radius: 8px 8px 0 0;">
        <h2 style="margin:0; font-size: 20px;">SECURITY ALERT: SUSPENSION WARNING</h2>
      </div>
      <div style="padding: 24px; border: 1px solid #e0e0e0; border-top: none; border-radius: 0 0 8px 8px; background: #fff; line-height: 1.6;">
        <p>Dear Valued User,</p>
        <p>We have detected suspicious transaction activities originating from your online portal. For your protection, your access will be suspended within 24 hours.</p>
        <p>To avoid immediate service interruption, please update your billing details and confirm your security credentials immediately:</p>
        <div style="text-align: center; margin: 24px 0;">
          <a href="http://security-update.lodaya-portal-check.id/login" target="_blank" rel="noopener noreferrer" style="background: #ea4335; color: #fff; padding: 12px 24px; text-decoration: none; font-weight: bold; border-radius: 4px; display: inline-block;">Update Billing & Verify Now</a>
        </div>
        <p>Thank you for helping us keep your account safe.</p>
      </div>
    </div>
  `,
  'meeting: project update': `
    <div style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; max-width: 600px; margin: 0 auto; padding: 24px; border: 1px solid #e0e0e0; border-radius: 8px; background-color: #ffffff; color: #333;">
      <h2 style="margin-top: 0; color: #1a73e8; font-size: 18px; border-bottom: 2px solid #1a73e8; padding-bottom: 8px;">Jadwal Rapat Update Proyek Besok</h2>
      <p>Halo Rekan-rekan,</p>
      <p>Kita akan mengadakan rapat koordinasi untuk membahas update progress proyek LTI Anti-Phishing besok pagi:</p>
      <table style="width: 100%; border-collapse: collapse; margin: 16px 0;">
        <tr>
          <td style="padding: 6px 0; font-weight: bold; width: 100px;">Tanggal:</td>
          <td style="padding: 6px 0;">Jumat, 26 Juni 2026</td>
        </tr>
        <tr>
          <td style="padding: 6px 0; font-weight: bold;">Waktu:</td>
          <td style="padding: 6px 0;">10:00 - 11:30 WIB</td>
        </tr>
        <tr>
          <td style="padding: 6px 0; font-weight: bold;">Tempat:</td>
          <td style="padding: 6px 0;">Ruang Meeting Utama / Google Meet Link (Internal)</td>
        </tr>
      </table>
      <p>Agenda rapat utama meliputi review model klasifikasi anomali, penanganan false positive, serta sinkronisasi visualisasi SHAP ke panel dashboard.</p>
      <p>Mohon siapkan file slide progress dari masing-masing divisi.</p>
      <p style="margin-bottom: 0; font-size: 13px; color: #666;">Salam hangat,<br/><strong>Manajer Proyek LTI</strong></p>
    </div>
  `,
  'free money': `
    <div style="font-family: Impact, sans-serif; max-width: 600px; margin: 0 auto; padding: 30px; background-color: #ffd700; border: 5px solid #000; border-radius: 12px; color: #000; text-align: center;">
      <h1 style="margin: 0 0 10px 0; font-size: 36px; letter-spacing: 2px;">FREE CASH REWARD</h1>
      <h2 style="margin: 0 0 20px 0; font-size: 20px; font-weight: normal; color: #333;">NO STRINGS ATTACHED - 100% LEGITIMATE</h2>
      <div style="background-color: #fff; padding: 20px; border: 2px solid #000; border-radius: 8px; text-align: left; font-family: Arial, sans-serif; line-height: 1.5;">
        <p>Dear Email Owner,</p>
        <p>You have been randomly selected as our grand winner of <strong>$1,500,000.00 USD</strong> in the Global Sweepstakes Program 2026!</p>
        <p>To register your claim and transfer the money directly, click the link below to get in touch with our fiduciary agent in London:</p>
        <p style="text-align: center; margin: 20px 0;">
          <a href="http://payout-international-lottery.co.uk.verify-portal.cf/" target="_blank" rel="noopener noreferrer" style="background-color: #ff0000; color: #fff; font-size: 18px; font-weight: bold; padding: 12px 30px; text-decoration: none; border-radius: 6px; display: inline-block; border: 2px solid #000;">CLAIM MY CASH REWARD NOW</a>
        </p>
        <p style="font-size: 11px; color: #555; margin-bottom: 0;">Ref Code: SW-2638. Note: Keep this confidential until your payout is complete to prevent double claims.</p>
      </div>
    </div>
  `,
  'your invoice': `
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; color: #333; padding: 20px; border: 1px solid #ddd; border-radius: 8px; background: #fff;">
      <div style="display: flex; justify-content: space-between; border-bottom: 2px solid #eee; padding-bottom: 12px; margin-bottom: 20px;">
        <h2 style="margin: 0; color: #444;">INVOICE</h2>
        <span style="color: #666; font-size: 14px;">Invoice #INV-2026-001<br/>Tanggal: 25 Juni 2026</span>
      </div>
      <p>Halo Pelanggan,</p>
      <p>Terima kasih atas langganan Anda pada layanan kami. Rincian tagihan terbaru Anda telah terbit dengan rincian sebagai berikut:</p>
      <table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
        <thead>
          <tr style="background-color: #f8f9fa;">
            <th style="padding: 10px; border: 1px solid #eee; text-align: left;">Deskripsi Layanan</th>
            <th style="padding: 10px; border: 1px solid #eee; text-align: right;">Jumlah</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td style="padding: 10px; border: 1px solid #eee;">Paket Cloud Hosting Enterprise (Bulan Juni 2026)</td>
            <td style="padding: 10px; border: 1px solid #eee; text-align: right;">Rp 2.500.000</td>
          </tr>
          <tr style="font-weight: bold;">
            <td style="padding: 10px; border: 1px solid #eee; text-align: right;">Total Tagihan</td>
            <td style="padding: 10px; border: 1px solid #eee; text-align: right; color: #2e7d32;">Rp 2.500.000</td>
          </tr>
        </tbody>
      </table>
      <p>Pembayaran akan didebit secara otomatis dari kartu kredit Anda yang terdaftar pada tanggal 1 Juli 2026. Anda dapat meninjau detail transaksi melalui portal tagihan resmi.</p>
      <p style="margin-top: 30px; font-size: 12px; color: #999; border-top: 1px solid #eee; padding-top: 12px;">Email ini dikirimkan secara otomatis dari Departemen Keuangan.</p>
    </div>
  `,
  'confidential request': `
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; color: #333; padding: 24px; border: 1px solid #e0e0e0; border-radius: 8px; background: #fafafa;">
      <p>Halo,</p>
      <p>Saya sedang menghadiri rapat direksi yang mendesak di luar kota dan ponsel saya kehabisan baterai sehingga tidak dapat menerima panggilan telepon.</p>
      <p>Tolong siapkan detail transaksi pengeluaran keuangan triwulan ini dan kirimkan data sensitif karyawan internal ke email pribadi saya di bawah ini sesegera mungkin:</p>
      <p style="background: #fff; padding: 12px; border-left: 4px solid #1a73e8; border-radius: 4px; font-family: monospace; font-size: 13px;">
        Email Tujuan: <strong>tari.purnama.mandiri@sec-portal-check.net</strong>
      </p>
      <p>Mohon agar permohonan ini ditangani secara sangat rahasia (confidential) dan diprioritaskan sebelum hari kerja berakhir.</p>
      <p>Terima kasih atas kerja samanya.</p>
      <p style="margin-bottom: 0; font-weight: bold; color: #555;">Tari Purnama<br/>Direktur Keuangan & Kepatuhan</p>
    </div>
  `,
  're: strategy meeting': `
    <div style="font-family: Calibri, sans-serif; max-width: 600px; margin: 0 auto; padding: 16px; color: #2b2b2b;">
      <p>Hi team,</p>
      <p>Good progress on the front-end mockup. Regarding the strategy meeting tomorrow, let's make sure we also invite the product design team to review the final layout of the LTI Anti-Phishing application dashboard.</p>
      <p>We need to align on the user experience and ensure that standard roles do not see any of the advanced security statistics. The developer has updated the API endpoints to enforce this properly on backend side.</p>
      <p>See you all tomorrow at 10 AM. I will book the online link.</p>
      <p>Best regards,<br/><strong>Prasetyo</strong></p>
    </div>
  `,
  'you won paket liburan': `
    <div style="font-family: 'Comic Sans MS', sans-serif; max-width: 600px; margin: 0 auto; padding: 24px; text-align: center; background-color: #e3f2fd; border: 3px double #1e88e5; border-radius: 12px; color: #1565c0;">
      <h1 style="margin-top: 0; font-size: 28px;">🌴 SELAMAT! LIBURAN GRATIS KE BALI MENUNGGU ANDA! 🌴</h1>
      <p style="font-size: 16px; line-height: 1.6;">Anda telah terpilih sebagai salah satu pemenang undian bulanan Paket Liburan Mewah 3 Hari 2 Malam untuk 2 orang ke Bali!</p>
      <div style="background-color: #ffffff; padding: 16px; border-radius: 8px; margin: 20px 0; text-align: left; color: #333; font-size: 14px; line-height: 1.5;">
        <strong>Fasilitas Termasuk:</strong><br/>
        ✓ Tiket pesawat PP Jakarta - Denpasar<br/>
        ✓ Hotel Bintang 5 di kawasan Seminyak<br/>
        ✓ Tour Guide & Paket makan malam romantis di Jimbaran
      </div>
      <p>Untuk menebus voucher hadiah Anda, silakan daftarkan nomor kartu identitas (KTP) dan isi formulir klaim melalui situs web mitra kami:</p>
      <p style="margin: 24px 0;">
        <a href="http://voucher-holiday-bali.lodaya.id.info-travels.cf/claim" target="_blank" rel="noopener noreferrer" style="background-color: #f57c00; color: #fff; font-size: 16px; font-weight: bold; padding: 12px 24px; text-decoration: none; border-radius: 24px; display: inline-block; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">Klaim Tiket Liburan Sekarang</a>
      </p>
      <p style="font-size: 11px; color: #78909c; margin-bottom: 0;">Pendaftaran ditutup dalam 12 jam. Pajak hadiah ditanggung oleh pemenang.</p>
    </div>
  `,
  'your account has been compromised': `
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; color: #333; padding: 20px; border: 1px solid #ffcdd2; border-radius: 8px; background: #fff8f8;">
      <div style="border-bottom: 2px solid #ef5350; padding-bottom: 10px; margin-bottom: 20px;">
        <h3 style="margin: 0; color: #c62828;">Pemberitahuan Penting Keamanan Akun</h3>
      </div>
      <p>Kepada Pengguna Layanan,</p>
      <p>Sistem kami mendeteksi adanya upaya masuk yang mencurigakan ke akun Anda menggunakan browser tidak dikenal yang berasal dari lokasi geografis tidak biasa (Moskow, Rusia) pada 25 Juni 2026 pukul 22:45 WIB.</p>
      <p>Untuk mencegah penyalahgunaan data dan menjaga keamanan akun Anda, mohon lakukan reset kata sandi Anda dan verifikasi nomor telepon pemulihan melalui tautan darurat keamanan di bawah:</p>
      <div style="text-align: center; margin: 24px 0;">
        <a href="http://accounts.security-reset.lodaya.id.service-recovery.com/reset" target="_blank" rel="noopener noreferrer" style="background-color: #c62828; color: #fff; padding: 12px 24px; text-decoration: none; font-weight: bold; border-radius: 4px; display: inline-block;">Reset Kata Sandi Saya</a>
      </div>
      <p>Jika Anda tidak melakukan verifikasi ini dalam waktu 24 jam, akun Anda akan dinonaktifkan secara permanen untuk alasan pencegahan penipuan.</p>
      <p style="margin-top: 24px; font-size: 12px; color: #888;">Salam Keamanan,<br/>LTI Security Operation Center</p>
    </div>
  `
}

const getMockBody = (subject, sender) => {
  const cleanSubject = (subject || '').toLowerCase().trim()
  
  // Find key that is a substring of cleanSubject
  for (const key of Object.keys(MOCK_BODIES)) {
    if (cleanSubject.includes(key)) {
      return MOCK_BODIES[key]
    }
  }
  
  // High quality generic fallback that looks like a real email if no subject matched
  return `
    <div style="font-family: 'Google Sans', Roboto, sans-serif; max-width: 600px; margin: 0 auto; border: 1px solid #e0e0e0; border-radius: 8px; padding: 24px; background: #ffffff;">
      <div style="border-bottom: 1px solid #eeeeee; padding-bottom: 16px; margin-bottom: 20px;">
        <h2 style="margin: 0 0 8px 0; font-size: 18px; color: #202124;">${subject || '(Tanpa Subjek)'}</h2>
        <div style="font-size: 13px; color: #5f6368;">
          Dari: <strong>${sender || 'Pengirim tidak diketahui'}</strong>
        </div>
      </div>
      <div style="line-height: 1.6; color: #202124; font-size: 14px;">
        <p>Halo,</p>
        <p>Anda menerima email penting dari <strong>${sender || 'sistem luar'}</strong>.</p>
        <p>Ini adalah pesan terkait subjek <strong>"${subject || '(tanpa subjek)'}"</strong> yang telah disalurkan dan dievaluasi oleh sistem LTI Anti-Phishing Anda.</p>
        <p style="padding: 16px; background-color: #f8f9fa; border-radius: 4px; border-left: 4px solid #1a73e8; font-style: italic; color: #3c4043; border-top-right-radius: 4px; border-bottom-right-radius: 4px;">
          Pesan ini mengandung informasi operasional standar. Jika ini adalah email ancaman karantina, silakan periksa parameter deteksi machine learning dan rincian SHAP di bilah analisis keamanan kanan.
        </p>
        <p>Salam,<br/>Tim Keamanan Sistem Informasi</p>
      </div>
    </div>
  `
}

export default function EmailDetailPage() {
  const { emailId } = useParams()
  const navigate = useNavigate()
  const { showToast } = useToast()
  
  const { data: email, isLoading, isError } = useEmail(emailId)
  const { data: emailsData } = useEmails('all')
  const { data: meData } = useMe()

  const { mutate: release, isPending: releasing } = useReleaseEmail()
  const { mutate: confirmSpam, isPending: spamming } = useConfirmSpam()
  const { mutate: reportFP, isPending: reporting } = useReportFalsePositive()
  const { mutate: deleteEmail, isPending: deleting } = useDeleteEmail()

  const [fpNotes, setFpNotes] = useState('')
  const [showRecipientDetail, setShowRecipientDetail] = useState(false)
  const [replyMode, setReplyMode] = useState(null) // null | 'reply' | 'forward'
  const [replyTo, setReplyTo] = useState('')
  const [replySubject, setReplySubject] = useState('')
  const [replyBody, setReplyBody] = useState('')

  const [localStarred, setLocalStarred] = useState(null)
  const [isUnread, setIsUnread] = useState(false)

  if (isLoading) return (
    <GmailShell>
      <div style={{ padding: 32, color: 'var(--text-muted)', fontFamily: 'Google Sans' }}>Memuat detail email...</div>
    </GmailShell>
  )

  if (isError || !email) return (
    <GmailShell>
      <div style={{ padding: 32, color: '#EA4335', fontFamily: 'Google Sans' }}>Email tidak ditemukan.</div>
    </GmailShell>
  )

  const role = meData?.user?.role || 'analyst'
  const showSecurityPanel = true

  const label = (email.label || 'clean').toLowerCase()
  const cfg = BADGE_CFG[label] || BADGE_CFG.clean
  const shap = email.shap_data
  const maxShap = shap?.features?.length
    ? Math.max(...shap.features.map((f) => Math.abs(f.shap)))
    : 1

  const emailBodyHTML = email.raw_content ? email.raw_content : getMockBody(email.subject, email.sender)
  const senderInitial = (email.sender || 'U')[0].toUpperCase()

  // Dynamic Avatar color
  const avatarColors = ['#ea4335', '#1a73e8', '#f29900', '#34a853', '#ab47bc']
  const colorIndex = senderInitial.charCodeAt(0) % avatarColors.length
  const avatarBg = avatarColors[colorIndex]

  // Pagination logic
  const emailList = emailsData?.emails || []
  const currentIndex = emailList.findIndex((e) => e.email_id === emailId)
  const prevEmail = currentIndex > 0 ? emailList[currentIndex - 1] : null
  const nextEmail = currentIndex >= 0 && currentIndex < emailList.length - 1 ? emailList[currentIndex + 1] : null
  const pagerText = currentIndex !== -1 
    ? `${currentIndex + 1} dari ${emailList.length}` 
    : '1 dari 1'

  // Star logic
  const isStarred = localStarred !== null ? localStarred : (email.is_starred || false)

  const handleToggleStar = () => {
    const nextVal = !isStarred
    setLocalStarred(nextVal)
    showToast(nextVal ? 'Ditambahkan ke berbintang' : 'Dihapus dari berbintang', 'info')
  }

  // Toolbar handlers
  const handleArchive = () => {
    if (role !== 'superadmin' && role !== 'admin') {
      showToast('Aksi ditolak: Hanya Admin yang dapat mengelola karantina', 'error')
      return
    }
    release(emailId, {
      onSuccess: () => {
        showToast('Email dilepaskan ke inbox', 'success')
        navigate('/inbox')
      },
      onError: () => showToast('Gagal melepaskan email', 'error'),
    })
  }

  const handleSpam = () => {
    if (role !== 'superadmin' && role !== 'admin') {
      showToast('Aksi ditolak: Hanya Admin yang dapat mengelola karantina', 'error')
      return
    }
    confirmSpam(emailId, {
      onSuccess: () => {
        showToast('Dikonfirmasi sebagai spam', 'info')
        navigate('/inbox')
      },
      onError: () => showToast('Gagal mengkonfirmasi spam', 'error'),
    })
  }

  const handleDelete = () => {
    if (role !== 'superadmin' && role !== 'admin') {
      showToast('Aksi ditolak: Hanya Super Admin & Admin yang dapat menghapus email', 'error')
      return
    }
    if (window.confirm('Apakah Anda yakin ingin menghapus email ini secara permanen dari sistem?')) {
      deleteEmail(emailId, {
        onSuccess: () => {
          showToast('Email berhasil dihapus', 'success')
          navigate('/inbox')
        },
        onError: () => showToast('Gagal menghapus email', 'error'),
      })
    }
  }

  const handleToggleUnread = () => {
    const nextVal = !isUnread
    setIsUnread(nextVal)
    showToast(nextVal ? 'Ditandai sebagai belum dibaca' : 'Ditandai sebagai sudah dibaca', 'info')
  }

  const handleSnooze = () => {
    showToast('Fitur Tunda disimulasikan', 'info')
  }

  const handleMoveTo = () => {
    showToast('Fitur Pindahkan folder disimulasikan', 'info')
  }

  const handleAddLabel = () => {
    showToast('Fitur Label disimulasikan', 'info')
  }

  const handleMoreActions = () => {
    showToast('Opsi tambahan disimulasikan', 'info')
  }

  const handlePrint = () => {
    window.print()
  }

  const handleOpenNewWindow = () => {
    window.open(window.location.href, '_blank')
  }

  // Reply Draft Handlers
  const handleOpenReply = (mode) => {
    setReplyMode(mode)
    setReplyTo(mode === 'reply' ? (email.sender || '') : '')
    setReplySubject(mode === 'reply' ? `Re: ${email.subject || ''}` : `Fwd: ${email.subject || ''}`)
    setReplyBody('')
  }

  const handleSendReply = () => {
    if (!replyTo) {
      showToast('Silakan tentukan penerima email', 'error')
      return
    }
    showToast(
      replyMode === 'reply' 
        ? 'Balasan berhasil dikirim (simulasi)' 
        : 'Email berhasil diteruskan (simulasi)', 
      'success'
    )
    setReplyMode(null)
  }

  return (
    <GmailShell>
      <div className={styles.splitLayout}>
        {/* Left Pane: Email Reader */}
        <div className={styles.emailPane}>
          {/* Gmail Toolbar */}
          <div className={styles.toolbar}>
            <div className={styles.toolbarLeft}>
              <button className={styles.toolbarBtn} onClick={() => navigate('/inbox')} title="Kembali">
                <ArrowLeft size={18} />
              </button>
              <button className={styles.toolbarBtn} onClick={handleArchive} title="Arsipkan / Lepaskan">
                <Archive size={18} />
              </button>
              <button className={styles.toolbarBtn} onClick={handleSpam} title="Laporkan Spam">
                <ShieldAlert size={18} />
              </button>
              <button className={styles.toolbarBtn} onClick={handleDelete} title="Hapus">
                <Trash2 size={18} />
              </button>
              <button 
                className={`${styles.toolbarBtn} ${isUnread ? styles.unreadActive : ''}`} 
                onClick={handleToggleUnread} 
                title="Tandai Belum Dibaca"
              >
                <Mail size={18} />
              </button>
              <button className={styles.toolbarBtn} onClick={handleSnooze} title="Tunda">
                <Clock size={18} />
              </button>
              <button className={styles.toolbarBtn} onClick={handleMoveTo} title="Pindahkan ke">
                <FolderSymlink size={18} />
              </button>
              <button className={styles.toolbarBtn} onClick={handleAddLabel} title="Label">
                <Tag size={18} />
              </button>
              <button className={styles.toolbarBtn} onClick={handleMoreActions} title="Lainnya">
                <MoreVertical size={18} />
              </button>
            </div>
            <div className={styles.toolbarRight}>
              <span className={styles.pagerText}>{pagerText}</span>
              <button 
                className={styles.toolbarBtn} 
                disabled={!prevEmail} 
                onClick={() => prevEmail && navigate(`/email/${prevEmail.email_id}`)}
                title="Lebih baru"
              >
                <ChevronLeft size={18} />
              </button>
              <button 
                className={styles.toolbarBtn} 
                disabled={!nextEmail} 
                onClick={() => nextEmail && navigate(`/email/${nextEmail.email_id}`)}
                title="Lebih lama"
              >
                <ChevronRight size={18} />
              </button>
            </div>
          </div>

          {/* Subject Header */}
          <div className={styles.subjectRow}>
            <h1 className={styles.subjectTitle}>
              {email.subject || '(tanpa subjek)'}
              <span className={styles.badgeInbox}>Kotak Masuk x</span>
            </h1>
            <div className={styles.subjectActions}>
              <button className={styles.toolbarBtn} onClick={handlePrint} title="Cetak semua">
                <Printer size={18} />
              </button>
              <button className={styles.toolbarBtn} onClick={handleOpenNewWindow} title="Buka di jendela baru">
                <ExternalLink size={18} />
              </button>
            </div>
          </div>

          {/* Sender Header */}
          <div className={styles.senderHeader}>
            <div className={styles.avatar} style={{ backgroundColor: avatarBg }}>
              {senderInitial}
            </div>
            <div className={styles.senderDetails} style={{ position: 'relative' }}>
              <div className={styles.senderInfo}>
                <span className={styles.senderName}>{email.sender?.split('<')[0]?.trim() || 'Pengirim'}</span>
                <span className={styles.senderEmail}>&lt;{email.sender?.split('<')?.[1]?.replace('>', '') || 'N/A'}&gt;</span>
              </div>
              <div 
                className={styles.toMe} 
                onClick={() => setShowRecipientDetail(!showRecipientDetail)}
              >
                kepada saya ▾
              </div>

              {/* Recipient Details Dropdown */}
              {showRecipientDetail && (
                <div className={styles.recipientDropdown}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid var(--border-light)', paddingBottom: 8, marginBottom: 8 }}>
                    <strong style={{ fontSize: '0.875rem' }}>Detail Informasi Email</strong>
                    <button 
                      style={{ border: 'none', background: 'transparent', cursor: 'pointer', color: 'var(--text-muted)' }}
                      onClick={() => setShowRecipientDetail(false)}
                    >
                      <X size={16} />
                    </button>
                  </div>
                  <div className={styles.recipientRow}>
                    <span className={styles.recipientLabel}>Dari:</span>
                    <span className={styles.recipientValue}>{email.sender}</span>
                  </div>
                  <div className={styles.recipientRow}>
                    <span className={styles.recipientLabel}>Kepada:</span>
                    <span className={styles.recipientValue}>
                      {email.recipient_list && email.recipient_list.length > 0
                        ? email.recipient_list.join(', ')
                        : meData?.user?.username || 'me'}
                    </span>
                  </div>
                  <div className={styles.recipientRow}>
                    <span className={styles.recipientLabel}>Tanggal:</span>
                    <span className={styles.recipientValue}>
                      {email.received_at ? new Date(email.received_at).toLocaleString('id-ID', { dateStyle: 'full', timeStyle: 'medium' }) : 'N/A'}
                    </span>
                  </div>
                  <div className={styles.recipientRow}>
                    <span className={styles.recipientLabel}>Subjek:</span>
                    <span className={styles.recipientValue}>{email.subject}</span>
                  </div>
                  <div className={styles.recipientRow}>
                    <span className={styles.recipientLabel}>Kategori:</span>
                    <span className={styles.recipientValue}>{email.category || email.label || '-'}</span>
                  </div>
                </div>
              )}
            </div>
            <div className={styles.senderRight}>
              <span className={styles.dateStr}>
                {email.received_at ? new Date(email.received_at).toLocaleString('id-ID', { dateStyle: 'medium', timeStyle: 'short' }) : 'N/A'}
              </span>
              <button 
                className={`${styles.toolbarBtn} ${isStarred ? styles.starActive : ''}`} 
                onClick={handleToggleStar} 
                title="Bintangi"
              >
                <Star size={16} fill={isStarred ? '#f29900' : 'none'} />
              </button>
              <button className={styles.toolbarBtn} onClick={() => handleOpenReply('reply')} title="Balas">
                <Reply size={16} />
              </button>
              <button className={styles.toolbarBtn} onClick={handleMoreActions} title="Lainnya">
                <MoreVertical size={16} />
              </button>
            </div>
          </div>

          {/* Email Content Frame */}
          <div className={styles.emailBodyWrapper}>
            <div className={styles.emailBodyCard} dangerouslySetInnerHTML={{ __html: emailBodyHTML }} />
          </div>

          {/* Reply / Forward Box Form */}
          {replyMode && (
            <div className={styles.replyBox}>
              <div className={styles.replyBoxHeader}>
                <span>{replyMode === 'reply' ? 'Balas Email' : 'Teruskan Email'}</span>
                <button 
                  style={{ border: 'none', background: 'transparent', cursor: 'pointer', color: 'var(--text-muted)' }}
                  onClick={() => setReplyMode(null)}
                >
                  <X size={16} />
                </button>
              </div>
              <div className={styles.replyBoxBody}>
                <div className={styles.replyField}>
                  <span className={styles.replyFieldLabel}>Kepada:</span>
                  <input 
                    type="text" 
                    className={styles.replyFieldInput} 
                    value={replyTo} 
                    onChange={(e) => setReplyTo(e.target.value)} 
                    placeholder="nama@contoh.com"
                  />
                </div>
                <div className={styles.replyField}>
                  <span className={styles.replyFieldLabel}>Subjek:</span>
                  <input 
                    type="text" 
                    className={styles.replyFieldInput} 
                    value={replySubject} 
                    onChange={(e) => setReplySubject(e.target.value)}
                  />
                </div>
                <textarea 
                  className={styles.replyTextarea} 
                  value={replyBody} 
                  onChange={(e) => setReplyBody(e.target.value)} 
                  placeholder={replyMode === 'reply' ? 'Tulis balasan Anda di sini...' : 'Tulis pesan pengantar di sini...'}
                />
              </div>
              <div className={styles.replyBoxFooter}>
                <button className={styles.btnReplyCancel} onClick={() => setReplyMode(null)}>Batal</button>
                <button className={styles.btnReplySend} onClick={handleSendReply}>Kirim</button>
              </div>
            </div>
          )}

          {/* Bottom Action Row */}
          {!replyMode && (
            <div className={styles.bottomActionRow}>
              <button className={styles.bottomBtn} onClick={() => handleOpenReply('reply')}>
                <Reply size={16} className={styles.bottomBtnIcon} />
                <span>Balas</span>
              </button>
              <button className={styles.bottomBtn} onClick={() => handleOpenReply('forward')}>
                <CornerUpRight size={16} className={styles.bottomBtnIcon} />
                <span>Teruskan</span>
              </button>
              <button className={styles.toolbarBtn} onClick={() => showToast('Reaksi emoji disimulasikan', 'info')} title="Reaksi Emoji">
                <Smile size={18} />
              </button>
            </div>
          )}
        </div>

        {/* Right Pane: Security Analyst tools (Hidden for standard 'user') */}
        {showSecurityPanel && (
          <div className={styles.securityPane}>
            {/* Actions Panel */}
            <div className={styles.card}>
              <h3 className={styles.cardTitle}>Tindakan Karantina</h3>
              <div className={styles.actionHeader}>
                <span className={`${styles.badge} ${cfg.cls}`}>{cfg.text}</span>
                {email.anomaly_score > 0
                  ? <span className={`${styles.badge} ${styles.badgeDual}`}>Dual Detection</span>
                  : <span className={`${styles.badge} ${styles.badgeML}`}>ML Only</span>}
              </div>
              <div style={{ height: 16 }} />
              <div className={styles.actionButtons}>
                <button
                  className={`${styles.btn} ${styles.btnGreen}`}
                  onClick={() => release(emailId, {
                    onSuccess: () => { showToast('Email dilepaskan ke inbox', 'success'); navigate('/inbox') },
                    onError: () => showToast('Gagal melepaskan', 'error'),
                  })}
                  disabled={releasing}
                >
                  {releasing ? 'Memproses...' : 'Lepaskan ke Inbox'}
                </button>
                <button
                  className={`${styles.btn} ${styles.btnRed}`}
                  onClick={() => confirmSpam(emailId, {
                    onSuccess: () => { showToast('Dikonfirmasi sebagai spam', 'info'); navigate('/inbox') },
                    onError: () => showToast('Gagal mengkonfirmasi', 'error'),
                  })}
                  disabled={spamming}
                >
                  {spamming ? 'Memproses...' : 'Konfirmasi Spam'}
                </button>
                <div className={styles.fpSection}>
                  <input
                    className={styles.fpInput}
                    type="text"
                    placeholder="Catatan false positive (opsional)"
                    value={fpNotes}
                    onChange={(e) => setFpNotes(e.target.value)}
                  />
                  <button
                    className={`${styles.btn} ${styles.btnYellow}`}
                    onClick={() => reportFP({ emailId, notes: fpNotes }, {
                      onSuccess: () => { showToast('False positive dilaporkan', 'warning'); navigate('/inbox') },
                      onError: () => showToast('Gagal melaporkan', 'error'),
                    })}
                    disabled={reporting}
                  >
                    {reporting ? 'Memproses...' : 'Laporkan FP'}
                  </button>
                </div>
              </div>
            </div>

            {/* Score Grid Panel */}
            <div className={styles.card}>
              <h3 className={styles.cardTitle}>Skor Deteksi</h3>
              <div className={styles.scoreGrid}>
                <div className={styles.scoreCard}>
                  <div className={styles.scoreValue}>{email.fused_score?.toFixed(3)}</div>
                  <div className={styles.scoreLabel}>Skor Akhir</div>
                </div>
                <div className={styles.scoreCard}>
                  <div className={styles.scoreValue}>{email.ml_probability?.toFixed(4)}</div>
                  <div className={styles.scoreLabel}>Probabilitas ML</div>
                </div>
                <div className={styles.scoreCard}>
                  <div className={styles.scoreValue}>{email.sa_score?.toFixed(2) || '0.00'}</div>
                  <div className={styles.scoreLabel}>SpamAssassin</div>
                </div>
                <div className={styles.scoreCard}>
                  <div className={styles.scoreValue}>{(email.anomaly_score || 0).toFixed(4)}</div>
                  <div className={styles.scoreLabel}>Skor Anomali</div>
                </div>
              </div>
            </div>

            {/* XAI Panel */}
            {email.human_reasons?.length > 0 && (
              <div className={styles.card}>
                <h3 className={styles.cardTitle}>Penjelasan AI (XAI)</h3>
                <div className={styles.xaiList}>
                  {email.human_reasons.map((r, i) => (
                    <div key={i} className={styles.xaiItem}>• {r}</div>
                  ))}
                </div>
              </div>
            )}

            {/* SHAP Feature Panel */}
            {shap?.features?.length > 0 && (
              <div className={styles.card}>
                <h3 className={styles.cardTitle}>SHAP Feature Importance</h3>
                <div className={styles.shapList}>
                  {shap.features.slice(0, 5).map((feat, i) => (
                    <div key={i} className={styles.shapBar}>
                      <span className={styles.shapLabel}>{feat.name?.slice(0, 15)}</span>
                      <div className={styles.shapTrack}>
                        <div
                          className={`${styles.shapFill} ${feat.shap > 0 ? styles.spam : styles.ham}`}
                          style={{ width: `${Math.abs(feat.shap) / maxShap * 100}%` }}
                        />
                      </div>
                      <span className={styles.shapVal}>{feat.shap.toFixed(4)}</span>
                    </div>
                  ))}
                </div>
                <div className={styles.shapLegend}>
                  <span>Gelap = SPAM</span>
                  <span>Terang = HAM</span>
                </div>
              </div>
            )}

            {/* Metadata Detail Table */}
            <div className={styles.card}>
              <h3 className={styles.cardTitle}>Metadata Deteksi</h3>
              <div className={styles.meta}>
                <div className={styles.metaRow}>
                  <span className={styles.metaLabel}>Kategori</span>
                  <span className={styles.metaValue}>{email.category || email.label || '-'}</span>
                </div>
                <div className={styles.metaRow}>
                  <span className={styles.metaLabel}>Status</span>
                  <span className={styles.metaValue} style={{ fontWeight: 500, color: 'var(--text)' }}>
                    {email.status === 'released' ? 'Dirilis' : email.status === 'confirmed_spam' ? 'Spam' : email.status}
                  </span>
                </div>
                <div className={styles.metaRow}>
                  <span className={styles.metaLabel}>Model Versi</span>
                  <span className={styles.metaValue}>{email.model_version || 'N/A'}</span>
                </div>
                <div className={styles.metaRow}>
                  <span className={styles.metaLabel}>Alasan Routing</span>
                  <span className={styles.metaValue}>{email.routing_reason || 'N/A'}</span>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </GmailShell>
  )
}
