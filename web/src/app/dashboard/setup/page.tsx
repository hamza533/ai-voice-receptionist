"use client";

import {
  ArrowLeft,
  ArrowRight,
  Building2,
  CalendarCheck2,
  Check,
  Clock3,
  Loader2,
  Mic,
  Plus,
  Scissors,
  Users,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { useDashboard } from "@/components/dashboard/context";
import { OptionSelect } from "@/components/dashboard/option-select";
import { toWeek, type Week, WeekEditor, weekError, weekRows } from "@/components/dashboard/week-editor";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api, json } from "@/lib/api";
import type { Business, Hours, Integrations, Service, Staff } from "@/lib/types";
import { useApi } from "@/lib/use-api";
import { cn } from "@/lib/utils";

const STEPS = [
  { key: "business", label: "Business", icon: Building2 },
  { key: "hours", label: "Opening hours", icon: Clock3 },
  { key: "team", label: "Team", icon: Users },
  { key: "services", label: "Services", icon: Scissors },
  { key: "connect", label: "Calendar & texts", icon: CalendarCheck2 },
  { key: "test", label: "Test call", icon: Mic },
] as const;

const DEFAULT_WEEK: Week = toWeek(
  [0, 1, 2, 3, 4, 5].map((d) => ({ weekday: d })),
  () => "10:00",
  () => "18:00",
);

function timeZones(): string[] {
  try {
    return (Intl as unknown as { supportedValuesOf(k: string): string[] }).supportedValuesOf("timeZone");
  } catch {
    return ["UTC", "Asia/Karachi", "Europe/London", "America/New_York"];
  }
}

export default function SetupPage() {
  const [step, setStep] = useState(0);
  const next = () => setStep((s) => Math.min(s + 1, STEPS.length - 1));
  const back = () => setStep((s) => Math.max(s - 1, 0));

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6 pb-16">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">Set up your receptionist</h2>
        <p className="text-sm text-muted-foreground">Six short steps. You can change everything later in Settings and Team.</p>
      </div>

      <ol className="grid grid-cols-3 gap-2 sm:grid-cols-6" data-testid="setup-steps">
        {STEPS.map((s, i) => (
          <li key={s.key}>
            <button
              type="button"
              onClick={() => setStep(i)}
              className={cn(
                "flex w-full flex-col items-center gap-1.5 rounded-xl px-2 py-2.5 text-xs font-medium transition-colors",
                i === step ? "bg-mint text-primary" : i < step ? "text-primary" : "text-muted-foreground hover:bg-surface-low",
              )}
            >
              <span
                className={cn(
                  "flex size-8 items-center justify-center rounded-full",
                  i < step ? "bg-primary text-white" : i === step ? "bg-primary/15" : "bg-surface-container",
                )}
              >
                {i < step ? <Check className="size-4" /> : <s.icon className="size-4" />}
              </span>
              {s.label}
            </button>
          </li>
        ))}
      </ol>

      <section className="surface-card flex flex-col gap-5 p-6">
        {step === 0 ? <BusinessStep onDone={next} /> : null}
        {step === 1 ? <HoursStep onDone={next} /> : null}
        {step === 2 ? <TeamStep /> : null}
        {step === 3 ? <ServicesStep /> : null}
        {step === 4 ? <ConnectStep /> : null}
        {step === 5 ? <TestStep /> : null}
      </section>

      <div className="flex justify-between">
        <Button variant="ghost" onClick={back} disabled={step === 0}>
          <ArrowLeft /> Back
        </Button>
        {step >= 2 && step < STEPS.length - 1 ? (
          <Button onClick={next} data-testid="setup-next">
            Next <ArrowRight />
          </Button>
        ) : null}
      </div>
    </div>
  );
}

function StepTitle({ title, hint }: { title: string; hint: string }) {
  return (
    <div>
      <h3 className="text-lg font-semibold">{title}</h3>
      <p className="text-sm text-muted-foreground">{hint}</p>
    </div>
  );
}

