import { loadFont } from "@remotion/google-fonts/Inter";

export const { fontFamily } = loadFont("normal", {
  weights: ["400", "500", "600", "700", "800"],
  subsets: ["latin"],
});

// "Clinical Calm" tokens from the Stitch design system (docs/design/DESIGN.md).
export const C = {
  primary: "#00685b",
  primaryContainer: "#008373",
  brand: "#0f9d8a",
  primaryFixed: "#83f6e0",
  mint: "#e8f7f4",
  navy: "#0b1b33",
  text: "#0b1c30",
  muted: "#5b6779",
  surface: "#f8f9ff",
  surfaceLow: "#eff4ff",
  surfaceContainer: "#e5eeff",
  border: "#e2e8f0",
  white: "#ffffff",
  error: "#ba1a1a",
  amber: "#f59e0b",
};

export const FPS = 30;
