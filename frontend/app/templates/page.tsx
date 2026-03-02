"use client";
import { useCallback, useEffect, useState } from "react";
import {
  Layers, Plus, Pencil, Copy, Trash2, Star, Mail, MessageSquare, Smartphone,
  Search, ChevronLeft, ChevronRight,
} from "lucide-react";
import { apiFetch } from "@/lib/api";

interface Template {
  id: number;
  name: string;
  description: string | null;
  type: string;
  header_html: string | null;
  footer_html: string | null;
  body_template: string | null;
  primary_color: string | null;
  logo_url: string | null;
  is_default: boolean;
  is_active: boolean;
  created_at: string | null;
  updated_at: string | null;
}

const CHANNEL_CONFIG: Record<string, { label: string; icon: any; color: string; bg: string }> = {
  email: { label: "E-Mail", icon: Mail, color: "text-blue-400", bg: "bg-blue-500/10" },
  whatsapp: { label: "WhatsApp", icon: MessageSquare, color: "text-green-400", bg: "bg-green-500/10" },
  sms: { label: "SMS", icon: Smartphone, color: "text-yellow-400", bg: "bg-yellow-500/10" },
  telegram: { label: "Telegram", icon: MessageSquare, color: "text-cyan-400", bg: "bg-cyan-500/10" },
};

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
      if (res.ok) {
        const data = await res.json();
        setTemplates(data.items || []);
        setTotal(data.total || 0);
      }
    } catch (e) {
      console.error("Failed to fetch templates", e);
    } finally {
      setLoading(false);
    }
  }, [page, filterType]);

  useEffect(() => { fetchTemplates(); }, [fetchTemplates]);

  const handleDuplicate = async (id: number) => {
    try {
      const res = await apiFetch(`/v2/admin/templates/${id}/duplicate`, { method: "POST" });
      if (res.ok) fetchTemplates();
    } catch (e) { console.error(e); }
  };

  const handleDelete = async (id: number) => {
    if (!confirm("Vorlage wirklich löschen?")) return;
    try {
      const res = await apiFetch(`/v2/admin/templates/${id}`, { method: "DELETE" });
      if (res.ok) fetchTemplates();
    } catch (e) { console.error(e); }
  };

  const handleSetDefault = async (template: Template) => {
    try {
      const res = await apiFetch(`/v2/admin/templates/${template.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ is_default: !template.is_default }),
      });
      if (res.ok) fetchTemplates();
    } catch (e) { console.error(e); }
  };

  const filtered = templates.filter((t) =>
    !search || t.name.toLowerCase().includes(search.toLowerCase())
  );

  const totalPages = Math.ceil(total / limit);

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-purple-500/10 rounded-lg">
            <Layers className="w-6 h-6 text-purple-400" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-white">Vorlagen</h1>
            <p className="text-sm text-zinc-400">CI-konforme Vorlagen für E-Mail, WhatsApp, SMS und Telegram</p>
          </div>
        </div>
        <button
          onClick={() => { setEditTemplate(null); setShowCreate(true); }}
          className="flex items-center gap-2 px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-lg transition-colors"
        >
          <Plus className="w-4 h-4" />
          Neue Vorlage
        </button>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-4">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-400" />
          <input
            type="text"
            placeholder="Vorlagen durchsuchen..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-10 pr-4 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-white placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-purple-500"
          />
        </div>
        <div className="flex gap-2">
          {["", "email", "whatsapp", "sms", "telegram"].map((type) => (
            <button
              key={type}
              onClick={() => { setFilterType(type); setPage(1); }}
              className={`px-3 py-1.5 rounded-lg text-sm transition-colors ${
                filterType === type
                  ? "bg-purple-600 text-white"
                  : "bg-zinc-800 text-zinc-400 hover:bg-zinc-700"
              }`}
            >
              {type === "" ? "Alle" : CHANNEL_CONFIG[type]?.label || type}
            </button>
          ))}
        </div>
      </div>

      {/* Table */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-xl overflow-hidden">
        {loading ? (
          <div className="flex items-center justify-center py-20">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-purple-500" />
          </div>
        ) : filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 text-zinc-500">
            <Layers className="w-12 h-12 mb-3 opacity-50" />
            <p className="text-lg font-medium">Keine Vorlagen gefunden</p>
            <p className="text-sm">Erstellen Sie Ihre erste Vorlage, um loszulegen.</p>
          </div>
        ) : (
          <table className="w-full">
            <thead>
              <tr className="border-b border-zinc-800">
                <th className="text-left px-4 py-3 text-xs font-medium text-zinc-400 uppercase tracking-wider">Name</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-zinc-400 uppercase tracking-wider">Typ</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-zinc-400 uppercase tracking-wider">Standard</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-zinc-400 uppercase tracking-wider">Farbe</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-zinc-400 uppercase tracking-wider">Erstellt</th>
                <th className="text-right px-4 py-3 text-xs font-medium text-zinc-400 uppercase tracking-wider">Aktionen</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-800">
              {filtered.map((t) => {
                const cfg = CHANNEL_CONFIG[t.type] || CHANNEL_CONFIG.email;
                const Icon = cfg.icon;
                return (
                  <tr key={t.id} className="hover:bg-zinc-800/50 transition-colors">
                    <td className="px-4 py-3">
                      <button
                        onClick={() => { setEditTemplate(t); setShowCreate(true); }}
                        className="text-white font-medium hover:text-purple-400 transition-colors text-left"
                      >
                        {t.name}
                      </button>
                      {t.description && (
                        <p className="text-xs text-zinc-500 mt-0.5 truncate max-w-xs">{t.description}</p>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${cfg.bg} ${cfg.color}`}>
                        <Icon className="w-3 h-3" />
                        {cfg.label}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <button onClick={() => handleSetDefault(t)} title={t.is_default ? "Standard entfernen" : "Als Standard setzen"}>
                        <Star className={`w-4 h-4 ${t.is_default ? "text-yellow-400 fill-yellow-400" : "text-zinc-600 hover:text-yellow-400"} transition-colors`} />
                      </button>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <div
                          className="w-5 h-5 rounded-full border border-zinc-600"
                          style={{ backgroundColor: t.primary_color || "#6C5CE7" }}
                        />
                        <span className="text-xs text-zinc-500">{t.primary_color || "#6C5CE7"}</span>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-sm text-zinc-400">
                      {t.created_at ? new Date(t.created_at).toLocaleDateString("de-DE") : "–"}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center justify-end gap-1">
                        <button
                          onClick={() => { setEditTemplate(t); setShowCreate(true); }}
                          className="p-1.5 text-zinc-400 hover:text-white hover:bg-zinc-700 rounded-lg transition-colors"
                          title="Bearbeiten"
                        >
                          <Pencil className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => handleDuplicate(t.id)}
                          className="p-1.5 text-zinc-400 hover:text-white hover:bg-zinc-700 rounded-lg transition-colors"
                          title="Duplizieren"
                        >
                          <Copy className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => handleDelete(t.id)}
                          className="p-1.5 text-zinc-400 hover:text-red-400 hover:bg-zinc-700 rounded-lg transition-colors"
                          title="Löschen"
                        >
                          <Trash2 className="w-4 h-4" />
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
          <div className="flex items-center justify-between px-4 py-3 border-t border-zinc-800">
            <span className="text-sm text-zinc-400">{total} Vorlagen gesamt</span>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
                className="p-1.5 text-zinc-400 hover:text-white disabled:opacity-30 disabled:cursor-not-allowed"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>
              <span className="text-sm text-zinc-400">
                Seite {page} von {totalPages}
              </span>
              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page === totalPages}
                className="p-1.5 text-zinc-400 hover:text-white disabled:opacity-30 disabled:cursor-not-allowed"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
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
    </div>
  );
}


