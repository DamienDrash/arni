"use client";

import { useEffect, useState, useRef } from "react";
import {
  Image as ImageIcon, Upload, Sparkles, Copy, Trash2, CheckCircle,
  AlertTriangle, RefreshCw, X, ChevronDown,
} from "lucide-react";
import { apiFetch } from "@/lib/api";
import { Card } from "@/components/ui/Card";
import { T } from "@/lib/tokens";

interface MediaItem {
  id: string;
  filename: string;
  url: string;
  content_type: string;
  size: number;
  created_at: string;
  source?: "upload" | "ai_generated";
  prompt?: string;
}

interface AiGenerateForm {
  prompt: string;
  size: "1024x1024" | "1792x1024" | "1024x1792";
  quality: "standard" | "hd";
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

export default function MediaPage() {
  const [items, setItems] = useState<MediaItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

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
  });

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
        throw new Error(body.detail || `HTTP ${res.status}`);
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
        throw new Error(body.detail || `HTTP ${res.status}`);
      }
      setShowAiForm(false);
      setAiForm({ prompt: "", size: "1024x1024", quality: "standard" });
      await fetchMedia();
    } catch (e) {
      setGenerateError(`Generierung fehlgeschlagen: ${e}`);
    } finally {
      setGenerating(false);
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
              <p style={{ fontSize: 11, color: T.textMuted, margin: 0 }}>Bild via DALL-E generieren und in Bibliothek speichern</p>
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
                    alt={item.filename}
                    style={{ width: "100%", height: "100%", objectFit: "cover" }}
                    onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
                  />
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
                </div>

                {/* Meta & actions */}
                <div style={{ padding: 12, display: "flex", flexDirection: "column", gap: 8, flex: 1 }}>
                  <p style={{ fontSize: 12, fontWeight: 600, color: T.text, margin: 0, wordBreak: "break-all", lineClamp: 2 }}>
                    {item.filename}
                  </p>
                  <p style={{ fontSize: 10, color: T.textDim, margin: 0 }}>
                    {formatSize(item.size)} &bull; {new Date(item.created_at).toLocaleDateString("de-DE")}
                  </p>
                  {item.prompt && (
                    <p style={{ fontSize: 10, color: T.textMuted, margin: 0, fontStyle: "italic", overflow: "hidden", display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical" as const }}>
                      {item.prompt}
                    </p>
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
