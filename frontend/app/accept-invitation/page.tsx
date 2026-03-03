"use client";

import dynamic from "next/dynamic";
const AcceptInvitationClient = dynamic(() => import("./AcceptInvitationClient"), { ssr: false });

export default function AcceptInvitationPage() {
  return <AcceptInvitationClient />;
}
