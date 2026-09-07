export const EFFECT_ASSET_MAP: Record<string, string> = {
  gold_rain: "/festival/effects/gold-dollar.gif",
  fireworks: "/festival/effects/fireworks.svg",
};

export const FORTUNE_CARD_ASSET_MAP: Record<string, string> = {
  fortune_rich: "/festival/cards/fortune_rich.webp",
  fortune_love: "/festival/cards/fortune_love.webp",
  fortune_lazy: "/festival/cards/fortune_lazy.webp",
  fortune_body: "/festival/cards/fortune_body.webp",
  fortune_career: "/festival/cards/fortune_career.svg",
};

export const getEffectAsset = (effectName: string): string => {
  return EFFECT_ASSET_MAP[effectName] ?? EFFECT_ASSET_MAP.gold_rain;
};

const normalizeFortuneImageId = (imageId: string): string => {
  const raw = String(imageId ?? "").trim().toLowerCase();
  const withoutExt = raw.replace(/\.(webp|png|jpg|jpeg|svg)$/i, "");
  if (!withoutExt) {
    return "fortune_rich";
  }
  if (withoutExt in FORTUNE_CARD_ASSET_MAP) {
    return withoutExt;
  }
  const stripped = withoutExt.replace(/^fortune_/, "");
  return `fortune_${stripped}`;
};

export const getFortuneCardAsset = (imageId: string): string => {
  const normalized = normalizeFortuneImageId(imageId);
  return (
    FORTUNE_CARD_ASSET_MAP[normalized] ?? FORTUNE_CARD_ASSET_MAP.fortune_rich
  );
};
