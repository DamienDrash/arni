"use client";

import React, { createContext, useContext, useState, useEffect, ReactNode } from "react";

// Static imports for Gold Standard performance & no-flicker
import de from "../../locales/de.json";
import en from "../../locales/en.json";
import bg from "../../locales/bg.json";

const dictionaries: Record<string, any> = { de, en, bg };

type Language = "de" | "en" | "bg";

interface i18nContextType {
  language: Language;
  setLanguage: (lang: Language) => void;
  t: (key: string) => any; // Return any to support arrays/objects if needed
}

const LanguageContext = createContext<i18nContextType | undefined>(undefined);

const getNestedValue = (obj: any, path: string): any => {
  const keys = path.split(".");
  let current = obj;
  for (const key of keys) {
    if (!current || current[key] === undefined) return path;
    current = current[key];
  }
  return current;
};

export const LanguageProvider = ({ children }: { children: ReactNode }) => {
  const [language, setLanguageState] = useState<Language>("en");
  const [mounted, setReady] = useState(false);

  const setLanguage = (lang: Language) => {
    setLanguageState(lang);
    if (typeof window !== "undefined") {
      localStorage.setItem("ariia_lang", lang);
      document.cookie = `ariia_lang=${lang}; path=/; max-age=31536000`;
      // We don't force reload unless strictly necessary for metadata sync
      // window.location.reload(); 
    }
  };

  useEffect(() => {
    const saved = localStorage.getItem("ariia_lang") as Language;
    const browserLang = navigator.language.split("-")[0] as Language;
    
    if (["de", "en", "bg"].includes(saved)) {
      setLanguageState(saved);
    } else if (["de", "en", "bg"].includes(browserLang)) {
      setLanguageState(browserLang);
    }
    setReady(true);
  }, []);

  const t = (key: string): any => {
    const dict = dictionaries[language] || dictionaries["en"];
    return getNestedValue(dict, key);
  };

  // Avoid hydration mismatch by rendering a consistent state until mounted
  if (!mounted) {
    return <div style={{ visibility: "hidden" }}>{children}</div>;
  }

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
