"use client";

import { CalendarCheck2, Hourglass, ListChecks, Loader2, Phone, Plus, X } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { selectClass } from "@/components/dashboard/calendar-picker";
import { useDashboard } from "@/components/dashboard/context";
import { Pill } from "@/components/outcome-badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { api, json } from "@/lib/api";
import { fmtTime } from "@/lib/format";
import type { Integrations, Service, Staff, WaitlistEntry } from "@/lib/types";
import { useApi } from "@/lib/use-api";

const WHEN: Record<WaitlistEntry["time_of_day"], string> = {
  any: "Any time",
  morning: "Morning",
  afternoon: "Afternoon",
  evening: "Evening",
};

export default function WaitlistPage() {
  const { business, tz } = useDashboard();
  const { data, reload } = useApi<WaitlistEntry[]>("/api/waitlist", { refreshMs: 20000 });
  const { data: integrations } = useApi<Integrations>("/api/integrations");
  const [adding, setAdding] = useState(false);
  const smsOn = Boolean(integrations?.sms.configured);

  const day = (iso: string) =>
    new Intl.DateTimeFormat("en-GB", { weekday: "long", day: "numeric", month: "long", timeZone: "UTC" }).format(
      new Date(`${iso}T00:00:00Z`),
    );

  async function book(e: WaitlistEntry) {
    try {
      await api(`/api/waitlist/${e.id}/book`, { method: "POST" });
      toast.success(`Booked ${e.name}`);
      void reload();
    } catch (err) {
      toast.error((err as Error).message);
      void reload();
    }
  }

  async function remove(e: WaitlistEntry) {
    try {
      await api(`/api/waitlist/${e.id}`, { method: "DELETE" });
      void reload();
    } catch (err) {
      toast.error((err as Error).message);
    }
  }

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-5 pb-16">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="max-w-2xl text-sm text-muted-foreground">
            People who wanted a full day. When a matching booking is cancelled, the first person waiting is offered the time
            {smsOn ? " by text and can reply YES to take it" : " (shown here, so you can call them)"}. It&apos;s held for{" "}
            {business.waitlist_hold_minutes} minutes, then offered to the next person.
          </p>
        </div>
        <Button onClick={() => setAdding((v) => !v)} variant="outline" data-testid="waitlist-add-toggle">
          <Plus /> Add someone
        </Button>
      </div>

      {!business.waitlist_enabled ? (
        <div className="rounded-xl border border-[#fde68a] bg-[#fffbeb] px-4 py-3 text-sm text-[#92400e]">
          The waitlist is switched off, so Ava won&apos;t offer it. Turn it on in Settings → Customer notifications.
        </div>
      ) : null}

      {adding ? <AddForm onAdded={() => { setAdding(false); void reload(); }} /> : null}

      {!data ? <Skeleton className="h-48 rounded-2xl" /> : null}
      {data && data.length === 0 ? (
        <div className="surface-card flex flex-col items-center gap-2 px-6 py-14 text-center">
          <ListChecks className="size-8 text-primary" />
          <p className="font-semibold">Nobody is waiting</p>
          <p className="max-w-md text-sm text-muted-foreground">
            When a caller wants a day that&apos;s full, Ava offers to put them here.
          </p>
        </div>
      ) : null}

      <div className="flex flex-col gap-3" data-testid="waitlist">
        {data?.map((e) => (
          <div key={e.id} className="surface-card flex flex-col gap-3 p-4 sm:flex-row sm:items-center">
            <div className="flex min-w-0 flex-1 flex-col gap-1">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-semibold">{e.name}</span>
                {e.status === "offered" ? (
                  <Pill className="bg-primary-fixed/70 text-[#00201b]">
                    <Hourglass className="size-3" /> Time held
                  </Pill>
                ) : (
                  <Pill>Waiting</Pill>
                )}
                <Pill className="bg-surface-container">{e.source === "ai" ? "Added by Ava" : "Added by staff"}</Pill>
              </div>
              <p className="text-sm text-muted-foreground">
                {e.service}
                {e.staff ? ` with ${e.staff}` : ""} · {day(e.day)} · {WHEN[e.time_of_day]}
              </p>
              {e.status === "offered" && e.offer_start_utc ? (
                <p className="text-sm font-medium text-primary">
                  Offered {fmtTime(e.offer_start_utc, tz)} with {e.offer_staff}
                  {e.offer_expires_at ? ` · held until ${fmtTime(e.offer_expires_at, tz)}` : ""}
                </p>
              ) : null}
            </div>
            <div className="flex shrink-0 items-center gap-2">
              <a href={`tel:${e.phone}`} className="inline-flex h-9 items-center gap-1.5 rounded-lg border px-3 text-sm font-medium hover:bg-surface-low">
                <Phone className="size-4" /> {e.phone}
              </a>
              {e.status === "offered" ? (
                <Button size="sm" onClick={() => void book(e)} data-testid="waitlist-book">
                  <CalendarCheck2 /> Book it
                </Button>
              ) : null}
              <Button size="sm" variant="ghost" onClick={() => void remove(e)} aria-label={`Remove ${e.name}`}>
                <X />
              </Button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function AddForm({ onAdded }: { onAdded: () => void }) {
  const { data: services } = useApi<Service[]>("/api/settings/services");
  const { data: staff } = useApi<Staff[]>("/api/settings/staff");
  const [form, setForm] = useState({ name: "", phone: "", service_id: 0, staff_id: 0, day: "", time_of_day: "any" });
  const [busy, setBusy] = useState(false);
  const set = (patch: Partial<typeof form>) => setForm((f) => ({ ...f, ...patch }));
  const service = services?.find((s) => s.id === form.service_id);

  async function add() {
    setBusy(true);
    try {
      await api("/api/waitlist", {
        method: "POST",
        ...json({ ...form, staff_id: form.staff_id || null }),
      });
      toast.success(`${form.name} added to the waitlist`);
      onAdded();
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="surface-card grid gap-3 p-5 sm:grid-cols-3">
      <div className="flex flex-col gap-1">
        <Label htmlFor="w-name" className="text-xs">Name</Label>
        <Input id="w-name" value={form.name} onChange={(e) => set({ name: e.target.value })} className="h-9" />
      </div>
      <div className="flex flex-col gap-1">
        <Label htmlFor="w-phone" className="text-xs">Mobile number</Label>
        <Input id="w-phone" value={form.phone} placeholder="+92 300 1234567" onChange={(e) => set({ phone: e.target.value })} className="h-9" />
      </div>
      <div className="flex flex-col gap-1">
        <Label htmlFor="w-day" className="text-xs">Day</Label>
        <Input id="w-day" type="date" value={form.day} onChange={(e) => set({ day: e.target.value })} className="h-9" />
      </div>
      <div className="flex flex-col gap-1">
        <Label htmlFor="w-service" className="text-xs">Service</Label>
        <select id="w-service" className={selectClass} value={form.service_id} onChange={(e) => set({ service_id: Number(e.target.value), staff_id: 0 })}>
          <option value={0}>Choose…</option>
          {services?.filter((s) => s.active).map((s) => (
            <option key={s.id} value={s.id}>
              {s.name}
            </option>
          ))}
        </select>
      </div>
      <div className="flex flex-col gap-1">
        <Label htmlFor="w-staff" className="text-xs">With</Label>
        <select id="w-staff" className={selectClass} value={form.staff_id} onChange={(e) => set({ staff_id: Number(e.target.value) })}>
          <option value={0}>Anyone</option>
          {staff
            ?.filter((m) => m.active && (!service || service.staff_ids.includes(m.id)))
            .map((m) => (
              <option key={m.id} value={m.id}>
                {m.name}
              </option>
            ))}
        </select>
      </div>
      <div className="flex flex-col gap-1">
        <Label htmlFor="w-when" className="text-xs">Time of day</Label>
        <select id="w-when" className={selectClass} value={form.time_of_day} onChange={(e) => set({ time_of_day: e.target.value })}>
          {Object.entries(WHEN).map(([k, v]) => (
            <option key={k} value={k}>
              {v}
            </option>
          ))}
        </select>
      </div>
      <Button
        onClick={() => void add()}
        disabled={busy || !form.name || !form.phone || !form.day || !form.service_id}
        className="sm:col-span-3 sm:justify-self-start"
      >
        {busy ? <Loader2 className="animate-spin" /> : <Plus />} Add to waitlist
      </Button>
    </div>
  );
}
