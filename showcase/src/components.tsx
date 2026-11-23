import React from "react";
import { AbsoluteFill, Easing, Img, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig } from "remotion";

import { C, fontFamily } from "./theme";

export const ease = Easing.bezier(0.16, 1, 0.3, 1);

export function useEnter(delay = 0, durationInFrames = 24) {
  const frame = useCurrentFrame();
  return interpolate(frame - delay, [0, durationInFrames], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: ease,
  });
}

export function useSpring(delay = 0, damping = 200) {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  return spring({ frame: frame - delay, fps, config: { damping } });
}

/** Soft gradient backdrop used behind every scene. */
export function Backdrop({ dark = false }: { dark?: boolean }) {
  const frame = useCurrentFrame();
  const drift = Math.sin(frame / 90) * 40;
  return (
    <AbsoluteFill
      style={{
        background: dark
          ? `radial-gradient(1200px 700px at ${30 + drift / 10}% 20%, #0f5f55 0%, ${C.navy} 60%)`
          : `radial-gradient(1100px 650px at ${20 + drift / 12}% 10%, ${C.mint} 0%, ${C.surface} 55%), ${C.surface}`,
      }}
    >
      <AbsoluteFill
        style={{
          backgroundImage: `radial-gradient(${dark ? "rgba(255,255,255,0.06)" : "rgba(11,27,51,0.05)"} 1.2px, transparent 1.2px)`,
          backgroundSize: "28px 28px",
          opacity: 0.8,
        }}
      />
    </AbsoluteFill>
  );
}

export function BrandMark({ size = 72 }: { size?: number }) {
  return (
    <div
      style={{
        width: size,
        height: size,
        borderRadius: size * 0.28,
        background: `linear-gradient(180deg, ${C.brand}, ${C.primary})`,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        boxShadow: "0 18px 40px -14px rgba(0,104,91,0.8)",
      }}
    >
      <svg viewBox="0 0 24 24" width={size * 0.56} height={size * 0.56} fill="none" stroke="white" strokeWidth={2.2} strokeLinecap="round">
        <path d="M4 10v4M8 7v10M12 4v16M16 8v8M20 11v2" />
      </svg>
    </div>
  );
}

/** Desktop browser window around a real screenshot. */
export function BrowserFrame({
  src,
  url,
  width = 1500,
  crop,
  style,
}: {
  src: string;
  url: string;
  width?: number;
  crop?: { top?: number; height?: number };
  style?: React.CSSProperties;
}) {
  const imgHeight = (width * 1800) / 2880;
  const visible = crop?.height ?? imgHeight;
  return (
    <div
      style={{
        width,
        borderRadius: 18,
        overflow: "hidden",
        background: C.white,
        boxShadow: "0 60px 120px -40px rgba(11,27,51,0.45), 0 0 0 1px rgba(11,27,51,0.06)",
        ...style,
      }}
    >
      <div style={{ height: 44, background: "#f1f4f9", display: "flex", alignItems: "center", gap: 8, padding: "0 18px", borderBottom: `1px solid ${C.border}` }}>
        {["#ff5f57", "#febc2e", "#28c840"].map((c) => (
          <span key={c} style={{ width: 12, height: 12, borderRadius: 6, background: c }} />
        ))}
        <div
          style={{
            marginLeft: 18,
            flex: 1,
            maxWidth: 520,
            height: 26,
            borderRadius: 8,
            background: C.white,
            border: `1px solid ${C.border}`,
            display: "flex",
            alignItems: "center",
            padding: "0 12px",
            fontFamily,
            fontSize: 14,
            color: C.muted,
          }}
        >
          🔒 {url}
        </div>
      </div>
      <div style={{ height: visible, overflow: "hidden", position: "relative" }}>
        <Img src={staticFile(src)} style={{ width, position: "absolute", top: -(crop?.top ?? 0) }} />
      </div>
    </div>
  );
}