function BusinessStep({ onDone }: { onDone: () => void }) {
  const { business, reloadBusiness } = useDashboard();
  const [form, setForm] = useState<Business>(business);
  const [zones] = useState(timeZones);
  const [busy, setBusy] = useState(false);
  const set = <K extends keyof Business>(k: K, v: Business[K]) => setForm((f) => ({ ...f, [k]: v }));

  async function save() {
    setBusy(true);
    try {
      const greeting = form.greeting || `Thank you for calling ${form.name}, this is Ava. How can I help you today?`;
      await api("/api/settings/business", { method: "PUT", ...json({ ...form, greeting }) });
      await reloadBusiness();
      onDone();
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <StepTitle title="Your business" hint="Ava uses these to greet callers and answer questions." />
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="s-name">Business name</Label>
          <Input id="s-name" value={form.name} onChange={(e) => set("name", e.target.value)} className="h-10" />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="s-phone">Phone</Label>
          <Input id="s-phone" value={form.phone} onChange={(e) => set("phone", e.target.value)} className="h-10" />
        </div>
        <div className="flex flex-col gap-1.5 sm:col-span-2">
          <Label htmlFor="s-address">Address</Label>
          <Input id="s-address" value={form.address} onChange={(e) => set("address", e.target.value)} className="h-10" />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="s-tz">Time zone</Label>
          <OptionSelect
            id="s-tz"
            value={form.timezone}
            onChange={(v) => set("timezone", v)}
            className="h-10"
            options={zones.map((z) => ({ value: z, label: z.replace(/_/g, " ") }))}
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="s-cur">Currency</Label>
          <Input id="s-cur" value={form.currency} maxLength={8} onChange={(e) => set("currency", e.target.value.toUpperCase())} className="h-10" />
        </div>
      </div>
      <Button onClick={() => void save()} disabled={busy || form.name.trim().length < 2} className="self-end" data-testid="setup-save-business">
        {busy ? <Loader2 className="animate-spin" /> : null} Save and continue <ArrowRight />
      </Button>
    </>
  );
}

function HoursStep({ onDone }: { onDone: () => void }) {
  const { data } = useApi<Hours[]>("/api/settings/hours");
  const [week, setWeek] = useState<Week | null>(null);
  const [busy, setBusy] = useState(false);
  const shown = week ?? (data && data.length ? toWeek(data, (h) => h.open_time, (h) => h.close_time) : DEFAULT_WEEK);

  async function save() {
    const err = weekError(shown);
    if (err) return void toast.error(err);
    setBusy(true);
    try {
      const body = weekRows(shown).map((r) => ({ weekday: r.weekday, open_time: r.from, close_time: r.to }));
      await api("/api/settings/hours", { method: "PUT", ...json(body) });
      onDone();
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <StepTitle title="Opening hours" hint="Ava answers 24/7, but only books inside these hours." />
      <WeekEditor week={shown} onChange={setWeek} />
      <Button onClick={() => void save()} disabled={busy} className="self-end" data-testid="setup-save-hours">
        {busy ? <Loader2 className="animate-spin" /> : null} Save and continue <ArrowRight />
      </Button>
    </>
  );
}

function TeamStep() {
  const { data: staff, reload } = useApi<Staff[]>("/api/settings/staff");
  const [name, setName] = useState("");
  const [title, setTitle] = useState("");

  async function add() {
    try {
      await api("/api/settings/staff", { method: "POST", ...json({ name: name.trim(), title, color: "#0f9d8a", active: true }) });
      setName("");
      setTitle("");
      void reload();
    } catch (e) {
      toast.error((e as Error).message);
    }
  }

  return (
    <>
      <StepTitle title="Who takes bookings?" hint="Add everyone Ava can book. Personal hours and time off can be set on the Team page." />
      <div className="flex flex-wrap gap-2">
        {staff?.map((m) => (
          <span key={m.id} className="rounded-full bg-mint px-3 py-1 text-sm font-medium text-primary">
            {m.name}
            {m.title ? ` · ${m.title}` : ""}
          </span>
        ))}
        {staff?.length === 0 ? <span className="text-sm text-muted-foreground">Nobody yet.</span> : null}
      </div>
      <div className="flex flex-wrap items-end gap-3">
        <div className="flex flex-col gap-1">
          <Label className="text-xs">Name</Label>
          <Input value={name} onChange={(e) => setName(e.target.value)} className="h-9" />
        </div>
        <div className="flex flex-col gap-1">
          <Label className="text-xs">Title (optional)</Label>
          <Input value={title} placeholder="Stylist" onChange={(e) => setTitle(e.target.value)} className="h-9" />
        </div>
        <Button variant="outline" onClick={() => void add()} disabled={!name.trim()} data-testid="setup-add-staff">
          <Plus /> Add
        </Button>
      </div>
      <Link href="/dashboard/team" className="text-sm font-medium text-primary">
        Set working hours and time off on the Team page →
      </Link>
    </>
  );
}

function ServicesStep() {
  const { business } = useDashboard();
  const { data: services, reload } = useApi<Service[]>("/api/settings/services");
  const { data: staff } = useApi<Staff[]>("/api/settings/staff");
  const [form, setForm] = useState({ name: "", duration_min: 30, price: 0, staff_ids: [] as number[] });

  async function add() {
    try {
      await api("/api/settings/services", {
        method: "POST",
        ...json({ ...form, name: form.name.trim(), buffer_min: 5, active: true, description: "" }),
      });
      setForm({ name: "", duration_min: 30, price: 0, staff_ids: [] });
      void reload();
    } catch (e) {
      toast.error((e as Error).message);
    }
  }

  return (
    <>
      <StepTitle title="What can callers book?" hint="Each service has a length, a price and the people who do it." />
      <div className="flex flex-col gap-2">
        {services?.map((s) => (
          <div key={s.id} className="flex items-center justify-between rounded-xl border px-4 py-2.5 text-sm">
            <span className="font-medium">{s.name}</span>
            <span className="text-muted-foreground">
              {s.duration_min} min · {business.currency} {Number(s.price).toLocaleString()} ·{" "}
              {staff?.filter((m) => s.staff_ids.includes(m.id)).map((m) => m.name).join(", ") || "nobody assigned"}
            </span>
          </div>
        ))}
      </div>
      <div className="flex flex-col gap-3 rounded-xl bg-surface-low p-4">
        <div className="grid gap-3 sm:grid-cols-[1.5fr_0.6fr_0.8fr]">
          <div className="flex flex-col gap-1">
            <Label className="text-xs">Service</Label>
            <Input value={form.name} placeholder="Haircut" onChange={(e) => setForm({ ...form, name: e.target.value })} className="h-9" />
          </div>
          <div className="flex flex-col gap-1">
            <Label className="text-xs">Minutes</Label>
            <Input type="number" min={5} value={form.duration_min} onChange={(e) => setForm({ ...form, duration_min: Number(e.target.value) })} className="h-9" />
          </div>
          <div className="flex flex-col gap-1">
            <Label className="text-xs">Price ({business.currency})</Label>
            <Input type="number" min={0} value={form.price} onChange={(e) => setForm({ ...form, price: Number(e.target.value) })} className="h-9" />
          </div>
        </div>
        <div className="flex flex-wrap gap-1.5">
          {staff?.map((m) => {
            const on = form.staff_ids.includes(m.id);
            return (
              <button
                type="button"
                key={m.id}
                onClick={() => setForm({ ...form, staff_ids: on ? form.staff_ids.filter((x) => x !== m.id) : [...form.staff_ids, m.id] })}
                className={cn("rounded-full px-2.5 py-0.5 text-xs font-medium", on ? "bg-primary text-white" : "bg-surface-container text-[#394761]")}
              >
                {m.name}
              </button>
            );
          })}
        </div>
        <Button variant="outline" onClick={() => void add()} disabled={form.name.trim().length < 2 || !form.staff_ids.length} className="self-start" data-testid="setup-add-service">
          <Plus /> Add service
        </Button>
      </div>
    </>
  );
}

function ConnectStep() {
  const { data: status } = useApi<Integrations>("/api/integrations");
  return (
    <>
      <StepTitle title="Calendar & texts" hint="Optional, and you can do it any time in Settings → Integrations." />
      <div className="flex flex-col gap-3">
        <div className="flex flex-wrap items-center gap-3 rounded-xl border p-4">
          <CalendarCheck2 className="size-5 text-primary" />
          <div className="min-w-0">
            <p className="text-sm font-semibold">Google Calendar</p>
            <p className="text-xs text-muted-foreground">
              {status?.google.mode === "connected"
                ? `Connected as ${status.google.account_email}`
                : "Bookings go straight into your calendar, and your events block busy times."}
            </p>
          </div>
          {status?.google.available ? (
            <a href="/api/integrations/google/start" className="ml-auto inline-flex h-9 items-center rounded-lg bg-primary px-3.5 text-sm font-semibold text-white">
              {status.google.connected ? "Reconnect" : "Connect"}
            </a>
          ) : (
            <span className="ml-auto text-xs text-muted-foreground">Built-in calendar in use</span>
          )}
        </div>
        <div className="flex items-center gap-3 rounded-xl border p-4">
          <Mic className="size-5 text-primary" />
          <div>
            <p className="text-sm font-semibold">Text confirmations & reminders</p>
            <p className="text-xs text-muted-foreground">
              {status?.sms.configured
                ? `On. Texts come from ${status.sms.from_number}.`
                : "Texts will be sent once your SMS provider is added. Until then they're listed but not sent."}
            </p>
          </div>
        </div>
      </div>
    </>
  );
}

function TestStep() {
  const { openCall, reloadBusiness } = useDashboard();
  const router = useRouter();
  const [busy, setBusy] = useState(false);

  async function finish() {
    setBusy(true);
    try {
      await api("/api/settings/setup/complete", { method: "POST" });
      await reloadBusiness();
      toast.success("All set. Ava is ready to answer your calls.");
      router.push("/dashboard");
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <StepTitle title="Try it" hint="Call Ava from your browser: ask about prices, then book something." />
      <div className="flex flex-wrap gap-3">
        <Button onClick={openCall} variant="outline" className="h-11 rounded-xl">
          <Mic /> Talk to Ava
        </Button>
        <Button onClick={() => void finish()} disabled={busy} className="btn-gradient h-11 rounded-xl px-5 text-white" data-testid="setup-finish">
          {busy ? <Loader2 className="animate-spin" /> : <Check />} Finish setup
        </Button>
      </div>
    </>
  );
}
