"use client";

import {
  ArrowRight,
  BarChart3,
  CalendarCheck2,
  CalendarPlus,
  Gauge,
  Headset,
  PhoneCall,
  Sparkles,
  Timer,
  TrendingUp,
} from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { Donut, WeeklyBars } from "@/components/charts";
import { useDashboard } from "@/components/dashboard/context";
import { OutcomeBadge, Pill } from "@/components/outcome-badge";
import { Skeleton } from "@/components/ui/skeleton";
import { fmtDuration, fmtTime, relDay } from "@/lib/format";
import type { Overview } from "@/lib/types";
import { useApi } from "@/lib/use-api";
import { cn } from "@/lib/utils";

const RANGES = [
  { days: 7, label: "Last 7 days" },
  { days: 1, label: "Today" },
  { days: 30, label: "30 days" },
];

export default function OverviewPage() {
  const { tz, openCall } = useDashboard();
  const [days, setDays] = useState(7);
  const { data, loading } = useApi<Overview>(`/api/stats/overview?days=${days}`, { refreshMs: 20000 });

  const outcomes = data?.outcomes ?? {};
  const total = data?.calls ?? 0;
  const pct = (n: number) => (total ? Math.round((n / total) * 100) : 0);
  const booked = outcomes.booked ?? 0;
  const faq = outcomes.faq_answered ?? 0;
  const resched = outcomes.rescheduled ?? 0;
  const other = total - booked - faq - resched;

  return (
    <div className="mx-auto flex max-w-7xl flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <span className="flex items-center gap-2 text-sm font-semibold">
            <span className="size-2 rounded-full bg-success" /> Salon live feed
          </span>
          <Pill>Auto-refresh 20s</Pill>
        </div>
        <div className="flex gap-2">
          {RANGES.map((r) => (
            <button
              key={r.days}
              type="button"
              onClick={() => setDays(r.days)}
              className={cn(
                "rounded-full px-3.5 py-1.5 text-sm font-medium transition-colors",
                days === r.days ? "bg-primary text-white" : "bg-surface-container text-[#394761] hover:bg-secondary",
              )}
            >
              {r.label}
            </button>
          ))}
        </div>
      </div>

      {/* KPI tiles */}
      <div className="grid grid-cols-2 gap-3 sm:gap-4 xl:grid-cols-4">
        <Tile
          icon={<PhoneCall className="size-4" />}
          value={loading ? null : String(total)}
          label="Calls answered"
          badge={
            data?.calls_change_pct != null ? (
              <span className="inline-flex items-center gap-1 rounded-full bg-primary-fixed/70 px-2 py-0.5 text-[11px] font-semibold text-[#00201b]">
                <TrendingUp className="size-3" /> {data.calls_change_pct > 0 ? "+" : ""}
                {data.calls_change_pct}%
              </span>
            ) : null
          }
        />
        <Tile
          highlight
          icon={<CalendarCheck2 className="size-4" />}
          value={loading ? null : String(data?.appointments_booked ?? 0)}
          label="Appointments booked by AI"
          badge={<span className="rounded-full bg-primary-fixed px-2 py-0.5 text-[11px] font-semibold text-[#00201b]">Auto-synced</span>}
        />
        <Tile
          icon={<Gauge className="size-4" />}
          value={loading ? null : `${data?.booking_rate ?? 0}%`}
          label="Booking rate"
          badge={<Ring value={data?.booking_rate ?? 0} />}
        />
        <Tile
          icon={<Timer className="size-4" />}
          value={loading ? null : fmtDuration(data?.avg_duration_s ?? 0)}
          label="Avg. call duration"
          badge={
            data?.median_latency_ms ? (
              <span className="rounded-full bg-surface-container px-2 py-0.5 text-[11px] font-semibold text-[#394761]">
                {(data.median_latency_ms / 1000).toFixed(1)} s replies
              </span>
            ) : null
          }
        />
      </div>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.35fr)_minmax(0,1fr)]">
        <div className="flex flex-col gap-6">
          <Link
            href="/dashboard/calls?outcome=handed_to_human"
            className="surface-card surface-card-hover flex items-center gap-4 p-5"
          >
            <span className="flex size-11 items-center justify-center rounded-xl bg-surface-container text-[#394761]">
              <Headset className="size-5" />
            </span>
            <div className="min-w-0 flex-1">
              <p className="font-semibold">
                {data?.handoffs ?? 0} staff {(data?.handoffs ?? 0) === 1 ? "handoff" : "handoffs"}{" "}
                <Pill className="ml-1">{pct(data?.handoffs ?? 0)}%</Pill>
              </p>
              <p className="text-sm text-muted-foreground">Callers who asked for a person — your team was alerted.</p>
            </div>
            <ArrowRight className="size-5 text-muted-foreground" />
          </Link>

          <div className="surface-card p-6">
            <div className="mb-5 flex items-start justify-between">
              <div>
                <h2 className="text-lg font-semibold">Call volume</h2>
                <p className="text-sm text-muted-foreground">
                  {data?.per_day?.length
                    ? `Busiest: ${peakLabel(data.per_day)}`
                    : "Calls per day"}
                </p>
              </div>
              <span className="flex size-9 items-center justify-center rounded-lg bg-surface-low text-primary">
                <BarChart3 className="size-4" />
              </span>
            </div>
            {data ? (
              <WeeklyBars
                data={data.per_day.map((d) => ({
                  label: new Date(`${d.date}T12:00:00`).toLocaleDateString("en-US", { weekday: "short" }),
                  value: d.calls,
                }))}
              />
            ) : (
              <Skeleton className="h-44 w-full" />
            )}
          </div>

          <div className="surface-card p-6">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-semibold">Call resolution</h2>
              <span className="text-sm font-semibold text-muted-foreground">{total} calls</span>
            </div>
            <div className="flex flex-col items-center gap-6 sm:flex-row">
              <Donut
                centerValue={`${pct(booked)}%`}
                centerLabel="Booked"
                segments={[
                  { label: "Booked", value: booked, color: "#00685b" },
                  { label: "FAQ", value: faq, color: "#505f7a" },
                  { label: "Rescheduled", value: resched, color: "#c9a227" },
                  { label: "Other", value: Math.max(0, other), color: "#ba1a1a" },
                ]}
              />
              <ul className="flex w-full flex-col gap-2.5 text-sm">
                {[
                  ["Booked", booked, "bg-primary"],
                  ["FAQ answered", faq, "bg-[#505f7a]"],
                  ["Rescheduled", resched, "bg-[#c9a227]"],
                  ["Cancelled / handed off / other", Math.max(0, other), "bg-destructive"],
                ].map(([label, value, dot]) => (
                  <li key={label as string} className="flex items-center gap-2.5">
                    <span className={cn("size-2.5 rounded-full", dot as string)} />
                    <span className="flex-1 text-muted-foreground">{label}</span>
                    <span className="font-semibold tabular-nums">{pct(value as number)}%</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>

          <div className="flex items-center gap-4 rounded-2xl bg-surface-container p-5">
            <span className="flex size-11 items-center justify-center rounded-full bg-primary-fixed text-primary">
              <Sparkles className="size-5" />
            </span>
            <div>
              <p className="font-semibold">Front-desk time saved: ~{((data?.time_saved_min ?? 0) / 60).toFixed(1)} hrs</p>
              <p className="text-sm text-muted-foreground">
                Ava handled {total} calls in this period — time your team spent on clients instead.
              </p>
            </div>
          </div>
        </div>

        <div className="flex flex-col gap-6">
          <div className="surface-card p-6">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="flex items-center gap-2 text-lg font-semibold">
                Upcoming today <Pill className="bg-primary-fixed/70 text-[#00201b]">{data?.upcoming_today.length ?? 0} left</Pill>
              </h2>
              <Link href="/dashboard/appointments" className="text-sm font-semibold text-primary">
                View all
              </Link>
            </div>
            <div className="flex flex-col gap-3">
              {data?.upcoming_today.length === 0 ? (
                <p className="rounded-xl bg-surface-low px-4 py-6 text-center text-sm text-muted-foreground">
                  No more appointments today.
                </p>
              ) : null}
              {data?.upcoming_today.map((a) => (
                <div key={a.id} className="flex items-center gap-4 rounded-xl border px-4 py-3">
                  <div className="flex w-14 flex-col items-center rounded-lg bg-mint py-1.5 text-primary">
                    <span className="text-[10px] font-semibold">{fmtTime(a.start_utc, tz).split(" ")[1]}</span>
                    <span className="text-base font-bold leading-tight">{fmtTime(a.start_utc, tz).split(" ")[0]}</span>
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="flex items-center gap-2 truncate font-semibold">
                      {a.customer_name}
                      {a.source === "ai" ? <Pill className="bg-primary-fixed/60 text-[#00201b]">✦ AI</Pill> : null}
                    </p>
                    <p className="truncate text-sm text-muted-foreground">
                      {a.service} · {a.staff}
                    </p>
                  </div>
                  <CalendarPlus className="size-5 text-muted-foreground" />
                </div>
              ))}
              {!data ? <Skeleton className="h-40 w-full" /> : null}
            </div>
          </div>

          <div className="surface-card p-6">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-semibold">Recent reception calls</h2>
              <Link href="/dashboard/calls" className="text-sm font-semibold text-primary">
                Full log
              </Link>
            </div>
            <div className="flex flex-col divide-y">
              {data?.recent_calls.map((c) => (
                <Link key={c.id} href={`/dashboard/calls/${c.id}`} className="flex flex-col gap-1.5 py-3 first:pt-0 last:pb-0">
                  <div className="flex items-center justify-between gap-2">
                    <OutcomeBadge outcome={c.outcome} />
                    <span className="text-xs text-muted-foreground">
                      {relDay(c.started_at, tz)}, {fmtTime(c.started_at, tz)} · {fmtDuration(c.duration_s)}
                    </span>
                  </div>
                  <p className="line-clamp-2 text-sm text-muted-foreground">{c.summary ?? "Processing…"}</p>
                </Link>
              ))}
              {data && data.recent_calls.length === 0 ? (
                <div className="flex flex-col items-center gap-3 py-6 text-center text-sm text-muted-foreground">
                  No calls yet.
                  <button type="button" onClick={openCall} className="font-semibold text-primary">
                    Make a test call
                  </button>
                </div>
              ) : null}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function peakLabel(perDay: { date: string; calls: number }[]) {
  const peak = perDay.reduce((a, b) => (b.calls > a.calls ? b : a), perDay[0]);
  const day = new Date(`${peak.date}T12:00:00`).toLocaleDateString("en-US", { weekday: "long" });
  return `${day} (${peak.calls} calls)`;
}

function Tile({
  icon,
  value,
  label,
  badge,
  highlight,
}: {
  icon: React.ReactNode;
  value: string | null;
  label: string;
  badge?: React.ReactNode;
  highlight?: boolean;
}) {
  return (
    <div
      className={cn(
        "relative overflow-hidden rounded-2xl border p-4 sm:p-5",
        highlight ? "border-primary bg-primary text-white shadow-[0_12px_30px_-14px_rgb(0_104_91/0.8)]" : "surface-card",
      )}
    >
      <div className="mb-4 flex items-center justify-between">
        <span
          className={cn(
            "flex size-9 items-center justify-center rounded-lg",
            highlight ? "bg-white/15 text-white" : "bg-surface-low text-primary",
          )}
        >
          {icon}
        </span>
        {badge}
      </div>
      {value === null ? (
        <Skeleton className={cn("h-9 w-20", highlight && "bg-white/20")} />
      ) : (
        <p className="text-2xl font-bold leading-8 tracking-tight tabular-nums sm:text-[32px] sm:leading-10">{value}</p>
      )}
      <p className={cn("text-sm", highlight ? "text-white/80" : "text-muted-foreground")}>{label}</p>
      {highlight ? (
        <CalendarCheck2 className="pointer-events-none absolute -right-3 top-12 size-16 text-white/10" aria-hidden />
      ) : null}
    </div>
  );
}

function Ring({ value }: { value: number }) {
  const r = 9;
  const c = 2 * Math.PI * r;
  return (
    <svg viewBox="0 0 24 24" className="size-7 -rotate-90" aria-hidden>
      <circle cx="12" cy="12" r={r} fill="none" stroke="#e5eeff" strokeWidth="3.5" />
      <circle
        cx="12"
        cy="12"
        r={r}
        fill="none"
        stroke="#00685b"
        strokeWidth="3.5"
        strokeLinecap="round"
        strokeDasharray={`${(Math.min(100, value) / 100) * c} ${c}`}
      />
    </svg>
  );
}
