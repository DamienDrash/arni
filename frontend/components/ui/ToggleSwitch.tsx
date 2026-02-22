"use client";

import { T } from "@/lib/tokens";

type ToggleSwitchProps = {
  value: boolean;
  onChange: (v: boolean) => void;
  label: string;
  disabled?: boolean;
};

export function ToggleSwitch({ value, onChange, label, disabled = false }: ToggleSwitchProps) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={value}
      aria-label={label}
      disabled={disabled}
      onClick={() => onChange(!value)}
      style={{
        position: "relative",
        width: 44,
        height: 24,
        borderRadius: 12,
        background: value ? T.accent : T.border,
        border: "none",
        cursor: disabled ? "not-allowed" : "pointer",
        transition: "background 0.2s",
        flexShrink: 0,
        opacity: disabled ? 0.6 : 1,
      }}
    >
      <span
        style={{
          position: "absolute",
          top: 3,
          left: value ? 23 : 3,
          width: 18,
          height: 18,
          borderRadius: "50%",
          background: "#fff",
          transition: "left 0.2s",
          boxShadow: "0 1px 3px rgba(0,0,0,0.3)",
        }}
      />
    </button>
  );
}
