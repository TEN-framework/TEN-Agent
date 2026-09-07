"use client";

import React, { useEffect, useMemo, useState } from "react";
import {
  FORTUNE_CARD_ASSET_MAP,
  getFortuneCardAsset,
  useAppDispatch,
  useAppSelector,
} from "@/common";
import { hideFortuneModal } from "@/store/reducers/global";

const loadedFortuneCards = new Set<string>();

const preloadImage = (src: string): Promise<void> => {
  if (loadedFortuneCards.has(src)) {
    return Promise.resolve();
  }
  return new Promise((resolve) => {
    const img = new Image();
    img.onload = () => {
      loadedFortuneCards.add(src);
      resolve();
    };
    img.onerror = () => resolve();
    img.src = src;
  });
};

export default function FortuneModal() {
  const dispatch = useAppDispatch();
  const modal = useAppSelector((state) => state.global.fortuneModal);
  const [cardReady, setCardReady] = useState(false);
  const allCardSources = useMemo(
    () => Object.values(FORTUNE_CARD_ASSET_MAP),
    []
  );

  useEffect(() => {
    Promise.all(allCardSources.map((src) => preloadImage(src))).catch(() => {});
  }, [allCardSources]);

  const cardSrc = modal?.open ? getFortuneCardAsset(modal.imageId) : "";

  useEffect(() => {
    if (!modal?.open || !cardSrc) {
      setCardReady(false);
      return;
    }
    if (loadedFortuneCards.has(cardSrc)) {
      setCardReady(true);
      return;
    }
    setCardReady(false);
    preloadImage(cardSrc).then(() => setCardReady(true));
  }, [modal?.open, cardSrc]);

  if (!modal?.open) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-[130] flex items-center justify-center">
      <button
        type="button"
        aria-label="Close fortune modal"
        className="absolute inset-0 bg-black/65"
        onClick={() => dispatch(hideFortuneModal())}
      />
      <div className="fortune-modal-enter relative z-[131] w-[min(90vw,420px)] rounded-xl border border-[#7a5a20] bg-[#1a1208] p-4 shadow-2xl">
        <picture>
          {cardSrc.endsWith(".webp") && (
            <source srcSet={cardSrc} type="image/webp" />
          )}
          <img
            src={cardSrc}
            alt={modal.imageId}
            width={417}
            height={1383}
            loading="eager"
            decoding="async"
            fetchPriority="high"
            className={`h-auto w-full rounded-lg border border-[#8a6725] transition-opacity duration-150 ${
              cardReady ? "opacity-100" : "opacity-0"
            }`}
          />
        </picture>
        <button
          type="button"
          className="mt-4 w-full rounded-md bg-[#d8a53a] px-4 py-2 font-semibold text-[#2b1b06] hover:bg-[#e4b24c]"
          onClick={() => dispatch(hideFortuneModal())}
        >
          收下祝福
        </button>
      </div>
    </div>
  );
}
