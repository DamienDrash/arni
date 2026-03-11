"use client";

import { useEffect, useState, useRef } from "react";
import {
  Image as ImageIcon, Upload, Sparkles, Copy, Trash2, CheckCircle,
  AlertTriangle, RefreshCw, X, ChevronDown, Save, Wand2, Star,
} from "lucide-react";
import { apiFetch } from "@/lib/api";
import { Card } from "@/components/ui/Card";
import { T } from "@/lib/tokens";

type UsageContext = "general" | "hero" | "thumbnail" | "email" | "social";
type Orientation = "landscape" | "portrait" | "square";

interface MediaItem {
  id: string;
  filename: string;
  url: string;
  content_type: string;
  size: number;
  created_at: string;
  source?: "upload" | "ai_generated";
  prompt?: string;
  // Metadata fields
  display_name?: string;
  description?: string;
  tags?: string[];
  alt_text?: string;
  usage_context?: UsageContext;
  orientation?: Orientation;
  brightness?: number; // 0–255
  width?: number;
  height?: number;
  dominant_colors?: string[];
  image_provider_slug?: string;
}

interface BrandRef {
  id: number;
  label: string | null;
  asset_id: number;
  url: string | null;
}

interface AiGenerateForm {
  prompt: string;
  size: "1024x1024" | "1792x1024" | "1024x1792";
  quality: "standard" | "hd";
  model_slug?: string;
}

interface ImageModel {
  slug: string;
  name: string;
  price_label: string;
  elo_score: number | null;
  elo_rank: number | null;
  quality_stars: number;
  badge: string | null;
  badge_color: string | null;
  cost_tier: string;
  cost_note?: string;
  description: string;
  is_default: boolean;
}

interface MetaEditState {
  display_name: string;
  description: string;
  tags: string; // comma-separated string for editing
  alt_text: string;
  usage_context: UsageContext;
}

const inputStyle: React.CSSProperties = {
  width: "100%",
  padding: "10px 14px",
  borderRadius: 10,
  background: T.surfaceAlt,
  border: `1px solid ${T.border}`,
  color: T.text,
  fontSize: 13,
  outline: "none",
  boxSizing: "border-box",
  transition: "border-color 0.2s ease",
};

const labelStyle: React.CSSProperties = {
  fontSize: 11,
  color: T.textMuted,
  textTransform: "uppercase",
  fontWeight: 700,
  marginBottom: 4,
  display: "block",
  letterSpacing: "0.04em",
};

const selectStyle: React.CSSProperties = {
  ...inputStyle,
  appearance: "none",
  cursor: "pointer",
};

const smallInputStyle: React.CSSProperties = {
  ...inputStyle,
  padding: "7px 10px",
  fontSize: 12,
  borderRadius: 7,
};

function brightnessLabel(brightness: number): string {
  if (brightness < 85) return "Dunkel";
  if (brightness < 170) return "Mittel";
  return "Hell";
}

function brightnessColor(brightness: number): string {
  if (brightness < 85) return T.textDim ?? "#666";
  if (brightness < 170) return T.warning ?? "#f59e0b";
  return T.success ?? "#22c55e";
}

function modelBadgeLabel(slug: string | undefined): string | null {
  if (!slug) return null;
  switch (slug) {
    case "fal_ai": return "FLUX Pro";
    case "fal_ai_schnell": return "FLUX Schnell";
    case "recraft_v3": return "Recraft V3";
    case "ideogram_v2": return "Ideogram";
    case "openai_images": return "DALL-E";
    default: return null;
  }
}

function initMetaEdit(item: MediaItem): MetaEditState {
  return {
    display_name: item.display_name ?? "",
    description: item.description ?? "",
    tags: (item.tags ?? []).join(", "),
    alt_text: item.alt_text ?? "",
    usage_context: item.usage_context ?? "general",
  };
}

/* ─────────────────────────────────────────────────────────────────────────
   MetadataPanel — expandable accordion below each card
   ───────────────────────────────────────────────────────────────────────── */
