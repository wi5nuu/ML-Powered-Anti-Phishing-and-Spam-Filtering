import { useState, useRef, useEffect, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { ShieldCheck, ArrowRight } from 'lucide-react'
import styles from './WelcomePage.module.css'

const TNC_TEXT = `
PERSYARATAN DAN KETENTUAN PENGGUNAAN SISTEM LTI ANTI-PHISHING

1. PENERIMAAN KETENTUAN
Dengan mengakses, mendaftarkan akun, dan/atau menggunakan sistem LTI Anti-Phishing ("Sistem") yang dioperasikan oleh PT Lodaya Teknologi Indonesia ("LTI", "kami", atau "milik kami"), Anda ("Pengguna", "Anda", atau "Organisasi Anda") secara hukum menyatakan telah membaca, memahami, dan menyetujui untuk terikat sepenuhnya oleh Persyaratan dan Ketentuan Penggunaan ini ("Ketentuan"). Apabila Anda tidak menyetujui salah satu atau seluruh bagian dari Ketentuan ini, Anda dilarang mengakses atau menggunakan Sistem dalam bentuk apa pun.

2. DEFINISI DAN INTERPRETASI
2.1. "Sistem" berarti platform LTI Anti-Phishing berbasis kecerdasan buatan dan machine learning yang menyediakan layanan deteksi, analisis, filtrasi, dan pelaporan ancaman keamanan siber berbasis email, termasuk seluruh fitur, API, dashboard, dokumentasi, dan pembaruannya.
2.2. "Data Email" berarti seluruh isi, metadata, lampiran, header, dan informasi lain yang terkandung dalam email yang dikirimkan ke atau diproses oleh Sistem.
2.3. "Pengguna Resmi" berarti individu yang terdaftar dan memiliki kredensial akses yang sah ke Sistem atas nama Organisasi Anda.
2.4. "Kebijakan Privasi" berarti dokumen terpisah yang mengatur pengumpulan, penggunaan, dan perlindungan data pribadi yang merupakan bagian tidak terpisahkan dari Ketentuan ini.
2.5. "Hari Kerja" berarti hari Senin sampai Jumat, tidak termasuk hari libur nasional yang ditetapkan oleh Pemerintah Republik Indonesia.

3. DESKRIPSI LAYANAN DAN CAKUPAN
3.1. Sistem menyediakan layanan filtrasi email inbound dan outbound berbasis machine learning yang dirancang untuk mengidentifikasi, mengklasifikasikan, dan mengkarantina ancaman keamanan siber termasuk namun tidak terbatas pada phishing, malware, spam, spoofing, dan ransomware.
3.2. Layanan mencakup analisis real-time terhadap email masuk, pelaporan berkala, dashboard monitoring, notifikasi keamanan, serta fitur manajemen kebijakan keamanan email organisasi.
3.3. LTI akan berupaya memberikan layanan dengan standar terbaik dan ketersediaan sistem yang optimal, namun tidak menjamin bahwa Sistem akan bebas dari gangguan, error, atau downtime di luar kendali LTI.
3.4. LTI berhak untuk menambah, mengurangi, memodifikasi, atau menghentikan sementara fitur tertentu dalam Sistem demi kepentingan pengembangan dan peningkatan kualitas layanan dengan pemberitahuan sebelumnya kepada Pengguna.

4. PERSYARATAN PENDAFTARAN DAN AKUN
4.1. Pengguna wajib mendaftarkan akun institusi melalui prosedur pendaftaran yang ditetapkan LTI dengan memberikan informasi yang akurat, lengkap, dan terkini.
4.2. Setiap akun bersifat rahasia, pribadi, dan tidak dapat dialihkan kepada pihak lain tanpa persetujuan tertulis dari LTI.
4.3. Pengguna bertanggung jawab penuh atas seluruh aktivitas yang terjadi di bawah akun terdaftar, termasuk namun tidak terbatas pada akses oleh Pengguna Resmi yang memperoleh kredensial dari Organisasi Anda.
4.4. Pengguna wajib segera melaporkan kepada LTI dalam waktu 1x24 jam apabila terdapat indikasi kebocoran, penyalahgunaan, atau akses tidak sah terhadap akun atau kredensial Sistem.

5. PENGGUNAAN YANG DIIZINKAN DAN LARANGAN
5.1. Pengguna hanya diizinkan menggunakan Sistem untuk tujuan keamanan email dan perlindungan aset informasi Organisasi Anda sendiri sesuai dengan lingkup yang ditentukan dalam perjanjian layanan.
5.2. Pengguna dilarang keras untuk:
a) Menggunakan Sistem untuk tujuan ilegal, melanggar hukum, atau melanggar hak pihak ketiga;
b) Melakukan reverse engineering, decompilation, disassembly, atau upaya mengekstraksi source code Sistem dalam bentuk apa pun;
c) Mendistribusikan, menjual, menyewakan, meminjamkan, atau melisensikan kembali akses ke Sistem kepada pihak ketiga tanpa persetujuan tertulis dari LTI;
d) Mengirimkan atau mengunggah data yang mengandung virus, worm, trojan, atau kode berbahaya lainnya ke dalam Sistem;
e) Melakukan uji penetrasi, vulnerability scanning, atau pengujian keamanan lainnya terhadap Sistem tanpa izin tertulis terlebih dahulu dari LTI;
f) Menggunakan Sistem untuk mengirimkan komunikasi komersial yang tidak diminta (spam) dalam bentuk apa pun;
g) Melebihi batas penggunaan yang wajar yang ditetapkan oleh LTI berdasarkan kebijakan penggunaan yang berlaku.

6. KEAMANAN DATA DAN PERLINDUNGAN INFORMASI
6.1. LTI menerapkan langkah-langkah keamanan teknis dan administratif yang wajar untuk melindungi Data Email dan informasi Pengguna, termasuk namun tidak terbatas pada enkripsi end-to-end (TLS 1.3), enkripsi data at-rest (AES-256), kontrol akses berbasis peran (RBAC), logging audit, dan firewall aplikasi web (WAF).
6.2. LTI tidak akan memeriksa, mengungkapkan, atau membagikan Data Email kepada pihak ketiga, kecuali:
a) Diwajibkan oleh hukum atau peraturan perundang-undangan yang berlaku;
b) Diperlukan untuk merespons pelanggaran keamanan atau ancaman langsung terhadap integritas Sistem;
c) Mendapat persetujuan tertulis terlebih dahulu dari Pengguna.
6.3. LTI akan memberitahukan kepada Pengguna dalam waktu 3x24 jam setelah mengetahui terjadinya pelanggaran keamanan data yang memengaruhi Data Email Pengguna, sesuai dengan ketentuan Peraturan Pemerintah Nomor 71 Tahun 2019 tentang Penyelenggaraan Sistem dan Transaksi Elektronik dan Undang-Undang Nomor 27 Tahun 2022 tentang Perlindungan Data Pribadi.
6.4. Seluruh Data Email yang diproses oleh Sistem akan disimpan dalam infrastruktur yang berlokasi di wilayah Republik Indonesia.
6.5. Pengguna setuju bahwa LTI dapat menggunakan data agregat anonim yang tidak dapat diidentifikasi kembali ke Pengguna tertentu untuk tujuan pelatihan model machine learning, peningkatan layanan, dan analisis tren keamanan siber.

7. HAK KEKAYAAN INTELEKTUAL
7.1. Seluruh hak cipta, hak paten, merek dagang, rahasia dagang, dan hak kekayaan intelektual lainnya yang terkandung dalam Sistem, termasuk namun tidak terbatas pada algoritma machine learning, kode sumber, antarmuka pengguna, database, dokumentasi teknis, dan konten visual, adalah milik eksklusif LTI dan/atau pemberi lisensinya.
7.2. Ketentuan ini tidak memberikan lisensi atau hak apa pun kepada Pengguna atas kekayaan intelektual LTI, kecuali hak terbatas untuk menggunakan Sistem sesuai dengan Ketentuan ini.
7.3. Pengguna dilarang menghapus, mengubah, atau menutupi pemberitahuan hak cipta, merek dagang, atau hak kepemilikan lainnya yang terdapat dalam atau pada Sistem.
7.4. Setiap masukan, saran, ide, atau umpan balik yang diberikan oleh Pengguna terkait pengembangan Sistem akan menjadi milik LTI dan LTI tidak berkewajiban untuk memberikan kompensasi atau atribusi apa pun sehubungan dengan penggunaannya.

8. KEWAJIBAN PENGGUNA
8.1. Pengguna wajib mematuhi seluruh ketentuan peraturan perundang-undangan yang berlaku, termasuk namun tidak terbatas pada Undang-Undang Informasi dan Transaksi Elektronik, Undang-Undang Perlindungan Data Pribadi, dan peraturan pelaksanaannya.
8.2. Pengguna wajib memastikan bahwa Pengguna Resmi telah menerima pelatihan yang memadai mengenai penggunaan Sistem yang aman dan sesuai ketentuan.
8.3. Pengguna bertanggung jawab untuk menjaga kerahasiaan kredensial akun dan segera mereset kata sandi apabila terdapat indikasi kompromi keamanan.
8.4. Pengguna wajib menunjuk setidaknya satu administrator Sistem yang bertanggung jawab atas koordinasi dengan LTI dalam hal operasional, pemeliharaan, dan insiden keamanan.

9. SLA DAN KETERSEDIAAN LAYANAN
9.1. LTI akan berupaya untuk menyediakan ketersediaan Sistem sebesar 99,5% per bulan kalender, di luar pemeliharaan terjadwal dan force majeure.
9.2. Pemeliharaan terjadwal akan dilakukan di luar jam kerja (pukul 22.00 – 06.00 WIB) dan akan diberitahukan setidaknya 48 jam sebelumnya melalui email atau notifikasi dalam Sistem.
9.3. LTI tidak bertanggung jawab atas ketidaktersediaan Sistem yang disebabkan oleh:
a) Gangguan pada infrastruktur internet atau jaringan Pengguna;
b) Force majeure sebagaimana didefinisikan dalam Pasal 13;
c) Tindakan atau kelalaian Pengguna atau pihak ketiga yang berada di bawah kendali Pengguna;
d) Serangan siber yang berada di luar kendali wajar LTI.

10. BATASAN TANGGUNG JAWAB
10.1. Dalam batas maksimum yang diizinkan oleh hukum yang berlaku, LTI dan/atau afiliasinya tidak bertanggung jawab atas kerugian langsung, tidak langsung, insidental, khusus, konsekuensial, atau punitif yang timbul dari atau terkait dengan penggunaan atau ketidakmampuan menggunakan Sistem, bahkan jika LTI telah diberitahukan tentang kemungkinan kerugian tersebut.
10.2. Total tanggung jawab kumulatif LTI kepada Pengguna yang timbul dari atau terkait dengan Ketentuan ini tidak akan melebihi jumlah biaya layanan yang dibayarkan oleh Pengguna kepada LTI dalam periode 12 (dua belas) bulan sebelum klaim diajukan.
10.3. Ketentuan dalam Pasal ini tidak berlaku untuk:
a) Kematian atau cedera pribadi yang disebabkan oleh kelalaian LTI;
b) Penipuan atau penggambaran yang keliru secara curang;
c) Pelanggaran kewajiban kerahasiaan berdasarkan Pasal 6;
d) Pelanggaran hak kekayaan intelektual LTI berdasarkan Pasal 7;
e) Hal-hal lain yang secara hukum tidak dapat dibatasi atau dikecualikan tanggung jawabnya.

11. GANTI RUGI (INDEMNITAS)
11.1. Pengguna setuju untuk membebaskan, mempertahankan, dan melindungi LTI, afiliasi, direktur, pejabat, karyawan, dan agennya dari dan terhadap segala klaim, tuntutan, kerugian, kewajiban, biaya, dan pengeluaran (termasuk biaya hukum wajar) yang timbul dari atau terkait dengan:
a) Pelanggaran Pengguna terhadap Ketentuan ini;
b) Penggunaan Sistem oleh Pengguna yang melanggar hukum yang berlaku;
c) Klaim pihak ketiga yang timbul dari Data Email atau konten yang diproses melalui Sistem;
d) Pelanggaran hak kekayaan intelektual pihak ketiga oleh Pengguna.

12. PEMUTUSAN AKSES DAN PENGHENTIAN LAYANAN
12.1. LTI berhak untuk menangguhkan sementara atau menghentikan permanen akses Pengguna ke Sistem, dengan atau tanpa pemberitahuan terlebih dahulu, apabila:
a) Pengguna melanggar ketentuan material dalam Perjanjian ini;
b) Pengguna gagal membayar biaya layanan yang jatuh tempo dalam waktu 30 (tiga puluh) hari kalender;
c) LTI mencurigai adanya aktivitas tidak sah atau penipuan yang melibatkan akun Pengguna;
d) Diwajibkan oleh hukum atau perintah otoritas yang berwenang.
12.2. Dalam hal penghentian layanan, LTI akan memberikan akses yang wajar kepada Pengguna untuk mengekstraksi Data Email yang telah diproses dalam waktu 14 (empat belas) hari kalender setelah penghentian, kecuali diwajibkan lain oleh hukum.
12.3. Ketentuan yang secara alami harus tetap berlaku setelah penghentian, termasuk namun tidak terbatas pada Pasal 6 (Keamanan Data), Pasal 7 (Hak Kekayaan Intelektual), Pasal 10 (Batasan Tanggung Jawab), dan Pasal 11 (Ganti Rugi), akan tetap berlaku setelah penghentian Ketentuan ini.

13. FORCE MAJEURE
13.1. LTI tidak bertanggung jawab atas keterlambatan atau kegagalan dalam memenuhi kewajibannya berdasarkan Ketentuan ini yang disebabkan oleh peristiwa di luar kendali wajar LTI, termasuk namun tidak terbatas pada bencana alam, perang, terorisme, huru-hara, pemogokan umum, pandemi, kebakaran, banjir, gempa bumi, gangguan listrik skala besar, kegagalan infrastruktur telekomunikasi nasional, dan tindakan pemerintah atau otoritas publik.
13.2. Apabila peristiwa force majeure berlangsung lebih dari 30 (tiga puluh) hari kalender berturut-turut, salah satu pihak berhak untuk mengakhiri Ketentuan ini dengan pemberitahuan tertulis kepada pihak lainnya.

14. PERUBAHAN KETENTUAN
14.1. LTI berhak untuk mengubah, memodifikasi, atau memperbarui Ketentuan ini setiap saat demi kepentingan kepatuhan hukum, pengembangan layanan, atau penyesuaian operasional.
14.2. Perubahan akan diumumkan melalui Sistem dan/atau pemberitahuan email kepada Pengguna sekurang-kurangnya 14 (empat belas) hari kalender sebelum tanggal efektif pemberlakuan perubahan, kecuali perubahan tersebut diwajibkan oleh hukum yang berlaku secara mendesak.
14.3. Pengguna yang terus menggunakan Sistem setelah tanggal efektif perubahan dianggap telah menyetujui perubahan tersebut. Apabila Pengguna tidak menyetujui perubahan, Pengguna berhak untuk menghentikan penggunaan Sistem dan mengakhiri Ketentuan ini.

15. HUKUM YANG BERLAKU DAN PENYELESAIAN SENGKETA
15.1. Persyaratan dan Ketentuan ini diatur oleh dan ditafsirkan sesuai dengan hukum Republik Indonesia.
15.2. Setiap sengketa, perselisihan, atau klaim yang timbul dari atau terkait dengan Ketentuan ini pertama-tama akan diselesaikan secara musyawarah untuk mufakat dalam jangka waktu 30 (tiga puluh) hari kalender.
15.3. Apabila penyelesaian secara musyawarah tidak tercapai, para pihak sepakat untuk menyelesaikan sengketa melalui Pengadilan Negeri Jakarta Pusat, tanpa prejudice terhadap hak LTI untuk mengajukan gugatan ke pengadilan lain yang berwenang sesuai dengan hukum yang berlaku.

16. KETENTUAN UMUM
16.1. Seluruh pemberitahuan sehubungan dengan Ketentuan ini akan disampaikan secara tertulis melalui email ke alamat yang terdaftar pada akun Pengguna atau melalui pos tercatat ke alamat kantor LTI.
16.2. Apabila salah satu atau sebagian ketentuan dalam Perjanjian ini dinyatakan tidak sah, batal, atau tidak dapat dilaksanakan oleh pengadilan yang berwenang, ketentuan lainnya tetap berlaku dan mengikat para pihak secara penuh.
16.3. Kegagalan LTI dalam menegakkan ketentuan dalam Perjanjian ini tidak dianggap sebagai pengesampingan hak LTI untuk menegakkannya di kemudian hari.
16.4. Ketentuan ini merupakan seluruh kesepakatan antara para pihak dan menggantikan seluruh perjanjian, pernyataan, dan pemahaman sebelumnya, baik lisan maupun tertulis, sehubungan dengan objek Ketentuan ini.
16.5. Pengguna tidak boleh mengalihkan hak atau kewajibannya berdasarkan Ketentuan ini tanpa persetujuan tertulis terlebih dahulu dari LTI. LTI berhak untuk mengalihkan hak dan kewajibannya berdasarkan Ketentuan ini kepada afiliasi atau pihak ketiga dalam rangka restrukturisasi bisnis atau pengalihan usaha dengan pemberitahuan kepada Pengguna.

17. KONTAK DAN PENGADUAN
Apabila Anda memiliki pertanyaan, keluhan, atau memerlukan klarifikasi lebih lanjut mengenai Ketentuan ini, Anda dapat menghubungi tim keamanan informasi LTI melalui saluran berikut:
Email: security@lodaya.id
Telepon: +62-21-1234-5678 (Jam kerja: 08.00 – 17.00 WIB, Senin – Jumat)
Alamat: PT Lodaya Teknologi Indonesia, Graha LTI Lantai 5, Jl. Soepomo No. 88, Menteng Dalam, Jakarta Selatan, DKI Jakarta 12870, Indonesia

Dengan mencentang kotak di bawah, Anda menyatakan bahwa Anda adalah pengguna yang sah dan memiliki wewenang penuh untuk mengikat Organisasi Anda secara hukum terhadap seluruh Persyaratan dan Ketentuan Penggunaan Sistem LTI Anti-Phishing ini, serta telah membaca dan memahaminya sepenuhnya sebelum menggunakan Sistem.
`

const ICON_PATHS = {
  1: [["M12 6a4 4 0 0 1 8 0v5"], ["M6 12h20v14H6z"], ["M16 18v4"]],
  2: [["M16 4L4 10v6c0 6.3 5.4 12 12 12s12-5.7 12-12v-6z"], ["M10 15l4 4 8-8"]],
  3: [["M4 10h24v14H4z"], ["M4 10l12 9 12-9"], ["M20 18l4 2"], ["M4 16l4 2"]],
  4: [["M13 8a7 7 0 1 0 0 14 7 7 0 0 0 0-14z"], ["M18 18l8 8"], ["M8 12h10"], ["M8 16h8"]],
  5: [["M16 4a12 12 0 1 0 0 24 12 12 0 0 0 0-24z"], ["M11 17l3 3 7-7"]],
  6: [["M16 4a12 12 0 1 0 0 24 12 12 0 0 0 0-24z"], ["M11 11l10 10"], ["M21 11l-10 10"]],
  7: [["M16 4L2 28h28z"], ["M16 12v8"], ["M16 23v1"]],
  8: [["M10 12h12v4H10z"], ["M16 16v8"], ["M12 24h8v5h-8z"]],
}

const ICON_POOL = [
  { id: 1, label: 'Kunci Keamanan' },
  { id: 2, label: 'Perisai Proteksi' },
  { id: 3, label: 'Email Masuk' },
  { id: 4, label: 'Pemindaian' },
  { id: 5, label: 'Verifikasi' },
  { id: 6, label: 'Blokir' },
  { id: 7, label: 'Peringatan' },
  { id: 8, label: 'Akses' },
]

function PuzzleIcon({ id, size = 28 }) {
  const paths = ICON_PATHS[id]
  if (!paths) return null
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      {paths.map((seg, i) => <path key={i} d={seg.join(' ')} />)}
    </svg>
  )
}

