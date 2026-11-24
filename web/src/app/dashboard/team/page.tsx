"use client";

import { CalendarOff, Clock3, Loader2, Plus, Save, Scissors, Trash2, UserRound } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";

import { CalendarPicker, selectClass } from "@/components/dashboard/calendar-picker";
import { useDashboard } from "@/components/dashboard/context";
import { toWeek, type Week, WeekEditor, weekError, weekRows } from "@/components/dashboard/week-editor";
import { Pill } from "@/components/outcome-badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { api, json } from "@/lib/api";
import { hhmm, initials, WEEKDAYS } from "@/lib/format";
import type { Hours, Service, Staff, TimeOff } from "@/lib/types";
import { useApi } from "@/lib/use-api";
import { cn } from "@/lib/utils";

const NEW: Staff = { id: -1, name: "", title: "", calendar_id: "", color: "#0f9d8a", active: true, shifts: [] };

export default function TeamPage() {
  const { me } = useDashboard();
  const isAdmin = me.role === "admin";
  const { data: staff, reload } = useApi<Staff[]>("/api/settings/staff");
  const [selected, setSelected] = useState<number | null>(null);
  const [adding, setAdding] = useState(false);

  const current = adding ? NEW : (staff?.find((s) => s.id === selected) ?? staff?.[0]);

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-5 pb-16">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-sm text-muted-foreground">
            Ava only offers a time when that person is working and free: their hours, time off and calendar all count.
          </p>
        </div>
        {isAdmin ? (
          <Button onClick={() => setAdding(true)} className="btn-gradient h-10 rounded-xl px-4 text-white" data-testid="add-member">
            <Plus /> Add team member
          </Button>
        ) : (
          <Pill>Read-only (staff)</Pill>
        )}
      </div>

      <div className="grid gap-5 lg:grid-cols-[280px_1fr]">
        <div className="surface-card flex flex-col gap-1 p-2" data-testid="team-list">
          {!staff ? <Skeleton className="h-40 rounded-xl" /> : null}
          {staff?.map((s) => {
            const active = !adding && current?.id === s.id;
            return (
              <button
                key={s.id}
                type="button"
                onClick={() => {
                  setAdding(false);
                  setSelected(s.id);
                }}
                className={cn(
                  "flex items-center gap-3 rounded-xl px-3 py-2.5 text-left transition-colors",
                  active ? "bg-mint" : "hover:bg-surface-low",
                  !s.active && "opacity-60",
                )}
              >
                <span className="flex size-9 shrink-0 items-center justify-center rounded-full text-xs font-bold text-white" style={{ background: s.color }}>
                  {initials(s.name)}
                </span>
                <span className="min-w-0">
                  <span className="block truncate text-sm font-semibold">{s.name}</span>
                  <span className="block truncate text-xs text-muted-foreground">
                    {s.title || "Team member"} · {s.shifts.length ? "Own hours" : "Salon hours"}
                  </span>
                </span>
                {!s.active ? <Pill className="ml-auto">Off</Pill> : null}
              </button>
            );
          })}
        </div>

        {current ? (
          <MemberDetail
            key={current.id}
            member={current}
            isAdmin={isAdmin}
            onSaved={(id) => {
              setAdding(false);
              setSelected(id);
              void reload();
            }}
          />
        ) : null}
      </div>
    </div>
  );
}

