"use client";
import { useCallback, useEffect, useState } from "react";
import {
  Layers, Plus, Pencil, Copy, Trash2, Star, Mail, MessageSquare, Smartphone,
  Search, ChevronLeft, ChevronRight, X,
} from "lucide-react";
import { apiFetch } from "@/lib/api";
import { T } from "@/lib/tokens";

/* ═══════════════════════════════════════════════════════════════════════════
   Types
   ═══════════════════════════════════════════════════════════════════════ */

interface Template {
  id: number; name: string; description: string | null; type: string;
  header_html: string | null; footer_html: string | null; body_template: string | null;
  primary_color: string | null; logo_url: string | null;
  is_default: boolean; is_active: boolean;
  created_at: string | null; updated_at: string | null;
}

const CHANNEL_CONFIG: Record<string, { label: string; icon: any; color: string; bg: string }> = {
  email:    { label: "E-Mail",    icon: Mail,           color: T.email,    bg: "rgba(234,67,53,0.12)" },
  whatsapp: { label: "WhatsApp",  icon: MessageSquare,  color: T.whatsapp, bg: "rgba(37,211,102,0.12)" },
  sms:      { label: "SMS",       icon: Smartphone,     color: T.warning,  bg: T.warningDim },
  telegram: { label: "Telegram",  icon: MessageSquare,  color: T.telegram, bg: "rgba(0,136,204,0.12)" },
};

/* ═══════════════════════════════════════════════════════════════════════════
   Shared Styles
   ═══════════════════════════════════════════════════════════════════════ */

const S = {
  page: { padding: "32px 40px 40px", minHeight: "100vh", background: T.bg } as React.CSSProperties,
  headerRow: { display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 28 } as React.CSSProperties,
  headerIcon: { width: 42, height: 42, borderRadius: 12, background: T.accentDim, display: "flex", alignItems: "center", justifyContent: "center" } as React.CSSProperties,
  title: { fontSize: 22, fontWeight: 800, color: T.text, letterSpacing: "-0.02em" } as React.CSSProperties,
  subtitle: { fontSize: 13, color: T.textMuted, marginTop: 2 } as React.CSSProperties,
  primaryBtn: { display: "inline-flex", alignItems: "center", gap: 8, padding: "10px 20px", borderRadius: 10, border: "none", background: T.accent, color: "#fff", fontSize: 13, fontWeight: 700, cursor: "pointer", transition: "background .15s" } as React.CSSProperties,
  secondaryBtn: { display: "inline-flex", alignItems: "center", gap: 6, padding: "8px 14px", borderRadius: 8, border: `1px solid ${T.border}`, background: T.surface, color: T.text, fontSize: 12, fontWeight: 600, cursor: "pointer", transition: "all .15s" } as React.CSSProperties,
  filterRow: { display: "flex", alignItems: "center", gap: 14, marginBottom: 20 } as React.CSSProperties,
  searchWrap: { position: "relative", flex: 1, maxWidth: 340 } as React.CSSProperties,
  searchIcon: { position: "absolute", left: 12, top: "50%", transform: "translateY(-50%)", color: T.textDim } as React.CSSProperties,
  searchInput: { width: "100%", paddingLeft: 38, paddingRight: 14, paddingTop: 9, paddingBottom: 9, borderRadius: 10, border: `1px solid ${T.border}`, background: T.surfaceAlt, color: T.text, fontSize: 13, outline: "none" } as React.CSSProperties,
  card: { background: T.surface, borderRadius: 16, border: `1px solid ${T.border}`, overflow: "hidden" } as React.CSSProperties,
  th: { textAlign: "left" as const, padding: "12px 16px", fontSize: 11, fontWeight: 700, color: T.textMuted, textTransform: "uppercase" as const, letterSpacing: "0.04em" } as React.CSSProperties,
  td: { padding: "12px 16px", fontSize: 13, color: T.text } as React.CSSProperties,
  trHover: { transition: "background .12s", cursor: "pointer" } as React.CSSProperties,
  iconBtn: { padding: "6px 7px", borderRadius: 8, border: "none", background: "transparent", color: T.textDim, cursor: "pointer", transition: "all .12s" } as React.CSSProperties,
  badge: (color: string, bg: string): React.CSSProperties => ({ display: "inline-flex", alignItems: "center", gap: 5, padding: "4px 10px", borderRadius: 20, fontSize: 11, fontWeight: 600, color, background: bg }),
  paginationRow: { display: "flex", alignItems: "center", justifyContent: "space-between", padding: "12px 16px", borderTop: `1px solid ${T.border}` } as React.CSSProperties,
  label: { display: "block", fontSize: 11, fontWeight: 700, color: T.textMuted, marginBottom: 5, textTransform: "uppercase" as const, letterSpacing: "0.04em" } as React.CSSProperties,
  input: { width: "100%", padding: "9px 12px", borderRadius: 8, border: `1px solid ${T.border}`, background: T.surfaceAlt, color: T.text, fontSize: 13, outline: "none", boxSizing: "border-box" as const } as React.CSSProperties,
  select: { width: "100%", padding: "9px 12px", borderRadius: 8, border: `1px solid ${T.border}`, background: T.surfaceAlt, color: T.text, fontSize: 13, outline: "none", boxSizing: "border-box" as const } as React.CSSProperties,
  textarea: { width: "100%", padding: "9px 12px", borderRadius: 8, border: `1px solid ${T.border}`, background: T.surfaceAlt, color: T.text, fontSize: 13, fontFamily: "monospace", outline: "none", boxSizing: "border-box" as const, resize: "vertical" as const } as React.CSSProperties,
};

