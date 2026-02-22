"use client";

import { useEffect } from "react";
import { T } from "@/lib/tokens";

export default function GlobalError({
    error,
    reset,
}: {
    error: Error & { digest?: string };
    reset: () => void;
}) {
    useEffect(() => {
        console.error(error);
    }, [error]);

    return (
        <html>
            <body className="antialiased font-sans" style={{ background: T.bg, color: T.text }}>
                <div className="flex flex-col items-center justify-center min-h-screen p-4">
                    <div
                        className="space-y-4"
                        style={{
                            width: "min(620px, 100%)",
                            padding: 26,
                            borderRadius: 16,
                            border: `1px solid ${T.border}`,
                            background: T.surface,
                            boxShadow: "0 26px 60px rgba(0,0,0,0.45)",
                        }}
                    >
                        <div style={{ fontSize: 11, color: T.textDim, textTransform: "uppercase", letterSpacing: "0.11em", fontWeight: 700 }}>
                            Incident
                        </div>
                        <h2 className="text-2xl font-bold" style={{ color: T.text, margin: 0 }}>Unerwarteter Systemfehler</h2>
                        <p style={{ color: T.textMuted, margin: 0 }}>
                            Die Ansicht konnte nicht korrekt geladen werden. Bitte erneut versuchen oder zur letzten stabilen Seite zurückkehren.
                        </p>
                        {error.digest && (
                            <div
                                style={{
                                    border: `1px solid ${T.border}`,
                                    borderRadius: 10,
                                    background: T.surfaceAlt,
                                    padding: "9px 10px",
                                    fontSize: 12,
                                    color: T.textDim,
                                    fontFamily: "var(--font-mono), monospace",
                                }}
                            >
                                Incident-ID: {error.digest}
                            </div>
                        )}
                        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                            <button
                                type="button"
                                onClick={() => reset()}
                                className="px-4 py-2 rounded transition"
                                style={{ background: T.accent, color: "#061018", fontWeight: 700 }}
                            >
                                Erneut versuchen
                            </button>
                            <button
                                type="button"
                                onClick={() => window.location.assign("/")}
                                className="px-4 py-2 rounded transition"
                                style={{ background: T.surfaceAlt, border: `1px solid ${T.border}`, color: T.text, fontWeight: 600 }}
                            >
                                Zum Dashboard
                            </button>
                        </div>
                    </div>
                </div>
            </body>
        </html>
    );
}
