"use client";

import SettingsSubnav from "@/components/settings/SettingsSubnav";
import { PlatformAiManager } from "@/components/settings/PlatformAiManager";
import { Card } from "@/components/ui/Card";

export default function AiSettingsPage() {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <SettingsSubnav />
      <Card style={{ padding: 24 }}>
        <PlatformAiManager />
      </Card>
    </div>
  );
}
