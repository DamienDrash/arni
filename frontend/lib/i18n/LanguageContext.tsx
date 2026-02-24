"use client";

import React, { createContext, useContext, useState, useEffect, ReactNode } from "react";

type Language = "de" | "en" | "bg";

interface i18nContextType {
  language: Language;
  setLanguage: (lang: Language) => void;
  t: (key: string) => string;
}

const LanguageContext = createContext<i18nContextType | undefined>(undefined);

// Helper to get nested properties from JSON via dot notation
const getNestedValue = (obj: any, path: string): string => {
  const keys = path.split(".");
  let current = obj;
  for (const key of keys) {
    if (current[key] === undefined) return path;
    current = current[key];
  }
  return current;
};

export const LanguageProvider = ({ children }: { children: ReactNode }) => {
  const [language, setLanguageState] = useState<Language>("en");
  const [translations, setTranslations] = useState<any>({});
  const [ready, setReady] = useState(false);

  const setLanguage = (lang: Language) => {
    setLanguageState(lang);
    localStorage.setItem("ariia_lang", lang);
    document.cookie = `ariia_lang=${lang}; path=/; max-age=31536000`;
    // Force reload to update all UI components (like NavShell metadata)
    window.location.reload();
  };

  useEffect(() => {
    // 1. Identification Priority
    const saved = localStorage.getItem("ariia_lang") as Language;
    const browserLang = typeof navigator !== "undefined" ? navigator.language.split("-")[0] : "en";
    
    let initialLang: Language = "en";
    if (["de", "en", "bg"].includes(saved)) {
      initialLang = saved;
    } else if (["de", "en", "bg"].includes(browserLang as Language)) {
      initialLang = browserLang as Language;
    }

    setLanguageState(initialLang);

    // 2. Load Translations
    const loadTranslations = async (lang: Language) => {
      try {
        const response = await fetch(`/arni/locales/${lang}.json?v=${Date.now()}`);
        if (!response.ok) throw new Error("Network response was not ok");
        const data = await response.json();
        setTranslations(data);
        setReady(true);
      } catch (error) {
        console.error("Failed to load translations", error);
        // Fallback to English if load fails
        if (lang !== "en") loadTranslations("en");
      }
    };

    void loadTranslations(initialLang);
  }, []);

  // Update translations when language changes manually
  useEffect(() => {
    const load = async () => {
      try {
        const response = await fetch(`/arni/locales/${language}.json?v=${Date.now()}`);
        if (!response.ok) throw new Error("Network response was not ok");
        const data = await response.json();
        setTranslations(data);
      } catch (err) {
        console.error("Manual reload failed", err);
      }
    };
    if (ready) void load();
  }, [language, ready]);

  const t = (key: string): string => {
    if (!ready || !translations) return "";
    return getNestedValue(translations, key);
  };

  return (
    <LanguageContext.Provider value={{ language, setLanguage, t }}>
      {children}
    </LanguageContext.Provider>
  );
};

export const useI18n = () => {
  const context = useContext(LanguageContext);
  if (context === undefined) {
    throw new Error("useI18n must be used within a LanguageProvider");
  }
  return context;
};
