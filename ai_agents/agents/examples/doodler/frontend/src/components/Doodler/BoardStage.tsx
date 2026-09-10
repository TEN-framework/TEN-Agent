"use client";

import * as React from "react";
import { AnimatePresence, motion } from "framer-motion";
import { cn } from "@/lib/utils";
import type { DoodlePhase } from "./MagicCanvasBackground";

export type CrayonSwatch = {
  id: string;
  label: string;
  stickerClass: string;
  ringClass: string;
  penBody: string;
  penTop: string;
};

export const DEFAULT_CRAYON_SWATCHES: CrayonSwatch[] = [
  {
    id: "ink",
    label: "Ink",
    stickerClass: "bg-[#111111]",
    ringClass: "ring-[#111111]",
    penBody: "#111111",
    penTop: "#3C3C3C",
  },
  {
    id: "lavender",
    label: "Lavender",
    stickerClass: "bg-[#BFA2FF]",
    ringClass: "ring-[#5C3DDE]",
    penBody: "#5C3DDE",
    penTop: "#BFA2FF",
  },
  {
    id: "mint",
    label: "Mint",
    stickerClass: "bg-[#9EE7B2]",
    ringClass: "ring-[#1C8B43]",
    penBody: "#1C8B43",
    penTop: "#9EE7B2",
  },
  {
    id: "sky",
    label: "Sky",
    stickerClass: "bg-[#9DD8FF]",
    ringClass: "ring-[#1D6FE2]",
    penBody: "#1D6FE2",
    penTop: "#9DD8FF",
  },
  {
    id: "rose",
    label: "Rose",
    stickerClass: "bg-[#FFB3C7]",
    ringClass: "ring-[#E72D6A]",
    penBody: "#E72D6A",
    penTop: "#FFB3C7",
  },
];

type DoodleStrokePoint = {
  x: number;
  y: number;
  rotate: number;
};

type DoodleStroke = {
  id: string;
  d: string;
  duration: number;
  points: DoodleStrokePoint[];
};

type TimedDoodleStroke = DoodleStroke & { delay: number };

const DOODLE_STROKES: DoodleStroke[] = [
  {
    id: "stroke-1",
    d: "M120 260 C 300 120, 420 340, 620 220 S 860 260, 920 200",
    duration: 1.2,
    points: [
      { x: 120, y: 260, rotate: -8 },
      { x: 320, y: 170, rotate: 6 },
      { x: 520, y: 260, rotate: -12 },
      { x: 720, y: 240, rotate: 10 },
      { x: 920, y: 200, rotate: -6 },
    ],
  },
  {
    id: "stroke-2",
    d: "M160 620 C 320 820, 460 520, 660 700 S 860 860, 940 640",
    duration: 1.1,
    points: [
      { x: 160, y: 620, rotate: 12 },
      { x: 340, y: 780, rotate: -6 },
      { x: 520, y: 560, rotate: 8 },
      { x: 720, y: 740, rotate: -10 },
      { x: 940, y: 640, rotate: 6 },
    ],
  },
  {
    id: "stroke-3",
    d: "M200 420 C 320 360, 420 460, 520 400 S 720 320, 820 440",
    duration: 0.95,
    points: [
      { x: 200, y: 420, rotate: -6 },
      { x: 360, y: 360, rotate: 8 },
      { x: 520, y: 420, rotate: -10 },
      { x: 700, y: 340, rotate: 12 },
      { x: 820, y: 440, rotate: -4 },
    ],
  },
  {
    id: "stroke-4",
    d: "M280 160 C 420 120, 520 200, 600 300 S 760 520, 880 480",
    duration: 1.05,
    points: [
      { x: 280, y: 160, rotate: -12 },
      { x: 440, y: 140, rotate: 6 },
      { x: 600, y: 260, rotate: -8 },
      { x: 760, y: 480, rotate: 10 },
      { x: 880, y: 480, rotate: -6 },
    ],
  },
];

const DOODLE_STROKE_GAP = 0.12;
const DOODLE_MASK_STROKE_WIDTH = 36;
const DOODLE_INK_STROKE_WIDTH = 3.6;

const TIMED_DOODLE_STROKES: TimedDoodleStroke[] = (() => {
  let offset = 0;
  return DOODLE_STROKES.map((stroke) => {
    const timed = { ...stroke, delay: offset };
    offset += stroke.duration + DOODLE_STROKE_GAP;
    return timed;
  });
})();

