"use client";

import { useCallback, useEffect, useState } from "react";
import { Gift, Plus, Trash2, Edit3, RefreshCw, Copy, Check, ExternalLink, Link2 } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { T } from "@/lib/tokens";

type Offer = {
  id: number;
  slug: string;
  name: string;
  confirmation_message: string;
  attachment_url: string | null;
  attachment_filename: string | null;
  is_active: boolean;
  updated_at: string | null;
};

const inputStyle: React.CSSProperties = {
  width: "100%", boxSizing: "border-box", padding: "9px 12px",
  fontSize: 13, color: T.text, background: T.surfaceAlt,
  border: `1px solid ${T.border}`, borderRadius: 8, outline: "none",
};

function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <div>
      <p style={{ margin: "0 0 4px", fontSize: 11, fontWeight: 600, color: T.textDim }}>{label}</p>
      {children}
      {hint && <p style={{ margin: "3px 0 0", fontSize: 10, color: T.textDim }}>{hint}</p>}
    </div>
  );
}

// ── Modal ──────────────────────────────────────────────────────────────────

function OfferModal({
  initial,
  onClose,
  onSaved,
}: {
  initial?: Offer;
  onClose: () => void;
  onSaved: () => void;
}) {
  const isEdit = !!initial;
  const [slug, setSlug] = useState(initial?.slug ?? "");
  const [name, setName] = useState(initial?.name ?? "");
  const [message, setMessage] = useState(initial?.confirmation_message ?? "");
  const [attachUrl, setAttachUrl] = useState(initial?.attachment_url ?? "");
  const [attachName, setAttachName] = useState(initial?.attachment_filename ?? "");
  const [isActive, setIsActive] = useState(initial?.is_active ?? true);
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState("");

  const submit = async () => {
    if (!name || !message) { setErr("Name und Bestätigungsnachricht sind pflicht"); return; }
    if (!isEdit && !slug) { setErr("URL-Parameter ist pflicht"); return; }
    setSaving(true);
    setErr("");
    try {
      const url = isEdit ? `/admin/campaign-offers/${initial!.id}` : "/admin/campaign-offers";
      const method = isEdit ? "PATCH" : "POST";
      const body = {
        ...(isEdit ? {} : { slug: slug.toLowerCase().replace(/[^a-z0-9-]/g, "-") }),
        name,
        confirmation_message: message,
        attachment_url: attachUrl || null,
        attachment_filename: attachName || null,
        is_active: isActive,
      };
      const res = await apiFetch(url, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const e = await res.json().catch(() => ({}));
        setErr(e.detail || String(res.status));
      } else {
        onSaved();
        onClose();
      }
    } finally {
      setSaving(false);
    }
  };

  return (
    <div
      style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.6)", zIndex: 1000, display: "flex", alignItems: "center", justifyContent: "center", padding: 24 }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 16, padding: 28, width: "100%", maxWidth: 520, maxHeight: "90vh", overflowY: "auto" }}>
        <h2 style={{ margin: "0 0 20px", fontSize: 15, fontWeight: 700, color: T.text }}>
          {isEdit ? `Angebot bearbeiten: ${initial!.name}` : "Neues Opt-in Angebot"}
        </h2>

        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          {!isEdit && (
            <Field label="URL-Parameter (slug)" hint='Wird als ?offer=... in der URL verwendet, z.B. "preisliste"'>
              <input
                value={slug}
                onChange={(e) => setSlug(e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, "-"))}
                placeholder="preisliste"
                style={inputStyle}
              />
            </Field>
          )}
          <Field label="Interner Name">
            <input value={name} onChange={(e) => setName(e.target.value)} placeholder="z.B. Preisliste Download" style={inputStyle} />
          </Field>
          <Field label="Bestätigungsnachricht" hint="Diese Nachricht wird nach erfolgreichem Double Opt-in gesendet">
            <textarea
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              placeholder="Herzlich willkommen! Hier ist deine Preisliste: ..."
              rows={4}
              style={{ ...inputStyle, resize: "vertical", lineHeight: 1.6 }}
            />
          </Field>
          <Field label="Anhang-URL (optional)" hint="Wird automatisch an die Nachricht angehängt">
            <input value={attachUrl} onChange={(e) => setAttachUrl(e.target.value)} placeholder="https://example.com/preisliste.pdf" style={inputStyle} />
          </Field>
          {attachUrl && (
            <Field label="Dateiname (optional)">
              <input value={attachName} onChange={(e) => setAttachName(e.target.value)} placeholder="preisliste.pdf" style={inputStyle} />
            </Field>
          )}
          <label style={{ display: "flex", alignItems: "center", gap: 10, cursor: "pointer" }}>
            <input type="checkbox" checked={isActive} onChange={(e) => setIsActive(e.target.checked)} style={{ width: 16, height: 16, accentColor: T.accent }} />
            <span style={{ fontSize: 13, color: T.text }}>Aktiv (sichtbar auf Anmeldeseiten)</span>
          </label>
        </div>

        {err && <p style={{ margin: "12px 0 0", fontSize: 12, color: T.danger }}>{err}</p>}

        <div style={{ display: "flex", gap: 10, justifyContent: "flex-end", marginTop: 20 }}>
          <button onClick={onClose} style={{ padding: "7px 16px", borderRadius: 8, fontSize: 13, fontWeight: 600, cursor: "pointer", background: T.surfaceAlt, color: T.text, border: `1px solid ${T.border}` }}>
            Abbrechen
          </button>
          <button onClick={() => void submit()} disabled={saving} style={{ padding: "7px 16px", borderRadius: 8, fontSize: 13, fontWeight: 600, cursor: "pointer", background: T.accent, color: "#fff", border: "none" }}>
            {saving ? "Speichern…" : isEdit ? "Speichern" : "Erstellen"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Copy button ───────────────────────────────────────────────────────────

function CopyBtn({ text, label }: { text: string; label: string }) {
  const [copied, setCopied] = useState(false);
  const copy = () => {
    void navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };
  return (
    <button onClick={copy} title={`${label} kopieren`} style={{ display: "inline-flex", alignItems: "center", gap: 4, fontSize: 11, fontFamily: "monospace", padding: "3px 8px", borderRadius: 6, border: `1px solid ${T.border}`, background: T.surfaceAlt, color: copied ? T.success : T.textDim, cursor: "pointer", maxWidth: "100%", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
      {copied ? <Check size={11} style={{ flexShrink: 0 }} /> : <Copy size={11} style={{ flexShrink: 0 }} />}
      <span style={{ overflow: "hidden", textOverflow: "ellipsis" }}>{text}</span>
    </button>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────

type SubscribeToken = { token: string; subscribe_path: string };

export default function CampaignOffersPage() {
  const [offers, setOffers] = useState<Offer[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [editing, setEditing] = useState<Offer | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<number | null>(null);
  const [toast, setToast] = useState("");
  const [subscribeToken, setSubscribeToken] = useState<SubscribeToken | null>(null);
  const [selectedChannel, setSelectedChannel] = useState("whatsapp");

  const showToast = (msg: string) => { setToast(msg); setTimeout(() => setToast(""), 3000); };

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const res = await apiFetch("/admin/campaign-offers");
      if (!res.ok) throw new Error(String(res.status));
      setOffers(await res.json());
    } catch (e) { setError(String(e)); }
    finally { setLoading(false); }
  }, []);

  const loadToken = useCallback(async (channel: string) => {
    try {
      const res = await apiFetch(`/admin/campaign-offers/subscribe-token?channel=${channel}`);
      if (!res.ok) return;
      setSubscribeToken(await res.json() as SubscribeToken);
    } catch { /* ignore */ }
  }, []);

  useEffect(() => { void load(); }, [load]);
  useEffect(() => { void loadToken(selectedChannel); }, [loadToken, selectedChannel]);

  const deleteOffer = async (id: number) => {
    const res = await apiFetch(`/admin/campaign-offers/${id}`, { method: "DELETE" });
    if (!res.ok) { showToast("Fehler beim Löschen"); return; }
    showToast("Angebot gelöscht");
    setConfirmDelete(null);
    await load();
  };

  return (
    <div style={{ padding: "32px 40px", maxWidth: 900, margin: "0 auto" }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 28 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div style={{ background: T.accentDim, borderRadius: 10, padding: 8 }}>
            <Gift size={20} color={T.accent} />
          </div>
          <div>
            <h1 style={{ margin: 0, fontSize: 20, fontWeight: 700, color: T.text }}>Opt-in Angebote</h1>
            <p style={{ margin: 0, fontSize: 13, color: T.textDim }}>
              Konfiguriere Lead-Magneten für deine Anmeldeseiten
            </p>
          </div>
        </div>
        <div style={{ display: "flex", gap: 10 }}>
          <button onClick={() => void load()} style={{ background: T.surfaceAlt, border: `1px solid ${T.border}`, borderRadius: 8, padding: "7px 14px", cursor: "pointer", display: "flex", alignItems: "center", gap: 6, fontSize: 13, color: T.text }}>
            <RefreshCw size={14} />
          </button>
          <button onClick={() => setShowCreate(true)} style={{ background: T.accent, border: "none", borderRadius: 8, padding: "7px 16px", cursor: "pointer", display: "flex", alignItems: "center", gap: 6, fontSize: 13, color: "#fff", fontWeight: 600 }}>
            <Plus size={14} /> Neu
          </button>
        </div>
      </div>

      {/* Subscribe Link Generator */}
      <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 12, padding: "18px 20px", marginBottom: 20 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
          <Link2 size={15} color={T.accent} />
          <p style={{ margin: 0, fontSize: 13, fontWeight: 700, color: T.text }}>Anmeldelinks für dein Tenant</p>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 14 }}>
          <p style={{ margin: 0, fontSize: 12, color: T.textDim }}>Kanal:</p>
          {["whatsapp", "email", "sms", "telegram"].map(ch => (
            <button
              key={ch}
              onClick={() => setSelectedChannel(ch)}
              style={{ padding: "4px 10px", borderRadius: 6, fontSize: 11, fontWeight: 600, cursor: "pointer", border: `1px solid ${selectedChannel === ch ? T.accent : T.border}`, background: selectedChannel === ch ? T.accentDim : T.surfaceAlt, color: selectedChannel === ch ? T.accent : T.textDim }}
            >
              {ch}
            </button>
          ))}
        </div>
        {subscribeToken && (
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            <div>
              <p style={{ margin: "0 0 4px", fontSize: 11, color: T.textDim, fontWeight: 600 }}>Basis-Anmeldelink (ohne Angebot)</p>
              <CopyBtn
                text={`${typeof window !== "undefined" ? window.location.origin : ""}${subscribeToken.subscribe_path}`}
                label="Basis-Link"
              />
            </div>
            {offers.filter(o => o.is_active).map(o => (
              <div key={o.id}>
                <p style={{ margin: "0 0 4px", fontSize: 11, color: T.textDim, fontWeight: 600 }}>Angebot: {o.name}</p>
                <CopyBtn
                  text={`${typeof window !== "undefined" ? window.location.origin : ""}${subscribeToken.subscribe_path}?offer=${o.slug}`}
                  label={o.name}
                />
              </div>
            ))}
          </div>
        )}
      </div>

      {/* How it works banner */}
      <div style={{ background: T.accentDim, border: `1px solid ${T.accent}30`, borderRadius: 12, padding: "14px 18px", marginBottom: 24 }}>
        <p style={{ margin: 0, fontSize: 13, color: T.accent, fontWeight: 600, marginBottom: 4 }}>So funktioniert es</p>
        <p style={{ margin: 0, fontSize: 12, color: T.textDim, lineHeight: 1.7 }}>
          Erstelle ein Angebot (z.B. <code style={{ background: "rgba(255,255,255,0.05)", padding: "1px 5px", borderRadius: 4 }}>preisliste</code>) und hänge den URL-Parameter an deine Anmeldeseite:
          {" "}<code style={{ background: "rgba(255,255,255,0.05)", padding: "1px 5px", borderRadius: 4 }}>/subscribe/[token]?offer=preisliste</code>.
          Nach dem Double Opt-in erhält der Kontakt automatisch die konfigurierte Nachricht mit Anhang.
          Ohne <code style={{ background: "rgba(255,255,255,0.05)", padding: "1px 5px", borderRadius: 4 }}>?offer=</code> wird eine einfache Bestätigung gesendet.
        </p>
      </div>

      {toast && (
        <div style={{ background: T.accentDim, color: T.accent, border: `1px solid ${T.accent}40`, borderRadius: 8, padding: "10px 16px", marginBottom: 20, fontSize: 13, fontWeight: 600 }}>{toast}</div>
      )}
      {error && (
        <div style={{ background: "rgba(255,107,107,0.1)", color: T.danger, border: `1px solid ${T.danger}30`, borderRadius: 8, padding: "10px 16px", marginBottom: 20, fontSize: 13 }}>{error}</div>
      )}

      {/* List */}
      {loading ? (
        <div style={{ padding: 40, textAlign: "center", color: T.textDim, fontSize: 13 }}>Laden…</div>
      ) : offers.length === 0 ? (
        <div style={{ padding: 60, textAlign: "center", background: T.surface, border: `1px solid ${T.border}`, borderRadius: 12 }}>
          <Gift size={32} style={{ color: T.textDim, marginBottom: 12 }} />
          <p style={{ margin: "0 0 16px", fontSize: 14, color: T.textDim }}>Noch keine Angebote. Erstelle dein erstes Opt-in Angebot.</p>
          <button onClick={() => setShowCreate(true)} style={{ background: T.accent, border: "none", borderRadius: 8, padding: "8px 18px", cursor: "pointer", fontSize: 13, color: "#fff", fontWeight: 600 }}>
            Erstes Angebot erstellen
          </button>
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {offers.map((o) => (
            <div key={o.id} style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 12, padding: "18px 20px" }}>
              <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 12 }}>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 6 }}>
                    <p style={{ margin: 0, fontSize: 14, fontWeight: 700, color: T.text }}>{o.name}</p>
                    {!o.is_active && (
                      <span style={{ fontSize: 10, fontWeight: 700, padding: "2px 6px", borderRadius: 4, background: `${T.danger}22`, color: T.danger }}>INAKTIV</span>
                    )}
                  </div>
                  <CopyBtn text={`?offer=${o.slug}`} label="URL-Parameter" />
                  <p style={{ margin: "10px 0 0", fontSize: 12, color: T.textDim, lineHeight: 1.6 }}>
                    {o.confirmation_message.length > 120 ? o.confirmation_message.slice(0, 120) + "…" : o.confirmation_message}
                  </p>
                  {o.attachment_url && (
                    <a href={o.attachment_url} target="_blank" rel="noopener noreferrer"
                      style={{ display: "inline-flex", alignItems: "center", gap: 4, marginTop: 8, fontSize: 11, color: T.accent, textDecoration: "none" }}>
                      <ExternalLink size={11} />
                      {o.attachment_filename || "Anhang öffnen"}
                    </a>
                  )}
                </div>
                <div style={{ display: "flex", gap: 8, flexShrink: 0 }}>
                  <button onClick={() => setEditing(o)} style={{ display: "flex", alignItems: "center", gap: 5, padding: "6px 12px", borderRadius: 8, fontSize: 12, cursor: "pointer", border: `1px solid ${T.border}`, background: T.surfaceAlt, color: T.text }}>
                    <Edit3 size={12} /> Bearbeiten
                  </button>
                  {confirmDelete === o.id ? (
                    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                      <span style={{ fontSize: 12, color: T.danger, fontWeight: 600 }}>Sicher?</span>
                      <button onClick={() => void deleteOffer(o.id)} style={{ padding: "5px 10px", borderRadius: 6, fontSize: 12, fontWeight: 700, cursor: "pointer", border: "none", background: T.danger, color: "#fff" }}>Ja</button>
                      <button onClick={() => setConfirmDelete(null)} style={{ padding: "5px 10px", borderRadius: 6, fontSize: 12, cursor: "pointer", border: `1px solid ${T.border}`, background: T.surfaceAlt, color: T.text }}>Nein</button>
                    </div>
                  ) : (
                    <button onClick={() => setConfirmDelete(o.id)} style={{ display: "flex", alignItems: "center", gap: 5, padding: "6px 12px", borderRadius: 8, fontSize: 12, cursor: "pointer", border: `1px solid ${T.danger}40`, background: "rgba(255,107,107,0.08)", color: T.danger }}>
                      <Trash2 size={12} />
                    </button>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {showCreate && <OfferModal onClose={() => setShowCreate(false)} onSaved={() => void load()} />}
      {editing && <OfferModal initial={editing} onClose={() => setEditing(null)} onSaved={() => void load()} />}
    </div>
  );
}
