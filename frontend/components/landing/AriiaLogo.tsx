/*
 * ARIIA Logo Component – Uses official brand PNG assets with transparent backgrounds
 *
 * Variants:
 * - "full": Full wordmark "ARIIA" with connector line and glow nodes
 * - "icon": Square icon (favicon-style)
 *
 * Theme support:
 * - "dark": White/light text version (for dark backgrounds) – default
 * - "light": Dark/navy text version (for light backgrounds)
 */

interface AriiaLogoProps {
  variant?: "full" | "icon";
  height?: number;
  className?: string;
  theme?: "dark" | "light";
}

/* Official logo assets – local paths (basePath-aware) */
const BASE = process.env.NEXT_PUBLIC_BASE_PATH || "";
const LOGO_URLS = {
  full: {
    dark: `${BASE}/logo-full-dark.png`,
    light: `${BASE}/logo-full-dark.png`,
  },
  icon: {
    dark: `${BASE}/logo-icon-square.png`,
    light: `${BASE}/logo-icon-square.png`,
  },
};

export default function AriiaLogo({
  variant = "full",
  height = 32,
  className = "",
  theme = "dark",
}: AriiaLogoProps) {
  const src = LOGO_URLS[variant][theme];
  const alt = variant === "full" ? "ARIIA Logo" : "ARIIA Icon";

  return (
    <img
      src={src}
      alt={alt}
      height={height}
      className={className}
      style={{
        height: `${height}px`,
        width: "auto",
        objectFit: "contain",
        display: "block",
      }}
      loading="eager"
      draggable={false}
    />
  );
}
