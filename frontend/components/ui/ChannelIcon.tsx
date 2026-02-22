"use client";

import { T } from "@/lib/tokens";

export type Channel = "whatsapp" | "telegram" | "email" | "phone";

interface ChannelIconProps {
  channel: Channel;
  size?: number;
}

const channelMap: Record<Channel, { bg: string; color: string; label: string }> = {
  whatsapp: { bg: "rgba(37,211,102,0.15)",  color: T.whatsapp, label: "WA" },
  telegram: { bg: "rgba(0,136,204,0.15)",   color: T.telegram, label: "TG" },
  email:    { bg: "rgba(234,67,53,0.15)",   color: T.email,    label: "EM" },
  phone:    { bg: "rgba(162,155,254,0.15)", color: T.phone,    label: "PH" },
};

export function ChannelIcon({ channel, size = 16 }: ChannelIconProps) {
  const c = channelMap[channel] ?? channelMap.whatsapp;
  return (
    <div
      style={{
        width: size + 10,
        height: size + 10,
        borderRadius: 6,
        background: c.bg,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        fontSize: size * 0.6,
        fontWeight: 700,
        color: c.color,
        letterSpacing: "0.05em",
      }}
    >
      {c.label}
    </div>
  );
}
