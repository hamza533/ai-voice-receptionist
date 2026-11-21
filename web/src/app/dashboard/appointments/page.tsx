"use client";

import { CalendarCheck2, ChevronLeft, ChevronRight, ExternalLink, Phone, Sparkles, XCircle } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";
import { toast } from "sonner";

import { useDashboard } from "@/components/dashboard/context";
import { Pill } from "@/components/outcome-badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { fmtDate, fmtTime, initials, isoDay } from "@/lib/format";
import type { Appointment, Hours, PublicBusiness, Staff } from "@/lib/types";
import { useApi } from "@/lib/use-api";
import { cn } from "@/lib/utils";

const HOUR_PX = 64;

function addDays(day: string, n: number) {
  const d = new Date(`${day}T12:00:00Z`);
  d.setUTCDate(d.getUTCDate() + n);
  return d.toISOString().slice(0, 10);
}

/** Minutes since local midnight in the business time zone. */
function localMinutes(iso: string, tz: string) {
  const parts = new Intl.DateTimeFormat("en-GB", { timeZone: tz, hour: "2-digit", minute: "2-digit", hour12: false })
    .formatToParts(new Date(iso));
  const h = Number(parts.find((p) => p.type === "hour")?.value ?? 0);
  const m = Number(parts.find((p) => p.type === "minute")?.value ?? 0);
  return (h % 24) * 60 + m;
}

