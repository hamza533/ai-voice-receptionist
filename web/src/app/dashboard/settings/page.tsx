"use client";

import {
  BellRing,
  Bot,
  Building2,
  CalendarCheck2,
  CalendarCog,
  CalendarX2,
  Check,
  Clock3,
  Headset,
  Loader2,
  MessageSquareText,
  Plug,
  Plus,
  Save,
  Scissors,
  Trash2,
  Users,
} from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { CalendarPicker } from "@/components/dashboard/calendar-picker";

import { useDashboard } from "@/components/dashboard/context";
import { Pill } from "@/components/outcome-badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { api, json } from "@/lib/api";
import { WEEKDAYS } from "@/lib/format";
import type { Business, Holiday, Hours, Integrations, Service, Staff } from "@/lib/types";
import { useApi } from "@/lib/use-api";
import { cn } from "@/lib/utils";

const VOICES = [
  { id: "Aoede", desc: "Warm, breezy · female" },
  { id: "Kore", desc: "Calm, professional · female" },
  { id: "Leda", desc: "Youthful, friendly · female" },
  { id: "Puck", desc: "Upbeat, energetic · male" },
  { id: "Charon", desc: "Informative, steady · male" },
  { id: "Orus", desc: "Firm, reassuring · male" },
];

interface Ready {
  checks: Record<string, string>;
  demo_mode: boolean;
}

