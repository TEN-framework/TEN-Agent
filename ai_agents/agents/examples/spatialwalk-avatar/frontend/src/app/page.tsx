"use client";

import dynamic from "next/dynamic";
import React from "react";
import Avatar from "@/components/Agent/AvatarSpatialwalk";
import AuthInitializer from "@/components/authInitializer";
import EffectOverlay from "@/components/Festival/EffectOverlay";
import FortuneModal from "@/components/Festival/FortuneModal";

const DynamicRTCCard = dynamic(() => import("@/components/Dynamic/RTCCard"), {
  ssr: false,
});

export default function Home() {
  React.useEffect(() => {
    const warmupImages = [
      "/festival/ui/caishen-bg.webp",
      "/festival/cards/fortune_rich.webp",
      "/festival/cards/fortune_love.webp",
      "/festival/cards/fortune_lazy.webp",
      "/festival/cards/fortune_body.webp",
    ];
    for (const src of warmupImages) {
      const img = new Image();
      img.src = src;
      img.decoding = "async";
      void img.decode().catch(() => {});
    }
  }, []);

  return (
    <AuthInitializer>
      <div
        className="relative h-screen w-screen overflow-hidden bg-[#181a1d] bg-cover bg-center bg-no-repeat"
        style={{ backgroundImage: "url('/festival/ui/caishen-bg.webp')" }}
      >
        <div className="pointer-events-none absolute inset-0 z-0 bg-black/35" />
        <EffectOverlay />
        <FortuneModal />
        {/* Keep RTC session lifecycle running, but hide its panel UI. */}
        <DynamicRTCCard className="hidden" />
        <Avatar />
      </div>
    </AuthInitializer>
  );
}