const DOODLE_REVEAL_DURATION = TIMED_DOODLE_STROKES.length
  ? TIMED_DOODLE_STROKES[TIMED_DOODLE_STROKES.length - 1].delay +
    TIMED_DOODLE_STROKES[TIMED_DOODLE_STROKES.length - 1].duration
  : 0;

function buildKeyframeTimes(count: number) {
  if (count <= 1) return [0];
  const times: number[] = [];
  for (let i = 0; i < count; i += 1) {
    times.push(i / (count - 1));
  }
  return times;
}

function DoodleRevealImage(props: {
  imageUrl: string;
  caption?: string;
  lineColor?: string;
  reducedMotion: boolean;
}) {
  const {
    imageUrl,
    caption,
    lineColor = "#111111",
    reducedMotion,
  } = props;
  const label = caption ?? "doodle";
  const maskId = React.useId();
  const inkFilterId = React.useId();

  const inkFilter = (
    <filter id={inkFilterId} colorInterpolationFilters="sRGB">
      <feColorMatrix
        type="matrix"
        values="
          1 0 0 0 0
          0 1 0 0 0
          0 0 1 0 0
          -0.2126 -0.7152 -0.0722 1 0
        "
        result="lineAlpha"
      />
      <feComponentTransfer in="lineAlpha" result="inkAlpha">
        <feFuncA type="gamma" amplitude="1" exponent="1.6" offset="0" />
      </feComponentTransfer>
      <feFlood floodColor={lineColor} result="inkColor" />
      <feComposite in="inkColor" in2="inkAlpha" operator="in" result="ink" />
    </filter>
  );

  if (reducedMotion) {
    return (
      <svg
        className="block h-full w-full rounded-[30px]"
        viewBox="0 0 1000 1000"
        preserveAspectRatio="xMidYMid meet"
        aria-label={label}
      >
        <title>{label}</title>
        <defs>{inkFilter}</defs>
        <image
          href={imageUrl}
          width="100%"
          height="100%"
          preserveAspectRatio="xMidYMid slice"
          filter={`url(#${inkFilterId})`}
          style={{
            opacity: 0.94,
            mixBlendMode: "multiply",
          }}
        />
      </svg>
    );
  }

  return (
    <svg
      className="block h-full w-full rounded-[30px]"
      viewBox="0 0 1000 1000"
      preserveAspectRatio="xMidYMid meet"
      aria-label={label}
    >
      <title>{label}</title>
      <defs>
        <mask id={maskId}>
          <rect width="100%" height="100%" fill="black" />
          {TIMED_DOODLE_STROKES.map((stroke) => (
            <motion.path
              key={`mask-${stroke.id}`}
              d={stroke.d}
              fill="none"
              stroke="white"
              strokeWidth={DOODLE_MASK_STROKE_WIDTH}
              strokeLinecap="round"
              strokeLinejoin="round"
              initial={{ pathLength: 0 }}
              animate={{ pathLength: 1 }}
              transition={{
                duration: stroke.duration,
                delay: stroke.delay,
                ease: "easeInOut",
              }}
            />
          ))}
          <motion.rect
            width="100%"
            height="100%"
            fill="white"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{
              duration: 0.25,
              delay: DOODLE_REVEAL_DURATION + 0.1,
              ease: "easeOut",
            }}
          />
        </mask>
        {inkFilter}
      </defs>

      <image
        href={imageUrl}
        width="100%"
        height="100%"
        preserveAspectRatio="xMidYMid slice"
        mask={`url(#${maskId})`}
        filter={`url(#${inkFilterId})`}
        style={{
          opacity: 0.94,
          mixBlendMode: "multiply",
        }}
      />

      <g pointerEvents="none">
        {TIMED_DOODLE_STROKES.map((stroke) => (
          <motion.path
            key={`ink-${stroke.id}`}
            d={stroke.d}
            fill="none"
            stroke={lineColor}
            strokeWidth={DOODLE_INK_STROKE_WIDTH}
            strokeLinecap="round"
            strokeLinejoin="round"
            initial={{ pathLength: 0, opacity: 0 }}
            animate={{ pathLength: 1, opacity: [0, 0.95, 0] }}
            transition={{
              pathLength: {
                duration: stroke.duration,
                delay: stroke.delay,
                ease: "easeInOut",
              },
              opacity: {
                duration: stroke.duration + 0.2,
                delay: stroke.delay,
                times: [0, 0.7, 1],
                ease: "easeInOut",
              },
            }}
          />
        ))}
      </g>

    </svg>
  );
}

