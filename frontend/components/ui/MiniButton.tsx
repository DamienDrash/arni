"use client";

import { CSSProperties, MouseEventHandler, ReactNode } from "react";
import { T } from "@/lib/tokens";

interface MiniButtonProps {
  children: ReactNode;
  active?: boolean;
  onClick?: MouseEventHandler<HTMLButtonElement>;
  style?: CSSProperties;
}

export function MiniButton({ children, active, onClick, style: s }: MiniButtonProps) {
  return (
    <button
      onClick={onClick}
      style={{
        padding: "6px 12px",
        borderRadius: 8,
        border: `1px solid ${active ? T.accent : T.border}`,
        background: active ? T.accentDim : "transparent",
        color: active ? T.accentLight : T.textMuted,
        fontSize: 11,
        fontWeight: 600,
        cursor: "pointer",
        transition: "all 0.15s",
        display: "flex",
        alignItems: "center",
        gap: 5,
        ...s,
      }}
    >
      {children}
    </button>
  );
}
