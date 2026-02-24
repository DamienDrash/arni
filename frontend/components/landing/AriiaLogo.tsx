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

/* Official logo assets with transparent backgrounds (uploaded 2026-02-24) */
const LOGO_URLS = {
  full: {
    /* White/light letters on transparent – for dark backgrounds (navbar, footer, hero, login, register)
     * File: logo_black_transparent.png (name refers to the background it was designed for) */
    dark: "https://files.manuscdn.com/user_upload_by_module/session_file/107911917/NvnArzynaJaJVLLc.png",
    /* Dark/navy letters on transparent – for light backgrounds
     * File: logo_white_transparent.png (name refers to the background it was designed for) */
    light: "https://files.manuscdn.com/user_upload_by_module/session_file/107911917/mqxeITbccMDjBUWg.png",
  },
  icon: {
    /* Icon card version for favicon / small displays */
    dark: "https://files.manuscdn.com/user_upload_by_module/session_file/107911917/NvnArzynaJaJVLLc.png",
    light: "https://files.manuscdn.com/user_upload_by_module/session_file/107911917/mqxeITbccMDjBUWg.png",
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
