"use client";
import { useEffect } from "react";

export default function ContactsError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("Contacts page error:", error);
  }, [error]);

  return (
    <div style={{ padding: 40, color: "#fff", background: "#0a0e14" }}>
      <h2>Kontakte-Fehler</h2>
      <pre style={{ color: "#ff6b6b", whiteSpace: "pre-wrap", fontSize: 12, maxWidth: 800 }}>
        {error.message}
        {"\n\n"}
        {error.stack}
      </pre>
      <button onClick={reset} style={{ marginTop: 20, padding: "8px 16px", background: "#00d4ff", color: "#000", border: "none", borderRadius: 8, cursor: "pointer" }}>
        Erneut versuchen
      </button>
    </div>
  );
}
