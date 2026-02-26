"use client";

import SettingsSubnav from "@/components/settings/SettingsSubnav";
import { PlatformAiManager } from "@/components/settings/PlatformAiManager";
import { TenantLLMManager } from "@/components/settings/TenantLLMManager";
import { Card } from "@/components/ui/Card";
import { getStoredUser } from "@/lib/auth";

export default function AiSettingsPage() {
  const user = getStoredUser();
  const isSystemAdmin = user?.role === "system_admin";

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <SettingsSubnav />
      {isSystemAdmin ? (
        <Card style={{ padding: 24 }}>
          <PlatformAiManager />
        </Card>
      ) : (
        <TenantLLMManager />
      )}
    </div>
  );
}
