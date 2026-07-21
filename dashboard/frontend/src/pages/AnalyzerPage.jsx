import { useState, useRef } from 'react'
import {
  Search, Upload, AlertTriangle, CheckCircle, Shield,
  ChevronDown, ChevronUp, ExternalLink, X, Loader2,
  Info, Activity, Link as LinkIcon, FileText
} from 'lucide-react'
import GmailShell from '../components/layout/GmailShell'
import { useAnalyzeEmail } from '../api/analyzer'
import { useToast } from '../hooks/useToast'
import { useTranslation } from '../i18n/context'
import styles from './AnalyzerPage.module.css'

// ─── Risk gauge ─────────────────────────────────────────────────────────────────
function RiskGauge({ score }) {
  const { t } = useTranslation()
  const pct = Math.round((score || 0) * 100)
  const angle = -135 + pct * 2.7
  const color = pct >= 70 ? '#EA4335' : pct >= 40 ? '#FBBC04' : '#34A853'
  return (
    <div className={styles.gaugeWrap} aria-label={`${t('analyzer.riskScore')}: ${pct}%`}>
      <svg viewBox="0 0 120 80" className={styles.gaugeSvg}>
        <path d="M10,70 A50,50 0 0,1 110,70" fill="none" stroke="#e8eaed" strokeWidth="12" strokeLinecap="round" />
        <path
          d="M10,70 A50,50 0 0,1 110,70"
          fill="none"
          stroke={color}
          strokeWidth="12"
          strokeLinecap="round"
          strokeDasharray={`${pct * 1.57} 157`}
          style={{ transition: 'stroke-dasharray 0.6s ease, stroke 0.6s ease' }}
        />
        <line
          x1="60" y1="70"
          x2={60 + 36 * Math.cos((angle * Math.PI) / 180)}
          y2={70 + 36 * Math.sin((angle * Math.PI) / 180)}
          stroke={color}
          strokeWidth="2.5"
          strokeLinecap="round"
          style={{ transition: 'all 0.6s ease' }}
        />
        <circle cx="60" cy="70" r="4" fill={color} />
      </svg>
      <div className={styles.gaugeValue} style={{ color }}>{pct}</div>
      <div className={styles.gaugeLabel}>{t('analyzer.riskScore')}</div>
    </div>
  )
}

// ─── Badge ───────────────────────────────────────────────────────────────────────
const LABEL_CFG = {
  QUARANTINE: { bg: '#fce8e6', fg: '#c5221f', icon: AlertTriangle, key: 'analyzer.labelQuarantine' },
  WARN:       { bg: '#fef7e0', fg: '#8c6d1f', icon: AlertTriangle, key: 'analyzer.labelWarn' },
  CLEAN:      { bg: '#e6f4ea', fg: '#137333', icon: CheckCircle, key: 'analyzer.labelClean' },
  UNKNOWN:    { bg: '#e8eaed', fg: '#5f6368', icon: Info, key: 'analyzer.labelUnknown' },
}

function ClassificationBadge({ label }) {
  const { t } = useTranslation()
  const cfg = LABEL_CFG[label] || LABEL_CFG.UNKNOWN
  const Icon = cfg.icon
  return (
    <span className={styles.badge} style={{ background: cfg.bg, color: cfg.fg }}>
      <Icon size={14} /> {t(cfg.key)}
    </span>
  )
}

// ─── Confidence bar ──────────────────────────────────────────────────────────────
function ConfidenceBar({ value, label, color }) {
  return (
    <div className={styles.confRow}>
      <span className={styles.confLabel}>{label}</span>
      <div className={styles.confBar}>
        <div
          className={styles.confFill}
          style={{ width: `${Math.round((value || 0) * 100)}%`, background: color }}
        />
      </div>
      <span className={styles.confVal} style={{ color }}>
        {Math.round((value || 0) * 100)}%
      </span>
    </div>
  )
}

