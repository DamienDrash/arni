"use client";

import { ReactNode } from "react";
import { T } from "@/lib/tokens";

type BadgeVariant = "default" | "success" | "warning" | "danger" | "info" | "accent";
type BadgeSize = "sm" | "xs";

interface BadgeProps {
  children: ReactNode;
  variant?: BadgeVariant;
  size?: BadgeSize;
}

const styles: Record<BadgeVariant, { background: string; color: string; border: string }> = {
  default: { background: T.surfaceAlt, color: T.textMuted, border: T.border },
  success: { background: T.successDim, color: T.success, border: "transparent" },
  warning: { background: T.warningDim, color: T.warning, border: "transparent" },
  danger:  { background: T.dangerDim,  color: T.danger,  border: "transparent" },
  info:    { background: T.infoDim,    color: T.info,    border: "transparent" },
  accent:  { background: T.accentDim,  color: T.accentLight, border: "transparent" },
};

export function Badge({ children, variant = "default", size = "sm" }: BadgeProps) {
  const s = styles[variant];
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 4,
        padding: size === "xs" ? "2px 6px" : "3px 10px",
        borderRadius: 6,
        fontSize: size === "xs" ? 10 : 11,
        fontWeight: 600,
        letterSpacing: "0.02em",
        background: s.background,
        color: s.color,
        border: `1px solid ${s.border}`,
      }}
    >
      {children}
    </span>
  );
}