/* ═══════════════════════════════════════════════════════════════════════════
   Main Page
   ═══════════════════════════════════════════════════════════════════════ */

export default function TemplatesPage() {
  const [templates, setTemplates] = useState<Template[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [filterType, setFilterType] = useState<string>("");
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [showCreate, setShowCreate] = useState(false);
  const [editTemplate, setEditTemplate] = useState<Template | null>(null);
  const limit = 20;

  const fetchTemplates = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ page: String(page), limit: String(limit) });
      if (filterType) params.set("type", filterType);
      const res = await apiFetch(`/v2/admin/templates?${params}`);
      if (res.ok) { const data = await res.json(); setTemplates(data.items || []); setTotal(data.total || 0); }
    } catch (e) { console.error("Failed to fetch templates", e); }
    finally { setLoading(false); }
  }, [page, filterType]);

  useEffect(() => { fetchTemplates(); }, [fetchTemplates]);

  const handleDuplicate = async (id: number) => { try { const res = await apiFetch(`/v2/admin/templates/${id}/duplicate`, { method: "POST" }); if (res.ok) fetchTemplates(); } catch (e) { console.error(e); } };
  const handleDelete = async (id: number) => { if (!confirm("Vorlage wirklich löschen?")) return; try { const res = await apiFetch(`/v2/admin/templates/${id}`, { method: "DELETE" }); if (res.ok) fetchTemplates(); } catch (e) { console.error(e); } };
  const handleSetDefault = async (template: Template) => { try { const res = await apiFetch(`/v2/admin/templates/${template.id}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ is_default: !template.is_default }) }); if (res.ok) fetchTemplates(); } catch (e) { console.error(e); } };

  const filtered = templates.filter((t) => !search || t.name.toLowerCase().includes(search.toLowerCase()));
  const totalPages = Math.ceil(total / limit);

  const filterTabs = [
    { key: "", label: "Alle" },
    { key: "email", label: "E-Mail" },
    { key: "whatsapp", label: "WhatsApp" },
    { key: "sms", label: "SMS" },
    { key: "telegram", label: "Telegram" },
  ];

  return (
    <div style={S.page}>
      {/* Header */}
      <div style={S.headerRow}>
        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
          <div style={S.headerIcon}><Layers size={20} style={{ color: T.accent }} /></div>
          <div>
            <h1 style={S.title}>Vorlagen</h1>
            <p style={S.subtitle}>CI-konforme Vorlagen für E-Mail, WhatsApp, SMS und Telegram</p>
          </div>
        </div>
        <button style={S.primaryBtn} onClick={() => { setEditTemplate(null); setShowCreate(true); }}
          onMouseEnter={(e) => (e.currentTarget.style.background = T.accentLight)}
          onMouseLeave={(e) => (e.currentTarget.style.background = T.accent)}>
          <Plus size={16} /> Neue Vorlage
        </button>
      </div>

      {/* Filters */}
      <div style={S.filterRow}>
        <div style={S.searchWrap as any}>
          <Search size={15} style={S.searchIcon as any} />
          <input style={S.searchInput} type="text" placeholder="Vorlagen durchsuchen..." value={search} onChange={(e) => setSearch(e.target.value)} />
        </div>
        <div style={{ display: "flex", gap: 6 }}>
          {filterTabs.map((tab) => (
            <button key={tab.key} onClick={() => { setFilterType(tab.key); setPage(1); }}
              style={{
                padding: "7px 14px", borderRadius: 8, border: `1px solid ${filterType === tab.key ? T.accent : T.border}`,
                background: filterType === tab.key ? T.accentDim : T.surface,
                color: filterType === tab.key ? T.accentLight : T.textMuted,
                fontSize: 12, fontWeight: 600, cursor: "pointer", transition: "all .15s",
              }}>
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Table Card */}
      <div style={S.card}>
        {loading ? (
          <div style={{ display: "flex", alignItems: "center", justifyContent: "center", padding: "80px 0" }}>
            <div style={{ width: 32, height: 32, border: `3px solid ${T.border}`, borderTopColor: T.accent, borderRadius: "50%", animation: "spin 0.8s linear infinite" }} />
          </div>
        ) : filtered.length === 0 ? (
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: "80px 0", color: T.textDim }}>
            <Layers size={48} style={{ marginBottom: 12, opacity: 0.4 }} />
            <p style={{ fontSize: 16, fontWeight: 600 }}>Keine Vorlagen gefunden</p>
            <p style={{ fontSize: 13, marginTop: 4 }}>Erstellen Sie Ihre erste Vorlage, um loszulegen.</p>
          </div>
        ) : (
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ borderBottom: `1px solid ${T.border}` }}>
                <th style={S.th}>Name</th>
                <th style={S.th}>Typ</th>
                <th style={S.th}>Standard</th>
                <th style={S.th}>Farbe</th>
                <th style={S.th}>Erstellt</th>
                <th style={{ ...S.th, textAlign: "right" }}>Aktionen</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((t) => {
                const cfg = CHANNEL_CONFIG[t.type] || CHANNEL_CONFIG.email;
                const Icon = cfg.icon;
                return (
                  <tr key={t.id} style={{ ...S.trHover, borderBottom: `1px solid ${T.border}` }}
                    onMouseEnter={(e) => (e.currentTarget.style.background = T.surfaceAlt)}
                    onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}>
                    <td style={S.td}>
                      <button onClick={() => { setEditTemplate(t); setShowCreate(true); }}
                        style={{ background: "none", border: "none", color: T.text, fontWeight: 600, cursor: "pointer", textAlign: "left", padding: 0, fontSize: 13 }}>
                        {t.name}
                      </button>
                      {t.description && <p style={{ fontSize: 11, color: T.textDim, marginTop: 2, maxWidth: 260, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{t.description}</p>}
                    </td>
                    <td style={S.td}>
                      <span style={S.badge(cfg.color, cfg.bg)}><Icon size={12} /> {cfg.label}</span>
                    </td>
                    <td style={S.td}>
                      <button onClick={() => handleSetDefault(t)} style={{ background: "none", border: "none", cursor: "pointer", padding: 0 }}>
                        <Star size={16} style={{ color: t.is_default ? T.warning : T.textDim, fill: t.is_default ? T.warning : "none", transition: "all .15s" }} />
                      </button>
                    </td>
                    <td style={S.td}>
                      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                        <div style={{ width: 20, height: 20, borderRadius: "50%", border: `1px solid ${T.border}`, background: t.primary_color || T.accent }} />
                        <span style={{ fontSize: 11, color: T.textDim }}>{t.primary_color || T.accent}</span>
                      </div>
                    </td>
                    <td style={{ ...S.td, color: T.textMuted }}>{t.created_at ? new Date(t.created_at).toLocaleDateString("de-DE") : "–"}</td>
                    <td style={{ ...S.td, textAlign: "right" }}>
                      <div style={{ display: "flex", alignItems: "center", justifyContent: "flex-end", gap: 4 }}>
                        <button style={S.iconBtn} title="Bearbeiten" onClick={() => { setEditTemplate(t); setShowCreate(true); }}
                          onMouseEnter={(e) => { e.currentTarget.style.background = T.surfaceAlt; e.currentTarget.style.color = T.text; }}
                          onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; e.currentTarget.style.color = T.textDim; }}>
                          <Pencil size={15} />
                        </button>
                        <button style={S.iconBtn} title="Duplizieren" onClick={() => handleDuplicate(t.id)}
                          onMouseEnter={(e) => { e.currentTarget.style.background = T.surfaceAlt; e.currentTarget.style.color = T.text; }}
                          onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; e.currentTarget.style.color = T.textDim; }}>
                          <Copy size={15} />
                        </button>
                        <button style={S.iconBtn} title="Löschen" onClick={() => handleDelete(t.id)}
                          onMouseEnter={(e) => { e.currentTarget.style.background = T.dangerDim; e.currentTarget.style.color = T.danger; }}
                          onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; e.currentTarget.style.color = T.textDim; }}>
                          <Trash2 size={15} />
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}

        {/* Pagination */}
        {totalPages > 1 && (
          <div style={S.paginationRow}>
            <span style={{ fontSize: 12, color: T.textMuted }}>{total} Vorlagen gesamt</span>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <button onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page === 1}
                style={{ ...S.iconBtn, opacity: page === 1 ? 0.3 : 1 }}><ChevronLeft size={16} /></button>
              <span style={{ fontSize: 12, color: T.textMuted }}>Seite {page} von {totalPages}</span>
              <button onClick={() => setPage((p) => Math.min(totalPages, p + 1))} disabled={page === totalPages}
                style={{ ...S.iconBtn, opacity: page === totalPages ? 0.3 : 1 }}><ChevronRight size={16} /></button>
            </div>
          </div>
        )}
      </div>

      {/* Create/Edit Modal */}
      {showCreate && (
        <TemplateEditorModal
          template={editTemplate}
          onClose={() => { setShowCreate(false); setEditTemplate(null); }}
          onSaved={() => { setShowCreate(false); setEditTemplate(null); fetchTemplates(); }}
        />
      )}

      {/* Spin animation */}
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════
   Template Editor Modal (Dark Theme)
   ═══════════════════════════════════════════════════════════════════════ */

function TemplateEditorModal({ template, onClose, onSaved }: { template: Template | null; onClose: () => void; onSaved: () => void; }) {
  const isEdit = !!template;
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({
    name: template?.name || "", description: template?.description || "", type: template?.type || "email",
    header_html: template?.header_html || "", footer_html: template?.footer_html || "",
    body_template: template?.body_template || "", primary_color: template?.primary_color || T.accent,
    logo_url: template?.logo_url || "", is_default: template?.is_default || false,
  });

  const handleSave = async () => {
    if (!form.name.trim()) return;
    setSaving(true);
    try {
      const url = isEdit ? `/v2/admin/templates/${template!.id}` : `/v2/admin/templates`;
      const res = await apiFetch(url, { method: isEdit ? "PUT" : "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(form) });
      if (res.ok) onSaved();
    } catch (e) { console.error(e); }
    finally { setSaving(false); }
  };

  const previewHtml = `
    <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;max-width:600px;margin:0 auto;background:#fff;">
      <div style="background:${form.primary_color};color:#fff;padding:24px;">
        ${form.logo_url ? `<img src="${form.logo_url}" alt="Logo" style="max-width:150px;height:auto;margin-bottom:8px;" />` : ""}
        ${form.header_html || "<h2 style='margin:0'>Header-Vorschau</h2>"}
      </div>
      <div style="padding:24px;color:#333;line-height:1.6;">${form.body_template || "<p>Hier erscheint der Kampagnen-Inhalt...</p>"}</div>
      <div style="padding:16px;background:#f4f4f7;color:#666;font-size:12px;text-align:center;">${form.footer_html || "<p>Footer-Vorschau</p>"}</div>
    </div>`;

  return (
    <div style={{ position: "fixed", inset: 0, zIndex: 50, display: "flex", alignItems: "center", justifyContent: "center", background: "rgba(0,0,0,0.65)", backdropFilter: "blur(6px)" }}>
      <div style={{ background: T.surface, border: `1px solid ${T.borderLight}`, borderRadius: 18, boxShadow: "0 24px 60px rgba(0,0,0,.5)", width: "100%", maxWidth: 1100, maxHeight: "90vh", overflow: "hidden", display: "flex", flexDirection: "column" }}>
        {/* Modal Header */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "16px 24px", borderBottom: `1px solid ${T.border}` }}>
          <span style={{ fontSize: 16, fontWeight: 700, color: T.text }}>{isEdit ? "Vorlage bearbeiten" : "Neue Vorlage erstellen"}</span>
          <button onClick={onClose} style={{ background: T.surfaceAlt, border: `1px solid ${T.border}`, borderRadius: 8, padding: "5px 7px", cursor: "pointer", color: T.textDim }}>
            <X size={16} />
          </button>
        </div>

        {/* Modal Body */}
        <div style={{ display: "flex", flex: 1, overflow: "hidden" }}>
          {/* Left: Form */}
          <div style={{ width: "50%", padding: 24, overflowY: "auto", borderRight: `1px solid ${T.border}`, display: "flex", flexDirection: "column", gap: 16 }}>
            <div><label style={S.label}>Name *</label><input style={S.input} type="text" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="z.B. Standard Newsletter" maxLength={100} /></div>
            <div><label style={S.label}>Beschreibung</label><textarea style={{ ...S.textarea, height: 56 }} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} placeholder="Optionale Beschreibung..." maxLength={500} /></div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
              <div><label style={S.label}>Kanal *</label><select style={S.select} value={form.type} onChange={(e) => setForm({ ...form, type: e.target.value })}><option value="email">E-Mail</option><option value="whatsapp">WhatsApp</option><option value="sms">SMS</option><option value="telegram">Telegram</option></select></div>
              <div>
                <label style={S.label}>Primärfarbe</label>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <input type="color" value={form.primary_color} onChange={(e) => setForm({ ...form, primary_color: e.target.value })} style={{ width: 38, height: 38, borderRadius: 8, border: `1px solid ${T.border}`, cursor: "pointer", background: "transparent" }} />
                  <input style={{ ...S.input, flex: 1 }} type="text" value={form.primary_color} onChange={(e) => setForm({ ...form, primary_color: e.target.value })} />
                </div>
              </div>
            </div>

            <div><label style={S.label}>Logo-URL</label><input style={S.input} type="url" value={form.logo_url} onChange={(e) => setForm({ ...form, logo_url: e.target.value })} placeholder="https://example.com/logo.png" /></div>

            {form.type === "email" && (
              <>
                <div><label style={S.label}>Header (HTML)</label><textarea style={{ ...S.textarea, height: 90 }} value={form.header_html} onChange={(e) => setForm({ ...form, header_html: e.target.value })} placeholder="<h1>Ihr Unternehmen</h1>" /></div>
                <div><label style={S.label}>Body-Vorlage (HTML)</label><textarea style={{ ...S.textarea, height: 90 }} value={form.body_template} onChange={(e) => setForm({ ...form, body_template: e.target.value })} placeholder="<p>Hallo {{ contact.first_name }},</p>" /></div>
                <div><label style={S.label}>Footer (HTML)</label><textarea style={{ ...S.textarea, height: 70 }} value={form.footer_html} onChange={(e) => setForm({ ...form, footer_html: e.target.value })} placeholder="<p>&copy; 2026 Ihr Unternehmen | <a href='#'>Abmelden</a></p>" /></div>
              </>
            )}

            {form.type !== "email" && (
              <div><label style={S.label}>Nachrichtenvorlage</label><textarea style={{ ...S.textarea, height: 140 }} value={form.body_template} onChange={(e) => setForm({ ...form, body_template: e.target.value })} placeholder="Hallo {{ contact.first_name }}, ..." /></div>
            )}

            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <input type="checkbox" id="is_default" checked={form.is_default} onChange={(e) => setForm({ ...form, is_default: e.target.checked })} style={{ width: 16, height: 16, accentColor: T.accent }} />
              <label htmlFor="is_default" style={{ fontSize: 13, color: T.textMuted }}>Als Standardvorlage für diesen Kanal setzen</label>
            </div>
          </div>

          {/* Right: Preview */}
          <div style={{ width: "50%", padding: 24, overflowY: "auto", background: T.bg }}>
            <span style={{ fontSize: 12, fontWeight: 700, color: T.textDim, textTransform: "uppercase", letterSpacing: "0.04em" }}>Live-Vorschau</span>
            <div style={{ marginTop: 12, borderRadius: 12, overflow: "hidden", boxShadow: "0 8px 24px rgba(0,0,0,.3)" }}>
              <iframe srcDoc={previewHtml} style={{ width: "100%", border: "none", minHeight: 460, background: "#fff" }} title="Template Preview" sandbox="allow-same-origin" />
            </div>
          </div>
        </div>

        {/* Modal Footer */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "flex-end", gap: 12, padding: "14px 24px", borderTop: `1px solid ${T.border}` }}>
          <button onClick={onClose} style={{ ...S.secondaryBtn, background: "transparent", border: "none", color: T.textMuted }}>Abbrechen</button>
          <button onClick={handleSave} disabled={saving || !form.name.trim()}
            style={{ ...S.primaryBtn, opacity: saving || !form.name.trim() ? 0.5 : 1 }}>
            {saving && <div style={{ width: 14, height: 14, border: `2px solid rgba(255,255,255,0.3)`, borderTopColor: "#fff", borderRadius: "50%", animation: "spin 0.8s linear infinite" }} />}
            {isEdit ? "Speichern" : "Erstellen"}
          </button>
        </div>
      </div>
    </div>
  );
}
