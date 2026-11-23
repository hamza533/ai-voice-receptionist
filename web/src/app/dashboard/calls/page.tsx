"use client";

import { ArrowRight, CalendarDays, Globe, PhoneIncoming, Search, Sparkles } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { useDashboard } from "@/components/dashboard/context";
import { OutcomeBadge } from "@/components/outcome-badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { fmtDuration, fmtTime, isoDay, OUTCOMES, relDay } from "@/lib/format";
import type { CallList } from "@/lib/types";
import { useApi } from "@/lib/use-api";
import { cn } from "@/lib/utils";

const RANGES: { key: string; label: string; days: number | null }[] = [
  { key: "7", label: "Last 7 days", days: 7 },
  { key: "30", label: "Last 30 days", days: 30 },
  { key: "all", label: "All time", days: null },
];
const FILTERS = ["all", "booked", "faq_answered", "rescheduled", "cancelled", "message_taken", "handed_to_human", "abandoned"];

function CallsInner() {
  const { tz } = useDashboard();
  const router = useRouter();
  const params = useSearchParams();
  const outcome = params.get("outcome") ?? "all";
  const range = params.get("range") ?? "7";
  const page = Number(params.get("page") ?? "1");
  const [q, setQ] = useState(params.get("q") ?? "");
  const [debounced, setDebounced] = useState(q);
  const [now] = useState(() => Date.now());

  useEffect(() => {
    const t = setTimeout(() => setDebounced(q), 300);
    return () => clearTimeout(t);
  }, [q]);

  const days = RANGES.find((r) => r.key === range)?.days ?? null;
  const qs = new URLSearchParams({ page: String(page), page_size: "12" });
  if (outcome !== "all") qs.set("outcome", outcome);
  if (debounced) qs.set("q", debounced);
  if (days) qs.set("date_from", isoDay(new Date(now - (days - 1) * 86_400_000), tz));
  const { data, loading } = useApi<CallList>(`/api/calls?${qs}`, { refreshMs: 15000 });

  function setParam(key: string, value: string | null) {
    const next = new URLSearchParams(params.toString());
    if (value === null) next.delete(key);
    else next.set(key, value);
    if (key !== "page") next.delete("page");
    router.replace(`/dashboard/calls?${next}`);
  }

  const pages = data ? Math.max(1, Math.ceil(data.total / 12)) : 1;

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-5">
      <div className="flex flex-col gap-3 sm:flex-row">
        <label className="surface-card flex items-center gap-3 px-4 py-2.5 sm:w-64">
          <CalendarDays className="size-5 text-primary" />
          <span className="flex flex-col">
            <span className="text-[11px] text-muted-foreground">Date range</span>
            <select
              value={range}
              onChange={(e) => setParam("range", e.target.value)}
              className="-ml-1 bg-transparent text-sm font-semibold outline-none"
              aria-label="Date range"
            >
              {RANGES.map((r) => (
                <option key={r.key} value={r.key}>{r.label}</option>
              ))}
            </select>
          </span>
        </label>
        <div className="surface-card flex flex-1 items-center gap-2 px-4">
          <Search className="size-5 text-muted-foreground" />
          <Input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search summaries or caller number…"
            className="h-12 border-0 bg-transparent px-0 shadow-none focus-visible:ring-0"
            aria-label="Search calls"
          />
        </div>
      </div>

      <div className="-mx-1 flex gap-2 overflow-x-auto px-1 pb-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
        {FILTERS.map((f) => {
          const count = data?.counts[f] ?? 0;
          const active = outcome === f;
          return (
            <button
              key={f}
              type="button"
              onClick={() => setParam("outcome", f === "all" ? null : f)}
              className={cn(
                "flex shrink-0 items-center gap-2 rounded-full px-3.5 py-1.5 text-sm font-medium transition-colors",
                active ? "bg-primary text-white" : "bg-card text-[#394761] ring-1 ring-border hover:bg-surface-low",
              )}
            >
              {f !== "all" ? <span className={cn("size-1.5 rounded-full", active ? "bg-white" : OUTCOMES[f as keyof typeof OUTCOMES].dot)} /> : null}
              {f === "all" ? "All" : OUTCOMES[f as keyof typeof OUTCOMES].label.replace("Appointment b", "B")}
              <span className={cn("rounded-full px-1.5 text-xs", active ? "bg-white/20" : "bg-surface-container")}>{count}</span>
            </button>
          );
        })}
      </div>

      <div className="flex flex-col gap-4">
        {loading && !data
          ? Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-40 w-full rounded-2xl" />)
          : null}
        {data?.items.map((c) => (
          <article key={c.id} className="surface-card surface-card-hover flex flex-col gap-3 p-5">
            <div className="flex items-start justify-between gap-3">
              <div className="flex items-center gap-3">
                <span className="flex size-11 items-center justify-center rounded-full bg-mint text-primary">
                  {c.channel === "phone" ? <PhoneIncoming className="size-5" /> : <Globe className="size-5" />}
                </span>
                <div>
                  <p className="font-semibold">{c.caller}</p>
                  <p className="text-xs text-muted-foreground">
                    {c.channel === "phone" ? "Phone call" : "Website call"}
                  </p>
                </div>
              </div>
              <div className="text-right text-sm">
                <p className="font-semibold">
                  {relDay(c.started_at, tz)}, {fmtTime(c.started_at, tz)}
                </p>
                <p className="text-xs text-muted-foreground">{fmtDuration(c.duration_s)}</p>
              </div>
            </div>
            <div>
              <OutcomeBadge outcome={c.outcome} />
            </div>
            <div className="flex gap-2.5 rounded-xl bg-surface-low px-4 py-3 text-sm leading-relaxed">
              <Sparkles className="mt-0.5 size-4 shrink-0 text-primary" />
              <p>{c.summary ?? "Summary is being generated…"}</p>
            </div>
            <div className="flex justify-end">
              <Link href={`/dashboard/calls/${c.id}`} className="flex items-center gap-1 text-sm font-semibold text-primary">
                View details <ArrowRight className="size-4" />
              </Link>
            </div>
          </article>
        ))}
        {data && data.items.length === 0 ? (
          <div className="surface-card px-6 py-12 text-center text-sm text-muted-foreground">
            No calls match these filters.
          </div>
        ) : null}
      </div>

      {data && data.total > 0 ? (
        <div className="surface-card flex items-center justify-between px-5 py-3 text-sm">
          <span className="text-muted-foreground">
            Showing <b className="text-foreground">{(page - 1) * 12 + 1}–{Math.min(page * 12, data.total)}</b> of{" "}
            {data.total} calls
          </span>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setParam("page", String(page - 1))}>
              Previous
            </Button>
            <Button variant="outline" size="sm" disabled={page >= pages} onClick={() => setParam("page", String(page + 1))}>
              Next
            </Button>
          </div>
        </div>
      ) : null}
    </div>
  );
}

export default function CallsPage() {
  return (
    <Suspense>
      <CallsInner />
    </Suspense>
  );
}
