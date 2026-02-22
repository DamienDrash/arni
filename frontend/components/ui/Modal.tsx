"use client";

import { useEffect, useRef } from "react";
import { T } from "@/lib/tokens";

type ModalProps = {
  open: boolean;
  title: string;
  subtitle?: string;
  onClose: () => void;
  children: React.ReactNode;
  footer?: React.ReactNode;
  width?: string;
};

export function Modal({ open, title, subtitle, onClose, children, footer, width = "min(860px, 100%)" }: ModalProps) {
  const modalRef = useRef<HTMLDivElement | null>(null);
  const onCloseRef = useRef(onClose);

  useEffect(() => {
    onCloseRef.current = onClose;
  }, [onClose]);

  useEffect(() => {
    if (!open) return;
    const focusables = () =>
      Array.from(
        (modalRef.current?.querySelectorAll(
          'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
        ) || []) as NodeListOf<HTMLElement>,
      ).filter((el) => !el.hasAttribute("disabled"));

    focusables()[0]?.focus();

    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onCloseRef.current();
        return;
      }
      if (e.key !== "Tab") return;
      const items = focusables();
      if (items.length === 0) return;
      const first = items[0];
      const last = items[items.length - 1];
      const active = document.activeElement as HTMLElement | null;
      if (!e.shiftKey && active === last) {
        e.preventDefault();
        first.focus();
      } else if (e.shiftKey && active === first) {
        e.preventDefault();
        last.focus();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open]);

  if (!open) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={title}
      onClick={onClose}
      style={{
        position: "fixed",
        inset: 0,
        background: "radial-gradient(circle at top, rgba(108,92,231,0.20), rgba(0,0,0,0.72))",
        backdropFilter: "blur(8px)",
        zIndex: 80,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 20,
      }}
    >
      <div
        ref={modalRef}
        onClick={(e) => e.stopPropagation()}
        style={{
          width,
          borderRadius: 16,
          border: `1px solid ${T.borderLight}`,
          background: T.surface,
          boxShadow: "0 26px 60px rgba(0,0,0,0.5)",
          overflow: "hidden",
        }}
      >
        <div style={{ padding: "14px 16px", borderBottom: `1px solid ${T.border}`, display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div>
            <div style={{ fontSize: 15, fontWeight: 700, color: T.text }}>{title}</div>
            {subtitle && <div style={{ fontSize: 11, color: T.textDim, marginTop: 2 }}>{subtitle}</div>}
          </div>
          <button
            type="button"
            onClick={onClose}
            style={{ border: `1px solid ${T.border}`, borderRadius: 8, background: T.surfaceAlt, color: T.textDim, cursor: "pointer", padding: "6px 10px", fontSize: 12 }}
          >
            Schließen
          </button>
        </div>
        <div style={{ padding: 16 }}>{children}</div>
        {footer && (
          <div style={{ padding: "12px 16px", borderTop: `1px solid ${T.border}`, display: "flex", justifyContent: "flex-end", gap: 8, background: T.surfaceAlt }}>
            {footer}
          </div>
        )}
      </div>
    </div>
  );
}