function SurfaceTexture() {
  const patternId = React.useId();
  return (
    <svg
      aria-hidden
      className="pointer-events-none absolute inset-0 h-full w-full opacity-[0.25]"
    >
      <defs>
        <pattern
          id={patternId}
          width="18"
          height="16"
          patternUnits="userSpaceOnUse"
        >
          <circle cx="4" cy="4" r="1.15" fill="rgba(0,0,0,0.22)" />
          <circle cx="13" cy="12" r="1.15" fill="rgba(0,0,0,0.22)" />
        </pattern>
      </defs>
      <rect width="100%" height="100%" fill={`url(#${patternId})`} />
    </svg>
  );
}

function Stylus(props: { bodyColor?: string; topColor?: string }) {
  const { bodyColor = "#F97316", topColor = "#FB923C" } = props;
  return (
    <svg width="54" height="280" viewBox="0 0 54 280" fill="none" aria-hidden>
      <rect
        x="12"
        y="14"
        width="30"
        height="220"
        rx="12"
        fill={bodyColor}
        stroke="rgba(0,0,0,0.16)"
      />
      <rect x="12" y="14" width="30" height="26" rx="12" fill={topColor} />
      <rect x="12" y="62" width="30" height="10" rx="4" fill="#1F1F1F" />
      <rect x="12" y="82" width="30" height="10" rx="4" fill="#1F1F1F" />
      <ellipse cx="27" cy="132" rx="8" ry="18" fill="#1F1F1F" />
      <rect x="12" y="192" width="30" height="10" rx="4" fill="#1F1F1F" />
      <path
        d="M18 32c4-6 14-6 18 0"
        stroke="rgba(255,255,255,0.5)"
        strokeWidth="4"
        strokeLinecap="round"
      />
    </svg>
  );
}

function StrokeStylusAnimator(props: {
  active: boolean;
  reducedMotion: boolean;
  bodyColor?: string;
  topColor?: string;
}) {
  const { active, reducedMotion, bodyColor, topColor } = props;
  if (!active || reducedMotion) return null;

  const scale = 0.32;
  const offsetX = -27 * scale;
  const offsetY = -250 * scale;

  return (
    <svg
      aria-hidden
      className="absolute inset-0 h-full w-full"
      viewBox="0 0 1000 1000"
      preserveAspectRatio="xMidYMid slice"
    >
      {TIMED_DOODLE_STROKES.map((stroke) => {
        const times = buildKeyframeTimes(stroke.points.length);
        return (
          <motion.g
            key={`stylus-${stroke.id}`}
            initial={{
              x: stroke.points[0]?.x ?? 0,
              y: stroke.points[0]?.y ?? 0,
              rotate: stroke.points[0]?.rotate ?? 0,
              opacity: 0,
            }}
            animate={{
              x: stroke.points.map((p) => p.x),
              y: stroke.points.map((p) => p.y),
              rotate: stroke.points.map((p) => p.rotate),
              opacity: [0, 1, 1, 0],
            }}
            transition={{
              x: {
                duration: stroke.duration,
                delay: stroke.delay,
                ease: "easeInOut",
                times,
              },
              y: {
                duration: stroke.duration,
                delay: stroke.delay,
                ease: "easeInOut",
                times,
              },
              rotate: {
                duration: stroke.duration,
                delay: stroke.delay,
                ease: "easeInOut",
                times,
              },
              opacity: {
                duration: stroke.duration,
                delay: stroke.delay,
                times: [0, 0.12, 0.86, 1],
                ease: "easeInOut",
              },
            }}
            style={
              {
                transformBox: "fill-box",
                transformOrigin: "center",
              } as React.CSSProperties
            }
          >
            <g transform={`translate(${offsetX} ${offsetY}) scale(${scale})`}>
              <Stylus bodyColor={bodyColor} topColor={topColor} />
            </g>
          </motion.g>
        );
      })}
    </svg>
  );
}