export default function SettingsPage() {
  const { me, business, reloadBusiness } = useDashboard();
  const isAdmin = me.role === "admin";
  const [form, setForm] = useState<Business>(business);
  const [prevBusiness, setPrevBusiness] = useState<Business>(business);
  const [saving, setSaving] = useState(false);
  if (business !== prevBusiness) {
    // Reset the form when the saved settings change (React's "adjust state on prop change").
    setPrevBusiness(business);
    setForm(business);
  }
  const dirty = JSON.stringify(form) !== JSON.stringify(business);

  function set<K extends keyof Business>(k: K, v: Business[K]) {
    setForm((f) => ({ ...f, [k]: v }));
  }

  async function saveBusiness() {
    setSaving(true);
    try {
      await api("/api/settings/business", { method: "PUT", ...json(form) });
      await reloadBusiness();
      toast.success("Settings saved — the next call uses them");
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6 pb-16">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="label-caps text-primary">{business.name}</p>
          <h2 className="text-2xl font-bold tracking-tight">Agent settings & preferences</h2>
          <p className="text-sm text-muted-foreground">
            Configure Ava&apos;s greeting and voice, opening hours, services, handoffs and email.
          </p>
        </div>
        {!isAdmin ? <Pill>Read-only (staff)</Pill> : null}
      </div>

      <fieldset disabled={!isAdmin} className="flex flex-col gap-6">
        <Section icon={<Bot />} title="Greeting & persona" right={<Pill className="bg-primary-fixed/60 text-[#00201b]">● Natural voice</Pill>}>
          <div className="flex flex-col gap-2">
            <div className="flex items-center justify-between">
              <Label htmlFor="greeting">Initial call greeting</Label>
              <span className="text-xs text-muted-foreground">{form.greeting.length} chars</span>
            </div>
            <Textarea id="greeting" rows={3} value={form.greeting} onChange={(e) => set("greeting", e.target.value)} data-testid="greeting" />
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="notice">Recording notice (always said after the greeting)</Label>
            <Input id="notice" value={form.recording_notice} onChange={(e) => set("recording_notice", e.target.value)} />
          </div>
          <div className="flex flex-col gap-2">
            <Label>Voice</Label>
            <div className="grid gap-2 sm:grid-cols-2">
              {VOICES.map((v) => (
                <button
                  type="button"
                  key={v.id}
                  onClick={() => set("voice", v.id)}
                  className={cn(
                    "flex items-center gap-3 rounded-xl border px-3.5 py-2.5 text-left transition-colors",
                    form.voice === v.id ? "border-primary bg-mint" : "hover:bg-surface-low",
                  )}
                >
                  <span className={cn("flex size-9 items-center justify-center rounded-full", form.voice === v.id ? "bg-primary text-white" : "bg-surface-container text-[#394761]")}>
                    {form.voice === v.id ? <Check className="size-4" /> : v.id[0]}
                  </span>
                  <span>
                    <span className="block text-sm font-semibold">Ava — {v.id}</span>
                    <span className="block text-xs text-muted-foreground">{v.desc}</span>
                  </span>
                  {form.voice === v.id ? <Pill className="ml-auto bg-primary text-white">Active</Pill> : null}
                </button>
              ))}
            </div>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Language" value={form.language} onChange={(v) => set("language", v)} hint="e.g. en-US, en-GB, ur-PK" />
            <Field label="Extra instructions (optional)" value={form.extra_instructions} onChange={(v) => set("extra_instructions", v)} />
          </div>
        </Section>

        <Section icon={<Building2 />} title="Business">
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Business name" value={form.name} onChange={(v) => set("name", v)} />
            <Field label="Time zone" value={form.timezone} onChange={(v) => set("timezone", v)} hint="IANA name, e.g. Asia/Karachi" />
            <Field label="Address" value={form.address} onChange={(v) => set("address", v)} />
            <Field label="Phone" value={form.phone} onChange={(v) => set("phone", v)} />
            <Field label="Website" value={form.website} onChange={(v) => set("website", v)} />
            <Field label="Currency" value={form.currency} onChange={(v) => set("currency", v)} />
          </div>
        </Section>

        <Section icon={<Headset />} title="Human escalation & handoff">
          <div className="grid gap-4 sm:grid-cols-2">
            <Field
              label="Handoff number (SIP transfer)"
              value={form.handoff_number}
              onChange={(v) => set("handoff_number", v)}
              hint="Used when TRANSFER_ENABLED=true. Otherwise Ava takes an urgent message."
            />
            <Field
              label="Staff notification email"
              value={form.staff_notify_email}
              onChange={(v) => set("staff_notify_email", v)}
              hint="Messages and handoff alerts go here."
            />
          </div>
          <Field label="Email signature" value={form.email_signature} onChange={(v) => set("email_signature", v)} />
        </Section>

        <Section icon={<BellRing />} title="Customer notifications & waitlist">
          <div className="grid gap-3 sm:grid-cols-2">
            <Toggle
              label="Text a confirmation"
              hint="When a booking is made, moved or cancelled."
              checked={form.sms_confirmations}
              onChange={(v) => set("sms_confirmations", v)}
            />
            <Toggle
              label="Text a reminder"
              hint="Customers can reply C to cancel, freeing the time for others."
              checked={form.sms_reminders}
              onChange={(v) => set("sms_reminders", v)}
            >
              <div className="flex items-center gap-2 text-sm">
                <Input
                  type="number"
                  min={1}
                  max={72}
                  value={form.reminder_hours}
                  onChange={(e) => set("reminder_hours", Number(e.target.value))}
                  className="h-8 w-20"
                  aria-label="Reminder hours before"
                />
                hours before
              </div>
            </Toggle>
            <Toggle
              label="Waitlist for full days"
              hint="Ava offers it when a day is full; cancellations go to the first person waiting."
              checked={form.waitlist_enabled}
              onChange={(v) => set("waitlist_enabled", v)}
            >
              <div className="flex items-center gap-2 text-sm">
                Hold an offered time for
                <Input
                  type="number"
                  min={5}
                  max={240}
                  value={form.waitlist_hold_minutes}
                  onChange={(e) => set("waitlist_hold_minutes", Number(e.target.value))}
                  className="h-8 w-20"
                  aria-label="Hold minutes"
                />
                minutes
              </div>
            </Toggle>
          </div>
          <p className="text-xs text-muted-foreground">
            Texts are sent once your SMS provider is connected (see Integrations). Until then they are listed but not sent.
          </p>
        </Section>

        {isAdmin ? (
          <div className="sticky bottom-20 z-10 flex justify-end lg:bottom-6">
            <Button
              onClick={() => void saveBusiness()}
              disabled={!dirty || saving}
              className="btn-gradient h-11 rounded-xl px-5 text-white shadow-lg"
              data-testid="save-settings"
            >
              {saving ? <Loader2 className="animate-spin" /> : <Save />} Save changes
            </Button>
          </div>
        ) : null}

        <HoursSection />
        <HolidaysSection />
        <div id="services" className="scroll-mt-24">
          <ServicesSection />
        </div>
        <TeamLink />
      </fieldset>
      <IntegrationsSection isAdmin={isAdmin} />
    </div>
  );
}

function Section({
  icon,
  title,
  right,
  children,
}: {
  icon: React.ReactNode;
  title: string;
  right?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section className="surface-card flex flex-col gap-5 p-6">
      <div className="flex items-center justify-between">
        <h3 className="flex items-center gap-2.5 font-semibold">
          <span className="flex size-8 items-center justify-center rounded-lg bg-mint text-primary [&_svg]:size-4">{icon}</span>
          {title}
        </h3>
        {right}
      </div>
      {children}
    </section>
  );
}

function Toggle({
  label,
  hint,
  checked,
  onChange,
  children,
}: {
  label: string;
  hint: string;
  checked: boolean;
  onChange: (v: boolean) => void;
  children?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-2 rounded-xl border p-4">
      <label className="flex items-start justify-between gap-3">
        <span>
          <span className="block text-sm font-semibold">{label}</span>
          <span className="block text-xs text-muted-foreground">{hint}</span>
        </span>
        <Switch checked={checked} onCheckedChange={onChange} aria-label={label} />
      </label>
      {checked ? children : null}
    </div>
  );
}

function Field({ label, value, onChange, hint }: { label: string; value: string; onChange: (v: string) => void; hint?: string }) {
  const id = label.toLowerCase().replace(/[^a-z]+/g, "-");
  return (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor={id}>{label}</Label>
      <Input id={id} value={value} onChange={(e) => onChange(e.target.value)} className="h-10" />
      {hint ? <p className="text-xs text-muted-foreground">{hint}</p> : null}
    </div>
  );
}

function HoursSection() {
  const { data, reload } = useApi<Hours[]>("/api/settings/hours");
  const [rows, setRows] = useState<Record<number, { open: boolean; from: string; to: string }>>({});
  const [loadedFrom, setLoadedFrom] = useState<Hours[] | undefined>(undefined);
  if (data && data !== loadedFrom) {
    const next: Record<number, { open: boolean; from: string; to: string }> = {};
    for (let d = 0; d < 7; d++) {
      const h = data.find((x) => x.weekday === d);
      next[d] = h
        ? { open: true, from: h.open_time.slice(0, 5), to: h.close_time.slice(0, 5) }
        : { open: false, from: "10:00", to: "20:00" };
    }
    setLoadedFrom(data);
    setRows(next);
  }

  async function save() {
    const body = Object.entries(rows)
      .filter(([, r]) => r.open)
      .map(([d, r]) => ({ weekday: Number(d), open_time: r.from, close_time: r.to }));
    try {
      await api("/api/settings/hours", { method: "PUT", ...json(body) });
      toast.success("Opening hours saved");
      void reload();
    } catch (e) {
      toast.error((e as Error).message);
    }
  }

  return (
    <Section icon={<Clock3 />} title="Hours & after-hours" right={<Button variant="outline" onClick={() => void save()}>Save hours</Button>}>
      <div className="flex flex-col divide-y rounded-xl border">
        {WEEKDAYS.map((day, d) => {
          const r = rows[d];
          if (!r) return null;
          return (
            <div key={day} className="flex flex-wrap items-center gap-3 px-4 py-2.5">
              <span className="w-28 text-sm font-medium">{day}</span>
              <Switch checked={r.open} onCheckedChange={(v) => setRows({ ...rows, [d]: { ...r, open: v } })} aria-label={`${day} open`} />
              {r.open ? (
                <div className="flex items-center gap-2 text-sm">
                  <Input type="time" value={r.from} onChange={(e) => setRows({ ...rows, [d]: { ...r, from: e.target.value } })} className="h-9 w-32" />
                  –
                  <Input type="time" value={r.to} onChange={(e) => setRows({ ...rows, [d]: { ...r, to: e.target.value } })} className="h-9 w-32" />
                </div>
              ) : (
                <span className="rounded-full bg-[#ffdad6] px-2 py-0.5 text-xs font-semibold text-[#93000a]">Closed</span>
              )}
            </div>
          );
        })}
      </div>
      <p className="text-xs text-muted-foreground">
        Outside these hours Ava still answers, gives information, books future slots and takes messages.
      </p>
    </Section>
  );
}

function ServicesSection() {
  const { business } = useDashboard();
  const { data: services, reload } = useApi<Service[]>("/api/settings/services");
  const { data: staff } = useApi<Staff[]>("/api/settings/staff");
  const [edit, setEdit] = useState<Record<number, Service>>({});

  async function save(s: Service, isNew = false) {
    const body = {
      name: s.name,
      description: s.description,
      duration_min: Number(s.duration_min),
      price: Number(s.price),
      buffer_min: Number(s.buffer_min),
      active: s.active,
      staff_ids: s.staff_ids,
    };
    try {
      if (isNew) await api("/api/settings/services", { method: "POST", ...json(body) });
      else await api(`/api/settings/services/${s.id}`, { method: "PUT", ...json(body) });
      toast.success(`${s.name} saved`);
      setEdit((e) => {
        const n = { ...e };
        delete n[s.id];
        return n;
      });
      void reload();
    } catch (e) {
      toast.error((e as Error).message);
    }
  }

  const rows: Service[] = [...(services ?? []), ...(edit[-1] ? [edit[-1]] : [])];

  return (
    <Section
      icon={<Scissors />}
      title="Booking durations, prices & buffers"
      right={
        <Button
          variant="outline"
          onClick={() =>
            setEdit((e) => ({
              ...e,
              [-1]: { id: -1, name: "", description: "", duration_min: 30, price: 0, buffer_min: 5, active: true, staff_ids: [] },
            }))
          }
        >
          <Plus /> Add service
        </Button>
      }
    >
      <div className="flex flex-col gap-3">
        {rows.map((orig) => {
          const s = edit[orig.id] ?? orig;
          const editing = Boolean(edit[orig.id]);
          const upd = (patch: Partial<Service>) => setEdit((e) => ({ ...e, [orig.id]: { ...s, ...patch } }));
          return (
            <div key={orig.id} className={cn("grid gap-3 rounded-xl border p-4 md:grid-cols-[1.4fr_repeat(3,0.6fr)_auto]", !s.active && "opacity-60")}>
              <div className="flex flex-col gap-1">
                <Label className="text-xs">Service</Label>
                <Input value={s.name} onChange={(e) => upd({ name: e.target.value })} className="h-9" />
                <div className="mt-1 flex flex-wrap gap-1.5">
                  {staff?.map((m) => {
                    const on = s.staff_ids.includes(m.id);
                    return (
                      <button
                        type="button"
                        key={m.id}
                        onClick={() => upd({ staff_ids: on ? s.staff_ids.filter((x) => x !== m.id) : [...s.staff_ids, m.id] })}
                        className={cn("rounded-full px-2.5 py-0.5 text-xs font-medium", on ? "bg-primary text-white" : "bg-surface-container text-[#394761]")}
                      >
                        {m.name}
                      </button>
                    );
                  })}
                </div>
              </div>
              <NumberField label="Minutes" value={s.duration_min} onChange={(v) => upd({ duration_min: v })} />
              <NumberField label={`Price (${business.currency})`} value={Number(s.price)} onChange={(v) => upd({ price: v })} />
              <NumberField label="Buffer" value={s.buffer_min} onChange={(v) => upd({ buffer_min: v })} />
              <div className="flex items-end gap-2">
                <div className="flex items-center gap-2 pb-2">
                  <Switch checked={s.active} onCheckedChange={(v) => upd({ active: v })} aria-label="Active" />
                </div>
                <Button size="sm" disabled={!editing || !s.name} onClick={() => void save(s, orig.id === -1)} className="mb-1">
                  Save
                </Button>
              </div>
            </div>
          );
        })}
      </div>
    </Section>
  );
}

function NumberField({ label, value, onChange }: { label: string; value: number; onChange: (v: number) => void }) {
  return (
    <div className="flex flex-col gap-1">
      <Label className="text-xs">{label}</Label>
      <Input type="number" min={0} value={value} onChange={(e) => onChange(Number(e.target.value))} className="h-9" />
    </div>
  );
}

function TeamLink() {
  const { data: staff } = useApi<Staff[]>("/api/settings/staff");
  return (
    <Section icon={<Users />} title="Team" right={<Link href="/dashboard/team" className="text-sm font-medium text-primary">Manage team →</Link>}>
      <p className="text-sm text-muted-foreground">
        {staff ? `${staff.filter((m) => m.active).length} people taking bookings. ` : ""}
        Add people, set each person&apos;s working hours, time off and calendar on the Team page.
      </p>
    </Section>
  );
}

function HolidaysSection() {
  const { me } = useDashboard();
  const { data, reload } = useApi<Holiday[]>("/api/settings/holidays");
  const [date, setDate] = useState("");
  const [label, setLabel] = useState("");
  const [today] = useState(() => new Date().toLocaleDateString("en-CA")); // local YYYY-MM-DD
  const upcoming = data?.filter((h) => h.date >= today) ?? [];

  async function add() {
    try {
      await api("/api/settings/holidays", { method: "POST", ...json({ date, label }) });
      toast.success("Closure added. Ava won't book that day.");
      setDate("");
      setLabel("");
      void reload();
    } catch (e) {
      toast.error((e as Error).message);
    }
  }

  async function remove(h: Holiday) {
    try {
      await api(`/api/settings/holidays/${h.id}`, { method: "DELETE" });
      void reload();
    } catch (e) {
      toast.error((e as Error).message);
    }
  }

  return (
    <Section icon={<CalendarX2 />} title="Holidays & closures">
      <div className="flex flex-col gap-2" data-testid="holidays">
        {data && upcoming.length === 0 ? <p className="text-sm text-muted-foreground">No closures coming up.</p> : null}
        {upcoming.map((h) => (
          <div key={h.id} className="flex items-center gap-3 rounded-xl border px-4 py-2.5 text-sm">
            <span className="font-medium">
              {new Intl.DateTimeFormat("en-GB", { weekday: "short", day: "numeric", month: "long", year: "numeric", timeZone: "UTC" }).format(new Date(`${h.date}T00:00:00Z`))}
            </span>
            {h.label ? <span className="text-muted-foreground">· {h.label}</span> : null}
            {me.role === "admin" ? (
              <button type="button" onClick={() => void remove(h)} className="ml-auto text-muted-foreground hover:text-destructive" aria-label="Remove closure">
                <Trash2 className="size-4" />
              </button>
            ) : null}
          </div>
        ))}
      </div>
      <div className="flex flex-wrap items-end gap-3">
        <div className="flex flex-col gap-1">
          <Label className="text-xs">Date</Label>
          <Input type="date" value={date} min={today} onChange={(e) => setDate(e.target.value)} className="h-9" aria-label="Closure date" />
        </div>
        <div className="flex min-w-48 flex-1 flex-col gap-1">
          <Label className="text-xs">Reason (optional)</Label>
          <Input value={label} placeholder="Eid, public holiday, staff training…" onChange={(e) => setLabel(e.target.value)} className="h-9" />
        </div>
        <Button variant="outline" onClick={() => void add()} disabled={!date}>
          <Plus /> Add closure
        </Button>
      </div>
    </Section>
  );
}

function IntegrationsSection({ isAdmin }: { isAdmin: boolean }) {
  const { data } = useApi<Ready>("/backend/ready");
  const { data: status, reload } = useApi<Integrations>("/api/integrations");
  const google = status?.google;

  useEffect(() => {
    const result = new URLSearchParams(window.location.search).get("calendar");
    if (!result) return;
    if (result === "connected") toast.success("Google Calendar connected. Pick the calendar to use below.");
    else if (result === "cancelled") toast.info("Google Calendar wasn't connected.");
    else toast.error("Couldn't connect Google Calendar. Please try again.");
    window.history.replaceState(null, "", window.location.pathname);
  }, []);

  async function pick(id: string) {
    try {
      await api("/api/integrations/google", { method: "PUT", ...json({ calendar_id: id }) });
      toast.success("Bookings will go to this calendar");
      void reload();
    } catch (e) {
      toast.error((e as Error).message);
    }
  }

  async function disconnect() {
    try {
      await api("/api/integrations/google", { method: "DELETE" });
      toast.success("Google Calendar disconnected");
      void reload();
    } catch (e) {
      toast.error((e as Error).message);
    }
  }

  const calendarDetail = !google
    ? "…"
    : google.mode === "connected"
      ? `Connected as ${google.account_email || "your Google account"}`
      : google.mode === "service_account"
        ? "Connected with a service account"
        : "Using the built-in calendar";

  const items = [
    { key: "livekit", label: "Phone & web calls", ok: data?.checks.livekit === "configured", detail: data?.checks.livekit === "configured" ? "Ready to answer" : "Not set up yet" },
    { key: "llm", label: "AI voice & summaries", ok: data?.checks.llm === "configured", detail: data?.checks.llm === "configured" ? "Ready" : "Not set up yet" },
    { key: "smtp", label: "Email", ok: data?.checks.smtp === "configured", detail: data?.checks.smtp === "configured" ? "Confirmations & alerts on" : "Emails are logged, not sent" },
    {
      key: "sms",
      label: "Text messages",
      ok: Boolean(status?.sms.configured),
      detail: status?.sms.configured ? `Sending from ${status.sms.from_number}` : "Add your SMS provider details to send texts",
    },
  ];

  return (
    <section className="surface-card flex flex-col gap-4 p-6">
      <h3 className="flex items-center gap-2.5 font-semibold">
        <span className="flex size-8 items-center justify-center rounded-lg bg-mint text-primary">
          <Plug className="size-4" />
        </span>
        Integrations
        {data?.demo_mode ? <Pill className="ml-2">Demo mode</Pill> : null}
      </h3>

      <div className="flex flex-col gap-3 rounded-xl border p-4" data-testid="google-calendar">
        <div className="flex flex-wrap items-center gap-3">
          <span className={cn("flex size-9 items-center justify-center rounded-lg", google?.mode !== "built_in" ? "bg-mint text-primary" : "bg-surface-container text-[#394761]")}>
            <CalendarCheck2 className="size-4" />
          </span>
          <div className="min-w-0">
            <p className="text-sm font-semibold">Google Calendar</p>
            <p className="truncate text-xs text-muted-foreground">{calendarDetail}</p>
          </div>
          {isAdmin && google?.available ? (
            <div className="ml-auto flex gap-2">
              {/* A real navigation (not fetch): Google's sign-in page needs the full browser window. */}
              <a href="/api/integrations/google/start" className="inline-flex h-9 items-center rounded-lg bg-primary px-3.5 text-sm font-semibold text-white hover:bg-primary/90" data-testid="connect-google">
                {google.connected ? "Reconnect" : "Connect Google Calendar"}
              </a>
              {google.connected ? (
                <Button variant="ghost" size="sm" onClick={() => void disconnect()}>
                  Disconnect
                </Button>
              ) : null}
            </div>
          ) : null}
        </div>
        {google?.connected && isAdmin ? (
          <div className="flex flex-col gap-1.5 sm:max-w-md">
            <Label className="text-xs">Calendar for bookings</Label>
            <CalendarPicker value={google.calendar_id} onChange={(id) => id && void pick(id)} emptyLabel="Choose a calendar…" />
            <p className="text-xs text-muted-foreground">
              New bookings appear here, and busy events here (or in a person&apos;s own calendar) block their time.
            </p>
          </div>
        ) : null}
        {google && !google.available ? (
          <p className="text-xs text-muted-foreground">
            The Connect button appears once Google sign-in is added to the server settings (see the README).
          </p>
        ) : null}
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        {items.map((i) => (
          <div key={i.key} className="flex items-center gap-3 rounded-xl border px-4 py-3">
            <span className={cn("flex size-9 items-center justify-center rounded-lg", i.ok ? "bg-mint text-primary" : "bg-surface-container text-[#394761]")}>
              {i.key === "sms" ? <MessageSquareText className="size-4" /> : <CalendarCog className="size-4" />}
            </span>
            <div className="min-w-0">
              <p className="text-sm font-semibold">{i.label}</p>
              <p className="truncate text-xs text-muted-foreground">{i.detail}</p>
            </div>
            <span className={cn("ml-auto rounded-full px-2 py-0.5 text-[11px] font-semibold", i.ok ? "bg-primary-fixed/70 text-[#00201b]" : "bg-[#fef3c7] text-[#92400e]")}>
              {i.ok ? "Connected" : "Setup"}
            </span>
          </div>
        ))}
      </div>
    </section>
  );
}
