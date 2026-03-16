"use client";

import { useParams } from "next/navigation";
import { getStoredUser } from "@/lib/auth";
import { T } from "@/lib/tokens";
import ToolForm from "../../ToolForm";

export default function EditToolPage() {
  const params = useParams();
  const user = getStoredUser();
  const toolId = params?.id as string;

  if (user?.role !== "system_admin") {
    return <div style={{ padding: 40, color: T.danger }}>Access denied. System admin only.</div>;
  }
  return <ToolForm toolId={toolId} />;
}
