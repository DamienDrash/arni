"use client";

import { useEffect, useState } from "react";
import { marked } from "marked";
import TurndownService from "turndown";
import { Bot, Save } from "lucide-react";

import TiptapEditor from "@/components/TiptapEditor";
import { Card } from "@/components/ui/Card";
import { T } from "@/lib/tokens";
import { apiFetch } from "@/lib/api";

const turndownService = new TurndownService({ headingStyle: "atx", codeBlockStyle: "fenced" });

const AGENTS = [
  { id: "ops", name: "Ops Agent" },
  { id: "sales", name: "Sales Agent" },
  { id: "medic", name: "Medic Agent" },
  { id: "persona", name: "Persona (Smalltalk)" },
  { id: "router", name: "Router (Intent)" },
];

export default function SystemPromptPage() {
  const [contentHtml, setContentHtml] = useState("");
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const [promptType, setPromptType] = useState<string>("ops");
  const [changeReason, setChangeReason] = useState("");
  const [loadedMtime, setLoadedMtime] = useState<number | null>(null);

  useEffect(() => {
    const endpoint =
      promptType === "member_memory"
        ? "/admin/prompts/member-memory-instructions"
        : `/admin/prompts/${promptType}/system`;
    apiFetch(endpoint)
      .then(async (res) => {
        if (res.status === 403) {
          setError("Zugriff verweigert. Prompt-Management ist nur für System-Admin verfügbar.");
          return;
        }
        if (!res.ok) throw new Error(String(res.status));
        const data = await res.json();
        setContentHtml(await marked.parse(data.content || ""));
        setLoadedMtime(typeof data.mtime === "number" ? data.mtime : null);
        setStatus("Geladen");
      })
      .catch((e) => setError(`Prompt konnte nicht geladen werden (${e?.message || "unknown"}).`));
  }, [promptType]);

  async function save() {
    if (!contentHtml) return;
    const reason = changeReason.trim();
    if (reason.length < 8) {
      setError("Bitte begründe die Änderung (mind. 8 Zeichen).");
      return;
    }
    setStatus("Speichere…");
    setError("");
    const markdown = turndownService.turndown(contentHtml || "");
    const endpoint =
      promptType === "member_memory"
        ? "/admin/prompts/member-memory-instructions"
        : `/admin/prompts/${promptType}/system`;
    const res = await apiFetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content: markdown, base_mtime: loadedMtime, reason }),
    });
    if (!res.ok) {
      if (res.status === 409) {
        setStatus("Konflikt erkannt");
        setError("Prompt wurde zwischenzeitlich geändert. Bitte neu laden.");
        return;
      }
      setStatus("");
      setError(`Speichern fehlgeschlagen (${res.status}).`);
      return;
    }
    const body = (await res.json().catch(() => ({}))) as { mtime?: number };
    if (typeof body.mtime === "number") setLoadedMtime(body.mtime);
    setStatus("Gespeichert");
  }

  return (
    <Card style={{ padding: 0, display: "flex", flexDirection: "column", minHeight: "calc(100svh - 12rem)" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "12px 14px", borderBottom: `1px solid ${T.border}` }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, color: T.text }}>
          <Bot size={16} />
          <strong>{promptType === "member_memory" ? "member-memory-instructions.md" : `${promptType}/system.j2`}</strong>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <input
            value={changeReason}
            onChange={(e) => setChangeReason(e.target.value)}
            placeholder="Änderungsgrund (mind. 8 Zeichen)"
            style={{ width: 260, borderRadius: 8, border: `1px solid ${T.border}`, background: T.surfaceAlt, color: T.text, fontSize: 12, padding: "6px 8px" }}
          />
          <select
            value={promptType}
            onChange={(e) => setPromptType(e.target.value)}
            style={{
              borderRadius: 8,
              border: `1px solid ${T.border}`,
              background: T.surfaceAlt,
              color: T.text,
              fontSize: 12,
              padding: "6px 8px",
            }}
          >
            {AGENTS.map(a => <option key={a.id} value={a.id}>{a.name}</option>)}
            <option value="member_memory">Member Memory Prompt</option>
          </select>
          <span style={{ color: T.textDim, fontSize: 12 }}>{status}</span>
          <button onClick={save} style={{ border: "none", borderRadius: 8, background: T.accent, color: "#061018", fontWeight: 700, padding: "7px 10px", cursor: "pointer", display: "flex", alignItems: "center", gap: 6 }}>
            <Save size={13} /> Speichern
          </button>
        </div>
      </div>
      <div style={{ padding: 14, flex: 1 }}>
        {error ? <div style={{ color: T.danger, fontSize: 12 }}>{error}</div> : <TiptapEditor content={contentHtml} onChange={setContentHtml} />}
      </div>
    </Card>
  );
}