/* ─── Template Editor Modal ─────────────────────────────────────────────── */

function TemplateEditorModal({
  template,
  onClose,
  onSaved,
}: {
  template: Template | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  const isEdit = !!template;
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({
    name: template?.name || "",
    description: template?.description || "",
    type: template?.type || "email",
    header_html: template?.header_html || "",
    footer_html: template?.footer_html || "",
    body_template: template?.body_template || "",
    primary_color: template?.primary_color || "#6C5CE7",
    logo_url: template?.logo_url || "",
    is_default: template?.is_default || false,
  });

  const handleSave = async () => {
    if (!form.name.trim()) return;
    setSaving(true);
    try {
      const url = isEdit
        ? `/v2/admin/templates/${template!.id}`
        : `/v2/admin/templates`;
      const res = await apiFetch(url, {
        method: isEdit ? "PUT" : "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      if (res.ok) onSaved();
    } catch (e) {
      console.error(e);
    } finally {
      setSaving(false);
    }
  };

  const previewHtml = `
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 600px; margin: 0 auto; background: #fff;">
      <div style="background: ${form.primary_color}; color: #fff; padding: 24px;">
        ${form.logo_url ? `<img src="${form.logo_url}" alt="Logo" style="max-width:150px;height:auto;margin-bottom:8px;" />` : ""}
        ${form.header_html || "<h2 style='margin:0'>Header-Vorschau</h2>"}
      </div>
      <div style="padding: 24px; color: #333; line-height: 1.6;">
        ${form.body_template || "<p>Hier erscheint der Kampagnen-Inhalt...</p>"}
      </div>
      <div style="padding: 16px; background: #f4f4f7; color: #666; font-size: 12px; text-align: center;">
        ${form.footer_html || "<p>Footer-Vorschau</p>"}
      </div>
    </div>
  `;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="bg-zinc-900 border border-zinc-700 rounded-2xl shadow-2xl w-full max-w-5xl max-h-[90vh] overflow-hidden flex flex-col">
        {/* Modal Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-zinc-800">
          <h2 className="text-lg font-semibold text-white">
            {isEdit ? "Vorlage bearbeiten" : "Neue Vorlage erstellen"}
          </h2>
          <button onClick={onClose} className="text-zinc-400 hover:text-white text-xl">&times;</button>
        </div>

        {/* Modal Body */}
        <div className="flex flex-1 overflow-hidden">
          {/* Left: Form */}
          <div className="w-1/2 p-6 overflow-y-auto space-y-4 border-r border-zinc-800">
            <div>
              <label className="block text-sm font-medium text-zinc-300 mb-1">Name *</label>
              <input
                type="text"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-purple-500"
                placeholder="z.B. Standard Newsletter"
                maxLength={100}
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-zinc-300 mb-1">Beschreibung</label>
              <textarea
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
                className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-purple-500"
                rows={2}
                placeholder="Optionale Beschreibung..."
                maxLength={500}
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-zinc-300 mb-1">Kanal *</label>
                <select
                  value={form.type}
                  onChange={(e) => setForm({ ...form, type: e.target.value })}
                  className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-purple-500"
                >
                  <option value="email">E-Mail</option>
                  <option value="whatsapp">WhatsApp</option>
                  <option value="sms">SMS</option>
                  <option value="telegram">Telegram</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-zinc-300 mb-1">Primärfarbe</label>
                <div className="flex items-center gap-2">
                  <input
                    type="color"
                    value={form.primary_color}
                    onChange={(e) => setForm({ ...form, primary_color: e.target.value })}
                    className="w-10 h-10 rounded-lg border border-zinc-700 cursor-pointer bg-transparent"
                  />
                  <input
                    type="text"
                    value={form.primary_color}
                    onChange={(e) => setForm({ ...form, primary_color: e.target.value })}
                    className="flex-1 px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-purple-500"
                  />
                </div>
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-zinc-300 mb-1">Logo-URL</label>
              <input
                type="url"
                value={form.logo_url}
                onChange={(e) => setForm({ ...form, logo_url: e.target.value })}
                className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-purple-500"
                placeholder="https://example.com/logo.png"
              />
            </div>

            {form.type === "email" && (
              <>
                <div>
                  <label className="block text-sm font-medium text-zinc-300 mb-1">Header (HTML)</label>
                  <textarea
                    value={form.header_html}
                    onChange={(e) => setForm({ ...form, header_html: e.target.value })}
                    className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-white font-mono text-sm focus:outline-none focus:ring-2 focus:ring-purple-500"
                    rows={4}
                    placeholder="<h1>Ihr Unternehmen</h1>"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-zinc-300 mb-1">Body-Vorlage (HTML)</label>
                  <textarea
                    value={form.body_template}
                    onChange={(e) => setForm({ ...form, body_template: e.target.value })}
                    className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-white font-mono text-sm focus:outline-none focus:ring-2 focus:ring-purple-500"
                    rows={4}
                    placeholder="<p>Hallo {{ contact.first_name }},</p>"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-zinc-300 mb-1">Footer (HTML)</label>
                  <textarea
                    value={form.footer_html}
                    onChange={(e) => setForm({ ...form, footer_html: e.target.value })}
                    className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-white font-mono text-sm focus:outline-none focus:ring-2 focus:ring-purple-500"
                    rows={3}
                    placeholder="<p>&copy; 2026 Ihr Unternehmen | <a href='#'>Abmelden</a></p>"
                  />
                </div>
              </>
            )}

            {form.type !== "email" && (
              <div>
                <label className="block text-sm font-medium text-zinc-300 mb-1">Nachrichtenvorlage</label>
                <textarea
                  value={form.body_template}
                  onChange={(e) => setForm({ ...form, body_template: e.target.value })}
                  className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-purple-500"
                  rows={6}
                  placeholder="Hallo {{ contact.first_name }}, ..."
                />
              </div>
            )}

            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                id="is_default"
                checked={form.is_default}
                onChange={(e) => setForm({ ...form, is_default: e.target.checked })}
                className="w-4 h-4 rounded border-zinc-600 bg-zinc-800 text-purple-600 focus:ring-purple-500"
              />
              <label htmlFor="is_default" className="text-sm text-zinc-300">
                Als Standardvorlage für diesen Kanal setzen
              </label>
            </div>
          </div>

          {/* Right: Preview */}
          <div className="w-1/2 p-6 overflow-y-auto bg-zinc-950">
            <h3 className="text-sm font-medium text-zinc-400 mb-3">Live-Vorschau</h3>
            <div className="bg-white rounded-lg overflow-hidden shadow-lg">
              <iframe
                srcDoc={previewHtml}
                className="w-full border-0"
                style={{ minHeight: 500 }}
                title="Template Preview"
                sandbox="allow-same-origin"
              />
            </div>
          </div>
        </div>

        {/* Modal Footer */}
        <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-zinc-800">
          <button
            onClick={onClose}
            className="px-4 py-2 text-zinc-400 hover:text-white transition-colors"
          >
            Abbrechen
          </button>
          <button
            onClick={handleSave}
            disabled={saving || !form.name.trim()}
            className="px-6 py-2 bg-purple-600 hover:bg-purple-700 disabled:opacity-50 text-white rounded-lg transition-colors flex items-center gap-2"
          >
            {saving ? (
              <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white" />
            ) : null}
            {isEdit ? "Speichern" : "Erstellen"}
          </button>
        </div>
      </div>
    </div>
  );
}
