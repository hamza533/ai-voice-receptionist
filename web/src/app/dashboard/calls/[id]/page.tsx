"use client";

import {
  ArrowLeft,
  CalendarCheck2,
  CalendarDays,
  Clock3,
  Gauge,
  Globe,
  Mail,
  MessageSquareText,
  PhoneIncoming,
  Search,
  ShieldCheck,
  Sparkles,
  Wrench,
  Zap,
} from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useMemo } from "react";

import { useDashboard } from "@/components/dashboard/context";
import { OutcomeBadge, Pill } from "@/components/outcome-badge";
import { Skeleton } from "@/components/ui/skeleton";
import { fmtDate, fmtDateTime, fmtDuration, fmtTime, TOOL_LABELS } from "@/lib/format";
import type { CallDetail, ToolCall, Turn } from "@/lib/types";
import { useApi } from "@/lib/use-api";
import { cn } from "@/lib/utils";

type Item = { kind: "turn"; at: number; turn: Turn } | { kind: "tool"; at: number; tool: ToolCall };

export default function CallDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { tz } = useDashboard();
  const { data: call, error } = useApi<CallDetail>(`/api/calls/${id}`, { refreshMs: 8000 });

  const timeline = useMemo<Item[]>(() => {
    if (!call) return [];
    const items: Item[] = [
      ...call.turns.map((t) => ({ kind: "turn" as const, at: Date.parse(t.ts), turn: t })),
      ...call.tool_calls.map((t) => ({ kind: "tool" as const, at: Date.parse(t.created_at), tool: t })),
    ];
    return items.sort((a, b) => a.at - b.at);
  }, [call]);

  if (error) {
    return <div className="surface-card mx-auto max-w-3xl p-8 text-center text-sm">Call not found.</div>;
  }
  if (!call) {
    return (
      <div className="mx-auto grid max-w-6xl gap-5">
        <Skeleton className="h-32 rounded-2xl" />
        <Skeleton className="h-96 rounded-2xl" />
      </div>
    );
  }

  const start = Date.parse(call.started_at);
  const offset = (at: number) => {
    const s = Math.max(0, Math.round((at - start) / 1000));
    return `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
  };

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-5">
      <Link
        href="/dashboard/calls"
        className="inline-flex w-fit items-center gap-1.5 rounded-full bg-surface-low px-3 py-1 text-sm font-medium text-primary"
      >
        <ArrowLeft className="size-4" /> Back to calls
      </Link>

      <div className="surface-card flex flex-col gap-4 p-5 md:flex-row md:items-center md:justify-between">
        <div className="flex items-center gap-4">
          <span className="flex size-14 items-center justify-center rounded-full bg-primary-fixed/70 text-primary">
            {call.channel === "phone" ? <PhoneIncoming className="size-6" /> : <Globe className="size-6" />}
          </span>
          <div className="flex flex-col gap-1">
            <h2 className="text-xl font-bold tracking-tight">{call.caller}</h2>
            <p className="flex items-center gap-1.5 text-sm text-muted-foreground">
              <CalendarDays className="size-4" /> {fmtDateTime(call.started_at, tz)}
              <span className="mx-1">·</span>
              {call.channel === "phone" ? "Phone" : "Website"} call
            </p>
            <div className="flex flex-wrap gap-2 pt-1">
              <OutcomeBadge outcome={call.outcome} />
              {call.status === "active" ? <Pill className="bg-primary-fixed/70 text-[#00201b]">● Live now</Pill> : null}
            </div>
          </div>
        </div>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Metric icon={<Clock3 className="size-4" />} label="Duration" value={fmtDuration(call.duration_s)} />
          <Metric icon={<Zap className="size-4" />} label="Reply p50" value={call.latency_p50_ms ? `${call.latency_p50_ms} ms` : "—"} />
          <Metric icon={<Gauge className="size-4" />} label="Reply p95" value={call.latency_p95_ms ? `${call.latency_p95_ms} ms` : "—"} />
          <Metric
            icon={<Wrench className="size-4" />}
            label="Tool calls"
            value={String(call.tool_calls.length)}
            hint={call.interruptions ? `${call.interruptions} barge-in${call.interruptions > 1 ? "s" : ""}` : undefined}
          />
        </div>
      </div>

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)]">
        <div className="surface-card flex flex-col">
          <div className="flex items-center justify-between border-b px-5 py-4">
            <h3 className="flex items-center gap-2 font-semibold">
              <span className="flex size-8 items-center justify-center rounded-lg bg-mint text-primary">
                <MessageSquareText className="size-4" />
              </span>
              Call transcript
            </h3>
            <Pill>{call.turns.length} turns</Pill>
          </div>
          <div className="flex flex-col gap-4 p-5" data-testid="transcript">
            {timeline.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                {call.status === "active" ? "The call is in progress…" : "No transcript (purged after the retention period or empty call)."}
              </p>
            ) : null}
            {timeline.map((item, i) =>
              item.kind === "tool" ? (
                <div
                  key={`t${item.tool.id}`}
                  className={cn(
                    "flex items-center gap-2 self-center rounded-full px-3 py-1 text-xs font-semibold",
                    item.tool.result_status === "ok" ? "bg-mint text-primary" : "bg-[#fef3c7] text-[#92400e]",
                  )}
                >
                  {item.tool.tool === "check_availability" ? <Search className="size-3.5" /> : <CalendarCheck2 className="size-3.5" />}
                  <span className="tabular-nums">{offset(item.at)}</span>
                  {TOOL_LABELS[item.tool.tool] ?? item.tool.tool}
                  {item.tool.result_summary && item.tool.result_status === "ok" ? (
                    <span className="hidden font-normal sm:inline">— {item.tool.result_summary}</span>
                  ) : item.tool.result_status !== "ok" ? (
                    <span className="font-normal">({item.tool.result_status.replace("_", " ")})</span>
                  ) : null}
                </div>
              ) : (
                <div
                  key={`m${i}`}
                  className={cn("flex flex-col gap-1", item.turn.speaker === "caller" ? "items-end" : "items-start")}
                >
                  <span className="text-xs text-muted-foreground">
                    {item.turn.speaker === "caller" ? (
                      <>{offset(item.at)} · Caller</>
                    ) : (
                      <span className="flex items-center gap-1">
                        <span className="size-1.5 rounded-full bg-primary" /> <b className="text-primary">Ava (AI)</b> · {offset(item.at)}
                      </span>
                    )}
                  </span>
                  <p
                    className={cn(
                      "max-w-[85%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed",
                      item.turn.speaker === "caller" ? "rounded-tr-sm bg-surface-low" : "rounded-tl-sm bg-mint",
                    )}
                  >
                    {item.turn.text}
                  </p>
                </div>
              ),
            )}
          </div>
        </div>

        <div className="flex flex-col gap-5">
          <div className="surface-card p-5">
            <h3 className="mb-3 flex items-center gap-2 font-semibold">
              <Sparkles className="size-4 text-primary" /> AI summary
            </h3>
            <p className="rounded-xl bg-surface-low p-4 text-sm leading-relaxed">
              {call.summary ?? "The summary is generated a few seconds after the call ends."}
            </p>
          </div>

          {call.appointments.map((a) => (
            <div key={a.id} className="surface-card p-5">
              <div className="mb-4 flex items-center justify-between">
                <h3 className="font-semibold">Appointment</h3>
                <span
                  className={cn(
                    "rounded-full px-2.5 py-0.5 text-xs font-semibold",
                    a.status === "cancelled" ? "bg-[#ffdad6] text-[#93000a]" : "bg-primary-fixed/70 text-[#00201b]",
                  )}
                >
                  ● {a.status === "cancelled" ? "Cancelled" : a.calendar_synced ? "Confirmed & synced" : "Confirmed"}
                </span>
              </div>
              <dl className="grid grid-cols-2 gap-3 text-sm">
                <Field label="Service" value={a.service} />
                <Field label="With" value={a.staff} />
                <Field label="Date" value={fmtDate(a.start_utc, tz, { year: "numeric" })} />
                <Field label="Time" value={`${fmtTime(a.start_utc, tz)} – ${fmtTime(a.end_utc, tz)}`} />
                <Field label="Customer" value={a.customer_name} />
                <Field label="Reference" value={a.ref} />
              </dl>
              <div className="mt-4 flex items-center gap-2 rounded-xl bg-mint px-3.5 py-2.5 text-sm text-primary">
                <CalendarCheck2 className="size-4" />
                {a.calendar_synced ? "Event created in Google Calendar" : "Saved (calendar sync not configured)"}
              </div>
              {a.email ? (
                <div className="mt-3 rounded-xl border p-3.5 text-sm">
                  <p className="mb-1 flex items-center gap-1.5 font-semibold">
                    <Mail className="size-4 text-primary" /> Confirmation email
                  </p>
                  <p className="text-muted-foreground">
                    Hi {a.customer_name.split(" ")[0]}, you&apos;re booked for {a.service} with {a.staff} on{" "}
                    {fmtDate(a.start_utc, tz)} at {fmtTime(a.start_utc, tz)}.
                  </p>
                  <p className="mt-1 text-xs text-muted-foreground">To {a.email}</p>
                </div>
              ) : null}
            </div>
          ))}

          <div className="surface-card p-5">
            <h3 className="mb-3 font-semibold">Tool calls</h3>
            <ul className="flex flex-col gap-2 text-sm">
              {call.tool_calls.length === 0 ? <li className="text-muted-foreground">None</li> : null}
              {call.tool_calls.map((t) => (
                <li key={t.id} className="flex items-center justify-between gap-3 rounded-lg bg-surface-low px-3 py-2">
                  <span className="truncate font-mono text-xs">{t.tool}</span>
                  <span className="flex shrink-0 items-center gap-2 text-xs">
                    <span className={cn("font-semibold", t.result_status === "ok" ? "text-primary" : "text-[#92400e]")}>
                      {t.result_status}
                    </span>
                    <span className="tabular-nums text-muted-foreground">{t.latency_ms} ms</span>
                  </span>
                </li>
              ))}
            </ul>
            <p className="mt-4 flex items-start gap-2 text-xs text-muted-foreground">
              <ShieldCheck className="mt-0.5 size-3.5 shrink-0" />
              Personal data in tool arguments is redacted. Raw audio is not stored; transcripts are deleted after the retention period.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

function Metric({ icon, label, value, hint }: { icon: React.ReactNode; label: string; value: string; hint?: string }) {
  return (
    <div className="rounded-xl bg-surface-low px-3.5 py-2.5">
      <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
        {icon} {label}
      </p>
      <p className="text-lg font-bold tabular-nums">{value}</p>
      {hint ? <p className="text-[11px] text-muted-foreground">{hint}</p> : null}
    </div>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border px-3 py-2">
      <dt className="label-caps text-muted-foreground">{label}</dt>
      <dd className="mt-0.5 font-semibold">{value}</dd>
    </div>
  );
}
