"use client";

import React, { createContext, useContext, useState, useEffect, ReactNode, useCallback, useRef } from "react";

import de from "../../locales/de.json";
import en from "../../locales/en.json";
import fr from "../../locales/fr.json";
import es from "../../locales/es.json";
import it from "../../locales/it.json";
import pt from "../../locales/pt.json";
import nl from "../../locales/nl.json";
import ru from "../../locales/ru.json";
import bg from "../../locales/bg.json";
import ja from "../../locales/ja.json";
import ko from "../../locales/ko.json";
import zh from "../../locales/zh.json";

const dictionaries: Record<string, any> = { de, en, fr, es, it, pt, nl, ru, bg, ja, ko, zh };

type Language = "de" | "en" | "fr" | "es" | "it" | "pt" | "nl" | "ru" | "bg" | "ja" | "ko" | "zh";
const ALLOWED_LANGUAGES: Language[] = ["de", "en", "fr", "es", "it", "pt", "nl", "ru", "bg", "ja", "ko", "zh"];

// GLOBAL SINGLETON: This survives even if the component remounts or parents re-render
let globalLanguage: Language = "en";

interface i18nContextType {
  language: Language;
  setLanguage: (lang: Language) => void;
  t: (key: string, variables?: Record<string, any>) => any;
}

const LanguageContext = createContext<i18nContextType | undefined>(undefined);

const getNestedValue = (obj: any, path: string): any => {
  if (!obj) return undefined;
  const keys = path.split(".");
  let current = obj;
  for (const key of keys) {
    if (current[key] === undefined) return undefined;
    current = current[key];
  }
  return current;
};

export const LanguageProvider = ({ children }: { children: ReactNode }) => {
  const [language, setLanguageState] = useState<Language | null>(null);
  const isInitialized = useRef(false);

  useEffect(() => {
    if (isInitialized.current) return;
    
    // 1. Recover from storage
    const saved = localStorage.getItem("ariia_lang") as Language;
    const finalLang: Language = (saved && ALLOWED_LANGUAGES.includes(saved)) ? saved : "en";
    
    console.log(`[i18n] BOOTSTRAP: Setting language to ${finalLang}`);
    globalLanguage = finalLang;
    setLanguageState(finalLang);
    
    // Set global helper for debug
    (window as any).ariia_lang = finalLang;
    
    isInitialized.current = true;
  }, []);

  const setLanguage = useCallback((lang: Language) => {
    if (!ALLOWED_LANGUAGES.includes(lang)) return;
    
    console.log(`[i18n] USER SWITCH: Changing to ${lang}`);
    globalLanguage = lang;
    setLanguageState(lang);
    localStorage.setItem("ariia_lang", lang);
    (window as any).ariia_lang = lang;
    
    // Optional: Sync to backend
    fetch("/ariia/proxy/auth/profile-settings", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ locale: lang })
    }).catch(() => {});
  }, []);

  const t = useCallback((key: string, variables?: Record<string, any>): any => {
    // ALWAYS USE THE GLOBAL SINGLETON FOR RESOLUTION TO PREVENT FLICKER
    const activeLang = globalLanguage || "en";
    
    const dict = dictionaries[activeLang] || dictionaries["en"];
    let value = getNestedValue(dict, key);
    
    // FALLBACK ONLY TO ENGLISH (Allow arrays)
    if (value === undefined || (typeof value === 'object' && !Array.isArray(value))) {
      value = getNestedValue(dictionaries["en"], key);
    }
    
    if (value === undefined || (typeof value === 'object' && !Array.isArray(value))) {
      return key;
    }

    if (typeof value === "string" && variables) {
      Object.entries(variables).forEach(([k, v]) => {
        value = (value as string).replace(`{{${k}}}`, String(v));
      });
    }
    return value;
  }, []); // Static reference, depends on global singleton

  if (language === null) return null;

  return (
    <LanguageContext.Provider value={{ language, setLanguage, t }}>
      {children}
    </LanguageContext.Provider>
  );
};

export const useI18n = () => {
  const context = useContext(LanguageContext);
  if (context === undefined) {
    return { language: "en" as Language, setLanguage: () => {}, t: (key: string) => key };
  }
  return context;
};
