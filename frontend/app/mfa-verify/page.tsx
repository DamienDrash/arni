"use client";

import dynamic from "next/dynamic";
const MfaVerifyClient = dynamic(() => import("./MfaVerifyClient"), { ssr: false });

export default function MfaVerifyPage() {
  return <MfaVerifyClient />;
}
