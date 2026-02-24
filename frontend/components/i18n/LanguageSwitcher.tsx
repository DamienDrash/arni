"use client";

import React, { useState, useRef, useEffect } from "react";
import { Globe, ChevronDown, Check } from "lucide-react";
import { useI18n } from "@/lib/i18n/LanguageContext";
import { motion, AnimatePresence } from "framer-motion";

const languages = [
  { code: "de", label: "Deutsch", flag: "🇩🇪" },
  { code: "en", label: "English", flag: "🇺🇸" },
  { code: "bg", label: "Български", flag: "🇧🇬" }
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
        className="flex items-center gap-2 px-3 py-1.5 rounded-lg transition-all duration-200 text-sm font-medium"
        style={{ 
          background: "oklch(0.62 0.22 292 / 0.1)", 
          color: "oklch(0.72 0.2 292)",
          border: "1px solid oklch(0.62 0.22 292 / 0.2)" 
        }}
      >
        <span>{currentLang.flag}</span>
        <span className="hidden sm:inline">{currentLang.label}</span>
        <ChevronDown size={14} className={`transition-transform duration-200 ${isOpen ? "rotate-180" : ""}`} />
      </button>

      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0, y: 10, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 10, scale: 0.95 }}
            transition={{ duration: 0.15 }}
            className="absolute right-0 mt-2 w-48 rounded-xl shadow-2xl overflow-hidden z-[100] backdrop-blur-xl"
            style={{ 
              background: "oklch(0.12 0.04 270 / 0.95)", 
              border: "1px solid oklch(0.62 0.22 292 / 0.3)",
              boxShadow: "0 20px 50px -12px oklch(0 0 0 / 0.5)"
            }}
          >
            <div className="py-1">
              {languages.map((lang) => (
                <button
                  key={lang.code}
                  onClick={() => {
                    setLanguage(lang.code as any);
                    setIsOpen(false);
                  }}
                  className="w-full flex items-center justify-between px-4 py-2.5 text-sm transition-colors duration-150 hover:bg-white/5"
                  style={{ color: language === lang.code ? "oklch(0.72 0.2 292)" : "oklch(0.8 0.01 270)" }}
                >
                  <div className="flex items-center gap-3">
                    <span>{lang.flag}</span>
                    <span>{lang.label}</span>
                  </div>
                  {language === lang.code && <Check size={14} />}
                </button>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
