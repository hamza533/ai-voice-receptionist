"use client";

import { useCallback, useEffect, useState } from "react";

import { api } from "./api";

/** Minimal data hook: fetch on mount/key change, optional polling, manual reload. */
export function useApi<T>(path: string | null, opts: { refreshMs?: number } = {}) {
  const [data, setData] = useState<T | undefined>(undefined);
  const [error, setError] = useState<Error | undefined>(undefined);
  const [loading, setLoading] = useState<boolean>(path !== null);
  const [nonce, setNonce] = useState(0);
  const { refreshMs } = opts;

  useEffect(() => {
    if (!path) return;
    let alive = true;
    const run = () =>
      api<T>(path)
        .then(
          (d) => {
            if (!alive) return;
            setData(d);
            setError(undefined);
          },
          (e: Error) => {
            if (alive) setError(e);
          },
        )
        .finally(() => {
          if (alive) setLoading(false);
        });
    void run();
    const timer = refreshMs ? setInterval(() => void run(), refreshMs) : undefined;
    return () => {
      alive = false;
      if (timer) clearInterval(timer);
    };
  }, [path, refreshMs, nonce]);

  const reload = useCallback(async () => {
    setNonce((n) => n + 1);
  }, []);

  return { data, error, loading, reload, setData };
}