// ─── Collapsible raw header ──────────────────────────────────────────────────────
function RawHeaderViewer({ raw }) {
  const { t } = useTranslation()
  const [open, setOpen] = useState(false)
  return (
    <div className={styles.rawWrap}>
      <button
        className={styles.rawToggle}
        onClick={() => setOpen(v => !v)}
        id="analyzer-raw-toggle"
      >
        <FileText size={14} />
        {t('analyzer.rawHeader')}
        {open ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
      </button>
      {open && (
        <pre className={styles.rawPre}>{raw || t('analyzer.noHeader')}</pre>
      )}
    </div>
  )
}

// ─── Main component ──────────────────────────────────────────────────────────────
export default function AnalyzerPage() {
  const [rawEmail, setRawEmail] = useState('')
  const [result, setResult] = useState(null)
  const fileInputRef = useRef(null)
  const { addToast } = useToast()
  const { t } = useTranslation()

  const { mutate: analyze, isPending } = useAnalyzeEmail()

  const handleAnalyze = () => {
    if (!rawEmail.trim()) {
      addToast(t('analyzer.emptyInput'), 'warning')
      return
    }
    analyze(rawEmail, {
      onSuccess: (data) => {
        setResult(data)
        addToast(t('analyzer.analysisDone'), 'success')
      },
      onError: (err) => {
        const msg = err?.response?.data?.detail || t('analyzer.error')
        addToast(msg, 'error')
      },
    })
  }

  const handleFileUpload = (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    if (!file.name.endsWith('.eml') && file.type !== 'message/rfc822') {
      addToast(t('analyzer.fileRequired'), 'warning')
      return
    }
    const reader = new FileReader()
    reader.onload = (ev) => setRawEmail(ev.target.result || '')
    reader.readAsText(file)
    addToast(`"${file.name}" ${t('analyzer.fileLoaded')}`, 'success')
  }

  const handleClear = () => {
    setRawEmail('')
    setResult(null)
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  // Score helpers
  const fusedScore = result?.fused_score ?? result?.spam_score ?? 0
  const mlProb = result?.ml_probability ?? result?.confidence ?? 0
  const saScore = result?.sa_score ?? 0
  const anomalyScore = result?.anomaly_score ?? 0
  const label = result?.label ?? (result?.classification?.toUpperCase()) ?? 'UNKNOWN'
  const reasons = result?.reasons || result?.human_reasons || []
  const urlAnalysis = result?.url_analysis || []
  const recommendedAction = result?.recommended_action

  return (
    <GmailShell>
      <div className={styles.wrap}>
        <div className={styles.header}>
          <h1 className={styles.title}>
            <Search size={22} />
            {t('analyzer.title')}
          </h1>
          <p className={styles.subtitle}>
            {t('analyzer.subtitle')}
          </p>
        </div>

        <div className={styles.body}>
          {/* ── Input Panel ─────────────────────────────────────── */}
          <div className={styles.inputPanel}>
            <div className={styles.textareaWrap}>
              <textarea
                id="analyzer-textarea"
                className={styles.textarea}
                placeholder={t('analyzer.placeholder')}
                value={rawEmail}
                onChange={(e) => setRawEmail(e.target.value)}
                spellCheck={false}
              />
              {rawEmail && (
                <button
                  className={styles.clearBtn}
                  onClick={handleClear}
                  title={t('analyzer.clear')}
                  id="analyzer-clear-btn"
                >
                  <X size={16} />
                </button>
              )}
            </div>

            <div className={styles.actions}>
              <input
                ref={fileInputRef}
                type="file"
                accept=".eml,message/rfc822"
                id="analyzer-file-input"
                style={{ display: 'none' }}
                onChange={handleFileUpload}
              />
              <button
                className={styles.btnSecondary}
                onClick={() => fileInputRef.current?.click()}
                id="analyzer-upload-btn"
              >
                <Upload size={16} />
                {t('analyzer.upload')}
              </button>
              <button
                className={styles.btnPrimary}
                onClick={handleAnalyze}
                disabled={isPending || !rawEmail.trim()}
                id="analyzer-analyze-btn"
              >
                {isPending ? (
                  <><Loader2 size={16} className={styles.spin} /> {t('analyzer.analyzing')}</>
                ) : (
                  <><Search size={16} /> {t('analyzer.analyze')}</>
                )}
              </button>
            </div>
          </div>

          {/* ── Result Panel ─────────────────────────────────────── */}
          {result && (
            <div className={styles.resultPanel}>
              {/* Recommendation banner */}
              {recommendedAction && (
                <div className={`${styles.banner} ${
                  recommendedAction === 'quarantine' ? styles.bannerDanger
                  : recommendedAction === 'warn' ? styles.bannerWarn
                  : styles.bannerSafe
                }`}>
                  {recommendedAction === 'quarantine' && <AlertTriangle size={18} />}
                  {recommendedAction === 'warn' && <AlertTriangle size={18} />}
                  {recommendedAction === 'deliver' && <CheckCircle size={18} />}
                  <strong>{t('analyzer.recommendation')}</strong>{' '}
                  {recommendedAction === 'quarantine'
                    ? t('analyzer.recQuarantine')
                    : recommendedAction === 'warn'
                    ? t('analyzer.recWarn')
                    : t('analyzer.recDeliver')}
                </div>
              )}

              {/* Top row: gauge + classification */}
              <div className={styles.topRow}>
                <RiskGauge score={fusedScore} />
                <div className={styles.classInfo}>
                  <div className={styles.classLabel}>{t('analyzer.label')}</div>
                  <ClassificationBadge label={label} />

                  {result.subject && (
                    <div className={styles.metaItem}>
                      <span className={styles.metaKey}>{t('common.subject')}</span>
                      <span className={styles.metaVal}>{result.subject}</span>
                    </div>
                  )}
                  {result.sender && (
                    <div className={styles.metaItem}>
                      <span className={styles.metaKey}>{t('common.sender')}</span>
                      <span className={styles.metaVal}>{result.sender}</span>
                    </div>
                  )}
                  {result.processing_time_ms != null && (
                    <div className={styles.metaItem}>
                      <span className={styles.metaKey}>{t('analyzer.processingTime')}</span>
                      <span className={styles.metaVal}>{result.processing_time_ms} {t('analyzer.ms')}</span>
                    </div>
                  )}
                </div>
              </div>

              {/* Confidence bars */}
              <div className={styles.card}>
                <h3 className={styles.cardTitle}><Activity size={15} /> {t('analyzer.detectionScores')}</h3>
                <ConfidenceBar value={fusedScore} label={t('analyzer.fusedScore')} color="#1a73e8" />
                <ConfidenceBar value={mlProb} label={t('analyzer.mlScore')} color="#8b44e8" />
                <ConfidenceBar value={anomalyScore} label={t('analyzer.anomalyScore')} color="#e8780a" />
                {saScore > 0 && (
                  <ConfidenceBar value={saScore / 20} label={t('analyzer.saScore').replace('{score}', saScore.toFixed(1))} color="#ea4335" />
                )}
              </div>

              {/* XAI Reasons */}
              {reasons.length > 0 && (
                <div className={styles.card}>
                  <h3 className={styles.cardTitle}><AlertTriangle size={15} /> {t('analyzer.xaiTitle')}</h3>
                  <ul className={styles.reasonsList}>
                    {reasons.map((r, i) => (
                      <li key={i} className={styles.reasonItem}>
                        <span className={styles.reasonDot} />
                        {typeof r === 'string' ? r : `${r.key}: ${r.value}`}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* URL Analysis */}
              {urlAnalysis.length > 0 && (
                <div className={styles.card}>
                  <h3 className={styles.cardTitle}><LinkIcon size={15} /> {t('analyzer.urlTitle').replace('{count}', urlAnalysis.length)}</h3>
                  <div className={styles.urlTable}>
                    <div className={styles.urlHeader}>
                      <span>{t('analyzer.urlHeader')}</span>
                      <span>{t('analyzer.statusHeader')}</span>
                      <span>{t('analyzer.lookalikeHeader')}</span>
                      <span>{t('analyzer.editDistHeader')}</span>
                    </div>
                    {urlAnalysis.map((u, i) => (
                      <div key={i} className={styles.urlRow}>
                        <span className={styles.urlText} title={u.url}>
                          <ExternalLink size={12} />
                          {u.url?.length > 55 ? u.url.slice(0, 52) + '…' : u.url}
                        </span>
                        <span className={u.is_suspicious ? styles.urlDanger : styles.urlSafe}>
                          {u.is_suspicious ? t('analyzer.urlSuspicious') : t('analyzer.urlSafe')}
                        </span>
                        <span className={styles.urlLookalike}>
                          {u.lookalike_of || '—'}
                        </span>
                        <span className={styles.urlDist}>
                          {u.levenshtein_score != null ? u.levenshtein_score : '—'}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Raw Header */}
              <RawHeaderViewer raw={rawEmail} />
            </div>
          )}

          {/* Empty state */}
          {!result && !isPending && (
            <div className={styles.emptyResult}>
              <Shield size={56} opacity={0.15} />
              <p>{t('analyzer.emptyResult')}</p>
            </div>
          )}

          {/* Loading skeleton */}
          {isPending && !result && (
            <div className={styles.skeleton}>
              <div className={styles.skeletonRow} style={{ height: 120 }} />
              <div className={styles.skeletonRow} style={{ height: 80 }} />
              <div className={styles.skeletonRow} style={{ height: 200 }} />
            </div>
          )}
        </div>
      </div>
    </GmailShell>
  )
}