function MetadataPanel({ item, onUpdated }: { item: MediaItem; onUpdated: (updated: MediaItem) => void }) {
  const [open, setOpen] = useState(false);
  const [edit, setEdit] = useState<MetaEditState>(() => initMetaEdit(item));
  const [saving, setSaving] = useState(false);
  const [describing, setDescribing] = useState(false);
  const [saveOk, setSaveOk] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  // Sync edit state when item prop changes (e.g. after describe)
  useEffect(() => {
    setEdit(initMetaEdit(item));
  }, [item]);

  const handleDescribe = async () => {
    setDescribing(true);
    setErr(null);
    try {
      const res = await apiFetch(`/admin/media/${item.id}/describe`, { method: "POST" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json() as {
        description?: string;
        tags?: string[];
        alt_text?: string;
        usage_context?: UsageContext;
        dominant_colors?: string[];
        brightness?: number;
      };
      const updated: MediaItem = {
        ...item,
        description: data.description ?? item.description,
        tags: data.tags ?? item.tags,
        alt_text: data.alt_text ?? item.alt_text,
        usage_context: data.usage_context ?? item.usage_context,
        dominant_colors: data.dominant_colors ?? item.dominant_colors,
        brightness: data.brightness ?? item.brightness,
      };
      onUpdated(updated);
      // edit state will sync via useEffect above
    } catch (e) {
      setErr(`KI-Beschreibung fehlgeschlagen: ${e}`);
    } finally {
      setDescribing(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    setErr(null);
    try {
      const tagsArray = edit.tags
        .split(/,\s*/)
        .map((t) => t.trim())
        .filter(Boolean);
      const body = {
        display_name: edit.display_name || undefined,
        description: edit.description || undefined,
        tags: tagsArray.length > 0 ? tagsArray : undefined,
        alt_text: edit.alt_text || undefined,
        usage_context: edit.usage_context,
      };
      const res = await apiFetch(`/admin/media/${item.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const updated: MediaItem = { ...item, ...body, tags: tagsArray };
      onUpdated(updated);
      setSaveOk(true);
      setTimeout(() => setSaveOk(false), 2000);
    } catch (e) {
      setErr(`Speichern fehlgeschlagen: ${e}`);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={{ borderTop: `1px solid ${T.border}` }}>
      {/* Accordion toggle */}
      <button
        onClick={() => setOpen((v) => !v)}
        style={{
          width: "100%", display: "flex", alignItems: "center", justifyContent: "space-between",
          padding: "8px 12px", background: "none", border: "none",
          cursor: "pointer", color: T.textMuted, fontSize: 11, fontWeight: 600,
        }}
      >
        <span>Metadaten</span>
        <ChevronDown
          size={12}
          style={{ transform: open ? "rotate(180deg)" : "rotate(0deg)", transition: "transform 0.2s" }}
        />
      </button>

      {open && (
        <div style={{ padding: "0 12px 12px", display: "flex", flexDirection: "column", gap: 10 }}>
          {/* Error */}
          {err && (
            <div style={{
              display: "flex", alignItems: "center", gap: 8,
              padding: "8px 10px", borderRadius: 7,
              background: T.dangerDim, border: `1px solid ${T.danger}30`,
            }}>
              <AlertTriangle size={12} color={T.danger} />
              <span style={{ fontSize: 11, color: T.danger, flex: 1 }}>{err}</span>
              <button onClick={() => setErr(null)} style={{ background: "none", border: "none", cursor: "pointer", color: T.danger, padding: 0 }}>
                <X size={11} />
              </button>
            </div>
          )}

          {/* Read-only badges */}
          <div style={{ display: "flex", flexWrap: "wrap", gap: 5 }}>
            {item.orientation && (
              <span style={{
                padding: "2px 8px", borderRadius: 20,
                background: T.accentDim, color: T.accent,
                fontSize: 10, fontWeight: 700,
              }}>
                {item.orientation === "landscape" ? "Querformat" : item.orientation === "portrait" ? "Hochformat" : "Quadrat"}
              </span>
            )}
            {item.brightness !== undefined && (
              <span style={{
                padding: "2px 8px", borderRadius: 20,
                background: T.surfaceAlt,
                border: `1px solid ${T.border}`,
                color: brightnessColor(item.brightness),
                fontSize: 10, fontWeight: 700,
              }}>
                {brightnessLabel(item.brightness)}
              </span>
            )}
            {item.width !== undefined && item.height !== undefined && (
              <span style={{
                padding: "2px 8px", borderRadius: 20,
                background: T.surfaceAlt,
                border: `1px solid ${T.border}`,
                color: T.textMuted,
                fontSize: 10, fontWeight: 600,
              }}>
                {item.width}&times;{item.height}
              </span>
            )}
          </div>

          {/* Dominant colors */}
          {item.dominant_colors && item.dominant_colors.length > 0 && (
            <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
              <span style={{ fontSize: 10, color: T.textDim, marginRight: 2 }}>Farben:</span>
              {item.dominant_colors.map((hex, i) => (
                <div
                  key={i}
                  title={hex}
                  style={{
                    width: 16, height: 16, borderRadius: "50%",
                    background: hex,
                    border: `1px solid ${T.border}`,
                    flexShrink: 0,
                  }}
                />
              ))}
            </div>
          )}

          {/* Editable: display_name */}
          <div>
            <label style={labelStyle}>Anzeigename</label>
            <input
              style={smallInputStyle}
              type="text"
              value={edit.display_name}
              onChange={(e) => setEdit((prev) => ({ ...prev, display_name: e.target.value }))}
              placeholder={item.filename}
            />
          </div>

          {/* Editable: alt_text */}
          <div>
            <label style={labelStyle}>Alt-Text</label>
            <input
              style={smallInputStyle}
              type="text"
              value={edit.alt_text}
              onChange={(e) => setEdit((prev) => ({ ...prev, alt_text: e.target.value }))}
              placeholder="Beschreibung für Screenreader..."
            />
          </div>

          {/* Editable: description */}
          <div>
            <label style={labelStyle}>Beschreibung</label>
            <textarea
              style={{ ...smallInputStyle, minHeight: 52, resize: "vertical", fontFamily: "inherit" }}
              value={edit.description}
              onChange={(e) => setEdit((prev) => ({ ...prev, description: e.target.value }))}
              placeholder="Kurze Beschreibung des Bildes..."
            />
          </div>

          {/* Editable: tags */}
          <div>
            <label style={labelStyle}>Tags (kommagetrennt)</label>
            <input
              style={smallInputStyle}
              type="text"
              value={edit.tags}
              onChange={(e) => setEdit((prev) => ({ ...prev, tags: e.target.value }))}
              placeholder="fitnessstudio, motivation, hell"
            />
          </div>

          {/* Editable: usage_context */}
          <div>
            <label style={labelStyle}>Verwendungskontext</label>
            <select
              style={{ ...smallInputStyle, appearance: "none" as const }}
              value={edit.usage_context}
              onChange={(e) => setEdit((prev) => ({ ...prev, usage_context: e.target.value as UsageContext }))}
            >
              <option value="general">Allgemein</option>
              <option value="hero">Hero-Bild</option>
              <option value="thumbnail">Thumbnail</option>
              <option value="email">E-Mail</option>
              <option value="social">Social Media</option>
            </select>
          </div>

          {/* Action buttons */}
          <div style={{ display: "flex", gap: 7, marginTop: 2 }}>
            <button
              onClick={handleDescribe}
              disabled={describing}
              style={{
                flex: 1, display: "flex", alignItems: "center", justifyContent: "center", gap: 5,
                padding: "7px 0", borderRadius: 7,
                background: T.accentDim, border: `1px solid ${T.accent}30`,
                color: T.accent, fontSize: 11, fontWeight: 700,
                cursor: describing ? "not-allowed" : "pointer",
                opacity: describing ? 0.6 : 1,
              }}
            >
              {describing ? <RefreshCw size={11} className="animate-spin" /> : <Wand2 size={11} />}
              {describing ? "Analysiert..." : "KI beschreiben"}
            </button>
            <button
              onClick={handleSave}
              disabled={saving}
              style={{
                flex: 1, display: "flex", alignItems: "center", justifyContent: "center", gap: 5,
                padding: "7px 0", borderRadius: 7,
                background: saveOk ? T.successDim : T.surface,
                border: `1px solid ${saveOk ? T.success + "40" : T.border}`,
                color: saveOk ? T.success : T.textMuted,
                fontSize: 11, fontWeight: 700,
                cursor: saving ? "not-allowed" : "pointer",
                opacity: saving ? 0.6 : 1,
                transition: "all 0.2s ease",
              }}
            >
              {saving ? <RefreshCw size={11} className="animate-spin" /> : saveOk ? <CheckCircle size={11} /> : <Save size={11} />}
              {saving ? "Speichert..." : saveOk ? "Gespeichert" : "Speichern"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

/* ─────────────────────────────────────────────────────────────────────────
   Main page
   ───────────────────────────────────────────────────────────────────────── */
export default function MediaPage() {
  const [items, setItems] = useState<MediaItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  // Brand references state
  const [brandRefs, setBrandRefs] = useState<BrandRef[]>([]);
  const [brandRefsLoading, setBrandRefsLoading] = useState(false);
  const [showBrandRefs, setShowBrandRefs] = useState(false);

  // Upload state
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // AI generate state
  const [showAiForm, setShowAiForm] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [generateError, setGenerateError] = useState<string | null>(null);
  const [aiForm, setAiForm] = useState<AiGenerateForm>({
    prompt: "",
    size: "1024x1024",
    quality: "standard",
    model_slug: "flux2_pro",
  });
  const [imageModels, setImageModels] = useState<ImageModel[]>([]);
  const [showModelPicker, setShowModelPicker] = useState(false);

  const fetchMedia = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await apiFetch("/admin/media");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setItems(Array.isArray(data) ? data : (data.items ?? []));
    } catch (e) {
      setError(`Fehler beim Laden der Medien: ${e}`);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchMedia();
    apiFetch("/admin/media/brand-references").then(r => r.json()).then((data: BrandRef[]) => setBrandRefs(data)).catch(() => {});
    apiFetch("/admin/media/image-models").then(r => r.json()).then((data: ImageModel[]) => {
      if (Array.isArray(data)) {
        setImageModels(data);
        const def = data.find(m => m.is_default);
        if (def) setAiForm(prev => ({ ...prev, model_slug: def.slug }));
      }
    }).catch(() => {});
  }, []);

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const allowed = ["image/png", "image/jpeg", "image/gif", "image/webp"];
    if (!allowed.includes(file.type)) {
      setUploadError("Nur PNG, JPG, GIF und WebP sind erlaubt.");
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      setUploadError("Maximale Dateigröße: 10 MB.");
      return;
    }

    setUploading(true);
    setUploadError(null);
    try {
      const form = new FormData();
      form.append("file", file);
      const res = await apiFetch("/admin/media/upload", { method: "POST", body: form });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error((body as { detail?: string }).detail || `HTTP ${res.status}`);
      }
      await fetchMedia();
    } catch (e) {
      setUploadError(`Upload fehlgeschlagen: ${e}`);
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const handleAiGenerate = async () => {
    if (!aiForm.prompt.trim()) {
      setGenerateError("Bitte einen Prompt eingeben.");
      return;
    }
    setGenerating(true);
    setGenerateError(null);
    try {
      const res = await apiFetch("/admin/media/ai-generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(aiForm),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error((body as { detail?: string }).detail || `HTTP ${res.status}`);
      }
      setShowAiForm(false);
      setAiForm({ prompt: "", size: "1024x1024", quality: "standard", model_slug: imageModels.find(m => m.is_default)?.slug ?? "flux2_pro" });
      await fetchMedia();
    } catch (e) {
      setGenerateError(`Generierung fehlgeschlagen: ${e}`);
    } finally {
      setGenerating(false);
    }
  };

  const handleAddBrandRef = async (assetId: string) => {
    setBrandRefsLoading(true);
    try {
      const res = await apiFetch("/admin/media/brand-references", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ asset_id: Number(assetId), label: null }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const created = await res.json() as BrandRef;
      setBrandRefs((prev) => [...prev, created]);
    } catch (e) {
      setError(`Referenz konnte nicht hinzugefügt werden: ${e}`);
    } finally {
      setBrandRefsLoading(false);
    }
  };

  const handleDeleteBrandRef = async (refId: number) => {
    try {
      const res = await apiFetch(`/admin/media/brand-references/${refId}`, { method: "DELETE" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setBrandRefs((prev) => prev.filter((r) => r.id !== refId));
    } catch (e) {
      setError(`Referenz konnte nicht gelöscht werden: ${e}`);
    }
  };

  const handleCopy = (url: string, id: string) => {
    navigator.clipboard.writeText(url).then(() => {
      setCopiedId(id);
      setTimeout(() => setCopiedId(null), 2000);
    });
  };

  const handleDelete = async (id: string) => {
    setDeletingId(id);
    try {
      const res = await apiFetch(`/admin/media/${id}`, { method: "DELETE" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setItems((prev) => prev.filter((item) => item.id !== id));
    } catch (e) {
      setError(`Löschen fehlgeschlagen: ${e}`);
    } finally {
      setDeletingId(null);
    }
  };

  const handleItemUpdated = (updated: MediaItem) => {
    setItems((prev) => prev.map((it) => (it.id === updated.id ? updated : it)));
  };

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 12 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div style={{
            width: 40, height: 40, borderRadius: 12,
            background: T.accentDim, display: "flex",
            alignItems: "center", justifyContent: "center",
          }}>
            <ImageIcon size={20} color={T.accent} />
          </div>
          <div>
            <h1 style={{ fontSize: 18, fontWeight: 700, color: T.text, margin: 0 }}>Media-Bibliothek</h1>
            <p style={{ fontSize: 12, color: T.textMuted, margin: 0 }}>{items.length} Dateien</p>
          </div>
        </div>
        <div style={{ display: "flex", gap: 10 }}>
          {/* Upload Button */}
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading}
            style={{
              display: "flex", alignItems: "center", gap: 6,
              padding: "9px 18px", borderRadius: 8,
              background: T.surfaceAlt, border: `1px solid ${T.border}`,
              color: T.text, fontSize: 13, fontWeight: 600,
              cursor: uploading ? "not-allowed" : "pointer",
              opacity: uploading ? 0.6 : 1,
            }}
          >
            {uploading ? <RefreshCw size={14} className="animate-spin" /> : <Upload size={14} />}
            {uploading ? "Wird hochgeladen..." : "Hochladen"}
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept="image/png,image/jpeg,image/gif,image/webp"
            style={{ display: "none" }}
            onChange={handleFileSelect}
          />

          {/* AI Generate Button */}
          <button
            onClick={() => setShowAiForm((prev) => !prev)}
            style={{
              display: "flex", alignItems: "center", gap: 6,
              padding: "9px 18px", borderRadius: 8,
              background: `linear-gradient(135deg, ${T.accent}, ${T.accentLight})`,
              border: "none", color: "#fff", fontSize: 13, fontWeight: 700,
              cursor: "pointer",
            }}
          >
            <Sparkles size={14} />
            KI-Bild generieren
            <ChevronDown size={12} style={{ transform: showAiForm ? "rotate(180deg)" : "rotate(0deg)", transition: "transform 0.2s" }} />
          </button>
        </div>
      </div>

      {/* Status messages */}
      {(uploadError || error) && (
        <div style={{
          display: "flex", alignItems: "center", gap: 10,
          padding: "12px 16px", borderRadius: 10,
          background: T.dangerDim, border: `1px solid ${T.danger}30`,
        }}>
          <AlertTriangle size={16} color={T.danger} />
          <span style={{ fontSize: 13, color: T.danger, fontWeight: 600 }}>{uploadError || error}</span>
          <button
            onClick={() => { setUploadError(null); setError(null); }}
            style={{ marginLeft: "auto", background: "none", border: "none", cursor: "pointer", color: T.danger }}
          >
            <X size={14} />
          </button>
        </div>
      )}

      {/* AI Generate Form */}
      {showAiForm && (
        <Card style={{ padding: 0, overflow: "hidden" }}>
          <div style={{
            padding: "16px 24px", borderBottom: `1px solid ${T.border}`,
            display: "flex", alignItems: "center", gap: 12,
          }}>
            <div style={{
              width: 36, height: 36, borderRadius: 10,
              background: T.accentDim, display: "flex",
              alignItems: "center", justifyContent: "center",
            }}>
              <Sparkles size={18} color={T.accent} />
            </div>
            <div>
              <h2 style={{ fontSize: 14, fontWeight: 700, color: T.text, margin: 0 }}>KI-Bildgenerierung</h2>
              <p style={{ fontSize: 11, color: T.textMuted, margin: 0 }}>KI-Bild mit gewähltem Modell generieren und in Bibliothek speichern</p>
            </div>
            <button
              onClick={() => setShowAiForm(false)}
              style={{ marginLeft: "auto", background: "none", border: "none", cursor: "pointer", color: T.textMuted }}
            >
              <X size={16} />
            </button>
          </div>
          <div style={{ padding: 24, display: "flex", flexDirection: "column", gap: 16 }}>
            {generateError && (
              <div style={{
                display: "flex", alignItems: "center", gap: 10,
                padding: "10px 14px", borderRadius: 8,
                background: T.dangerDim, border: `1px solid ${T.danger}30`,
              }}>
                <AlertTriangle size={14} color={T.danger} />
                <span style={{ fontSize: 12, color: T.danger }}>{generateError}</span>
              </div>
            )}
            <div>
              <label style={labelStyle}>Prompt</label>
              <textarea
                style={{ ...inputStyle, minHeight: 80, resize: "vertical", fontFamily: "inherit" }}
                placeholder="Ein futuristisches Fitnessstudio mit Neon-Lichtern und modernen Trainingsgeräten..."
                value={aiForm.prompt}
                onChange={(e) => setAiForm((prev) => ({ ...prev, prompt: e.target.value }))}
              />
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
              <div>
                <label style={labelStyle}>Bildgröße</label>
                <div style={{ position: "relative" }}>
                  <select
                    style={selectStyle}
                    value={aiForm.size}
                    onChange={(e) => setAiForm((prev) => ({ ...prev, size: e.target.value as AiGenerateForm["size"] }))}
                  >
                    <option value="1024x1024">1024 × 1024 (Quadrat)</option>
                    <option value="1792x1024">1792 × 1024 (Breitbild)</option>
                    <option value="1024x1792">1024 × 1792 (Hochformat)</option>
                  </select>
                </div>
              </div>
              <div>
                <label style={labelStyle}>Qualität</label>
                <div style={{ position: "relative" }}>
                  <select
                    style={selectStyle}
                    value={aiForm.quality}
                    onChange={(e) => setAiForm((prev) => ({ ...prev, quality: e.target.value as AiGenerateForm["quality"] }))}
                  >
                    <option value="standard">Standard</option>
                    <option value="hd">HD (höhere Kosten)</option>
                  </select>
                </div>
              </div>
            </div>
            {/* Model picker */}
            {imageModels.length > 0 && (
              <div>
                <label style={labelStyle}>Modell</label>
                <button
                  type="button"
                  onClick={() => setShowModelPicker(p => !p)}
                  style={{
                    width: "100%", padding: "10px 14px", borderRadius: 10,
                    background: T.surfaceAlt, border: `1px solid ${T.border}`,
                    color: T.text, fontSize: 13, cursor: "pointer",
                    display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8,
                  }}
                >
                  <span style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    {(() => {
                      const m = imageModels.find(x => x.slug === aiForm.model_slug);
                      return m ? (
                        <>
                          {m.badge && (
                            <span style={{ fontSize: 10, padding: "1px 6px", borderRadius: 4, background: m.badge_color ?? T.accentDim, color: "#fff", fontWeight: 700 }}>
                              {m.badge}
                            </span>
                          )}
                          <span>{m.name}</span>
                          <span style={{ color: T.textMuted, fontSize: 12 }}>{m.price_label}</span>
                          {m.elo_rank && <span style={{ color: T.textDim, fontSize: 11 }}>#{m.elo_rank} Elo {m.elo_score}</span>}
                        </>
                      ) : <span>Modell wählen</span>;
                    })()}
                  </span>
                  <ChevronDown size={13} style={{ transform: showModelPicker ? "rotate(180deg)" : "none", transition: "transform 0.2s", flexShrink: 0 }} />
                </button>
                {showModelPicker && (
                  <div style={{
                    marginTop: 4, borderRadius: 10, border: `1px solid ${T.border}`,
                    background: T.surface, overflow: "hidden", maxHeight: 360, overflowY: "auto",
                  }}>
                    {imageModels.map(m => {
                      const selected = m.slug === aiForm.model_slug;
                      return (
                        <button
                          key={m.slug}
                          type="button"
                          onClick={() => { setAiForm(prev => ({ ...prev, model_slug: m.slug })); setShowModelPicker(false); }}
                          style={{
                            width: "100%", padding: "10px 14px", textAlign: "left",
                            background: selected ? T.accentDim : "transparent",
                            border: "none", borderBottom: `1px solid ${T.border}20`,
                            cursor: "pointer", display: "flex", flexDirection: "column", gap: 3,
                          }}
                        >
                          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                            {m.badge && (
                              <span style={{ fontSize: 10, padding: "1px 6px", borderRadius: 4, background: m.badge_color ?? T.accentDim, color: "#fff", fontWeight: 700 }}>
                                {m.badge}
                              </span>
                            )}
                            <span style={{ fontSize: 13, fontWeight: 600, color: T.text }}>{m.name}</span>
                            <span style={{ marginLeft: "auto", fontSize: 12, color: T.textMuted }}>{m.price_label}</span>
                          </div>
                          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                            <span style={{ fontSize: 11, color: T.textDim }}>
                              {"★".repeat(m.quality_stars)}{"☆".repeat(5 - m.quality_stars)}
                            </span>
                            {m.elo_rank && <span style={{ fontSize: 11, color: T.textDim }}>Rang #{m.elo_rank}</span>}
                            {m.cost_tier === "expensive" && (
                              <span style={{ fontSize: 11, color: T.warning ?? "#f59e0b" }}>⚠️ Teuer</span>
                            )}
                          </div>
                          {m.cost_note && <p style={{ fontSize: 11, color: T.warning ?? "#f59e0b", margin: 0 }}>{m.cost_note}</p>}
                        </button>
                      );
                    })}
                  </div>
                )}
              </div>
            )}

            <div style={{ display: "flex", justifyContent: "flex-end" }}>
              <button
                onClick={handleAiGenerate}
                disabled={generating}
                style={{
                  display: "flex", alignItems: "center", gap: 6,
                  padding: "10px 24px", borderRadius: 8,
                  background: `linear-gradient(135deg, ${T.accent}, ${T.accentLight})`,
                  border: "none", color: "#fff", fontSize: 13, fontWeight: 700,
                  cursor: generating ? "not-allowed" : "pointer",
                  opacity: generating ? 0.6 : 1,
                }}
              >
                {generating ? <RefreshCw size={13} className="animate-spin" /> : <Sparkles size={13} />}
                {generating ? "Wird generiert..." : "Bild generieren"}
              </button>
            </div>
          </div>
        </Card>
      )}

      {/* Brand References Section */}
      <Card style={{ padding: 0, overflow: "hidden" }}>
        {/* Collapsible header */}
        <button
          onClick={() => setShowBrandRefs((v) => !v)}
          style={{
            width: "100%", display: "flex", alignItems: "center", justifyContent: "space-between",
            padding: "14px 24px", background: "none", border: "none", cursor: "pointer",
            borderBottom: showBrandRefs ? `1px solid ${T.border}` : "none",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <Star size={16} color={T.warning ?? "#f59e0b"} />
            <span style={{ fontSize: 14, fontWeight: 700, color: T.text }}>Marken-Referenzbilder</span>
            {brandRefs.length > 0 && (
              <span style={{
                padding: "2px 8px", borderRadius: 20,
                background: T.accentDim, color: T.accentLight,
                fontSize: 11, fontWeight: 700,
              }}>
                {brandRefs.length}
              </span>
            )}
          </div>
          <ChevronDown
            size={14}
            color={T.textMuted}
            style={{ transform: showBrandRefs ? "rotate(180deg)" : "rotate(0deg)", transition: "transform 0.2s" }}
          />
        </button>

        {showBrandRefs && (
          <div style={{ padding: "16px 24px", display: "flex", flexDirection: "column", gap: 12 }}>
            {/* Info text */}
            <p style={{ fontSize: 11, color: T.textDim, margin: 0 }}>
              Business/Enterprise: Referenzbilder verbessern die Markenkonsistenz bei KI-generierten Bildern
            </p>

            {/* Existing brand ref thumbnails */}
            {brandRefs.length > 0 && (
              <div style={{ display: "flex", flexWrap: "wrap", gap: 10 }}>
                {brandRefs.map((ref) => (
                  <div key={ref.id} style={{ position: "relative" }}>
                    {ref.url ? (
                      <img
                        src={ref.url}
                        alt={ref.label ?? "Referenzbild"}
                        style={{ width: 60, height: 60, objectFit: "cover", borderRadius: 8, border: `1px solid ${T.border}` }}
                        onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
                      />
                    ) : (
                      <div style={{ width: 60, height: 60, borderRadius: 8, border: `1px solid ${T.border}`, background: T.surfaceAlt, display: "flex", alignItems: "center", justifyContent: "center" }}>
                        <ImageIcon size={20} color={T.textDim} />
                      </div>
                    )}
                    <button
                      onClick={() => handleDeleteBrandRef(ref.id)}
                      title="Entfernen"
                      style={{
                        position: "absolute", top: -6, right: -6,
                        width: 18, height: 18, borderRadius: "50%",
                        background: T.danger, border: "none", cursor: "pointer",
                        display: "flex", alignItems: "center", justifyContent: "center",
                        fontSize: 10, color: "#fff", fontWeight: 700,
                        lineHeight: 1,
                      }}
                    >
                      ×
                    </button>
                    {ref.label && (
                      <p style={{ fontSize: 9, color: T.textDim, textAlign: "center", margin: "4px 0 0", maxWidth: 60, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{ref.label}</p>
                    )}
                  </div>
                ))}
              </div>
            )}

            {brandRefs.length === 0 && !brandRefsLoading && (
              <p style={{ fontSize: 12, color: T.textDim, margin: 0 }}>
                Noch keine Referenzbilder gesetzt. Klicken Sie auf &quot;⭐ Ref.&quot; bei einem Bild unten.
              </p>
            )}
          </div>
        )}
      </Card>

      {/* Media Grid */}
      <Card style={{ padding: 0, overflow: "hidden" }}>
        <div style={{
          padding: "16px 24px", borderBottom: `1px solid ${T.border}`,
          display: "flex", alignItems: "center", gap: 12,
        }}>
          <h2 style={{ fontSize: 14, fontWeight: 700, color: T.text, margin: 0 }}>Alle Medien</h2>
          <button
            onClick={fetchMedia}
            disabled={loading}
            style={{
              marginLeft: "auto", background: "none", border: "none",
              cursor: "pointer", color: T.textMuted, display: "flex", alignItems: "center", gap: 4,
              fontSize: 12, fontWeight: 600,
            }}
          >
            <RefreshCw size={13} style={{ animation: loading ? "spin 1s linear infinite" : "none" }} />
            Aktualisieren
          </button>
        </div>

        {loading ? (
          <div style={{ padding: 60, textAlign: "center", color: T.textMuted, fontSize: 13 }}>
            <RefreshCw size={24} style={{ margin: "0 auto 12px", display: "block", animation: "spin 1s linear infinite" }} />
            Medien werden geladen...
          </div>
        ) : items.length === 0 ? (
          <div style={{ padding: 60, textAlign: "center" }}>
            <ImageIcon size={48} color={T.textDim} style={{ margin: "0 auto 16px", display: "block" }} />
            <p style={{ fontSize: 14, color: T.textMuted, margin: "0 0 6px", fontWeight: 600 }}>Keine Medien vorhanden</p>
            <p style={{ fontSize: 12, color: T.textDim, margin: 0 }}>Lade ein Bild hoch oder generiere eines mit KI</p>
          </div>
        ) : (
          <div style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))",
            gap: 16,
            padding: 24,
          }}>
            {items.map((item) => (
              <div
                key={item.id}
                style={{
                  borderRadius: 12,
                  overflow: "hidden",
                  border: `1px solid ${T.border}`,
                  background: T.surfaceAlt,
                  display: "flex",
                  flexDirection: "column",
                  transition: "border-color 0.2s ease",
                }}
              >
                {/* Image preview */}
                <div style={{ position: "relative", aspectRatio: "1", background: T.bg, overflow: "hidden" }}>
                  <img
                    src={item.url}
                    alt={item.alt_text || item.display_name || item.filename}
                    style={{ width: "100%", height: "100%", objectFit: "cover" }}
                    onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
                  />
                  {/* AI source badge */}
                  {item.source === "ai_generated" && (
                    <div style={{
                      position: "absolute", top: 8, right: 8,
                      background: `${T.accent}CC`, borderRadius: 6,
                      padding: "3px 7px", display: "flex", alignItems: "center", gap: 4,
                    }}>
                      <Sparkles size={10} color="#fff" />
                      <span style={{ fontSize: 9, color: "#fff", fontWeight: 700 }}>KI</span>
                    </div>
                  )}
                  {/* Model badge */}
                  {modelBadgeLabel(item.image_provider_slug) && (
                    <div style={{
                      position: "absolute", top: 8, left: 8,
                      background: "rgba(0,0,0,0.55)", borderRadius: 5,
                      padding: "2px 6px",
                    }}>
                      <span style={{ fontSize: 10, color: "rgba(255,255,255,0.85)", fontWeight: 600 }}>
                        {modelBadgeLabel(item.image_provider_slug)}
                      </span>
                    </div>
                  )}
                </div>

                {/* Meta & actions */}
                <div style={{ padding: 12, display: "flex", flexDirection: "column", gap: 8, flex: 1 }}>
                  <p style={{ fontSize: 12, fontWeight: 600, color: T.text, margin: 0, wordBreak: "break-all" }}>
                    {item.display_name || item.filename}
                  </p>
                  <p style={{ fontSize: 10, color: T.textDim, margin: 0 }}>
                    {formatSize(item.size)} &bull; {new Date(item.created_at).toLocaleDateString("de-DE")}
                  </p>
                  {item.prompt && (
                    <p style={{ fontSize: 10, color: T.textMuted, margin: 0, fontStyle: "italic", overflow: "hidden", display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical" as const }}>
                      {item.prompt}
                    </p>
                  )}
                  {/* Tag chips */}
                  {item.tags && item.tags.length > 0 && (
                    <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
                      {item.tags.slice(0, 4).map((tag) => (
                        <span key={tag} style={{
                          padding: "1px 6px", borderRadius: 20,
                          background: T.surface, border: `1px solid ${T.border}`,
                          fontSize: 9, color: T.textMuted, fontWeight: 600,
                        }}>
                          {tag}
                        </span>
                      ))}
                      {item.tags.length > 4 && (
                        <span style={{ fontSize: 9, color: T.textDim, padding: "1px 4px" }}>
                          +{item.tags.length - 4}
                        </span>
                      )}
                    </div>
                  )}
                  <div style={{ display: "flex", gap: 8, marginTop: "auto" }}>
                    <button
                      onClick={() => handleCopy(item.url, item.id)}
                      title="URL kopieren"
                      style={{
                        flex: 1, display: "flex", alignItems: "center", justifyContent: "center", gap: 5,
                        padding: "7px 0", borderRadius: 7,
                        background: copiedId === item.id ? T.successDim : T.surface,
                        border: `1px solid ${copiedId === item.id ? T.success + "40" : T.border}`,
                        color: copiedId === item.id ? T.success : T.textMuted,
                        fontSize: 11, fontWeight: 600, cursor: "pointer",
                        transition: "all 0.2s ease",
                      }}
                    >
                      {copiedId === item.id ? <CheckCircle size={12} /> : <Copy size={12} />}
                      {copiedId === item.id ? "Kopiert" : "URL"}
                    </button>
                    {/* Brand ref button */}
                    <button
                      onClick={() => handleAddBrandRef(item.id)}
                      disabled={brandRefsLoading || brandRefs.some((r) => r.asset_id === Number(item.id))}
                      title="Als Marken-Referenz setzen"
                      style={{
                        display: "flex", alignItems: "center", justifyContent: "center", gap: 4,
                        padding: "7px 8px", borderRadius: 7,
                        background: brandRefs.some((r) => r.asset_id === Number(item.id)) ? T.accentDim : "none",
                        border: `1px solid ${brandRefs.some((r) => r.asset_id === Number(item.id)) ? T.accent + "60" : T.border}`,
                        color: brandRefs.some((r) => r.asset_id === Number(item.id)) ? T.accentLight : T.textDim,
                        fontSize: 10, fontWeight: 700,
                        cursor: (brandRefsLoading || brandRefs.some((r) => r.asset_id === Number(item.id))) ? "not-allowed" : "pointer",
                        opacity: brandRefsLoading ? 0.6 : 1,
                        transition: "all 0.2s ease",
                      }}
                    >
                      <Star size={11} />
                      Ref.
                    </button>
                    <button
                      onClick={() => handleDelete(item.id)}
                      disabled={deletingId === item.id}
                      title="Löschen"
                      style={{
                        display: "flex", alignItems: "center", justifyContent: "center",
                        padding: "7px 10px", borderRadius: 7,
                        background: "none",
                        border: `1px solid ${T.border}`,
                        color: T.textDim, fontSize: 11, cursor: deletingId === item.id ? "not-allowed" : "pointer",
                        opacity: deletingId === item.id ? 0.5 : 1,
                        transition: "all 0.2s ease",
                      }}
                    >
                      {deletingId === item.id ? <RefreshCw size={12} className="animate-spin" /> : <Trash2 size={12} />}
                    </button>
                  </div>
                </div>

                {/* Metadata accordion panel */}
                <MetadataPanel item={item} onUpdated={handleItemUpdated} />
              </div>
            ))}
          </div>
        )}
      </Card>

      <style>{`
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
        .animate-spin { animation: spin 1s linear infinite; }
      `}</style>
    </div>
  );
}