export function PhoneFrame({ src, height = 860 }: { src: string; height?: number }) {
  const width = (height * 1170) / 2532;
  return (
    <div
      style={{
        width: width + 28,
        height: height + 28,
        borderRadius: 64,
        background: "#0b1220",
        padding: 14,
        boxShadow: "0 60px 120px -40px rgba(11,27,51,0.6)",
      }}
    >
      <div style={{ width, height, borderRadius: 52, overflow: "hidden", position: "relative" }}>
        <Img src={staticFile(src)} style={{ width, height }} />
        <div style={{ position: "absolute", top: 12, left: "50%", marginLeft: -60, width: 120, height: 34, borderRadius: 20, background: "#0b1220" }} />
      </div>
    </div>
  );
}

/** Scene title: small caps eyebrow + big headline, slides up. */
export function Title({
  eyebrow,
  title,
  sub,
  dark = false,
  align = "left",
  delay = 0,
  size = 64,
}: {
  eyebrow?: string;
  title: React.ReactNode;
  sub?: React.ReactNode;
  dark?: boolean;
  align?: "left" | "center";
  delay?: number;
  size?: number;
}) {
  const a = useEnter(delay, 26);
  const b = useEnter(delay + 8, 26);
  return (
    <div style={{ fontFamily, textAlign: align, display: "flex", flexDirection: "column", gap: 14, alignItems: align === "center" ? "center" : "flex-start" }}>
      {eyebrow ? (
        <div
          style={{
            opacity: a,
            transform: `translateY(${(1 - a) * 16}px)`,
            fontSize: 20,
            fontWeight: 700,
            letterSpacing: "0.12em",
            textTransform: "uppercase",
            color: dark ? C.primaryFixed : C.primary,
          }}
        >
          {eyebrow}
        </div>
      ) : null}
      <div
        style={{
          opacity: a,
          transform: `translateY(${(1 - a) * 30}px)`,
          fontSize: size,
          lineHeight: 1.06,
          fontWeight: 800,
          letterSpacing: "-0.03em",
          color: dark ? C.white : C.text,
        }}
      >
        {title}
      </div>
      {sub ? (
        <div style={{ opacity: b, transform: `translateY(${(1 - b) * 20}px)`, fontSize: 28, lineHeight: 1.4, color: dark ? "rgba(255,255,255,0.75)" : C.muted, maxWidth: 760 }}>
          {sub}
        </div>
      ) : null}
    </div>
  );
}

/** Highlight ring + label pointing at part of a screenshot. */
export function Callout({
  x,
  y,
  w,
  h,
  label,
  delay = 0,
  side = "right",
}: {
  x: number;
  y: number;
  w: number;
  h: number;
  label: string;
  delay?: number;
  side?: "right" | "left" | "top" | "bottom";
}) {
  const p = useSpring(delay, 18);
  const lp = useEnter(delay + 6, 20);
  const labelPos: React.CSSProperties =
    side === "right"
      ? { left: x + w + 18, top: y + h / 2 - 26 }
      : side === "left"
        ? { right: 1920 - x + 18, top: y + h / 2 - 26 }
        : side === "top"
          ? { left: x, top: y - 70 }
          : { left: x, top: y + h + 16 };
  return (
    <>
      <div
        style={{
          position: "absolute",
          left: x,
          top: y,
          width: w,
          height: h,
          borderRadius: 18,
          border: `4px solid ${C.brand}`,
          boxShadow: "0 0 0 8px rgba(15,157,138,0.18)",
          transform: `scale(${0.9 + 0.1 * p})`,
          opacity: Math.min(1, p * 1.4),
        }}
      />
      <div
        style={{
          position: "absolute",
          ...labelPos,
          opacity: lp,
          transform: `translateY(${(1 - lp) * 10}px)`,
          background: C.navy,
          color: C.white,
          fontFamily,
          fontWeight: 600,
          fontSize: 24,
          padding: "12px 18px",
          borderRadius: 14,
          whiteSpace: "nowrap",
          boxShadow: "0 18px 40px -12px rgba(11,27,51,0.5)",
        }}
      >
        {label}
      </div>
    </>
  );
}

export function Pill({ children, bg = C.primaryFixed, color = "#00201b", style }: { children: React.ReactNode; bg?: string; color?: string; style?: React.CSSProperties }) {
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 8, background: bg, color, borderRadius: 999, padding: "6px 14px", fontFamily, fontWeight: 600, fontSize: 18, ...style }}>
      {children}
    </span>
  );
}