export default function AppointmentsPage() {
  const { tz, me } = useDashboard();
  const today = isoDay(new Date(), tz);
  const [day, setDay] = useState(today);
  const weekStart = useMemo(() => {
    const wd = (new Date(`${day}T12:00:00Z`).getUTCDay() + 6) % 7;
    return addDays(day, -wd);
  }, [day]);
  const weekEnd = addDays(weekStart, 6);
  const { data: appts, reload } = useApi<Appointment[]>(
    `/api/appointments?date_from=${weekStart}&date_to=${weekEnd}`,
    { refreshMs: 20000 },
  );
  const { data: staff } = useApi<Staff[]>("/api/settings/staff");
  const { data: hours } = useApi<Hours[]>("/api/settings/hours");
  const { data: pub } = useApi<PublicBusiness>("/api/public/business");
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const dayAppts = (appts ?? []).filter((a) => isoDay(new Date(a.start_utc), tz) === day);
  const selected = dayAppts.find((a) => a.id === selectedId) ?? dayAppts[0];
  const weekday = (new Date(`${day}T12:00:00Z`).getUTCDay() + 6) % 7;
  const todaysHours = (hours ?? []).filter((h) => h.weekday === weekday);
  const openMin = todaysHours.length ? Math.min(...todaysHours.map((h) => toMin(h.open_time))) : 10 * 60;
  const closeMin = todaysHours.length ? Math.max(...todaysHours.map((h) => toMin(h.close_time))) : 20 * 60;
  const startHour = Math.floor(openMin / 60);
  const endHour = Math.ceil(closeMin / 60);
  const activeStaff = (staff ?? []).filter((s) => s.active);
  const upcoming = (appts ?? []).filter((a) => isoDay(new Date(a.start_utc), tz) > day).slice(0, 6);

  async function cancel(a: Appointment) {
    if (!window.confirm(`Cancel ${a.service} for ${a.customer_name}? The calendar event is removed and the customer is emailed.`)) return;
    try {
      await api(`/api/appointments/${a.id}/cancel`, { method: "POST" });
      toast.success("Appointment cancelled");
      void reload();
    } catch (e) {
      toast.error((e as Error).message);
    }
  }

  return (
    <div className="mx-auto flex max-w-7xl flex-col gap-5">
      <div className="surface-card flex flex-col gap-4 p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <Button variant="outline" size="icon" onClick={() => setDay(addDays(day, -7))} aria-label="Previous week">
              <ChevronLeft />
            </Button>
            <p className="min-w-44 text-center font-semibold">
              {fmtDate(`${weekStart}T12:00:00Z`, "UTC", { weekday: undefined })} – {fmtDate(`${weekEnd}T12:00:00Z`, "UTC", { weekday: undefined, year: "numeric" })}
            </p>
            <Button variant="outline" size="icon" onClick={() => setDay(addDays(day, 7))} aria-label="Next week">
              <ChevronRight />
            </Button>
            <Button variant="outline" onClick={() => setDay(today)}>Today</Button>
          </div>
          <span className="inline-flex items-center gap-1.5 rounded-full bg-mint px-3 py-1 text-xs font-semibold text-primary">
            <CalendarCheck2 className="size-3.5" />
            {pub?.calendar === "local" ? "Built-in calendar (connect Google in .env)" : "Synced with Google Calendar"}
          </span>
        </div>
        <div className="grid grid-cols-7 gap-2">
          {Array.from({ length: 7 }).map((_, i) => {
            const d = addDays(weekStart, i);
            const count = (appts ?? []).filter((a) => isoDay(new Date(a.start_utc), tz) === d).length;
            const date = new Date(`${d}T12:00:00Z`);
            const active = d === day;
            return (
              <button
                key={d}
                type="button"
                onClick={() => {
                  setDay(d);
                  setSelectedId(null);
                }}
                className={cn(
                  "flex flex-col items-center gap-0.5 rounded-xl py-2.5 transition-colors",
                  active ? "bg-primary text-white" : "bg-surface-low hover:bg-surface-container",
                )}
              >
                <span className={cn("text-[11px] font-semibold uppercase", active ? "text-white/80" : "text-muted-foreground")}>
                  {date.toLocaleDateString("en-US", { weekday: "short", timeZone: "UTC" })}
                </span>
                <span className="text-lg font-bold">{date.getUTCDate()}</span>
                <span className={cn("h-1.5 w-1.5 rounded-full", count ? (active ? "bg-primary-fixed" : "bg-primary") : "bg-transparent")} />
              </button>
            );
          })}
        </div>
      </div>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
        <div className="surface-card overflow-hidden">
          <div className="flex items-center justify-between border-b px-5 py-3.5">
            <h2 className="font-semibold">
              {fmtDate(`${day}T12:00:00Z`, "UTC", { weekday: "long" })} schedule{" "}
              <Pill className="ml-1">{dayAppts.length} booked</Pill>
            </h2>
            {todaysHours.length === 0 ? <span className="text-sm font-semibold text-destructive">Closed</span> : null}
          </div>
          {!appts || !staff ? (
            <Skeleton className="m-5 h-96" />
          ) : (
            <div className="overflow-x-auto">
              <div className="min-w-[560px]">
                <div className="grid border-b" style={{ gridTemplateColumns: `64px repeat(${activeStaff.length}, 1fr)` }}>
                  <div />
                  {activeStaff.map((s) => (
                    <div key={s.id} className="flex items-center gap-2 border-l px-3 py-2.5 text-sm font-semibold">
                      <span className="flex size-7 items-center justify-center rounded-full text-xs text-white" style={{ background: s.color }}>
                        {initials(s.name)}
                      </span>
                      {s.name} <span className="font-normal text-muted-foreground">· {s.title}</span>
                    </div>
                  ))}
                </div>
                <div className="relative grid" style={{ gridTemplateColumns: `64px repeat(${activeStaff.length}, 1fr)` }}>
                  <div>
                    {Array.from({ length: endHour - startHour }).map((_, i) => (
                      <div key={i} className="h-16 pr-2 pt-1 text-right text-xs text-muted-foreground" style={{ height: HOUR_PX }}>
                        {((startHour + i + 11) % 12) + 1} {startHour + i < 12 ? "AM" : "PM"}
                      </div>
                    ))}
                  </div>
                  {activeStaff.map((s) => (
                    <div key={s.id} className="relative border-l" style={{ height: (endHour - startHour) * HOUR_PX }}>
                      {Array.from({ length: endHour - startHour }).map((_, i) => (
                        <div key={i} className="border-b border-dashed border-border/70" style={{ height: HOUR_PX }} />
                      ))}
                      {dayAppts
                        .filter((a) => a.staff_id === s.id)
                        .map((a) => {
                          const top = ((localMinutes(a.start_utc, tz) - startHour * 60) / 60) * HOUR_PX;
                          const height = Math.max(
                            30,
                            ((localMinutes(a.end_utc, tz) - localMinutes(a.start_utc, tz)) / 60) * HOUR_PX - 4,
                          );
                          const isSel = selected?.id === a.id;
                          return (
                            <button
                              key={a.id}
                              type="button"
                              onClick={() => setSelectedId(a.id)}
                              className={cn(
                                "absolute inset-x-1.5 overflow-hidden rounded-xl px-2.5 py-1.5 text-left text-xs transition-shadow",
                                isSel ? "bg-primary text-white shadow-lg" : "border bg-surface-low hover:shadow-md",
                              )}
                              style={{ top: top + 2, height }}
                            >
                              <div className="flex items-center justify-between gap-1">
                                <span className={cn("label-caps truncate", isSel ? "text-primary-fixed" : "text-primary")}>{a.service}</span>
                                {a.source === "ai" ? (
                                  <span className={cn("shrink-0 rounded-full px-1.5 text-[10px] font-semibold", isSel ? "bg-white/20" : "bg-primary-fixed/70 text-[#00201b]")}>
                                    ✦ AI
                                  </span>
                                ) : null}
                              </div>
                              <p className="truncate text-sm font-semibold">{a.customer_name}</p>
                              <p className={cn("truncate", isSel ? "text-white/80" : "text-muted-foreground")}>
                                {fmtTime(a.start_utc, tz)} – {fmtTime(a.end_utc, tz)}
                              </p>
                            </button>
                          );
                        })}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>

        <div className="flex flex-col gap-5">
          <div className="surface-card p-5">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-semibold">Appointment details</h2>
              {selected ? (
                <span className="rounded-full bg-primary-fixed/70 px-2.5 py-0.5 text-xs font-semibold text-[#00201b]">
                  ● {selected.status === "rescheduled" ? "Rescheduled" : "Confirmed"}
                </span>
              ) : null}
            </div>
            {selected ? (
              <div className="flex flex-col gap-4">
                <div className="flex items-center gap-3">
                  <span className="flex size-12 items-center justify-center rounded-full bg-mint font-semibold text-primary">
                    {initials(selected.customer_name)}
                  </span>
                  <div>
                    <p className="font-semibold">{selected.customer_name}</p>
                    <p className="flex items-center gap-1 text-sm text-muted-foreground">
                      <Phone className="size-3.5" /> {selected.phone || "—"}
                      {selected.email ? <span className="ml-1">· {selected.email}</span> : null}
                    </p>
                  </div>
                </div>
                {selected.source === "ai" ? (
                  <div className="flex items-start gap-2.5 rounded-xl bg-mint px-3.5 py-2.5 text-sm">
                    <Sparkles className="mt-0.5 size-4 text-primary" />
                    <div>
                      <p className="font-semibold text-primary">Booked by AI on a call</p>
                      <p className="text-xs text-muted-foreground">Handled end-to-end by the voice receptionist</p>
                    </div>
                  </div>
                ) : null}
                <div className="grid grid-cols-2 gap-3 text-sm">
                  <Info label="Service" value={selected.service} />
                  <Info label="Stylist" value={selected.staff} />
                  <Info label="Time" value={`${fmtTime(selected.start_utc, tz)} – ${fmtTime(selected.end_utc, tz)}`} />
                  <Info label="Reference" value={selected.ref} />
                </div>
                <div className="flex gap-2">
                  {selected.call_id ? (
                    <Link
                      href={`/dashboard/calls/${selected.call_id}`}
                      className="inline-flex h-9 flex-1 items-center justify-center gap-1.5 rounded-lg border bg-card text-sm font-medium hover:bg-surface-low"
                    >
                      <ExternalLink className="size-4" /> Open call
                    </Link>
                  ) : null}
                  <Button variant="destructive" className="h-9 flex-1" onClick={() => void cancel(selected)} disabled={!me}>
                    <XCircle /> Cancel
                  </Button>
                </div>
              </div>
            ) : (
              <p className="rounded-xl bg-surface-low px-4 py-8 text-center text-sm text-muted-foreground">
                No appointments on this day.
              </p>
            )}
          </div>

          <div className="surface-card p-5">
            <h2 className="mb-3 font-semibold">Later this week</h2>
            <ul className="flex flex-col divide-y">
              {upcoming.length === 0 ? <li className="py-3 text-sm text-muted-foreground">Nothing else booked this week.</li> : null}
              {upcoming.map((a) => (
                <li key={a.id} className="flex items-center gap-3 py-2.5">
                  <span className="flex size-9 items-center justify-center rounded-full bg-surface-container text-xs font-semibold">
                    {initials(a.customer_name)}
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-semibold">
                      {a.customer_name} {a.source === "ai" ? <Pill className="ml-1 bg-primary-fixed/60 text-[#00201b]">✦ AI</Pill> : null}
                    </p>
                    <p className="truncate text-xs text-muted-foreground">
                      {a.service} · {a.staff}
                    </p>
                  </div>
                  <span className="text-right text-xs font-medium">
                    {fmtDate(a.start_utc, tz)}
                    <br />
                    <span className="text-muted-foreground">{fmtTime(a.start_utc, tz)}</span>
                  </span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}

function toMin(t: string) {
  const [h, m] = t.split(":").map(Number);
  return h * 60 + m;
}

function Info({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border px-3 py-2">
      <p className="label-caps text-muted-foreground">{label}</p>
      <p className="mt-0.5 font-semibold">{value}</p>
    </div>
  );
}
