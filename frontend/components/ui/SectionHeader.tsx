"use client";

import { ReactNode } from "react";
import { T } from "@/lib/tokens";

interface SectionHeaderProps {
  title: string;
  subtitle?: string;
  action?: ReactNode;
}

export function SectionHeader({ title, subtitle, action }: SectionHeaderProps) {
  return (
    <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 20 }}>
      <div>
        <h2 style={{ fontSize: 18, fontWeight: 700, color: T.text, margin: 0, letterSpacing: "-0.02em" }}>{title}</h2>
        {subtitle && (
          <p style={{ fontSize: 12, color: T.textMuted, margin: "4px 0 0", letterSpacing: "0.01em" }}>{subtitle}</p>
        )}
      </div>
      {action}
    </div>
  );
}
