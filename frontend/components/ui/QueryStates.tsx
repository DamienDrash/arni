"use client";

import { Loader2, AlertTriangle, InboxIcon } from "lucide-react";

// ── Loading ───────────────────────────────────────────────────────────────────

interface LoadingSpinnerProps {
    label?: string;
    size?: "sm" | "md" | "lg";
}

export function LoadingSpinner({ label = "Laden…", size = "md" }: LoadingSpinnerProps) {
    const sizeClass = size === "sm" ? "h-4 w-4" : size === "lg" ? "h-10 w-10" : "h-6 w-6";
    return (
        <div className="flex flex-col items-center justify-center gap-3 py-12 text-zinc-400">
            <Loader2 className={`${sizeClass} animate-spin`} />
            <span className="text-sm">{label}</span>
        </div>
    );
}

// ── Error ─────────────────────────────────────────────────────────────────────

interface ErrorCardProps {
    message?: string;
    onRetry?: () => void;
}

export function ErrorCard({ message = "Daten konnten nicht geladen werden.", onRetry }: ErrorCardProps) {
    return (
        <div className="flex flex-col items-center justify-center gap-4 rounded-xl border border-red-500/20 bg-red-500/5 p-8 text-center">
            <AlertTriangle className="h-8 w-8 text-red-400" />
            <p className="text-sm text-red-300">{message}</p>
            {onRetry && (
                <button
                    onClick={onRetry}
                    className="rounded-lg bg-red-500/10 px-4 py-2 text-sm text-red-300 hover:bg-red-500/20 transition-colors"
                >
                    Erneut versuchen
                </button>
            )}
        </div>
    );
}

// ── Empty ─────────────────────────────────────────────────────────────────────

interface EmptyStateProps {
    title?: string;
    description?: string;
    icon?: React.ReactNode;
}

export function EmptyState({
    title = "Keine Daten",
    description = "Es wurden keine Einträge gefunden.",
    icon,
}: EmptyStateProps) {
    return (
        <div className="flex flex-col items-center justify-center gap-3 py-16 text-center text-zinc-500">
            {icon ?? <InboxIcon className="h-10 w-10 text-zinc-600" />}
            <p className="text-sm font-medium text-zinc-300">{title}</p>
            <p className="max-w-xs text-xs">{description}</p>
        </div>
    );
}
