"use client";

import React from "react";
import { getEffectAsset, useAppDispatch, useAppSelector } from "@/common";
import { clearFestivalEffect } from "@/store/reducers/global";

const EFFECT_DURATION_MS = 2500;

export default function EffectOverlay() {
  const dispatch = useAppDispatch();
  const effect = useAppSelector((state) => state.global.festivalEffect);

  React.useEffect(() => {
    if (!effect?.active) {
      return;
    }

    const timer = setTimeout(() => {
      dispatch(clearFestivalEffect());
    }, EFFECT_DURATION_MS);

    return () => {
      clearTimeout(timer);
    };
  }, [dispatch, effect?.active, effect?.nonce]);

  if (!effect?.active) {
    return null;
  }

  const effectSrc = getEffectAsset(effect.name);

  return (
    <div className="pointer-events-none fixed inset-0 z-[120] flex items-center justify-center">
      <img
        key={effect.nonce}
        src={effectSrc}
        alt={effect.name}
        className="h-full w-full object-cover opacity-90 animate-in fade-in duration-200"
      />
    </div>
  );
}