export default function WelcomePage() {
  const navigate = useNavigate()
  const [step, setStep] = useState('tnc')
  const [tncRead, setTncRead] = useState(false)
  const [check1, setCheck1] = useState(false)
  const [check2, setCheck2] = useState(false)
  const tncRef = useRef(null)

  const puzzle = useMemo(() => {
    const shuffled = [...ICON_POOL].sort(() => Math.random() - 0.5)
    const board = shuffled.slice(0, 5)
    const clues = board.slice(0, 2)
    return { board, clues, boardLayout: board.sort(() => Math.random() - 0.5) }
  }, [])

  const [clueStep, setClueStep] = useState(0)
  const [completed, setCompleted] = useState(null)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState(false)

  const handleScroll = () => {
    if (!tncRef.current) return
    const { scrollTop, scrollHeight, clientHeight } = tncRef.current
    if (scrollHeight - scrollTop - clientHeight < 40) {
      setTncRead(true)
    }
  }

  const canConfirm = tncRead && check1 && check2

  const handleConfirm = () => {
    if (!canConfirm) return
    setStep('puzzle')
  }

  const handleBoardClick = (icon) => {
    if (error) setError('')
    const expected = puzzle.clues[clueStep]
    if (icon.id === expected.id) {
      const next = clueStep + 1
      setClueStep(next)
      setCompleted((p) => ({ ...p, [icon.id]: true }))
      if (next >= 2) {
        setSuccess(true)
        setTimeout(() => navigate('/login'), 900)
      }
    } else {
      setError(`Salah. Klik gambar yang sesuai dengan petunjuk ${clueStep + 1}.`)
      setClueStep(0)
      setCompleted(null)
    }
  }

  if (step === 'puzzle') {
    return (
      <div className={styles.page}>
        <div className={styles.card}>
          <div className={styles.logoRow}>
            <span className={styles.logoText}>LTI <b>Anti-Phishing</b></span>
          </div>
          <h1 className={styles.title}>Verifikasi Keamanan</h1>
          <p className={styles.subtitle}>Temukan ikon yang sesuai dengan petunjuk</p>

          {success ? (
            <div className={styles.successMsg}>
              <ShieldCheck size={32} />
              <span>Verifikasi berhasil! Mengarahkan ke login...</span>
            </div>
          ) : (
            <>
              {/* Clue icons - clearly shown */}
              <div className={styles.clueSection}>
                <p className={styles.clueTitle}>Petunjuk:</p>
                <div className={styles.clueRow}>
                  {puzzle.clues.map((c, i) => (
                    <div
                      key={c.id}
                      className={`${styles.clueCard} ${
                        completed?.[c.id] ? styles.clueDone : clueStep === i ? styles.clueActive : styles.clueInactive
                      }`}
                    >
                      <span className={styles.clueNum}>{i + 1}</span>
                      <PuzzleIcon id={c.id} size={32} />
                      <span className={styles.clueLabel}>{c.label}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Blurry board - 5 distorted icons */}
              <div className={styles.boardSection}>
                <p className={styles.boardHint}>Klik gambar buram yang sesuai dengan petunjuk di atas:</p>
                <div className={styles.boardGrid}>
                  {puzzle.boardLayout.map((icon) => {
                    const isCompleted = completed?.[icon.id]
                    return (
                      <button
                        key={icon.id}
                        className={`${styles.boardBtn} ${isCompleted ? styles.boardDone : ''}`}
                        onClick={() => !isCompleted && handleBoardClick(icon)}
                        disabled={!!isCompleted}
                      >
                        <PuzzleIcon id={icon.id} size={40} />
                        <span className={styles.boardLabel}>{icon.label}</span>
                      </button>
                    )
                  })}
                </div>
              </div>

              {error && <div className={styles.error}>{error}</div>}
            </>
          )}
        </div>
      </div>
    )
  }

  return (
    <div className={styles.page}>
      <div className={styles.card}>
        <div className={styles.logoRow}>
          <svg width="44" height="44" viewBox="0 0 40 40" fill="none">
            <circle cx="20" cy="20" r="20" fill="#f6f8fc"/>
            <path d="M20 6L8 11v9c0 6.07 5.12 11.74 12 13 6.88-1.26 12-6.93 12-13v-9L20 6z" fill="#EA4335"/>
            <path d="M20 6L8 11v9c0 6.07 5.12 11.74 12 13V6z" fill="#c5221f"/>
            <path d="M16 20l3 3 6-6" stroke="#fff" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
          <span className={styles.logoText}>LTI <b>Anti-Phishing</b></span>
        </div>

        <h1 className={styles.title}>Selamat Datang</h1>
        <p className={styles.subtitle}>Sistem Keamanan Email Perusahaan</p>

        <div
          ref={tncRef}
          className={styles.tncBox}
          onScroll={handleScroll}
        >
          {TNC_TEXT.trim().split('\n').filter(Boolean).map((line, i) => {
            const t = line.trim()
            const isTitle = t.startsWith('PERSYARATAN')
            const isArticle = /^\d{1,2}\.\s+[A-Z]/.test(t)
            const isSubArticle = /^\d{1,2}\.\d+\./.test(t)
            const isLetterItem = /^[a-z]\)\s/.test(t)
            let cls = styles.tncPara
            if (isTitle) cls = styles.tncTitle
            else if (isArticle) cls = styles.tncArticle
            else if (isSubArticle) cls = styles.tncSubArticle
            else if (isLetterItem) cls = styles.tncLetterItem
            return <p key={i} className={cls}>{t}</p>
          })}
        </div>

        {!tncRead && <p className={styles.scrollHint}>Gulir ke bawah untuk melanjutkan...</p>}

        <div className={`${styles.checkSection} ${tncRead ? styles.visible : ''}`}>
          <label className={styles.checkLabel}>
            <input type="checkbox" checked={check1} onChange={(e) => setCheck1(e.target.checked)} />
            <span>Saya telah membaca dan memahami seluruh persyaratan di atas</span>
          </label>
          <label className={styles.checkLabel}>
            <input type="checkbox" checked={check2} onChange={(e) => setCheck2(e.target.checked)} />
            <span>Saya menyetujui ketentuan penggunaan sistem ini</span>
          </label>
        </div>

        <button
          className={`${styles.btnConfirm} ${canConfirm ? styles.btnReady : ''}`}
          disabled={!canConfirm}
          onClick={handleConfirm}
        >
          Konfirmasi & Lanjutkan
          <ArrowRight size={18} />
        </button>
      </div>
    </div>
  )
}
