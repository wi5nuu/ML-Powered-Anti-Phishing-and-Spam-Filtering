import GmailShell from '../components/layout/GmailShell'
import { useMe } from '../api/auth'
import styles from './HelpPage.module.css'

export default function HelpPage() {
  const { data: me } = useMe()
  const role = me?.user?.role || ''
  const isUser = role === 'user'
  const isAdmin = role === 'admin'
  const isSuper = role === 'superadmin'

  return (
    <GmailShell>
      <div className={styles.wrapper}>
        <h1 className={styles.title}>Bantuan & Dokumentasi Sistem</h1>
        <p className={styles.subtitle}>
          {isSuper && 'Panduan lengkap untuk Super Admin — kelola pengguna, pantau sistem, dan konfigurasi keamanan.'}
          {isAdmin && 'Panduan untuk Admin - kelola laporan, release email, dan pantau aktivitas sistem.'}
          {isUser && 'Panduan untuk User - cara membaca email, melapor masalah, dan menggunakan fitur filtering.'}
        </p>

        {/* ── 1. Alur Deteksi (semua role lihat) ── */}
        <section className={styles.section}>
          <h2 className={styles.sectionTitle}>1. Alur Deteksi & Pemrosesan Email</h2>
          <p className={styles.paragraph}>
            Setiap email yang masuk ke sistem melewati pipeline deteksi multi-lapis secara real-time. Berikut adalah tahapan detail yang dilalui setiap email:
          </p>
          <div className={styles.mlDetail}>
            <div className={styles.mlStep}>
              <div className={styles.mlStepNumber}>1</div>
              <div className={styles.mlStepContent}>
                <div className={styles.mlStepTitle}>Penerimaan & Ekstraksi Metadata</div>
                <div className={styles.mlStepText}>
                  Email diterima via koneksi IMAP. Sistem mengekstrak alamat pengirim, domain, header DKIM/SPF/DMARC,
                  daftar tautan, lampiran, dan konten teks untuk dianalisis.
                </div>
              </div>
            </div>
            <div className={styles.mlStep}>
              <div className={styles.mlStepNumber}>2</div>
              <div className={styles.mlStepContent}>
                <div className={styles.mlStepTitle}>SpamAssassin Scoring</div>
                <div className={styles.mlStepText}>
                  Engine SpamAssassin memberikan skor awal berdasarkan aturan heuristik: pola spam, reputasi domain,
                  blacklist publik, dan teknik manipulatif pada konten email.
                </div>
              </div>
            </div>
            <div className={styles.mlStep}>
              <div className={styles.mlStepNumber}>3</div>
              <div className={styles.mlStepContent}>
                <div className={styles.mlStepTitle}>Klasifikasi Machine Learning</div>
                <div className={styles.mlStepText}>
                  Model XGBoost/LightGBM menganalisis fitur tekstual dan struktural email. Hasilnya berupa probabilitas
                  Phishing vs Ham. Model diperbarui secara periodik dari umpan balik feedback loop.
                </div>
              </div>
            </div>
            <div className={styles.mlStep}>
              <div className={styles.mlStepNumber}>4</div>
              <div className={styles.mlStepContent}>
                <div className={styles.mlStepTitle}>Deteksi Anomali</div>
                <div className={styles.mlStepText}>
                  Isolation Forest mendeteksi email dengan struktur abnormal — jumlah tautan ekstrem, domain baru,
                  ukuran lampiran mencurigakan. Skor anomali berkisar 0.0 (normal) hingga 1.0 (abnormal).
                </div>
              </div>
            </div>
            <div className={styles.mlStep}>
              <div className={styles.mlStepNumber}>5</div>
              <div className={styles.mlStepContent}>
                <div className={styles.mlStepTitle}>Fusion Engine & Skor Akhir</div>
                <div className={styles.mlStepText}>
                  Tiga skor (ML, SpamAssassin, Anomaly) digabung menggunakan bobot adaptif. Skor akhir (Fused Score)
                  0.0 - 1.0 menentukan keputusan: Clean, Warning, atau Quarantine.
                </div>
              </div>
            </div>
            <div className={styles.mlStep}>
              <div className={styles.mlStepNumber}>6</div>
              <div className={styles.mlStepContent}>
                <div className={styles.mlStepTitle}>Routing & Tindakan</div>
                <div className={styles.mlStepText}>
                  Berdasarkan Fused Score: Clean (&lt; threshold) → inbox langsung. Warning → inbox dengan label.
                  Quarantine (&gt; threshold) → ditahan, tidak masuk ke inbox.
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* ── 2. Kategori ── */}
        <section className={styles.section}>
          <h2 className={styles.sectionTitle}>2. Kategori Keamanan Email</h2>
          <div className={styles.grid}>
            <div className={styles.card}>
              <div className={styles.cardIcon}>🟢</div>
              <div className={styles.cardTitle}>Inbox / Clean</div>
              <div className={styles.cardText}>
                Email dinyatakan aman oleh semua modul. Masuk ke kotak masuk tanpa intervensi.
              </div>
            </div>
            <div className={styles.card}>
              <div className={styles.cardIcon}>🟠</div>
              <div className={styles.cardTitle}>Spam</div>
              <div className={styles.cardText}>
                Email dengan skor mencurigakan. Masuk ke inbox dengan label [SPAM]. Jangan klik tautan di dalamnya.
              </div>
            </div>
            <div className={styles.card}>
              <div className={styles.cardIcon}>🔴</div>
              <div className={styles.cardTitle}>Phishing</div>
              <div className={styles.cardText}>
                Indikasi phising kuat (domain lookalike, minta kredensial). Email dikarantina — tidak masuk inbox.
              </div>
            </div>
            <div className={styles.card}>
              <div className={styles.cardIcon}>⚠️</div>
              <div className={styles.cardTitle}>Warning</div>
              <div className={styles.cardText}>
                Email dengan skor sedang. Masuk ke inbox dengan spanduk peringatan oranye. Verifikasi sebelum klik.
              </div>
            </div>
            <div className={styles.card}>
              <div className={styles.cardIcon}>🚫</div>
              <div className={styles.cardTitle}>Quarantine</div>
              <div className={styles.cardText}>
                Email berbahaya ditahan. Tidak muncul di inbox pengguna biasa.
              </div>
            </div>
          </div>
        </section>

        {/* ── 3. Panduan User ── */}
        {isUser && (
          <section className={styles.section}>
            <h2 className={styles.sectionTitle}>3. Panduan Penggunaan untuk User</h2>
            <div className={styles.roleGuide}>
              <ol className={styles.roleSteps}>
                <li><strong>Login:</strong> Buka halaman login, klik "Login dengan Google" atau masukkan kredensial dari admin.</li>
                <li><strong>Cek Email:</strong> Email bersih ada di Kotak Masuk. Email spam masuk dengan label kuning [SPAM].</li>
                <li><strong>Filter per Kategori:</strong> Klik kategori di sidebar (Spam, Phishing, Transaction, dll) untuk memfilter.</li>
                <li><strong>Detail Email:</strong> Klik email untuk melihat detail. Jika ada peringatan, baca penjelasan skor AI.</li>
                <li><strong>Cari Email:</strong> Gunakan bilah pencarian di atas untuk mencari berdasarkan subjek, pengirim, atau konten.</li>
                <li><strong>Lapor Masalah:</strong> Jika menemukan email mencurigakan atau bug, klik ikon bendera <strong>Lapor</strong> di pojok kanan atas. Pilih kategori dan kirim — admin akan menindaklanjuti.</li>
                <li><strong>Metrik:</strong> Klik "Metrik" di sidebar untuk melihat statistik deteksi harian.</li>
                <li><strong>Tema:</strong> Klik ikon bulan/matahari untuk toggle tema gelap/terang.</li>
              </ol>
            </div>
          </section>
        )}

        {/* ── 4. Panduan Admin ── */}
        {(isAdmin || isSuper) && (
          <section className={styles.section}>
            <h2 className={styles.sectionTitle}>{isSuper ? '4.' : '3.'} Panduan untuk Admin</h2>
            <div className={styles.roleGuide}>
              <ol className={styles.roleSteps}>
                <li><strong>Akses Admin Panel:</strong> Klik "Admin Panel" di sidebar untuk dashboard.</li>
                <li><strong>Tab Overview:</strong> Lihat ringkasan: total email diproses, jumlah terkarantina, laporan terbuka.</li>
                <li><strong>Tab Laporan:</strong> Kelola laporan dari pengguna. Filter kategori, lihat detail, balas laporan, update status (open → in_progress → resolved).</li>
                <li><strong>Release Email:</strong> Buka detail email terkarantina, klik "Lepaskan ke Inbox" jika aman. Atau "Konfirmasi Phishing" untuk memperkuat deteksi.</li>
                <li><strong>Tab Aktivitas:</strong> Lihat log aktivitas: login, logout, release email, perubahan pengaturan.</li>
                <li><strong>Pengaturan:</strong> Ubah threshold deteksi, whitelist pengirim, domain terlindungi, konfigurasi IMAP, dan notifikasi.</li>
              </ol>
            </div>
          </section>
        )}

        {/* ── 5. Panduan Super Admin (hanya superadmin) ── */}
        {isSuper && (
          <section className={styles.section}>
            <h2 className={styles.sectionTitle}>5. Panduan untuk Super Admin</h2>
            <div className={styles.roleGuide}>
              <ol className={styles.roleSteps}>
                <li><strong>Manajemen User:</strong> Tab Users — tambah user baru, edit role, reset password, nonaktifkan/aktifkan akun.</li>
                <li><strong>Hapus Email:</strong> Dapat menghapus email dari sistem secara permanen jika diperlukan.</li>
                <li><strong>Semua akses Admin:</strong> Super Admin memiliki semua kemampuan yang dimiliki Admin.</li>
              </ol>
            </div>
          </section>
        )}

        {/* ── 6. FAQ (disesuaikan role) ── */}
        <section className={styles.section}>
          <h2 className={styles.sectionTitle}>{isSuper ? '6.' : isAdmin ? '4.' : '3.'} Pertanyaan Umum</h2>

          {isUser && (
            <>
              <div className={styles.faqItem}>
                <div className={styles.faqQ}>Q: Email saya tidak masuk ke inbox, bagaimana?</div>
                <div className={styles.faqA}>Hubungi admin melalui menu Lapor atau saluran komunikasi internal. Admin akan memeriksa karantina.</div>
              </div>
              <div className={styles.faqItem}>
                <div className={styles.faqQ}>Q: Saya menemukan email phishing di inbox, apa yang harus saya lakukan?</div>
                <div className={styles.faqA}>Jangan klik tautan/lampiran. Klik tombol Lapor untuk melaporkan ke admin.</div>
              </div>
              <div className={styles.faqItem}>
                <div className={styles.faqQ}>Q: Kenapa email dari mitra bisnis masuk karantina?</div>
                <div className={styles.faqA}>Domain mitra mungkin belum dikenal sistem. Hubungi admin untuk melepas dan menambahkan ke whitelist.</div>
              </div>
              <div className={styles.faqItem}>
                <div className={styles.faqQ}>Q: Bagaimana cara mengganti password?</div>
                <div className={styles.faqA}>Buka Pengaturan → Akun. Jika login via Google, gunakan akun Google Anda. Hubungi admin jika lupa password.</div>
              </div>
            </>
          )}

          {isAdmin && (
            <>
              <div className={styles.faqItem}>
                <div className={styles.faqQ}>Q: Bagaimana cara melepas email dari karantina?</div>
                <div className={styles.faqA}>Buka detail email, klik "Lepaskan ke Inbox". Tambahkan catatan jika perlu. Email akan masuk ke inbox pengguna.</div>
              </div>
              <div className={styles.faqItem}>
                <div className={styles.faqQ}>Q: Apakah saya bisa menghapus email permanen?</div>
                <div className={styles.faqA}>Tidak. Hanya Super Admin yang memiliki akses hapus permanen.</div>
              </div>
              <div className={styles.faqItem}>
                <div className={styles.faqQ}>Q: Berapa lama email bertahan di karantina?</div>
                <div className={styles.faqA}>Sesuai pengaturan retensi (default 30 hari). Setelah itu otomatis dihapus.</div>
              </div>
              <div className={styles.faqItem}>
                <div className={styles.faqQ}>Q: Apa yang harus saya lakukan jika menerima laporan false positive?</div>
                <div className={styles.faqA}>Verifikasi email, lepaskan ke inbox, tambahkan catatan FP, dan masukkan domain ke whitelist di Pengaturan.</div>
              </div>
            </>
          )}

          {isSuper && (
            <>
              <div className={styles.faqItem}>
                <div className={styles.faqQ}>Q: Bagaimana cara menambah user baru?</div>
                <div className={styles.faqA}>Buka Admin Panel → tab Users → klik "Tambah User". Masukkan email dan pilih role. Password awal: Welcome123!.</div>
              </div>
              <div className={styles.faqItem}>
                <div className={styles.faqQ}>Q: Bagaimana cara mereset password user?</div>
                <div className={styles.faqA}>Buka Admin Panel → tab Users → klik Edit pada user → masukkan password baru → Simpan.</div>
              </div>
              <div className={styles.faqItem}>
                <div className={styles.faqQ}>Q: Bagaimana cara menonaktifkan akun user?</div>
                <div className={styles.faqA}>Buka Admin Panel → tab Users → klik Nonaktifkan pada user yang dituju. User tidak bisa login sampai diaktifkan kembali.</div>
              </div>
              <div className={styles.faqItem}>
                <div className={styles.faqQ}>Q: Berapa lama retensi data karantina?</div>
                <div className={styles.faqA}>Default 30 hari. Bisa diubah di Pengaturan → Retensi Karantina.</div>
              </div>
            </>
          )}
        </section>

        {/* ── 7. Tips Keamanan (semua role) ── */}
        <section className={styles.section}>
          <h2 className={styles.sectionTitle}>{isSuper ? '7.' : isAdmin ? '5.' : '4.'} Tips Keamanan</h2>
          <ul className={styles.tipsList}>
            <li>Jangan pernah memberikan password atau OTP melalui email.</li>
            <li>Periksa domain pengirim dengan teliti (contoh: l0daya.com vs lodaya.com).</li>
            <li>Jika ragu, jangan klik tautan. Arahkan kursor untuk melihat URL tujuan.</li>
            <li>Laporkan email mencurigakan — ini membantu sistem mendeteksi lebih baik.</li>
            <li>Gunakan autentikasi dua faktor (2FA) untuk keamanan tambahan.</li>
          </ul>
        </section>
      </div>
    </GmailShell>
  )
}

