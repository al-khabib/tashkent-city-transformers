import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import en from './locales/en.json';
import ru from './locales/ru.json';
import uz from './locales/uz.json';

const LANGUAGE_STORAGE_KEY = 'dashboard-language';
const savedLanguage =
  typeof window !== 'undefined' ? window.localStorage.getItem(LANGUAGE_STORAGE_KEY) : null;

i18n.use(initReactI18next).init({
  resources: {
    en: { translation: en },
    ru: { translation: ru },
    uz: { translation: uz },
  },
  lng: savedLanguage || 'en',
  fallbackLng: 'en',
  interpolation: {
    escapeValue: false,
  },
});

if (typeof window !== 'undefined') {
  i18n.on('languageChanged', (language) => {
    window.localStorage.setItem(LANGUAGE_STORAGE_KEY, language);
  });
}

export default i18n;
export { LANGUAGE_STORAGE_KEY };
