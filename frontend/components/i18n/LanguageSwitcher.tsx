"use client";

import React, { useState, useRef, useEffect } from "react";
import { Globe, ChevronDown, Check } from "lucide-react";
import { useI18n } from "@/lib/i18n/LanguageContext";
import { motion, AnimatePresence } from "framer-motion";

const languages = [
  { code: "de", label: "Deutsch", flag: "de" },
  { code: "en", label: "English", flag: "us" },
  { code: "fr", label: "Français", flag: "fr" },
  { code: "es", label: "Español", flag: "es" },
  { code: "it", label: "Italiano", flag: "it" },
  { code: "pt", label: "Português", flag: "pt" },
  { code: "nl", label: "Nederlands", flag: "nl" },
  { code: "bg", label: "Български", flag: "bg" },
  { code: "ru", label: "Русский", flag: "ru" }
];

export default function LanguageSwitcher() {
  const { language, setLanguage } = useI18n();
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const currentLang = languages.find(l => l.code === language) || languages[1];

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2.5 px-3 py-1.5 rounded-lg transition-all duration-200 text-sm font-medium"
        style={{ 
          background: "oklch(0.62 0.22 292 / 0.12)", 
          color: "oklch(0.72 0.2 292)",
          border: "1px solid oklch(0.62 0.22 292 / 0.25)" 
        }}
      >
        <img 
          src={`https://flagcdn.com/w40/${currentLang.flag}.png`} 
          alt={currentLang.label}
          className="w-5 h-auto rounded-sm shadow-sm"
        />
        <span className="hidden xs:inline">{currentLang.label}</span>
        <ChevronDown size={14} className={`transition-transform duration-200 ${isOpen ? "rotate-180" : ""}`} />
      </button>

      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0, y: 10, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 10, scale: 0.95 }}
            transition={{ duration: 0.15 }}
            className="absolute left-0 mt-2 w-52 rounded-xl shadow-2xl overflow-hidden z-[100] backdrop-blur-xl"
            style={{ 
              background: "oklch(0.12 0.04 270 / 0.98)", 
              border: "1px solid oklch(0.62 0.22 292 / 0.35)",
              boxShadow: "0 20px 50px -12px oklch(0 0 0 / 0.6)"
            }}
          >
            <div className="py-1.5">
              {languages.map((lang) => (
                <button
                  key={lang.code}
                  onClick={() => {
                    setLanguage(lang.code as any);
                    setIsOpen(false);
                  }}
                  className="w-full flex items-center justify-between px-4 py-3 text-sm transition-colors duration-150 hover:bg-white/10"
                  style={{ color: language === lang.code ? "oklch(0.72 0.2 292)" : "oklch(0.85 0.01 270)" }}
                >
                  <div className="flex items-center gap-3.5">
                    <img 
                      src={`https://flagcdn.com/w40/${lang.flag}.png`} 
                      alt={lang.label}
                      className="w-6 h-auto rounded-sm"
                    />
                    <span className="font-medium">{lang.label}</span>
                  </div>
                  {language === lang.code && <Check size={16} strokeWidth={2.5} />}
                </button>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
