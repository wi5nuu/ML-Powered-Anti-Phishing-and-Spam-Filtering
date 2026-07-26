import GmailShell from '../components/layout/GmailShell'
import { useMe } from '../api/auth'
import { useTranslation } from '../i18n/context'
import styles from './HelpPage.module.css'

export default function HelpPage() {
  const { data: me } = useMe()
  const { t } = useTranslation()
  const role = me?.user?.role || ''
  const isUser = role === 'user'
  const isAdmin = role === 'admin'
  const isSuper = role === 'superadmin'

  return (
    <GmailShell>
      <div className={styles.wrapper}>
        <h1 className={styles.title}>{t('help.pageTitle')}</h1>
        <p className={styles.subtitle}>
          {isSuper && t('help.subtitle.super')}
          {isAdmin && t('help.subtitle.admin')}
          {isUser && t('help.subtitle.user')}
        </p>

        <section className={styles.section}>
          <h2 className={styles.sectionTitle}>{t('help.section1.title')}</h2>
          <p className={styles.paragraph}>{t('help.section1.intro')}</p>
          <div className={styles.mlDetail}>
            <div className={styles.mlStep}>
              <div className={styles.mlStepNumber}>1</div>
              <div className={styles.mlStepContent}>
                <div className={styles.mlStepTitle}>{t('help.section1.step1.title')}</div>
                <div className={styles.mlStepText}>{t('help.section1.step1.text')}</div>
              </div>
            </div>
            <div className={styles.mlStep}>
              <div className={styles.mlStepNumber}>2</div>
              <div className={styles.mlStepContent}>
                <div className={styles.mlStepTitle}>{t('help.section1.step2.title')}</div>
                <div className={styles.mlStepText}>{t('help.section1.step2.text')}</div>
              </div>
            </div>
            <div className={styles.mlStep}>
              <div className={styles.mlStepNumber}>3</div>
              <div className={styles.mlStepContent}>
                <div className={styles.mlStepTitle}>{t('help.section1.step3.title')}</div>
                <div className={styles.mlStepText}>{t('help.section1.step3.text')}</div>
              </div>
            </div>
            <div className={styles.mlStep}>
              <div className={styles.mlStepNumber}>4</div>
              <div className={styles.mlStepContent}>
                <div className={styles.mlStepTitle}>{t('help.section1.step4.title')}</div>
                <div className={styles.mlStepText}>{t('help.section1.step4.text')}</div>
              </div>
            </div>
            <div className={styles.mlStep}>
              <div className={styles.mlStepNumber}>5</div>
              <div className={styles.mlStepContent}>
                <div className={styles.mlStepTitle}>{t('help.section1.step5.title')}</div>
                <div className={styles.mlStepText}>{t('help.section1.step5.text')}</div>
              </div>
            </div>
            <div className={styles.mlStep}>
              <div className={styles.mlStepNumber}>6</div>
              <div className={styles.mlStepContent}>
                <div className={styles.mlStepTitle}>{t('help.section1.step6.title')}</div>
                <div className={styles.mlStepText}>{t('help.section1.step6.text')}</div>
              </div>
            </div>
          </div>
        </section>

        <section className={styles.section}>
          <h2 className={styles.sectionTitle}>{t('help.section2.title')}</h2>
          <div className={styles.grid}>
            <div className={styles.card}>
              <div className={styles.cardIcon}>🟢</div>
              <div className={styles.cardTitle}>{t('help.section2.card1.title')}</div>
              <div className={styles.cardText}>{t('help.section2.card1.text')}</div>
            </div>
            <div className={styles.card}>
              <div className={styles.cardIcon}>🟠</div>
              <div className={styles.cardTitle}>{t('help.section2.card2.title')}</div>
              <div className={styles.cardText}>{t('help.section2.card2.text')}</div>
            </div>
            <div className={styles.card}>
              <div className={styles.cardIcon}>🔴</div>
              <div className={styles.cardTitle}>{t('help.section2.card3.title')}</div>
              <div className={styles.cardText}>{t('help.section2.card3.text')}</div>
            </div>
            <div className={styles.card}>
              <div className={styles.cardIcon}>⚠️</div>
              <div className={styles.cardTitle}>{t('help.section2.card4.title')}</div>
              <div className={styles.cardText}>{t('help.section2.card4.text')}</div>
            </div>
            <div className={styles.card}>
              <div className={styles.cardIcon}>🚫</div>
              <div className={styles.cardTitle}>{t('help.section2.card5.title')}</div>
              <div className={styles.cardText}>{t('help.section2.card5.text')}</div>
            </div>
          </div>
        </section>

        {isUser && (
          <section className={styles.section}>
            <h2 className={styles.sectionTitle}>{t('help.section3.title')}</h2>
            <div className={styles.roleGuide}>
              <ol className={styles.roleSteps}>
                <li dangerouslySetInnerHTML={{ __html: t('help.section3.step1') }} />
                <li dangerouslySetInnerHTML={{ __html: t('help.section3.step2') }} />
                <li dangerouslySetInnerHTML={{ __html: t('help.section3.step3') }} />
                <li dangerouslySetInnerHTML={{ __html: t('help.section3.step4') }} />
                <li dangerouslySetInnerHTML={{ __html: t('help.section3.step5') }} />
                <li dangerouslySetInnerHTML={{ __html: t('help.section3.step6') }} />
                <li dangerouslySetInnerHTML={{ __html: t('help.section3.step7') }} />
                <li dangerouslySetInnerHTML={{ __html: t('help.section3.step8') }} />
              </ol>
            </div>
          </section>
        )}

        {(isAdmin || isSuper) && (
          <section className={styles.section}>
            <h2 className={styles.sectionTitle}>{isSuper ? '4.' : '3.'} {t('help.section4.title')}</h2>
            <div className={styles.roleGuide}>
              <ol className={styles.roleSteps}>
                <li dangerouslySetInnerHTML={{ __html: t('help.section4.step1') }} />
                <li dangerouslySetInnerHTML={{ __html: t('help.section4.step2') }} />
                <li dangerouslySetInnerHTML={{ __html: t('help.section4.step3') }} />
                <li dangerouslySetInnerHTML={{ __html: t('help.section4.step4') }} />
                <li dangerouslySetInnerHTML={{ __html: t('help.section4.step5') }} />
                <li dangerouslySetInnerHTML={{ __html: t('help.section4.step6') }} />
              </ol>
            </div>
          </section>
        )}

        {isSuper && (
          <section className={styles.section}>
            <h2 className={styles.sectionTitle}>{t('help.section5.title')}</h2>
            <div className={styles.roleGuide}>
              <ol className={styles.roleSteps}>
                <li dangerouslySetInnerHTML={{ __html: t('help.section5.step1') }} />
                <li dangerouslySetInnerHTML={{ __html: t('help.section5.step2') }} />
                <li dangerouslySetInnerHTML={{ __html: t('help.section5.step3') }} />
              </ol>
            </div>
          </section>
        )}

        <section className={styles.section}>
          <h2 className={styles.sectionTitle}>{isSuper ? '6.' : isAdmin ? '4.' : '3.'} {t('help.faq.title')}</h2>

          {isUser && (
            <>
              <div className={styles.faqItem}>
                <div className={styles.faqQ}>{t('help.faq.user.q1')}</div>
                <div className={styles.faqA}>{t('help.faq.user.a1')}</div>
              </div>
              <div className={styles.faqItem}>
                <div className={styles.faqQ}>{t('help.faq.user.q2')}</div>
                <div className={styles.faqA}>{t('help.faq.user.a2')}</div>
              </div>
              <div className={styles.faqItem}>
                <div className={styles.faqQ}>{t('help.faq.user.q3')}</div>
                <div className={styles.faqA}>{t('help.faq.user.a3')}</div>
              </div>
              <div className={styles.faqItem}>
                <div className={styles.faqQ}>{t('help.faq.user.q4')}</div>
                <div className={styles.faqA}>{t('help.faq.user.a4')}</div>
              </div>
            </>
          )}

          {isAdmin && (
            <>
              <div className={styles.faqItem}>
                <div className={styles.faqQ}>{t('help.faq.admin.q1')}</div>
                <div className={styles.faqA}>{t('help.faq.admin.a1')}</div>
              </div>
              <div className={styles.faqItem}>
                <div className={styles.faqQ}>{t('help.faq.admin.q2')}</div>
                <div className={styles.faqA}>{t('help.faq.admin.a2')}</div>
              </div>
              <div className={styles.faqItem}>
                <div className={styles.faqQ}>{t('help.faq.admin.q3')}</div>
                <div className={styles.faqA}>{t('help.faq.admin.a3')}</div>
              </div>
              <div className={styles.faqItem}>
                <div className={styles.faqQ}>{t('help.faq.admin.q4')}</div>
                <div className={styles.faqA}>{t('help.faq.admin.a4')}</div>
              </div>
            </>
          )}

          {isSuper && (
            <>
              <div className={styles.faqItem}>
                <div className={styles.faqQ}>{t('help.faq.super.q1')}</div>
                <div className={styles.faqA}>{t('help.faq.super.a1')}</div>
              </div>
              <div className={styles.faqItem}>
                <div className={styles.faqQ}>{t('help.faq.super.q2')}</div>
                <div className={styles.faqA}>{t('help.faq.super.a2')}</div>
              </div>
              <div className={styles.faqItem}>
                <div className={styles.faqQ}>{t('help.faq.super.q3')}</div>
                <div className={styles.faqA}>{t('help.faq.super.a3')}</div>
              </div>
              <div className={styles.faqItem}>
                <div className={styles.faqQ}>{t('help.faq.super.q4')}</div>
                <div className={styles.faqA}>{t('help.faq.super.a4')}</div>
              </div>
            </>
          )}
        </section>

        <section className={styles.section}>
          <h2 className={styles.sectionTitle}>{isSuper ? '7.' : isAdmin ? '5.' : '4.'} {t('help.tips.title')}</h2>
          <ul className={styles.tipsList}>
            <li>{t('help.tips.item1')}</li>
            <li>{t('help.tips.item2')}</li>
            <li>{t('help.tips.item3')}</li>
            <li>{t('help.tips.item4')}</li>
            <li>{t('help.tips.item5')}</li>
          </ul>
        </section>
      </div>
    </GmailShell>
  )
}
