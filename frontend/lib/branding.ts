export interface BrandingPrefs {
  tenant_app_title: string;
  tenant_display_name: string;
  tenant_logo_url: string;
  tenant_primary_color: string;
  tenant_support_email: string;
  tenant_timezone: string;
  tenant_locale: string;
}

/** Parse hex → "r, g, b" for CSS rgba() usage */
function hexToRgb(hex: string): string {
  const h = hex.replace("#", "");
  const r = parseInt(h.slice(0, 2), 16);
  const g = parseInt(h.slice(2, 4), 16);
  const b = parseInt(h.slice(4, 6), 16);
  return `${r}, ${g}, ${b}`;
}

/** Inject tenant branding into CSS custom properties on :root */
export function applyBrandingCSS(prefs: Partial<BrandingPrefs>): void {
  const root = document.documentElement;
  const color = prefs.tenant_primary_color?.trim();
  if (color && /^#[0-9a-fA-F]{6}$/.test(color)) {
    root.style.setProperty("--arni-accent", color);
    root.style.setProperty("--arni-accent-dim", `rgba(${hexToRgb(color)}, 0.15)`);
  }
  const title = prefs.tenant_app_title?.trim();
  if (title) document.title = title;
}
