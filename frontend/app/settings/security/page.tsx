"use client";

import dynamic from "next/dynamic";
const SecuritySettingsClient = dynamic(() => import("./SecuritySettingsClient"), { ssr: false });

export default function SecuritySettingsPage() {
  return <SecuritySettingsClient />;
}