function Card({ icon, title, right, children }: { icon: React.ReactNode; title: string; right?: React.ReactNode; children: React.ReactNode }) {
  return (
    <section className="surface-card flex flex-col gap-4 p-5">
      <div className="flex items-center justify-between gap-3">
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

function MemberDetail({ member, isAdmin, onSaved }: { member: Staff; isAdmin: boolean; onSaved: (id: number) => void }) {
  const isNew = member.id === -1;
  const [form, setForm] = useState<Staff>(member);
  const [saving, setSaving] = useState(false);
  const upd = (patch: Partial<Staff>) => setForm((f) => ({ ...f, ...patch }));

  async function saveProfile() {
    setSaving(true);
    const body = { name: form.name.trim(), title: form.title, calendar_id: form.calendar_id, color: form.color, active: form.active };
    try {
      const saved = isNew
        ? await api<Staff>("/api/settings/staff", { method: "POST", ...json(body) })
        : await api<Staff>(`/api/settings/staff/${member.id}`, { method: "PUT", ...json(body) });
      toast.success(isNew ? `${saved.name} added. Set their hours next.` : `${saved.name} saved`);
      onSaved(saved.id);
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <fieldset disabled={!isAdmin} className="flex min-w-0 flex-col gap-5">
      <Card
        icon={<UserRound />}
        title={isNew ? "New team member" : "Profile"}
        right={
          <Button onClick={() => void saveProfile()} disabled={saving || !form.name.trim()} size="sm" data-testid="save-member">
            {saving ? <Loader2 className="animate-spin" /> : <Save />} {isNew ? "Add" : "Save"}
          </Button>
        }
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="m-name">Name</Label>
            <Input id="m-name" value={form.name} onChange={(e) => upd({ name: e.target.value })} className="h-10" />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="m-title">Title</Label>
            <Input id="m-title" value={form.title} placeholder="e.g. Senior Stylist" onChange={(e) => upd({ title: e.target.value })} className="h-10" />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label>Their calendar (optional)</Label>
            <CalendarPicker value={form.calendar_id} onChange={(v) => upd({ calendar_id: v })} isAdmin={isAdmin} />
            <p className="text-xs text-muted-foreground">Events in it (lunch, training, personal) block their time.</p>
          </div>
          <div className="flex items-end gap-5">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="m-color">Colour</Label>
              <input id="m-color" type="color" value={form.color} onChange={(e) => upd({ color: e.target.value })} className="h-10 w-14 rounded-md border" />
            </div>
            <label className="flex items-center gap-2 pb-2.5 text-sm font-medium">
              <Switch checked={form.active} onCheckedChange={(v) => upd({ active: v })} aria-label="Taking bookings" />
              Taking bookings
            </label>
          </div>
        </div>
      </Card>

      {isNew ? null : (
        <>
          <ScheduleCard member={member} isAdmin={isAdmin} onSaved={() => onSaved(member.id)} />
          <TimeOffCard member={member} isAdmin={isAdmin} />
          <ServicesCard member={member} />
        </>
      )}
    </fieldset>
  );
}

function ScheduleCard({ member, isAdmin, onSaved }: { member: Staff; isAdmin: boolean; onSaved: () => void }) {
  const { data: salon } = useApi<Hours[]>("/api/settings/hours");
  const [custom, setCustom] = useState(member.shifts.length > 0);
  const [week, setWeek] = useState<Week>(() => toWeek(member.shifts, (s) => s.start_time, (s) => s.end_time));
  const [saving, setSaving] = useState(false);

  async function save() {
    const err = custom ? weekError(week) : null;
    if (err) return void toast.error(err);
    setSaving(true);
    const body = custom ? weekRows(week).map((r) => ({ weekday: r.weekday, start_time: r.from, end_time: r.to })) : [];
    try {
      await api(`/api/settings/staff/${member.id}/shifts`, { method: "PUT", ...json(body) });
      toast.success(custom ? `${member.name}'s hours saved` : `${member.name} now works the salon's hours`);
      onSaved();
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card
      icon={<Clock3 />}
      title="Working hours"
      right={
        isAdmin ? (
          <Button variant="outline" size="sm" onClick={() => void save()} disabled={saving} data-testid="save-shifts">
            {saving ? <Loader2 className="animate-spin" /> : null} Save hours
          </Button>
        ) : null
      }
    >
      <div className="flex rounded-full bg-surface-container p-1 text-sm">
        {[
          { v: false, label: "Same as salon hours" },
          { v: true, label: "Their own hours" },
        ].map((o) => (
          <button
            key={o.label}
            type="button"
            onClick={() => {
              // Start their own hours from the salon's, so only the differences need changing.
              if (o.v && !custom && member.shifts.length === 0 && salon?.length) {
                setWeek(toWeek(salon, (h) => h.open_time, (h) => h.close_time));
              }
              setCustom(o.v);
            }}
            className={cn("flex-1 rounded-full px-4 py-1.5 font-medium", custom === o.v ? "bg-card shadow-sm" : "text-muted-foreground")}
          >
            {o.label}
          </button>
        ))}
      </div>
      {custom ? (
        <>
          <WeekEditor week={week} onChange={setWeek} offLabel="Day off" disabled={!isAdmin} testId="shift-editor" />
          <p className="text-xs text-muted-foreground">
            Hours outside the salon&apos;s opening hours are never offered. For a lunch break, add a weekly break under Time off.
          </p>
        </>
      ) : (
        <p className="rounded-xl bg-surface-low px-4 py-3 text-sm text-muted-foreground">
          {salon && salon.length
            ? `Works whenever the salon is open: ${summariseHours(salon)}.`
            : "Works whenever the salon is open (set opening hours in Settings)."}
        </p>
      )}
    </Card>
  );
}

function summariseHours(rows: Hours[]) {
  return rows.map((h) => `${WEEKDAYS[h.weekday].slice(0, 3)} ${hhmm(h.open_time)}–${hhmm(h.close_time)}`).join(", ");
}

function addDay(isoDate: string) {
  const d = new Date(`${isoDate}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + 1);
  return d.toISOString().slice(0, 10);
}

function TimeOffCard({ member, isAdmin }: { member: Staff; isAdmin: boolean }) {
  const { tz } = useDashboard();
  const { data, reload } = useApi<TimeOff[]>(`/api/settings/time-off?staff_id=${member.id}`);
  const [today] = useState(() => new Date().toLocaleDateString("en-CA")); // local YYYY-MM-DD
  const [kind, setKind] = useState<"once" | "weekly">("once");
  const [from, setFrom] = useState(today);
  const [to, setTo] = useState(today);
  const [allDay, setAllDay] = useState(true);
  const [startT, setStartT] = useState("13:00");
  const [endT, setEndT] = useState("14:00");
  const [weekday, setWeekday] = useState(0);
  const [label, setLabel] = useState("");
  const [busy, setBusy] = useState(false);

  async function add() {
    const body =
      kind === "weekly"
        ? { staff_id: member.id, kind, weekday, start_time: startT, end_time: endT, label }
        : allDay
          ? { staff_id: member.id, kind, start_local: `${from}T00:00`, end_local: `${addDay(to < from ? from : to)}T00:00`, label }
          : { staff_id: member.id, kind, start_local: `${from}T${startT}`, end_local: `${to < from ? from : to}T${endT}`, label };
    setBusy(true);
    try {
      await api("/api/settings/time-off", { method: "POST", ...json(body) });
      toast.success("Time off added. Ava won't offer those times.");
      setLabel("");
      void reload();
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function remove(t: TimeOff) {
    try {
      await api(`/api/settings/time-off/${t.id}`, { method: "DELETE" });
      void reload();
    } catch (e) {
      toast.error((e as Error).message);
    }
  }

  const fmt = (iso: string, opts: Intl.DateTimeFormatOptions) =>
    new Intl.DateTimeFormat("en-GB", { timeZone: tz, ...opts }).format(new Date(iso));
  const describe = (t: TimeOff) => {
    if (t.kind === "weekly") return `Every ${WEEKDAYS[t.weekday ?? 0]}, ${hhmm(t.start_time)}–${hhmm(t.end_time)}`;
    const s = new Date(t.start_utc ?? "");
    const e = new Date(t.end_utc ?? "");
    const wholeDays = fmt(s.toISOString(), { hour: "2-digit", minute: "2-digit", hour12: false }) === "00:00" &&
      fmt(e.toISOString(), { hour: "2-digit", minute: "2-digit", hour12: false }) === "00:00";
    if (wholeDays) {
      const last = new Date(e.getTime() - 1).toISOString();
      const a = fmt(s.toISOString(), { weekday: "short", day: "numeric", month: "short" });
      const b = fmt(last, { weekday: "short", day: "numeric", month: "short" });
      return a === b ? `${a}, all day` : `${a} – ${b}`;
    }
    return `${fmt(s.toISOString(), { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })} – ${fmt(e.toISOString(), { hour: "2-digit", minute: "2-digit" })}`;
  };

  return (
    <Card icon={<CalendarOff />} title="Time off & breaks">
      <div className="flex flex-col gap-2" data-testid="time-off-list">
        {data?.length === 0 ? <p className="text-sm text-muted-foreground">No time off planned.</p> : null}
        {data?.map((t) => (
          <div key={t.id} className="flex items-center gap-3 rounded-xl border px-4 py-2.5 text-sm">
            <Pill className={t.kind === "weekly" ? "bg-secondary text-[#394761]" : "bg-[#fef3c7] text-[#92400e]"}>
              {t.kind === "weekly" ? "Weekly" : "Off"}
            </Pill>
            <span className="font-medium">{describe(t)}</span>
            {t.label ? <span className="truncate text-muted-foreground">· {t.label}</span> : null}
            {isAdmin ? (
              <button type="button" onClick={() => void remove(t)} className="ml-auto text-muted-foreground hover:text-destructive" aria-label="Remove time off">
                <Trash2 className="size-4" />
              </button>
            ) : null}
          </div>
        ))}
      </div>

      {isAdmin ? (
        <div className="flex flex-col gap-3 rounded-xl bg-surface-low p-4">
          <div className="flex flex-wrap gap-3">
            <div className="flex min-w-40 flex-col gap-1">
              <Label className="text-xs">Type</Label>
              <select className={selectClass} value={kind} onChange={(e) => setKind(e.target.value as "once" | "weekly")} aria-label="Time off type">
                <option value="once">Day(s) off / appointment</option>
                <option value="weekly">Weekly break (e.g. lunch)</option>
              </select>
            </div>
            {kind === "once" ? (
              <>
                <div className="flex flex-col gap-1">
                  <Label className="text-xs">From</Label>
                  <Input type="date" value={from} onChange={(e) => setFrom(e.target.value)} className="h-9" aria-label="From date" />
                </div>
                <div className="flex flex-col gap-1">
                  <Label className="text-xs">To</Label>
                  <Input type="date" value={to} min={from} onChange={(e) => setTo(e.target.value)} className="h-9" aria-label="To date" />
                </div>
                <label className="flex items-center gap-2 self-end pb-2 text-sm">
                  <Switch checked={allDay} onCheckedChange={setAllDay} aria-label="All day" /> All day
                </label>
              </>
            ) : (
              <div className="flex flex-col gap-1">
                <Label className="text-xs">Day</Label>
                <select className={selectClass} value={weekday} onChange={(e) => setWeekday(Number(e.target.value))} aria-label="Weekday">
                  {WEEKDAYS.map((d, i) => (
                    <option key={d} value={i}>
                      {d}
                    </option>
                  ))}
                </select>
              </div>
            )}
            {kind === "weekly" || !allDay ? (
              <div className="flex items-end gap-2">
                <div className="flex flex-col gap-1">
                  <Label className="text-xs">Start</Label>
                  <Input type="time" value={startT} onChange={(e) => setStartT(e.target.value)} className="h-9 w-28" aria-label="Start time" />
                </div>
                <div className="flex flex-col gap-1">
                  <Label className="text-xs">End</Label>
                  <Input type="time" value={endT} onChange={(e) => setEndT(e.target.value)} className="h-9 w-28" aria-label="End time" />
                </div>
              </div>
            ) : null}
            <div className="flex min-w-40 flex-1 flex-col gap-1">
              <Label className="text-xs">Note (optional)</Label>
              <Input value={label} placeholder="Holiday, training, lunch…" onChange={(e) => setLabel(e.target.value)} className="h-9" />
            </div>
          </div>
          <Button onClick={() => void add()} disabled={busy} size="sm" className="self-start" data-testid="add-time-off">
            {busy ? <Loader2 className="animate-spin" /> : <Plus />} Add time off
          </Button>
        </div>
      ) : null}
    </Card>
  );
}

function ServicesCard({ member }: { member: Staff }) {
  const { data: services } = useApi<Service[]>("/api/settings/services");
  const theirs = services?.filter((s) => s.active && s.staff_ids.includes(member.id)) ?? [];
  return (
    <Card icon={<Scissors />} title="Services" right={<Link href="/dashboard/settings#services" className="text-sm font-medium text-primary">Edit in Settings</Link>}>
      {services && theirs.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          {member.name} isn&apos;t assigned to any service yet, so Ava won&apos;t book them. Tick their name on a service in Settings.
        </p>
      ) : (
        <div className="flex flex-wrap gap-2">
          {theirs.map((s) => (
            <span key={s.id} className="rounded-full bg-mint px-3 py-1 text-sm font-medium text-primary">
              {s.name} · {s.duration_min} min
            </span>
          ))}
        </div>
      )}
    </Card>
  );
}
