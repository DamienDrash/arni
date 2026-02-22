"use client";

import { T } from "@/lib/tokens";

interface TooltipEntry {
  name: string;
  value: number | string;
  color: string;
}

interface CustomTooltipProps {
  active?: boolean;
  payload?: TooltipEntry[];
  label?: string;
}

export function CustomTooltip({ active, payload, label }: CustomTooltipProps) {
  if (!active || !payload?.length) return null;
  return (
    <div
      style={{
        background: T.surface,
        border: `1px solid ${T.border}`,
        borderRadius: 10,
        padding: "10px 14px",
        boxShadow: "0 8px 32px rgba(0,0,0,0.4)",
      }}
    >
      <p style={{ fontSize: 11, fontWeight: 600, color: T.text, margin: "0 0 6px" }}>{label}</p>
      {payload.map((e, i) => (
        <p key={i} style={{ fontSize: 11, color: e.color, margin: "2px 0" }}>
          {e.name}: <strong>{e.value}</strong>
        </p>
      ))}
    </div>
  );
}
