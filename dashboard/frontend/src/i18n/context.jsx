import { createContext, useContext, useState, useCallback, useMemo } from 'react'
import en from './en.json'
import id from './id.json'

const LOCALES = { en, id }

const I18nContext = createContext(null)

export function I18nProvider({ children }) {
  const [lang, setLangState] = useState(() => {
    try { return localStorage.getItem('app-lang') || 'id' }
    catch { return 'id' }
  })

  const setLang = useCallback((l) => {
    setLangState(l)
    try { localStorage.setItem('app-lang', l) } catch {}
  }, [])

  const toggleLang = useCallback(() => {
    setLang(lang === 'id' ? 'en' : 'id')
  }, [lang, setLang])

  const t = useCallback((key, fallback) => {
    return LOCALES[lang]?.[key] ?? fallback ?? key
  }, [lang])

  const value = useMemo(() => ({ lang, setLang, toggleLang, t }), [lang, setLang, toggleLang, t])

  return (
    <I18nContext.Provider value={value}>
      {children}
    </I18nContext.Provider>
  )
}

export function useTranslation() {
  const ctx = useContext(I18nContext)
  if (!ctx) throw new Error('useTranslation must be used within I18nProvider')
  return ctx
}
