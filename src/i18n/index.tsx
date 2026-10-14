import AsyncStorage from '@react-native-async-storage/async-storage';
import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from 'react';
import { catalog } from './catalog';

export const languages = [
  { code: 'en', name: 'English', locale: 'en-GB' },
  { code: 'ro', name: 'Română', locale: 'ro-RO' },
  { code: 'es', name: 'Español', locale: 'es-ES' },
  { code: 'fr', name: 'Français', locale: 'fr-FR' },
  { code: 'de', name: 'Deutsch', locale: 'de-DE' },
  { code: 'it', name: 'Italiano', locale: 'it-IT' },
] as const;
export type Language = typeof languages[number]['code'];
type Params = Record<string, string | number>;
const LanguageContext = createContext<{ language: Language; setLanguage: (language: Language) => void }>({ language: 'en', setLanguage: () => {} });

export function I18nProvider({ children }: { children: ReactNode }) {
  const [language, updateLanguage] = useState<Language>('en');
  const manuallySelected = useRef(false);
  useEffect(() => {
    let mounted = true;
    void AsyncStorage.getItem('ghost-travel-language').then((saved) => {
      if (mounted && !manuallySelected.current && languages.some((item) => item.code === saved)) updateLanguage(saved as Language);
    }).catch(() => {});
    return () => { mounted = false; };
  }, []);
  const setLanguage = (next: Language) => {
    manuallySelected.current = true;
    updateLanguage(next);
    void AsyncStorage.setItem('ghost-travel-language', next).catch(() => {});
  };
  return <LanguageContext.Provider value={{ language, setLanguage }}>{children}</LanguageContext.Provider>;
}

export function useI18n() {
  const context = useContext(LanguageContext);
  const index = languages.findIndex((item) => item.code === context.language);
  const locale = languages[index].locale;
  const t = (key: string, params: Params = {}) => (catalog[key]?.[index] ?? key).replace(/\{(\w+)\}/g, (match, name: string) => String(params[name] ?? match));
  const formatDate = (value?: string) => value ? new Date(`${value}T12:00:00`).toLocaleDateString(locale, { day: 'numeric', month: 'short', year: 'numeric' }) : '';
  const formatBudget = (value: number) => new Intl.NumberFormat(locale, { style: 'currency', currency: 'EUR' }).format(value);
  return { ...context, locale, t, formatDate, formatBudget };
}
