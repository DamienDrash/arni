"use client";
import { useState } from "react";
import SettingsSubnav from "@/components/settings/SettingsSubnav";
import { AIProviderManager } from "@/components/ai-config/AIProviderManager";
import { AIPromptRegistry } from "@/components/ai-config/AIPromptRegistry";
import { AIAgentRegistry } from "@/components/ai-config/AIAgentRegistry";
import { AIBudgetManager } from "@/components/ai-config/AIBudgetManager";
import { AIObservabilityDashboard } from "@/components/ai-config/AIObservabilityDashboard";
import { TenantAIConfig } from "@/components/ai-config/TenantAIConfig";
import { Card } from "@/components/ui/Card";
import { T } from "@/lib/tokens";
import { getStoredUser } from "@/lib/auth";
import {
  Cpu, FileText, Bot, Wallet, BarChart3,
} from "lucide-react";

type TabId = "providers" | "prompts" | "agents" | "budgets" | "observability";

const ADMIN_TABS: { id: TabId; label: string; icon: typeof Cpu }[] = [
  { id: "providers", label: "LLM Provider", icon: Cpu },
  { id: "prompts", label: "Prompt Registry", icon: FileText },
  { id: "agents", label: "Agent Registry", icon: Bot },
  { id: "budgets", label: "Budget & Limits", icon: Wallet },
  { id: "observability", label: "Observability", icon: BarChart3 },
];

export default function AiSettingsPage() {
  const user = getStoredUser();
  const isSystemAdmin = user?.role === "system_admin";
  const [activeTab, setActiveTab] = useState<TabId>("providers");

  if (!isSystemAdmin) {
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        <SettingsSubnav />
        <TenantAIConfig />
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <SettingsSubnav />

      {/* Tab Navigation */}
      <div
        style={{
          display: "flex",
          gap: 4,
          padding: "6px 8px",
          borderRadius: 14,
          border: `1px solid ${T.border}`,
          background: T.surface,
          flexWrap: "wrap",
        }}
      >
        {ADMIN_TABS.map((tab) => {
          const isActive = activeTab === tab.id;
          const Icon = tab.icon;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 7,
                padding: "8px 14px",
                borderRadius: 10,
                border: isActive ? `1px solid ${T.accent}50` : "1px solid transparent",
                background: isActive
                  ? `linear-gradient(135deg, ${T.accentDim}, rgba(108,92,231,0.08))`
                  : "transparent",
                color: isActive ? T.text : T.textMuted,
                fontSize: 12,
                fontWeight: isActive ? 700 : 600,
                cursor: "pointer",
                transition: "all 0.2s ease",
                position: "relative",
              }}
            >
              <Icon size={14} color={isActive ? T.accent : T.textDim} />
              {tab.label}
              {isActive && (
                <div
                  style={{
                    position: "absolute",
                    bottom: -1,
                    left: "50%",
                    transform: "translateX(-50%)",
                    width: 16,
                    height: 2,
                    borderRadius: 1,
                    background: T.accent,
                  }}
                />
              )}
            </button>
          );
        })}
      </div>

      {/* Tab Content */}
      <Card style={{ padding: 24 }}>
        {activeTab === "providers" && <AIProviderManager />}
        {activeTab === "prompts" && <AIPromptRegistry />}
        {activeTab === "agents" && <AIAgentRegistry />}
        {activeTab === "budgets" && <AIBudgetManager />}
        {activeTab === "observability" && <AIObservabilityDashboard />}
      </Card>
    </div>
  );
}
