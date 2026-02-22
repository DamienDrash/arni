"use client";

import { CSSProperties, HTMLAttributes, ReactNode } from "react";
import { T } from "@/lib/tokens";

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode;
  style?: CSSProperties;
  hover?: boolean;
}

export function Card({ children, style, hover = true, ...props }: CardProps) {
  return (
    <div
      style={{
        background: T.surface,
        borderRadius: 16,
        border: `1px solid ${T.border}`,
        transition: "all 0.2s ease",
        cursor: hover ? "default" : undefined,
        ...style,
      }}
      {...props}
    >
      {children}
    </div>
  );
}