function ToyStylusAnimator(props: {
  phase?: DoodlePhase;
  reducedMotion: boolean;
  bodyColor?: string;
  topColor?: string;
}) {
  const { phase, reducedMotion, bodyColor, topColor } = props;

  if (reducedMotion) return null;

  const active = Boolean(phase && phase !== "idle");
  const looping = phase === "queued" || phase === "sketch" || phase === "color";
  const anim = React.useMemo(() => {
    if (!looping) {
      return {
        left: "82%",
        top: "62%",
        rotate: 18,
      };
    }
    return {
      left: ["86%", "44%", "70%", "52%", "78%"],
      top: ["56%", "38%", "68%", "54%", "34%"],
      rotate: [18, 6, 24, 10, 22],
    };
  }, [looping]);

  return (
    <AnimatePresence>
      {active ? (
        <motion.div
          key="toy-stylus"
          className="absolute left-0 top-0 z-30"
          initial={{ opacity: 0, scale: 0.96, left: "112%", top: "74%" }}
          animate={{
            opacity: 1,
            scale: 1,
            ...anim,
          }}
          exit={{ opacity: 0, scale: 0.98, left: "118%", top: "70%" }}
          transition={{
            duration: looping ? 1.9 : 0.55,
            ease: "easeInOut",
            repeat: looping ? Infinity : 0,
          }}
          style={{
            width: 52,
            transform: "translate(-50%, -22%)",
            filter: "drop-shadow(0 18px 22px rgba(0,0,0,0.18))",
          }}
        >
          <Stylus bodyColor={bodyColor} topColor={topColor} />
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}

export default function BoardStage(props: {
  imageUrl?: string;
  caption?: string;
  className?: string;
  overlay?: React.ReactNode;
  phase?: DoodlePhase;
  reducedMotion?: boolean;
  swatches?: CrayonSwatch[];
  activeSwatchId?: string;
  onSwatchSelect?: (id: string) => void;
  penBodyColor?: string;
  penTopColor?: string;
  onErase?: () => void;
  eraseDisabled?: boolean;
}) {
  const {
    imageUrl,
    caption,
    className,
    overlay,
    phase,
    reducedMotion = false,
    swatches = DEFAULT_CRAYON_SWATCHES,
    activeSwatchId,
    onSwatchSelect,
    penBodyColor,
    penTopColor,
    onErase,
    eraseDisabled = false,
  } = props;
  const isGenerating =
    phase === "queued" || phase === "sketch" || phase === "color";
  const showPlaceholder = isGenerating && !imageUrl;
  const drawingActive = showPlaceholder;
  const resolvedActiveId = activeSwatchId ?? swatches[0]?.id;
  const activeSwatch =
    swatches.find((swatch) => swatch.id === resolvedActiveId) ?? swatches[0];
  const resolvedPenBody = penBodyColor ?? activeSwatch?.penBody ?? "#F97316";
  const resolvedPenTop = penTopColor ?? activeSwatch?.penTop ?? "#FB923C";
  const stylusPhase = imageUrl || !isGenerating ? "idle" : (phase ?? "idle");
  const canErase = Boolean(onErase) && !eraseDisabled;
  const [eraseProgress, setEraseProgress] = React.useState(0);
  const eraseTriggeredRef = React.useRef(false);
  const eraseTimerRef = React.useRef<number | null>(null);

  const triggerErase = React.useCallback(() => {
    if (!onErase || eraseTriggeredRef.current) return;
    eraseTriggeredRef.current = true;
    onErase();
    if (eraseTimerRef.current !== null) {
      window.clearTimeout(eraseTimerRef.current);
    }
    eraseTimerRef.current = window.setTimeout(() => {
      eraseTriggeredRef.current = false;
      setEraseProgress(0);
      eraseTimerRef.current = null;
    }, 420);
  }, [onErase]);

  const handleEraseChange = React.useCallback(
    (event: React.ChangeEvent<HTMLInputElement>) => {
      if (!canErase) return;
      const next = Number(event.target.value);
      setEraseProgress(next);
      if (next >= 96) {
        triggerErase();
      }
    },
    [canErase, triggerErase]
  );

  const resetErase = React.useCallback(() => {
    if (eraseTriggeredRef.current) return;
    setEraseProgress(0);
  }, []);

  React.useEffect(() => {
    if (!canErase) {
      setEraseProgress(0);
      eraseTriggeredRef.current = false;
    }
  }, [canErase]);

  React.useEffect(() => {
    return () => {
      if (eraseTimerRef.current !== null) {
        window.clearTimeout(eraseTimerRef.current);
      }
    };
  }, []);

  return (
    <div className={cn("relative w-full", className)}>
      <div className="toy-board-frame">
        <div className="grid grid-cols-[56px_minmax(0,1fr)_56px] gap-3 sm:grid-cols-[72px_minmax(0,1fr)_72px] sm:gap-4">
          <div className="flex flex-col items-center justify-center gap-3 sm:gap-4">
            {swatches.map((swatch, idx) => {
              const isActive = swatch.id === resolvedActiveId;
              return (
              <button
                key={swatch.id || idx}
                type="button"
                className={cn(
                  "toy-board-sticker",
                  swatch.stickerClass,
                  "ring-offset-2 ring-offset-transparent",
                  swatch.ringClass,
                  isActive ? "ring-4 scale-105" : "ring-2",
                  onSwatchSelect ? "cursor-pointer" : "cursor-default"
                )}
                aria-label={`Crayon color ${swatch.label}`}
                aria-pressed={onSwatchSelect ? isActive : undefined}
                onClick={() => onSwatchSelect?.(swatch.id)}
              >
                <span className="toy-board-sticker__shine" aria-hidden />
              </button>
            );
            })}
          </div>

          <div className="toy-board-bezel">
            <div className="relative overflow-hidden toy-board-screen min-h-[50vh] sm:min-h-[58vh]">
              <SurfaceTexture />
              <div className="pointer-events-none absolute inset-0 doodle-board-grid opacity-20" />

              <div
                className={cn(
                  "absolute inset-0 flex items-center justify-center",
                  showPlaceholder && "flex-col gap-3 text-center"
                )}
              >
                <AnimatePresence mode="wait">
                  {imageUrl ? (
                    <motion.div
                      key={imageUrl}
                      className="relative h-full w-full"
                      initial={{ opacity: 0, y: 10, rotate: -0.6, scale: 0.985 }}
                      animate={{ opacity: 1, y: 0, rotate: 0, scale: 1 }}
                      exit={{ opacity: 0, y: 10, scale: 0.98 }}
                      transition={{ duration: 0.32, ease: "easeOut" }}
                    >
                      <div className="doodle-image-frame relative h-full w-full">
                        <StrokeStylusAnimator
                          active
                          reducedMotion={reducedMotion}
                          bodyColor={resolvedPenBody}
                          topColor={resolvedPenTop}
                        />
                        <DoodleRevealImage
                          imageUrl={imageUrl}
                          caption={caption}
                          lineColor={resolvedPenBody}
                          reducedMotion={reducedMotion}
                        />
                      </div>
                    </motion.div>
                  ) : null}
                </AnimatePresence>
                {showPlaceholder ? (
                  <>
                    <div
                      className="h-2 w-40 rounded-full"
                      style={{
                        background: `linear-gradient(90deg, ${resolvedPenBody} 0%, rgba(255,255,255,0.6) 100%)`,
                      }}
                      aria-hidden
                    />
                    <div className="text-sm font-semibold text-neutral-700">
                      Sketching your doodle…
                    </div>
                    <div className="text-xs text-neutral-500">
                      The pen is warming up with your color.
                    </div>
                  </>
                ) : null}
              </div>

              <div className="pointer-events-none absolute inset-0">
                {overlay}
                <ToyStylusAnimator
                  phase={stylusPhase}
                  reducedMotion={reducedMotion}
                  bodyColor={resolvedPenBody}
                  topColor={resolvedPenTop}
                />
              </div>
            </div>
          </div>

          <div className="toy-board-pen-slot">
            <div className="toy-board-pen-slot__well">
              <div className="toy-board-pen-slot__cord" aria-hidden />
              <div
                className={cn(
                  "toy-board-pen-slot__stylus transition-opacity duration-200",
                  drawingActive ? "opacity-0" : "opacity-100"
                )}
              >
                <Stylus bodyColor={resolvedPenBody} topColor={resolvedPenTop} />
              </div>
            </div>
          </div>
        </div>

        <div className="toy-board-bottom">
          <div className="toy-board-bottom__rail" aria-hidden />
          <span className="toy-board-bottom__label" aria-hidden>
            Erase
          </span>
          <input
            type="range"
            min={0}
            max={100}
            step={1}
            value={canErase ? eraseProgress : 0}
            onChange={handleEraseChange}
            onPointerUp={resetErase}
            onPointerCancel={resetErase}
            onMouseUp={resetErase}
            onTouchEnd={resetErase}
            onBlur={resetErase}
            disabled={!canErase}
            className="toy-board-erase__slider"
            aria-label="Slide to erase"
          />
        </div>
      </div>
    </div>
  );
}
