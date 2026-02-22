"use client";

import { T } from "@/lib/tokens";

interface ProgressBarProps {
  value: number;
  max?: number;
  color?: string;
  height?: number;
}

export function ProgressBar({ value, max = 100, color = T.accent, height = 4 }: ProgressBarProps) {
  return (
    <div style={{ width: "100%", height, borderRadius: height, background: T.surfaceAlt, overflow: "hidden" }}>
      <div
        style={{
          width: `${Math.min((value / max) * 100, 100)}%`,
          height: "100%",
          borderRadius: height,
          background: color,
          transition: "width 0.6s ease",
        }}
      />
    </div>
  );
}
