"use client";

import { getStoredUser } from "@/lib/auth";
import { T } from "@/lib/tokens";
import ToolForm from "../ToolForm";

export default function NewToolPage() {
  const user = getStoredUser();
  if (user?.role !== "system_admin") {
    return <div style={{ padding: 40, color: T.danger }}>Access denied. System admin only.</div>;
  }
  return <ToolForm />;
}
