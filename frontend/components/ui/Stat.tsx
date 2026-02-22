"use client";

import { ArrowUpRight, ArrowDownRight } from "lucide-react";
import { T } from "@/lib/tokens";

interface StatProps {
  label: string;
  value: string | number;
  unit?: string;
  trend?: string;
  trendDir?: "up" | "down";
  color?: string;
}

export function Stat({ label, value, unit, trend, trendDir, color }: StatProps) {
  return (
    <div>
      <p style={{ fontSize: 11, color: T.textMuted, margin: "0 0 6px", fontWeight: 500, textTransform: "uppercase", letterSpacing: "0.06em" }}>
        {label}
      </p>
      <div style={{ display: "flex", alignItems: "baseline", gap: 4 }}>
        <span style={{ fontSize: 28, fontWeight: 800, color: color || T.text, letterSpacing: "-0.03em", lineHeight: 1 }}>
          {value}
        </span>
        {unit && <span style={{ fontSize: 12, color: T.textMuted, fontWeight: 500 }}>{unit}</span>}
      </div>
      {trend !== undefined && (
        <div style={{ display: "flex", alignItems: "center", gap: 3, marginTop: 6 }}>
          {trendDir === "up"
            ? <ArrowUpRight size={12} color={T.success} />
            : <ArrowDownRight size={12} color={T.danger} />}
          <span style={{ fontSize: 11, fontWeight: 600, color: trendDir === "up" ? T.success : T.danger }}>{trend}</span>
          <span style={{ fontSize: 10, color: T.textDim }}>vs gestern</span>
        </div>
      )}
    </div>
  );
}
