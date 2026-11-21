"use client";

import { Loader2 } from "lucide-react";
import { useEffect, useState } from "react";

/** Render's free plan sleeps when idle: tell people why the first load is slow. */
export function WakingBanner({ ready }: { ready: boolean }) {
  const [slow, setSlow] = useState(false);
  useEffect(() => {
    if (ready) return;
    const t = setTimeout(() => setSlow(true), 2500);
    return () => clearTimeout(t);
  }, [ready]);
  if (ready || !slow) return null;
  return (
    <div
      role="status"
      className="fixed inset-x-0 top-0 z-50 flex items-center justify-center gap-2 bg-navy px-4 py-2 text-sm text-white"
    >
      <Loader2 className="size-4 animate-spin" />
      Waking up the demo server… free hosting sleeps when idle, this takes up to a minute.
    </div>
  );
}
